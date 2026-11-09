# bandbox — a band in a box that Claude can drive

Tell Claude what you want in plain words, or give it your lyrics. bandbox writes the arrangement,
plays it offline with sampled instruments, and hands back an MP3 and one WAV per track.
It runs as an MCP server, so any MCP client (Claude Code, Claude Desktop) can drive it.

## Example 1: a sentence in, a track out

> "A 4/4 trucker song with drums and bass and guitars, with rough music."

Claude reads `list_styles`, picks the closest recipe and makes one call:

```text
arrange(name="trucker_rough", style="trucker", grit=0.85)
```

Out comes `out/trucker_rough/mix.mp3`. It has a verse, a chorus, a verse and a chorus at 150 bpm,
with the train beat on a sampled kit, boom-chick electric guitar, strummed acoustic, upright bass
and a harmonica line written for it. `grit` turns up the drive on the electric guitar, the drums
and the harmonica together; the acoustic guitar and the bass stay clean. The score
is saved as `songs/trucker_rough.json`, and Claude can edit it and render it again.

## Example 2: your words in, three tunes out

```text
Lights out, and it's runnin'.
Lights out, and it's runnin'.
Lights out, and it's runnin'.
It does the job and writes it down,
what it did, and why, and what it cost.
I'm asleep, and nothin's lost.
```

1. `set_lyrics` puts the stressed syllables on the beat and shows the layout before any note is
   chosen (`LIGHTS OUT, and it's RUN nin'.`, with the bar and beat of each syllable). If a stress is
   wrong, mark it by hand: `*Lights *out, and it's *run-nin'`.
2. `melody_options(name="lights_out", lyrics=..., style="trucker", tempo=160, chords=["E","E","E","A","B7","E"])`
   writes three tunes over the same band and chords. Each is rendered to its own MP3, and a lyric
   sheet lists the chords and the note names for each line:
   - **A, hook**: talky. The first line is the hook and falls home. A line
     sung again with the same words keeps its notes, the line before last climbs, and the last line falls home like the hook.
   - **B, climb**: sung, with the stressed syllables held. Each line starts higher than the one
     before, and the last comes down home.
   - **C, answer**: on the backbeat. The lines go in pairs, a rising question and then a falling answer.

bandbox does not sing. A lead instrument stands in for the voice: the style's own lead, or
`lead_instrument="voice_oohs"`.

(The lyrics are from "Lights Out" by Brian Findlay, used with permission.)

## What is ours and what is borrowed

This repository is bandbox's own code only (MIT): the MCP server, the genre recipes, the
arranger, the lyric layout and tune writer, the score format, the rhythm styles, the mixer and
drive, the drum sampler, the beat finder and hum-to-notes.

Four free third-party works are **not** included:
- the sound engine, FluidSynth
- two instrument sets, GeneralUser GS and MuseScore General
- the drum kit, Gogodze Phu Vol II by Karoryfer Samples

