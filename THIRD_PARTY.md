# What bandbox borrows, and what is its own

**bandbox's own work** (MIT, Brian Findlay, 2026): the MCP server and its tools, the score
format and checker, the rhythm-section styles (boom-chick, train, shuffle and the rest), the
chord voicings, the per-track drive, the mixer and limiter, the one-shot drum sampler, the
clap-tempo finder, hum-to-notes, the fetch script and the demo songs.

**Borrowed, never bundled.** The repository contains none of the files below.
`python -m bandbox.fetch_vendor` downloads each one from its original source and refuses any
file whose SHA-256 differs from the hash recorded here. GeneralUser GS is the exception: its
author asks that his download files not be linked to directly, so the script sends you to his
web page to download it yourself, then checks the file you put in place.

| Piece | Version | Licence | Size | What bandbox uses it for |
|---|---|---|---|---|
| FluidSynth | 2.6.1, win10-x64-cpp11 | LGPL-2.1 | 2.7 MB zip | renders each MIDI track with a SoundFont; run as an unmodified program. The zip also carries `sndfile.dll` (libsndfile, LGPL-2.1) and `SDL3.dll` (SDL 3, zlib licence), which FluidSynth loads |
| GeneralUser GS | 2.0.3 (commit 9704918) | GeneralUser GS License v2.0: free for any music, commercial included | 32.3 MB | instrument set A |
| MuseScore General | 0.2 (.sf3) | MIT (FluidR3 lineage) | 39.9 MB | instrument set B |
| Gogodze Phu Vol II | 1.001 | CC0-1.0 | 139.5 MB zip | the sampled drum kits `gogodze_kit` and `gogodze_retro_kit` |

Sources and SHA-256:

| File | Source | SHA-256 |
|---|---|---|
| fluidsynth-v2.6.1-win10-x64-cpp11.zip | github.com/FluidSynth/fluidsynth/releases/tag/v2.6.1 | `fab7a2e4b85675b66970f97a39bbc239729c5e0f237198b5922a6a73cbc8677c` |
| GeneralUser-GS.sf2 | downloaded by hand via schristiancollins.com/generaluser.php (the author's GitHub, commit 97049183643d5fc5a9322a69c5b09efb667c6c3a) | `9575028c7a1f589f5770fccc8cff2734566af40cd26ed836944e9a5152688cfe` |
| GeneralUser-GS LICENSE.txt | same commit, documentation/LICENSE.txt | `7b32efefdf95ce38a043799f0659853ddc00fbaa14d8c50f0aca16b9b8b405be` |
| MuseScore_General.sf3 | ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General/ (MuseScore's own mirror) | `5b85b6c2c61d10b2b91cddd41efcce7b25cd31c8271d511c73afafbef20b6fa3` |
| MuseScore_General_License.md | same folder | `5ad8d737e13c7f01f5b9674872a82a92b4ba253603e8ed14b9db12293550b4b9` |
| Karoryfer_Gogodze_Phu_vol_II.v1.001.zip | github.com/sfzinstruments/karoryfer.gogodze-phu-vol-ii/releases/tag/v1.001 | `3ff7728f82001af2144e42d94c29770cded57389018e27d4a281f1a0496f7d49` |

Each SoundFont's licence file is downloaded beside it; the drum kit's CC0 `LICENSE` is inside its zip.

## Python libraries (installed with pip, not bundled)

| Library | Version tested | Licence | Used for |
|---|---|---|---|
| mcp | 2.3.0 | MIT | the MCP server |
| mido | 1.3.3 | MIT | writing and reading MIDI files |
| numpy | 2.5.1 | BSD-3-Clause | all audio maths |
| scipy | 1.17.1 | BSD-3-Clause | one filter in the drive effect |
| soundfile | 0.13.1 (with libsndfile) | BSD-3-Clause (libsndfile: LGPL-2.1) | reading and writing WAV |
| pyloudnorm | 0.2.0 | MIT | loudness measurement (LUFS) |

ffmpeg (on PATH, LGPL/GPL build as installed) encodes the MP3.

## Inspiration

[mcp-server-synth](https://github.com/Digital-Physics/mcp-server-synth) by Digital-Physics showed
the idea of a synth Claude can drive. It has no licence, so all rights are reserved: no code,
samples or text were taken from it. bandbox was written from scratch.

## Credit lines (for an article or video description)

- Sound engine: FluidSynth (fluidsynth.org), LGPL-2.1.
- Instruments: GeneralUser GS by S. Christian Collins (schristiancollins.com).
- Instruments: MuseScore General (MIT): FluidR3 by Frank Wen, FluidR3Mono by Michael Cowgill, adapted by S. Christian Collins; Temple Blocks by Ethan Winer; Drumline Cymbals by Michael Schorsch.
- Drums: Gogodze Phu Vol II by Karoryfer Samples (Karoryfer Lecolds, karoryfer.com), CC0.
- Band in a box, score format and MCP server: bandbox by Brian Findlay, MIT.
