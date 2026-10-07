"""Factory-default MIDI map for the Allen & Heath Xone:K2."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Tuple


NOTE_PATTERN = re.compile(r"^([A-G])([#b]?)(-?\d+)$")
NOTE_OFFSETS = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}


def midi_note(note_name: str) -> int:
    match = NOTE_PATTERN.match(note_name)
    if not match:
        raise ValueError("Invalid note name: %s" % note_name)
    note, accidental, octave_text = match.groups()
    octave = int(octave_text)
    semitone = NOTE_OFFSETS[note]
    if accidental == "#":
        semitone += 1
    elif accidental == "b":
        semitone -= 1
    return ((octave + 1) * 12) + semitone


def notes(*values: str) -> Tuple[int, ...]:
    return tuple(midi_note(value) for value in values)


@dataclass(frozen=True)
class FactoryMidiMap:
    top_encoders: Tuple[int, ...] = (0, 1, 2, 3)
    send_a_pots: Tuple[int, ...] = (4, 5, 6, 7)
    send_b_pots: Tuple[int, ...] = (8, 9, 10, 11)
    pan_pots: Tuple[int, ...] = (12, 13, 14, 15)
    faders: Tuple[int, ...] = (16, 17, 18, 19)
    navigation_encoders: Tuple[int, ...] = (20, 21)
    top_encoder_switches: Tuple[int, ...] = notes("E3", "F3", "F#3", "G3")
    mute_switches: Tuple[int, ...] = notes("C3", "C#3", "D3", "D#3")
    solo_switches: Tuple[int, ...] = notes("G#2", "A2", "A#2", "B2")
    arm_switches: Tuple[int, ...] = notes("E2", "F2", "F#2", "G2")
    clip_rows: Tuple[Tuple[int, ...], ...] = (
        notes("C2", "C#2", "D2", "D#2"),
        notes("G#1", "A1", "A#1", "B1"),
        notes("E1", "F1", "F#1", "G1"),
        notes("C1", "C#1", "D1", "D#1"),
    )
    play_button: int = midi_note("C0")
    stop_button: int = midi_note("C#0")
    record_button: int = midi_note("D0")
    overdub_button: int = midi_note("D#0")


FACTORY_MAP = FactoryMidiMap()
