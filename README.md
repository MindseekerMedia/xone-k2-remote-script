# XoneK2 Ableton Live Remote Script

Custom Ableton Live Remote Script for the Allen & Heath Xone:K2 with support for:

- one K2 on a configured MIDI channel
- multiple K2s linked over `X:LINK` on a single USB connection
- multiple script instances in Live when you use multiple USB-connected K2 chains

The script targets Live 11 and Live 12, which use Python 3 for Remote Scripts.
Tested in Ableton Live 12; see [Testing](#testing) for details.

The default configuration uses four K2s on hardware MIDI channels **1, 2, 3,
and 4**, in left-to-right order, providing a **16-track by 4-scene** session box.

## What It Does

Each K2 contributes a 4-track by 4-scene block:

- 4 faders: track volume
- volume faders are capped by default at MIDI value `100` and full-open maps to Ableton's unity gain (0 dB)
- bottom row of pots: Send A
- middle row of pots: Send B
- top row of pots: Send C
- top row of lit buttons: Arm
- middle row of lit buttons: Solo
- bottom row of lit buttons: Mute
- 4 x 4 matrix: clip launch, with pad LEDs matching the closest K2 color
  for each Ableton clip color
- top encoder push buttons: track select
- top encoder turns: Send D nudging for the matching track column

The first K2 in the configured channel list also provides global controls:

- bottom-left encoder turn: move the session box left and right one track at a time
- bottom-right encoder turn: move the session box up and down by scene
- left bottom button: play/stop toggle
- left bottom button LED: on while Live is playing
- far-right bottom button: lock/unlock horizontal session scrolling
- far-right bottom button LED: on while horizontal session scrolling is locked
- bottom encoder clicks: unused

When you have more than one linked K2, the last K2 in the configured channel
list also provides:

- bottom-right encoder turn: nudge Live's tempo

## K2 Hardware Setup

1. Leave `Latching Layers` off.
2. Set the four K2s to MIDI channels **1, 2, 3, and 4**, from left to right,
   to match the default configuration. For a different number of units, update
   the channel list as described below.
3. Keep the units in the same left-to-right order as the channel list in the script config.

The Allen & Heath manual confirms two important details that this script is built around:

- `X:LINK` carries power and MIDI data between K2s.
- linked K2s only work independently when each unit uses a different MIDI channel.

Source:

- [Allen & Heath Xone:K2 User Guide (official PDF)](https://www.allen-heath.com/content/uploads/2023/06/XoneK2_UG_AP8509_3.pdf)
- [Ableton: Installing third-party remote scripts](https://help.ableton.com/hc/en-us/articles/209072009-Installing-third-party-remote-scripts)

## Configure Linked Units

Edit [`XoneK2/config.py`](XoneK2/config.py) and set `LINKED_K2_MIDI_CHANNELS`.
Use hardware channel numbers **1–16**; the script converts them to Ableton's
internal zero-based numbers. List only the connected units, in left-to-right
order. Any distinct hardware channels can be used if the config matches them.

Examples:

```python
LINKED_K2_MIDI_CHANNELS = (1,)
```

Single K2 on hardware MIDI channel 1: 4 tracks by 4 scenes.

```python
LINKED_K2_MIDI_CHANNELS = (1, 2)
```

Two linked K2s on hardware channels 1 and 2: 8 tracks by 4 scenes.

```python
LINKED_K2_MIDI_CHANNELS = (1, 2, 3)
```

Three linked K2s on hardware channels 1, 2, and 3: 12 tracks by 4 scenes.

```python
LINKED_K2_MIDI_CHANNELS = (1, 2, 3, 4)
```

Four linked K2s on hardware channels 1, 2, 3, and 4: 16 tracks by 4 scenes
(the default configuration). Channel 1 provides the global controls; channel 4
provides the tempo encoder.

## Adjustable Behavior

You can tweak these values in [`XoneK2/config.py`](XoneK2/config.py):

```python
VOLUME_MAX_MIDI_VALUE = 100
TOP_ENCODER_SEND_SENSITIVITY = 4.0
TEMPO_ENCODER_BPM_STEP = 0.1
```

- `VOLUME_MAX_MIDI_VALUE`
  Caps the effective slider range. `100` means MIDI values from `100` to `127` all count as fully open, and fully open maps to Ableton's unity gain (0 dB).
- `TOP_ENCODER_SEND_SENSITIVITY`
  Changes how aggressively the top endless encoders nudge Send D. If a track has fewer than four sends, turning the encoder does nothing for that track.
- `TEMPO_ENCODER_BPM_STEP`
  Changes how many BPM each relative step from the last K2's bottom-right
  encoder adds or subtracts from Live's tempo.

## Clip Color LEDs

The K2 pads are tri-colour LEDs rather than full RGB LEDs, so clip colors are
matched to the closest available hardware color: red, amber, or green. Visible
clips are lit in their matched pad color, empty visible clip slots are unlit,
and playing or triggered clip slots blink. Blue and teal clip colors are mapped
to green because the K2 has no blue LED layer.

## Install In Ableton Live

1. Set the MIDI channel list in `XoneK2/config.py` to match your hardware.
2. Copy the `XoneK2` folder into your Ableton User Library `Remote Scripts` folder.
3. Restart Live.
4. Open `Preferences > Link, Tempo & MIDI`.
5. In a Control Surface slot, choose `XoneK2`.
6. Set the input and output ports to the K2 port.

For an X:LINK chain on one USB connection, use one Control Surface slot for
the whole chain. After changing the config, copy the updated folder again and
restart Live.

User Library Remote Script folder locations:

- macOS: `~/Music/Ableton/User Library/Remote Scripts`
- Windows: `\Users\[username]\Documents\Ableton\User Library\Remote Scripts`

## Using Multiple USB Ports

If you have more than one USB-connected K2 chain, add the script in multiple Control Surface slots.
Each instance uses the same channel list from `XoneK2/config.py`, so each chain
must match that configured list.

Example:

- slot 1: `XoneK2` on K2 chain A
- slot 2: `XoneK2` on K2 chain B

When `LINK_INSTANCES_IN_SESSION = True`, the script automatically offsets later instances to the right so the session boxes do not stack on top of each other.

## Factory MIDI Map Assumption

This script uses the factory K2 MIDI note and CC layout defined in
[`XoneK2/midi_map.py`](XoneK2/midi_map.py). Keep Latching Layers off and match
the hardware MIDI channels to the config.

## Testing

Tested in Ableton Live 12. The hardware setup uses four Xone:K2 controllers
on MIDI channels 1, 2, 3, and 4.
Live 11 is a target, but testing on Live 11 has not been confirmed. Other
controller counts and multiple USB-connected chains have not been confirmed
as tested.

Run the automated tests from the repository root with Python 3:

```sh
python3 -m unittest discover -s tests
```

All 21 tests pass. They cover the pure-Python helpers for MIDI channel
conversion, session offsets, value clamping, note parsing, and clip LED colors
and messages. They do not run the controller inside Ableton or verify physical
MIDI input, LED feedback, or Live framework integration.

## License

Licensed under the [MIT License](LICENSE).
