"""User-editable configuration for the Xone:K2 Ableton Live Remote Script.

This config uses the Xone:K2's hardware MIDI channel numbering (1..16).
The script converts these to Ableton's internal zero-based channel numbers.
"""

# For X:LINK chains, list the units in left-to-right order as they appear on the
# table or stand. Each unit must use a different MIDI channel in hardware.
#
# Examples:
#   One K2 on hardware MIDI channel 1: (1,)
#   Two K2s linked over X:LINK on hardware channels 1 and 2: (1, 2)
#   Three K2s linked over X:LINK on hardware channels 1, 2 and 3: (1, 2, 3)
#   Four K2s linked over X:LINK on hardware channels 1, 2, 3 and 4: (1, 2, 3, 4)
LINKED_K2_MIDI_CHANNELS = (1, 2, 3, 4)

# Each K2 contributes four track columns and four clip-launch rows.
TRACKS_PER_K2 = 4
SCENES = 4

# Cap the effective slider output to a lower MIDI value so the track volume never
# moves past unity gain (0 dB) unless you explicitly change the target mapping.
# Values at or above this MIDI value are treated as fully open.
VOLUME_MAX_MIDI_VALUE = 100

# Relative top encoders are used as Send 4 nudges for the matching track column.
# Lower values make them less sensitive.
TOP_ENCODER_SEND_SENSITIVITY = 4.0

# The last K2's bottom-right endless encoder nudges Live's tempo by this many
# BPM per relative MIDI step.
TEMPO_ENCODER_BPM_STEP = 0.1

# When the same script is loaded in multiple Ableton control-surface slots, each
# instance shifts its red box to the right by the width of the preceding K2
# instance(s).
LINK_INSTANCES_IN_SESSION = True
