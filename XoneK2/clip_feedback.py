"""Clip-color helpers for the Xone:K2 launch pad LEDs."""

from __future__ import annotations

import colorsys

from typing import Optional, Tuple


K2_LED_OFF = "off"
K2_LED_RED = "red"
K2_LED_AMBER = "amber"
K2_LED_GREEN = "green"

K2_LED_LAYERS = (
    (K2_LED_RED, 0),
    (K2_LED_AMBER, 36),
    (K2_LED_GREEN, 72),
)
K2_LED_NOTE_OFFSETS = dict(K2_LED_LAYERS)
K2_LED_LAYER_OFFSETS = tuple(note_offset for _, note_offset in K2_LED_LAYERS)
K2_LED_MAX_NOTE_OFFSET = max(K2_LED_LAYER_OFFSETS)

MIDI_NOTE_ON_STATUS = 0x90
MIDI_NOTE_OFF_STATUS = 0x80
MIDI_MAX_VALUE = 127


def rgb_from_live_color(color: int) -> Tuple[int, int, int]:
    """Return an Ableton packed RGB clip color as an ``(r, g, b)`` tuple."""
    if color < 0 or color > 0xFFFFFF:
        raise ValueError("Live clip colors must be packed RGB values.")
    return ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)


def nearest_k2_led_color(live_color: Optional[int]) -> str:
    """Map an Ableton RGB clip color to a useful K2 hardware LED color."""
    if live_color is None:
        return K2_LED_OFF

    rgb = rgb_from_live_color(live_color)
    if max(rgb) == 0:
        return K2_LED_OFF

    red, green, blue = [float(component) / 255.0 for component in rgb]
    hue, saturation, _ = colorsys.rgb_to_hsv(red, green, blue)
    if saturation < 0.15:
        return K2_LED_AMBER

    hue_degrees = hue * 360.0
    if 30.0 <= hue_degrees < 90.0:
        return K2_LED_AMBER
    if 90.0 <= hue_degrees < 270.0:
        return K2_LED_GREEN
    return K2_LED_RED


def k2_led_messages(
    channel: int, base_note: int, led_color: str
) -> Tuple[Tuple[int, int, int], ...]:
    """Build MIDI messages that set one K2 pad to the requested LED color."""
    if channel < 0 or channel > 15:
        raise ValueError("MIDI channels must be between 0 and 15 inclusive.")
    if base_note < 0 or base_note > MIDI_MAX_VALUE:
        raise ValueError("MIDI notes must be in the range 0..127.")
    if led_color not in K2_LED_NOTE_OFFSETS and led_color != K2_LED_OFF:
        raise ValueError("Unsupported K2 LED color: %s" % led_color)
    if base_note + K2_LED_MAX_NOTE_OFFSET > MIDI_MAX_VALUE:
        raise ValueError("K2 LED layer note exceeds MIDI note range.")

    note_off_status = MIDI_NOTE_OFF_STATUS + channel
    note_on_status = MIDI_NOTE_ON_STATUS + channel
    messages = tuple(
        (note_off_status, base_note + note_offset, MIDI_MAX_VALUE)
        for note_offset in K2_LED_LAYER_OFFSETS
    )
    if led_color != K2_LED_OFF:
        note = base_note + K2_LED_NOTE_OFFSETS[led_color]
        messages += ((note_on_status, note, MIDI_MAX_VALUE),)
    return messages
