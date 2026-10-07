from __future__ import absolute_import, print_function, unicode_literals

import Live

from _Framework.ButtonElement import ButtonElement
from _Framework.ControlSurface import ControlSurface
from _Framework.EncoderElement import EncoderElement
from _Framework.InputControlElement import MIDI_CC_TYPE, MIDI_NOTE_TYPE
from _Framework.MixerComponent import MixerComponent
from _Framework.SessionComponent import SessionComponent
from _Framework.SliderElement import SliderElement
from _Framework.TransportComponent import TransportComponent

from .config import (
    LINKED_K2_MIDI_CHANNELS,
    LINK_INSTANCES_IN_SESSION,
    SCENES,
    TEMPO_ENCODER_BPM_STEP,
    TOP_ENCODER_SEND_SENSITIVITY,
    TRACKS_PER_K2,
    VOLUME_MAX_MIDI_VALUE,
)
from .linking import (
    capped_midi_fraction,
    clamp_scene_offset,
    clamp_tempo,
    clamp_track_offset,
    hardware_to_script_midi_channels,
    linked_session_offset,
    relative_two_complement_delta,
    track_width_for_channels,
)
from .clip_feedback import (
    K2_LED_OFF,
    K2_LED_RED,
    MIDI_MAX_VALUE,
    k2_led_messages,
    nearest_k2_led_color,
)
from .midi_map import FACTORY_MAP


class K2ClipButtonElement(ButtonElement):
    """Button element that translates framework feedback to K2 LED colors."""

    def __init__(self, is_momentary, msg_type, channel, identifier):
        ButtonElement.__init__(self, is_momentary, msg_type, channel, identifier)
        self._led_color = K2_LED_RED
        self._last_led_value = 0
        self._blink_override = False
        self._blink_on = True

    def set_led_color(self, led_color):
        if self._led_color == led_color:
            return
        self._led_color = led_color
        if self._blink_override:
            self._send_k2_led_value(MIDI_MAX_VALUE if self._blink_on else 0)
        elif self._last_led_value > 0:
            self._send_k2_led_value(self._last_led_value)

    def set_blink_override(self, enabled, led_on=True):
        if self._blink_override == enabled and self._blink_on == led_on:
            return
        self._blink_override = enabled
        self._blink_on = led_on
        if enabled:
            self._send_k2_led_value(MIDI_MAX_VALUE if led_on else 0)
        else:
            self._send_k2_led_value(self._last_led_value)

    def turn_off(self):
        self.send_value(0, force=True)

    def _do_send_value(self, value, channel=None):
        self._last_led_value = value
        if not self._blink_override:
            self._send_k2_led_value(value, channel=channel)

    def _send_k2_led_value(self, value, channel=None):
        led_color = self._led_color if value > 0 else K2_LED_OFF
        for message in k2_led_messages(
            self._target_channel(channel), self._target_identifier(), led_color
        ):
            self.send_midi(message)

    def _target_channel(self, channel=None):
        if channel is not None:
            return channel
        if hasattr(self, "message_channel"):
            message_channel = self.message_channel()
            if message_channel is not None:
                return message_channel
        return self._original_channel

    def _target_identifier(self):
        if hasattr(self, "message_identifier"):
            message_identifier = self.message_identifier()
            if message_identifier is not None:
                return message_identifier
        return self._original_identifier