The fetch script downloads each one from its original source and checks its SHA-256.
[THIRD_PARTY.md](THIRD_PARTY.md) lists the versions, licences, hashes and credit lines.
bandbox was inspired by [mcp-server-synth](https://github.com/Digital-Physics/mcp-server-synth),
but nothing was taken from it.

How it works: a score (JSON) becomes one MIDI file per track. FluidSynth renders each track with
a SoundFont, and the drum sampler plays the sampled kit. The stems are then balanced, mixed and
brought to −16 LUFS, with peaks held under −1 dBFS by a look-ahead limiter. The mix is saved as
an MP3.

## Install (Windows; about 180 MB of downloads)

```bash
git clone https://github.com/brfindla/bandbox
cd bandbox
py -m venv .venv
.venv/Scripts/python -m pip install mido mcp numpy scipy soundfile pyloudnorm
.venv/Scripts/python -m bandbox.fetch_vendor
```

The fetch script fills `vendor/`, which git ignores. One step is yours: instrument set A,
GeneralUser GS. Its author asks people not to link straight to his download files, so the script
tells you where to download it and where to put it. Without it, use `soundfont="musescore"`
(set B). `fetch_vendor --check` re-hashes every download and checks that every unpacked file is
in place. ffmpeg must be on PATH to make MP3s.

## Use it from Claude Code

```bash
claude mcp add bandbox -s user -e PYTHONPATH=<bandbox folder> -- <bandbox folder>/.venv/Scripts/python.exe -m bandbox.server
```

`PYTHONPATH` lets the server start from any folder. Songs and renders go to the bandbox folder's
`songs/` and `out/`; set `BANDBOX_SONGS` and `BANDBOX_OUT` to put them somewhere else.

| Tool | Does |
|---|---|
| `list_styles` | genre recipes: trucker, boom_chicka, outlaw, rockabilly, blues_shuffle, country_waltz. Each gives tempo, beat, bass, comp, instruments, grit, chords and form |
| `arrange` | plain brief → full score from a recipe → rendered track |
| `set_lyrics` | lyrics → syllables placed on beats, to check before writing a tune |
| `melody_options` | lyrics → up to three different tunes, each rendered, plus a lyric sheet |
| `list_instruments` | instrument names, styles and chord types, and what the chosen SoundFont really has |
| `write_score` | checks a score you wrote by hand and saves it as `songs/<name>.json`; reports every error at once |
| `get_score` | reads a saved score back |
| `render` | score → `out/<name>/mix.mp3` + `stems/*.wav` |
| `mix` | re-balances the last render from its stems (level in dB, pan, drive, mute) without re-rendering |
| `analyse_beat` | clap or tap into a WAV; get the tempo and the hit times |
| `hum_to_notes` | hum a tune (one voice) into a WAV; get lead notes ready for a score |

## Score format (for full control)

```json
{
  "title": "Lights Out", "tempo": 160, "beats_per_bar": 4, "count_in_bars": 1, "swing": 0,
  "tracks": {
    "guitar":    {"instrument": "steel_guitar", "part": "comp",  "style": "boom_chick", "pan": -0.3},
    "bass":      {"instrument": "upright_bass", "part": "bass",  "style": "root_fifth"},
    "drums":     {"instrument": "gogodze_kit",  "part": "drums", "style": "train", "drive": 0.3},
    "harmonica": {"instrument": "harmonica",    "part": "lead"}
  },
  "sections": [
    {"name": "verse",  "chords": ["E", "%", "%", "%", "A", "%", "E", "%", "B7", "%", "%", "%", "E", "%", "%", "%"]},
    {"name": "chorus", "chords": ["E", "%", "A E", "B7"],
     "lead": {"harmonica": [["B4", 1], ["B4", 1], ["G#4", 0.5], ["r", 0.5], ["E4+G#4", 5]]},
     "styles": {"drums": "rock"}, "mute": ["guitar"], "repeat": 2}
  ],
  "form": ["verse", "chorus"]
}
```

- **chords**: one entry per bar. `"A E"` splits the bar and `"%"` repeats the bar before.
  - Types: major, `m`, `7`, `m7`, `maj7`, `6`, `m6`, `9`, `dim`, `dim7`, `aug`, `sus4`, `sus2`.
  - Slash bass is allowed (`C/G`).
  - In `arrange` and `melody_options`, Roman numerals (`I IV V7 vi bVII`) also work. They follow the key.
- **lead notes**: `[note, beats]` or `[note, beats, velocity]`.
  - Notes: `E4` (C4 = middle C), `F#3`, `Bb2`.
  - `r` is a rest, and `+` plays two notes together.
- **parts and styles**:
  - comp: `boom_chick`, `strum`, `train`, `sustain`, `arpeggio`, `waltz`
  - bass: `root_fifth`, `walking`, `root`, `root_eighths`, `waltz`
  - drums: `train`, `boom_chick`, `rock`, `shuffle`, `brush_swing`, `waltz`, `none`
  - lead: plays the notes as written
- **drum kits**:
  - General MIDI kits: `standard_kit`, `room_kit`, `power_kit`, `jazz_kit`, `brush_kit`.
  - Sampled `gogodze_kit`: the kit's own default mic blend (close, front, and side and overhead
    panned left and right).
  - Sampled `gogodze_retro_kit`: its lo-fi mic.
  - The sampled kit plays kick, snare, toms and closed hi-hat. Ride, crash, open hat and
    tambourine come from the General MIDI kit, mixed in under it.
- **beats_per_bar**: 2, 3 or 4 quarter-note beats. `waltz` styles need 3.
  - `swing` (0-1) delays the off-beat eighths of every part, lead included.
  - `count_in_bars` is played on the drums track.
- **pickup** (notes before the bar line): put them at the end of the previous section's lead
  list, after a rest.
- **turnaround / intro / break**: write a short section with lead notes and put it in `form`
  (see `songs/lights_out_v3_turnaround.json`).
- **mix**: each stem starts at a level set by its part, with the lead loudest. Then `level_db`
  and `pan` apply, and `drive` (0-1) adds saturation for grit. Track names in `mute`, `levels_db`,
  `pans` and `drives` must match the score; a typo is an error, not something silently ignored.

Humming tips for `hum_to_notes`: one voice, a small breath between two notes on the same pitch,
and a quiet room. It is a plain pitch tracker (YIN, numpy only), not a neural model, so expect to
tidy a note or two.

## Check it

```bash
.venv/Scripts/python tests/test_score.py
.venv/Scripts/python tests/test_songwriting.py
.venv/Scripts/python tests/e2e_stdio.py
.venv/Scripts/python demo/make_demo_pack.py
```

The two test files hold one gate per defect found in review. Each gate was shown to fail with its
bug put back. The e2e script runs every tool over the real MCP connection. The demo script
renders the same chorus played by different line-ups.

## Licence

bandbox code: MIT (see LICENSE). FluidSynth, the SoundFonts and the drum kit keep their own
licences; see THIRD_PARTY.md.
