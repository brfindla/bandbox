# What bandbox borrows, and what is its own

**bandbox's own work** (MIT, Brian Findlay, 2026): the MCP server and its tools, the score
format and checker, the rhythm-section styles (boom-chick, train, shuffle and the rest), the
chord voicings, the per-track drive, the mixer and limiter, the one-shot drum sampler, the
clap-tempo finder, hum-to-notes, the fetch script and the demo songs, the tala and bol tables
(`bandbox/tabla.json`, written from the standard thekas as commonly taught) and the tabla sampler.

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
| Tabla strokes: "tabla bols" pack by mmiron (freesound.org/people/mmiron/packs/8162/) | HQ previews, fetched 2026-11-09 | CC0-1.0 | 21 files, 0.3 MB | ge, ke, na, tun, te, re takes |
| Tabla strokes: "Tabla Strokes" pack by ajaysm (freesound.org/people/ajaysm/packs/10737/) | HQ previews, fetched 2026-11-09 | CC BY 4.0 | 7 files, 0.1 MB | tin (the only one), extra ke, na, te, re takes; one tun used only to measure that drum's note |

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

The tabla files are Freesound's public high-quality previews (OGG), which need no login; the original
WAVs need a Freesound account. Each is saved as `vendor/tabla/<stroke>/<author>_<sound id>.ogg`:

| File (under vendor/tabla/) | Source | Licence | SHA-256 |
|---|---|---|---|
| ge/mmiron_130404.ogg | freesound.org/s/130404/ by mmiron | CC0-1.0 | `728685d12f9c252ee329199d61cc530d8d389ef877388f26dff4c99634f4843e` |
| ge/mmiron_130405.ogg | freesound.org/s/130405/ by mmiron | CC0-1.0 | `2a1a2af88716c845cc7cc4d7e52bb619245f1426aaeb668cf5f644b4d08f4cb4` |
| ge/mmiron_130406.ogg | freesound.org/s/130406/ by mmiron | CC0-1.0 | `5be5737a224c5be5a56b5ef26fa11e8dd02770f5e496f63f1563c3b1c3b13a9f` |
| ge/mmiron_130408.ogg | freesound.org/s/130408/ by mmiron | CC0-1.0 | `0a647f47ae47bc6a27524d414aff9e88d227520a2bdc79c8e936ab8e98e4b14f` |
| ge/mmiron_130409.ogg | freesound.org/s/130409/ by mmiron | CC0-1.0 | `d579a0cfb0e39ea2b87d8a52c1ada0d51c97bd9d3d1a0984c27ebc6715d42703` |
| ge/mmiron_130410.ogg | freesound.org/s/130410/ by mmiron | CC0-1.0 | `4ceea873677063ac39738254bfcff37ce4dfa9bab210a3ffb1bab773c70f54e8` |
| ge/mmiron_130411.ogg | freesound.org/s/130411/ by mmiron | CC0-1.0 | `5bbea145e755271deac976b93a32cceedcd64910ec77b09430870164a9e43689` |
| ge/mmiron_130414.ogg | freesound.org/s/130414/ by mmiron | CC0-1.0 | `525592d12f38d0193755e0822a265b62892f0d505bee7f490a74a3a7cf0d37fb` |
| ke/mmiron_130413.ogg | freesound.org/s/130413/ by mmiron | CC0-1.0 | `627a9ad863145db9f6258631ef3db745a9c50dd13da7cdb9fc096201c4e060a9` |
| ke/mmiron_130423.ogg | freesound.org/s/130423/ by mmiron | CC0-1.0 | `443a8efd29fa896c0058dd34c7a729a3e8c7a854b2cd347d8f006c6603b75c2c` |
| ke/mmiron_130424.ogg | freesound.org/s/130424/ by mmiron | CC0-1.0 | `ea7cf993edabd3d860a8b44e76c4932454189baa7afda2d5ee10267385a4b4d9` |
| ke/ajaysm_171901.ogg | freesound.org/s/171901/ by ajaysm | CC BY 4.0 | `29f43eda70206fafcfe9c96331ee1a07d810c8444fa00505ae030117b7428c14` |
| ke/ajaysm_171906.ogg | freesound.org/s/171906/ by ajaysm | CC BY 4.0 | `47afcab94c40348adfdeb814582d4a3e894ef69f06c4f08978a51bc115e9df95` |
| na/mmiron_130421.ogg | freesound.org/s/130421/ by mmiron | CC0-1.0 | `adb244e66c871cb87f4949196d6fbb345b75a3f7ad298248ed27813694052d82` |
| na/mmiron_130428.ogg | freesound.org/s/130428/ by mmiron | CC0-1.0 | `63b8fb599d337a037cd77374dcbba1cddf0e29bc90c392b109cd82542c101254` |
| na/ajaysm_171905.ogg | freesound.org/s/171905/ by ajaysm | CC BY 4.0 | `c881f871ceb62b77972d76816650c62f0be13c0bc49e60b985563868e70197a8` |
| tin/ajaysm_171911.ogg | freesound.org/s/171911/ by ajaysm | CC BY 4.0 | `b2761ca03418eb2fd4c214643571b7cead0f926cb14ee2a667ba912002300dd0` |
| tun/mmiron_130416.ogg | freesound.org/s/130416/ by mmiron | CC0-1.0 | `72805cbf910ed15dbaa8d14f12af136c28ee06763c0a75291665115fb1e7f4ed` |
| tun/mmiron_130419.ogg | freesound.org/s/130419/ by mmiron | CC0-1.0 | `972225489f3c30c056988ce3166ae47f49987045be8629348dcbc1e3385f73e5` |
| tun/mmiron_130420.ogg | freesound.org/s/130420/ by mmiron | CC0-1.0 | `6362fc36a658630117b6b209ae17ca266a7a9bc2638e17b00e3acd956744245a` |
| _tune/ajaysm_171909.ogg | freesound.org/s/171909/ by ajaysm | CC BY 4.0 | `bb9291568793f13c550280f1f3556e985fe96be9b89c2f3b463cf939d7629591` |
| te/mmiron_130429.ogg | freesound.org/s/130429/ by mmiron | CC0-1.0 | `b009be9e98ceb47f7270d781a91010e284b099ef920e55b218b4bd2602093c76` |
| te/mmiron_130418.ogg | freesound.org/s/130418/ by mmiron | CC0-1.0 | `ad6310f0e62c5b4ada0cfac35957f7e2e71140bec836b6d9c6426a7769e87bd4` |
| te/mmiron_130415.ogg | freesound.org/s/130415/ by mmiron | CC0-1.0 | `9d9a85021b4f66823ce7fe154f1f48f9ed7a31ad0502fccb26ef824fc718262e` |
| te/mmiron_130417.ogg | freesound.org/s/130417/ by mmiron | CC0-1.0 | `55199488583945f1f84b46c4f49be6116f97b79b697849e6ca973d1f5f84cc04` |
| te/ajaysm_171913.ogg | freesound.org/s/171913/ by ajaysm | CC BY 4.0 | `1bc4e8454a2fe1021884ebe3fd236af6225518b0341a5085ea23e98cb9e74212` |
| re/mmiron_130427.ogg | freesound.org/s/130427/ by mmiron | CC0-1.0 | `2ab1e0675d474ab94d1ba1e1b7796d6e4209fb431c84d62fd5285326808bc427` |
| re/ajaysm_171907.ogg | freesound.org/s/171907/ by ajaysm | CC BY 4.0 | `c0f37d8ecd3c0882ad94cd50d41fba133909ac3c424bf5015a77e3a0c48e3427` |

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
- Tabla: "tabla bols" by mmiron (freesound.org), CC0.
- Tabla: "Tabla Strokes" by ajaysm (freesound.org), CC BY 4.0, these sounds:
  - "ka stroke" by ajaysm, https://freesound.org/s/171901/, licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Used unchanged except: trimmed to the attack, mixed to mono.
  - "kat stroke" by ajaysm, https://freesound.org/s/171906/, licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Used unchanged except: trimmed to the attack, mixed to mono.
  - "na stroke" by ajaysm, https://freesound.org/s/171905/, licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Used unchanged except: trimmed to the attack, mixed to mono, re-tuned to the song's key.
  - "tin stroke" by ajaysm, https://freesound.org/s/171911/, licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Used unchanged except: trimmed to the attack, mixed to mono, re-tuned to the song's key.
  - "tun stroke" by ajaysm, https://freesound.org/s/171909/, licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Not played: used only to measure that drum's note, so its other strokes can be tuned.
  - "te stroke" by ajaysm, https://freesound.org/s/171913/, licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Used unchanged except: trimmed to the attack, mixed to mono, re-tuned to the song's key.
  - "re stroke" by ajaysm, https://freesound.org/s/171907/, licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Used unchanged except: trimmed to the attack, mixed to mono, re-tuned to the song's key.
- Band in a box, score format and MCP server: bandbox by Brian Findlay, MIT.