class XoneK2(ControlSurface):
    """Ableton Live Remote Script for the Allen & Heath Xone:K2."""

    _CLIP_LED_BLINK_DELAY = 4

    def __init__(self, c_instance):
        super(XoneK2, self).__init__(c_instance)
        self._channels = hardware_to_script_midi_channels(LINKED_K2_MIDI_CHANNELS)
        self.set_feedback_channels(list(self._channels))
        self._width = track_width_for_channels(self._channels, TRACKS_PER_K2)
        self._current_track_offset = 0
        self._current_scene_offset = 0
        self._track_nav_encoder = None
        self._scene_nav_encoder = None
        self._tempo_encoder = None
        self._play_button = None
        self._horizontal_lock_button = None
        self._horizontal_scroll_locked = False
        self._linked_in_live = False
        self._value_listeners = []
        self._clip_launch_buttons = {}
        self._clip_slot_listeners = []
        self._clip_color_listeners = []
        self._clip_feedback_refresh_scheduled = False
        self._clip_led_blink_on = True
        self._clip_led_blink_timer_running = False
        self._song_is_playing_listener = None

        with self.component_guard():
            self._create_components()
            self._start_clip_led_blink_timer()

    def disconnect(self):
        self._clip_led_blink_timer_running = False
        for control, callback in self._value_listeners:
            if control.value_has_listener(callback):
                control.remove_value_listener(callback)
        self._clear_clip_feedback_listeners()
        self._clear_all_clip_leds()
        if self._song_is_playing_listener is not None:
            song = self.song()
            if song.is_playing_has_listener(self._song_is_playing_listener):
                song.remove_is_playing_listener(self._song_is_playing_listener)
            self._song_is_playing_listener = None
        if self._linked_in_live and hasattr(self._session, "_unlink"):
            self._session._unlink()
            self._linked_in_live = False
        super(XoneK2, self).disconnect()

    def connect_script_instances(self, instanciated_scripts):
        if not LINK_INSTANCES_IN_SESSION:
            return

        sibling_scripts = [
            script for script in instanciated_scripts if isinstance(script, XoneK2)
        ]
        widths = [script._width for script in sibling_scripts]
        instance_index = sibling_scripts.index(self)
        self._current_track_offset = linked_session_offset(widths, instance_index)
        self._current_scene_offset = 0
        self._apply_session_offsets()

        if hasattr(self._session, "_unlink") and self._linked_in_live:
            self._session._unlink()
            self._linked_in_live = False
        if hasattr(self._session, "_link"):
            self._session._link()
            self._linked_in_live = True

    def _create_components(self):
        self._session = SessionComponent(self._width, SCENES)
        self._session.name = "Session"
        self.set_highlighting_session_component(self._session)

        self._mixer = MixerComponent(self._width, 0, False, False)
        self._mixer.name = "Mixer"
        self._session.set_mixer(self._mixer)

        self._transport = TransportComponent()
        self._transport.name = "Transport"

        self._wire_units()
        self._apply_session_offsets()

    def _wire_units(self):
        for unit_index, channel in enumerate(self._channels):
            track_offset = unit_index * TRACKS_PER_K2
            self._wire_unit(
                channel,
                track_offset,
                is_primary=(unit_index == 0),
                is_last=(unit_index == len(self._channels) - 1),
            )

    def _wire_unit(self, channel, track_offset, is_primary, is_last):
        for column in range(TRACKS_PER_K2):
            absolute_track = track_offset + column
            strip = self._mixer.channel_strip(absolute_track)
            strip.name = "Channel_Strip_%d" % absolute_track

            select_button = self._create_button(
                channel,
                FACTORY_MAP.top_encoder_switches[column],
                "Track_Select_%d" % absolute_track,
            )
            strip.set_select_button(select_button)

            send_4_nudge = self._create_relative_encoder(
                channel,
                FACTORY_MAP.top_encoders[column],
                "Send_4_Nudge_%d" % absolute_track,
            )
            send_c = self._create_absolute_encoder(
                channel,
                FACTORY_MAP.send_a_pots[column],
                "Send_C_%d" % absolute_track,
            )
            send_b = self._create_absolute_encoder(
                channel,
                FACTORY_MAP.send_b_pots[column],
                "Send_B_%d" % absolute_track,
            )
            send_a = self._create_absolute_encoder(
                channel,
                FACTORY_MAP.pan_pots[column],
                "Send_A_%d" % absolute_track,
            )
            volume = self._create_slider(
                channel,
                FACTORY_MAP.faders[column],
                "Volume_%d" % absolute_track,
            )

            arm_button = self._create_button(
                channel,
                FACTORY_MAP.mute_switches[column],
                "Arm_%d" % absolute_track,
            )
            solo_button = self._create_button(
                channel,
                FACTORY_MAP.solo_switches[column],
                "Solo_%d" % absolute_track,
            )
            mute_button = self._create_button(
                channel,
                FACTORY_MAP.arm_switches[column],
                "Mute_%d" % absolute_track,
            )

            strip.set_mute_button(mute_button)
            strip.set_solo_button(solo_button)
            strip.set_arm_button(arm_button)
            if hasattr(strip, "set_invert_mute_feedback"):
                strip.set_invert_mute_feedback(True)
            self._bind_volume_control(volume, strip)
            self._bind_send_control(send_a, strip, 0)
            self._bind_send_control(send_b, strip, 1)
            self._bind_send_control(send_c, strip, 2)
            self._bind_send_4_nudge(send_4_nudge, strip)

            for scene_index in range(SCENES):
                launch_button = self._create_clip_button(
                    channel,
                    FACTORY_MAP.clip_rows[scene_index][column],
                    "Clip_%d_%d" % (absolute_track, scene_index),
                )
                self._bind_clip_launch_button(
                    launch_button,
                    absolute_track,
                    scene_index,
                )

        if is_primary:
            self._wire_primary_controls(channel)
        if is_last and not is_primary:
            self._wire_last_unit_controls(channel)

    def _wire_primary_controls(self, channel):
        self._play_button = self._create_button(
            channel, FACTORY_MAP.play_button, "Transport_Play"
        )
        self._add_value_listener(self._play_button, self._on_play_button)
        self._song_is_playing_listener = self._on_is_playing_changed
        self.song().add_is_playing_listener(self._song_is_playing_listener)
        self._on_is_playing_changed()

        self._horizontal_lock_button = self._create_button(
            channel, FACTORY_MAP.overdub_button, "Horizontal_Scroll_Lock"
        )
        self._add_value_listener(
            self._horizontal_lock_button, self._on_horizontal_lock_button
        )
        self._refresh_horizontal_lock_button()

        self._track_nav_encoder = self._create_relative_encoder(
            channel,
            FACTORY_MAP.navigation_encoders[0],
            "Track_Navigation",
        )
        self._scene_nav_encoder = self._create_relative_encoder(
            channel,
            FACTORY_MAP.navigation_encoders[1],
            "Scene_Navigation",
        )

        self._add_value_listener(self._track_nav_encoder, self._on_track_nav)
        self._add_value_listener(self._scene_nav_encoder, self._on_scene_nav)

    def _wire_last_unit_controls(self, channel):
        self._tempo_encoder = self._create_relative_encoder(
            channel,
            FACTORY_MAP.navigation_encoders[1],
            "Tempo_Nudge",
        )
        self._add_value_listener(self._tempo_encoder, self._on_tempo_nudge)

    def _bind_volume_control(self, slider, strip):
        def callback(value, bound_strip=strip):
            self._set_strip_volume_from_midi(bound_strip, value)

        self._add_value_listener(slider, callback)

    def _bind_send_control(self, encoder, strip, send_index):
        def callback(value, bound_strip=strip, bound_send_index=send_index):
            self._set_strip_send_from_midi(bound_strip, bound_send_index, value)

        self._add_value_listener(encoder, callback)

    def _bind_send_4_nudge(self, encoder, strip):
        def callback(value, bound_strip=strip):
            self._nudge_strip_send(bound_strip, value, 3)

        self._add_value_listener(encoder, callback)

    def _bind_clip_launch_button(self, button, local_track_index, scene_index):
        self._clip_launch_buttons[(local_track_index, scene_index)] = button
        self._session.scene(scene_index).clip_slot(local_track_index).set_launch_button(
            button
        )

    def _add_value_listener(self, control, callback):
        control.add_value_listener(callback)
        self._value_listeners.append((control, callback))

    def _on_play_button(self, value):
        if value == 0:
            return
        song = self.song()
        if song.is_playing:
            song.stop_playing()
        else:
            song.start_playing()

    def _on_is_playing_changed(self):
        if self._play_button is None:
            return
        if self.song().is_playing:
            self._play_button.turn_on()
        else:
            self._play_button.turn_off()

    def _on_horizontal_lock_button(self, value):
        if value == 0:
            return
        self._horizontal_scroll_locked = not self._horizontal_scroll_locked
        self._refresh_horizontal_lock_button()

    def _refresh_horizontal_lock_button(self):
        if self._horizontal_lock_button is None:
            return
        if self._horizontal_scroll_locked:
            self._horizontal_lock_button.turn_on()
        else:
            self._horizontal_lock_button.turn_off()

    def _on_track_nav(self, value):
        if self._horizontal_scroll_locked:
            return
        delta = relative_two_complement_delta(value)
        if delta == 0:
            return
        step = 1 if delta > 0 else -1
        track_count = len(self.song().visible_tracks)
        self._current_track_offset = clamp_track_offset(
            self._current_track_offset + step, track_count, self._width
        )
        self._apply_session_offsets()

    def _on_scene_nav(self, value):
        delta = relative_two_complement_delta(value)
        if delta == 0:
            return
        step = 1 if delta > 0 else -1
        scene_count = len(self.song().scenes)
        self._current_scene_offset = clamp_scene_offset(
            self._current_scene_offset + step, scene_count, SCENES
        )
        self._apply_session_offsets()

    def _on_tempo_nudge(self, value):
        delta = relative_two_complement_delta(value)
        if delta == 0:
            return
        song = self.song()
        song.tempo = clamp_tempo(song.tempo + (delta * TEMPO_ENCODER_BPM_STEP))

    def _apply_session_offsets(self):
        self._session.set_offsets(
            self._current_track_offset,
            self._current_scene_offset,
        )
        self._refresh_clip_feedback_bindings()

    def _visible_clip_slot(self, local_track_index, scene_index, visible_tracks=None):
        track = self._visible_track(local_track_index, visible_tracks)
        if track is None:
            return None
        absolute_scene_index = self._current_scene_offset + scene_index
        clip_slots = track.clip_slots
        if absolute_scene_index < 0 or absolute_scene_index >= len(clip_slots):
            return None
        return clip_slots[absolute_scene_index]

    def _refresh_clip_feedback_bindings(self):
        self._clip_feedback_refresh_scheduled = False
        self._clear_clip_feedback_listeners()

        visible_tracks = self.song().visible_tracks
        for local_track_index, scene_index in self._clip_launch_buttons:
            clip_slot = self._visible_clip_slot(
                local_track_index, scene_index, visible_tracks
            )
            self._set_clip_button_color(local_track_index, scene_index, clip_slot)
            if clip_slot is not None:
                self._listen_to_clip_slot(clip_slot, local_track_index, scene_index)
        self._apply_clip_led_blink_overrides(visible_tracks)

    def _request_clip_feedback_refresh(self):
        if self._clip_feedback_refresh_scheduled:
            return
        self._clip_feedback_refresh_scheduled = True
        self.schedule_message(1, self._refresh_clip_feedback_bindings)

    def _listen_to_clip_slot(self, clip_slot, local_track_index, scene_index):
        self._add_live_listener(
            self._clip_slot_listeners,
            clip_slot,
            "has_clip",
            self._request_clip_feedback_refresh,
        )
        self._add_live_listener(
            self._clip_slot_listeners,
            clip_slot,
            "color",
            lambda: self._refresh_clip_button_color(
                local_track_index, scene_index
            ),
        )
        if clip_slot.has_clip:
            self._listen_to_clip_color(clip_slot.clip, local_track_index, scene_index)

    def _listen_to_clip_color(self, clip, local_track_index, scene_index):
        def callback():
            self._refresh_clip_button_color(local_track_index, scene_index)

        self._add_live_listener(self._clip_color_listeners, clip, "color", callback)

    def _add_live_listener(self, listener_store, subject, property_name, callback):
        add_listener = getattr(subject, "add_%s_listener" % property_name, None)
        if add_listener is None:
            return
        try:
            add_listener(callback)
        except RuntimeError:
            return
        listener_store.append((subject, property_name, callback))

    def _clear_clip_feedback_listeners(self):
        for clip_slot, property_name, callback in self._clip_slot_listeners:
            self._remove_live_listener(clip_slot, property_name, callback)
        self._clip_slot_listeners = []

        for clip, property_name, callback in self._clip_color_listeners:
            self._remove_live_listener(clip, property_name, callback)
        self._clip_color_listeners = []

    def _remove_live_listener(self, subject, property_name, callback):
        has_listener_name = "%s_has_listener" % property_name
        remove_name = "remove_%s_listener" % property_name
        if not hasattr(subject, remove_name):
            return
        has_listener = getattr(subject, has_listener_name, None)
        if has_listener is None or has_listener(callback):
            getattr(subject, remove_name)(callback)

    def _refresh_clip_button_color(self, local_track_index, scene_index):
        clip_slot = self._visible_clip_slot(local_track_index, scene_index)
        self._set_clip_button_color(local_track_index, scene_index, clip_slot)

    def _set_clip_button_color(self, local_track_index, scene_index, clip_slot):
        led_color = self._clip_slot_led_color(clip_slot)
        button = self._clip_launch_buttons.get((local_track_index, scene_index))
        if button is not None and hasattr(button, "set_led_color"):
            button.set_led_color(led_color if led_color != K2_LED_OFF else K2_LED_RED)
        clip_component = self._session.scene(scene_index).clip_slot(local_track_index)
        if hasattr(clip_component, "update"):
            clip_component.update()

    def _clip_slot_led_color(self, clip_slot):
        if clip_slot is None:
            return K2_LED_OFF

        live_color = None
        if clip_slot.has_clip and hasattr(clip_slot.clip, "color"):
            live_color = clip_slot.clip.color
        elif hasattr(clip_slot, "color"):
            live_color = clip_slot.color
        return nearest_k2_led_color(live_color)

    def _visible_track(self, local_track_index, visible_tracks=None):
        track_index = self._current_track_offset + local_track_index
        tracks = (
            visible_tracks if visible_tracks is not None else self.song().visible_tracks
        )
        if track_index < 0 or track_index >= len(tracks):
            return None
        return tracks[track_index]

    def _start_clip_led_blink_timer(self):
        if self._clip_led_blink_timer_running:
            return
        self._clip_led_blink_timer_running = True
        self.schedule_message(self._CLIP_LED_BLINK_DELAY, self._on_clip_led_blink)

    def _on_clip_led_blink(self):
        if not self._clip_led_blink_timer_running:
            return
        self._clip_led_blink_on = not self._clip_led_blink_on
        self._apply_clip_led_blink_overrides()
        self.schedule_message(self._CLIP_LED_BLINK_DELAY, self._on_clip_led_blink)

    def _apply_clip_led_blink_overrides(self, visible_tracks=None):
        visible_tracks = (
            visible_tracks if visible_tracks is not None else self.song().visible_tracks
        )
        for clip_button_key, button in self._clip_launch_buttons.items():
            local_track_index, scene_index = clip_button_key
            clip_slot = self._visible_clip_slot(
                local_track_index, scene_index, visible_tracks
            )
            has_clip = clip_slot is not None and clip_slot.has_clip
            should_blink = self._clip_slot_should_blink(
                local_track_index, scene_index, clip_slot, visible_tracks
            )
            if hasattr(button, "set_blink_override"):
                button.set_blink_override(
                    has_clip,
                    self._clip_led_blink_on if should_blink else True,
                )

    def _clip_slot_should_blink(
        self, local_track_index, scene_index, clip_slot, visible_tracks=None
    ):
        if clip_slot is None or not clip_slot.has_clip:
            return False
        track = self._visible_track(local_track_index, visible_tracks)
        absolute_scene_index = self._current_scene_offset + scene_index
        return self._clip_slot_is_playing(
            track, absolute_scene_index, clip_slot
        ) or self._clip_slot_is_triggered(track, absolute_scene_index, clip_slot)

    def _clip_slot_is_playing(self, track, absolute_scene_index, clip_slot):
        if (
            track is not None
            and hasattr(track, "playing_slot_index")
            and track.playing_slot_index == absolute_scene_index
        ):
            return True
        if hasattr(clip_slot, "is_playing") and clip_slot.is_playing:
            return True
        if hasattr(clip_slot.clip, "is_playing") and clip_slot.clip.is_playing:
            return True
        return False

    def _clip_slot_is_triggered(self, track, absolute_scene_index, clip_slot):
        if (
            track is not None
            and hasattr(track, "fired_slot_index")
            and track.fired_slot_index == absolute_scene_index
        ):
            return True
        if hasattr(clip_slot, "is_triggered") and clip_slot.is_triggered:
            return True
        if hasattr(clip_slot.clip, "is_triggered") and clip_slot.clip.is_triggered:
            return True
        return False

    def _clear_all_clip_leds(self):
        for button in self._clip_launch_buttons.values():
            if hasattr(button, "set_blink_override"):
                button.set_blink_override(False)
            if hasattr(button, "turn_off"):
                button.turn_off()

    def _set_strip_volume_from_midi(self, strip, midi_value):
        track = getattr(strip, "_track", None)
        if track is None:
            return
        volume = track.mixer_device.volume
        fraction = capped_midi_fraction(midi_value, VOLUME_MAX_MIDI_VALUE)
        target_maximum = volume.default_value
        volume_range = target_maximum - volume.min
        volume.value = volume.min + (volume_range * fraction)

    def _set_strip_send_from_midi(self, strip, send_index, midi_value):
        track = getattr(strip, "_track", None)
        if track is None:
            return
        sends = track.mixer_device.sends
        if send_index >= len(sends):
            return
        send = sends[send_index]
        send_range = send.max - send.min
        send.value = send.min + (send_range * (float(midi_value) / 127.0))

    def _nudge_strip_send(self, strip, midi_value, send_index):
        track = getattr(strip, "_track", None)
        if track is None:
            return
        sends = track.mixer_device.sends
        if send_index >= len(sends):
            return
        delta = relative_two_complement_delta(midi_value)
        if delta == 0:
            return
        send = sends[send_index]
        send_range = send.max - send.min
        step = (send_range / 127.0) * TOP_ENCODER_SEND_SENSITIVITY
        next_value = send.value + (delta * step)
        send.value = max(send.min, min(send.max, next_value))

    def _create_button(self, channel, note, name):
        button = ButtonElement(True, MIDI_NOTE_TYPE, channel, note)
        button.name = name
        return button

    def _create_clip_button(self, channel, note, name):
        button = K2ClipButtonElement(True, MIDI_NOTE_TYPE, channel, note)
        button.name = name
        return button

    def _create_slider(self, channel, cc, name):
        slider = SliderElement(MIDI_CC_TYPE, channel, cc)
        slider.name = name
        return slider

    def _create_absolute_encoder(self, channel, cc, name):
        encoder = EncoderElement(
            MIDI_CC_TYPE,
            channel,
            cc,
            Live.MidiMap.MapMode.absolute,
        )
        encoder.name = name
        return encoder

    def _create_relative_encoder(self, channel, cc, name):
        encoder = EncoderElement(
            MIDI_CC_TYPE,
            channel,
            cc,
            Live.MidiMap.MapMode.relative_smooth_two_compliment,
        )
        encoder.name = name
        return encoder
