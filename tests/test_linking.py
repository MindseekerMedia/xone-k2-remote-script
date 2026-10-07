import unittest

from XoneK2.linking import (
    capped_midi_fraction,
    clamp_midi_value,
    clamp_scene_offset,
    clamp_tempo,
    clamp_track_offset,
    hardware_to_script_midi_channels,
    linked_session_offset,
    normalize_midi_channels,
    relative_two_complement_delta,
    track_width_for_channels,
)
from XoneK2.clip_feedback import (
    K2_LED_AMBER,
    K2_LED_GREEN,
    K2_LED_OFF,
    K2_LED_RED,
    k2_led_messages,
    nearest_k2_led_color,
    rgb_from_live_color,
)
from XoneK2.midi_map import midi_note


class LinkingTests(unittest.TestCase):
    def test_normalize_midi_channels_removes_duplicates(self):
        self.assertEqual(normalize_midi_channels([14, 13, 14]), (14, 13))

    def test_normalize_midi_channels_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            normalize_midi_channels([16])

    def test_hardware_to_script_midi_channels(self):
        self.assertEqual(hardware_to_script_midi_channels([14, 15, 16]), (13, 14, 15))

    def test_three_linked_k2s_create_twelve_track_width(self):
        script_channels = hardware_to_script_midi_channels([14, 15, 16])
        self.assertEqual(track_width_for_channels(script_channels, 4), 12)

    def test_four_linked_k2s_create_sixteen_track_width(self):
        script_channels = hardware_to_script_midi_channels([13, 14, 15, 16])
        self.assertEqual(track_width_for_channels(script_channels, 4), 16)

    def test_hardware_to_script_midi_channels_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            hardware_to_script_midi_channels([0])

    def test_track_width_for_channels(self):
        self.assertEqual(track_width_for_channels((14, 13), 4), 8)

    def test_linked_session_offset(self):
        widths = [4, 8, 4]
        self.assertEqual(linked_session_offset(widths, 0), 0)
        self.assertEqual(linked_session_offset(widths, 1), 4)
        self.assertEqual(linked_session_offset(widths, 2), 12)

    def test_linked_session_offset_rejects_out_of_range_index(self):
        with self.assertRaises(ValueError):
            linked_session_offset([4, 8, 4], 3)

    def test_clamp_track_offset(self):
        self.assertEqual(clamp_track_offset(-4, 12, 4), 0)
        self.assertEqual(clamp_track_offset(3, 12, 4), 3)
        self.assertEqual(clamp_track_offset(20, 12, 4), 8)

    def test_clamp_scene_offset(self):
        self.assertEqual(clamp_scene_offset(-1, 6, 4), 0)
        self.assertEqual(clamp_scene_offset(2, 6, 4), 2)
        self.assertEqual(clamp_scene_offset(8, 6, 4), 2)

    def test_relative_two_complement_delta(self):
        self.assertEqual(relative_two_complement_delta(1), 1)
        self.assertEqual(relative_two_complement_delta(127), -1)

    def test_clamp_midi_value(self):
        self.assertEqual(clamp_midi_value(80, 100), 80)
        self.assertEqual(clamp_midi_value(120, 100), 100)

    def test_capped_midi_fraction(self):
        self.assertAlmostEqual(capped_midi_fraction(50, 100), 0.5)
        self.assertAlmostEqual(capped_midi_fraction(100, 100), 1.0)
        self.assertAlmostEqual(capped_midi_fraction(127, 100), 1.0)

    def test_capped_midi_fraction_validates_value_with_zero_maximum(self):
        with self.assertRaises(ValueError):
            capped_midi_fraction(128, 0)

    def test_clamp_tempo(self):
        self.assertAlmostEqual(clamp_tempo(12.0), 20.0)
        self.assertAlmostEqual(clamp_tempo(128.5), 128.5)
        self.assertAlmostEqual(clamp_tempo(1200.0), 999.0)

    def test_midi_note_parser(self):
        self.assertEqual(midi_note("C0"), 12)
        self.assertEqual(midi_note("D#3"), 51)
        self.assertEqual(midi_note("Bb1"), 34)

    def test_rgb_from_live_color(self):
        self.assertEqual(rgb_from_live_color(0x12ABEF), (0x12, 0xAB, 0xEF))

    def test_nearest_k2_led_color(self):
        self.assertEqual(nearest_k2_led_color(None), K2_LED_OFF)
        self.assertEqual(nearest_k2_led_color(0x000000), K2_LED_OFF)
        self.assertEqual(nearest_k2_led_color(0xFF0000), K2_LED_RED)
        self.assertEqual(nearest_k2_led_color(0xFFCC00), K2_LED_AMBER)
        self.assertEqual(nearest_k2_led_color(0x00FF00), K2_LED_GREEN)
        self.assertEqual(nearest_k2_led_color(0x0000FF), K2_LED_GREEN)

    def test_k2_led_messages_turn_off_all_layers_before_color(self):
        base_note = midi_note("C2")
        self.assertEqual(
            k2_led_messages(13, base_note, K2_LED_AMBER),
            (
                (0x80 + 13, base_note, 127),
                (0x80 + 13, base_note + 36, 127),
                (0x80 + 13, base_note + 72, 127),
                (0x90 + 13, base_note + 36, 127),
            ),
        )

    def test_k2_led_messages_rejects_layer_note_overflow(self):
        with self.assertRaises(ValueError):
            k2_led_messages(0, 56, K2_LED_RED)


if __name__ == "__main__":
    unittest.main()
