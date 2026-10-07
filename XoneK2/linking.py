"""Pure-Python helpers shared by the Live script and local tests."""

from __future__ import annotations

from typing import Iterable, Sequence, Tuple


def _validated_unique_channels(
    channels: Iterable[int], minimum: int, maximum: int, label: str, offset: int = 0
) -> Tuple[int, ...]:
    normalized = []
    seen = set()
    prefix = "%s " % label if label else ""
    lower_prefix = "%s " % label.lower() if label else ""
    for channel in channels:
        if not isinstance(channel, int):
            raise TypeError("%sMIDI channels must be integers." % prefix)
        if channel < minimum or channel > maximum:
            raise ValueError(
                "%sMIDI channels must be between %d and %d inclusive."
                % (prefix, minimum, maximum)
            )
        normalized_channel = channel + offset
        if normalized_channel not in seen:
            normalized.append(normalized_channel)
            seen.add(normalized_channel)
    if not normalized:
        raise ValueError(
            "At least one %sMIDI channel must be configured." % lower_prefix
        )
    return tuple(normalized)


def normalize_midi_channels(channels: Iterable[int]) -> Tuple[int, ...]:
    return _validated_unique_channels(channels, 0, 15, "")


def hardware_to_script_midi_channels(channels: Iterable[int]) -> Tuple[int, ...]:
    return _validated_unique_channels(channels, 1, 16, "Hardware", -1)


def track_width_for_channels(channels: Sequence[int], tracks_per_k2: int) -> int:
    return len(channels) * tracks_per_k2


def linked_session_offset(widths: Sequence[int], instance_index: int) -> int:
    if instance_index < 0 or instance_index >= len(widths):
        raise ValueError("Instance index is out of range.")
    return sum(widths[:instance_index])


def clamp_track_offset(offset: int, total_tracks: int, width: int) -> int:
    max_offset = max(0, total_tracks - width)
    return max(0, min(offset, max_offset))


def clamp_scene_offset(offset: int, total_scenes: int, height: int) -> int:
    max_offset = max(0, total_scenes - height)
    return max(0, min(offset, max_offset))


def relative_two_complement_delta(value: int) -> int:
    if value < 0 or value > 127:
        raise ValueError("Relative MIDI values must be in the range 0..127.")
    return value if value < 64 else value - 128


def clamp_midi_value(value: int, maximum: int) -> int:
    if value < 0 or value > 127:
        raise ValueError("MIDI values must be in the range 0..127.")
    if maximum < 0 or maximum > 127:
        raise ValueError("Maximum MIDI values must be in the range 0..127.")
    return min(value, maximum)


def capped_midi_fraction(value: int, maximum: int) -> float:
    clamp_midi_value(value, maximum)
    if maximum == 0:
        return 0.0
    return float(min(value, maximum)) / float(maximum)


def clamp_tempo(tempo: float) -> float:
    return max(20.0, min(999.0, tempo))
