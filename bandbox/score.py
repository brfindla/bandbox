"""Score (JSON) -> one MIDI file per track. The arranger half of bandbox.

A score names tracks (instrument + part + style) and sections (chords per bar, lead
notes, per-section style changes). The rhythm section is generated from style presets;
the lead is written note by note. See README.md for the format, with an example.
"""
import json
import random
import re
from pathlib import Path

import mido

PPQ = 480

# Friendly name -> (bank, program). General MIDI numbering; drum kits are bank 128.
INSTRUMENTS = {
    "grand_piano": (0, 0), "honky_tonk_piano": (0, 3), "electric_piano": (0, 4),
    "drawbar_organ": (0, 16), "rock_organ": (0, 18), "accordion": (0, 21), "harmonica": (0, 22),
    "nylon_guitar": (0, 24), "steel_guitar": (0, 25), "jazz_guitar": (0, 26), "clean_guitar": (0, 27),
    "muted_guitar": (0, 28), "overdrive_guitar": (0, 29),
    "upright_bass": (0, 32), "finger_bass": (0, 33), "picked_bass": (0, 34), "fretless_bass": (0, 35),
    "slap_bass": (0, 36), "distortion_guitar": (0, 30),
    "choir_aahs": (0, 52), "voice_oohs": (0, 53),
    "fiddle": (0, 110), "violin": (0, 40), "cello": (0, 42), "strings": (0, 48),
    "trumpet": (0, 56), "trombone": (0, 57), "tenor_sax": (0, 66), "clarinet": (0, 71),
    "flute": (0, 73), "whistle": (0, 78), "banjo": (0, 105), "steel_drums": (0, 114),
    "standard_kit": (128, 0), "room_kit": (128, 8), "power_kit": (128, 16),
    "jazz_kit": (128, 32), "brush_kit": (128, 40),
    # sampled kits (bandbox/sampler.py); the bank/program is the General MIDI kit used for the
    # hits they have no sample for (ride, crash, tambourine)
    "gogodze_kit": (128, 0), "gogodze_retro_kit": (128, 0),
}
PARTS = {
    "comp": ["boom_chick", "strum", "train", "sustain", "arpeggio", "waltz"],
    "bass": ["root_fifth", "walking", "root", "root_eighths", "waltz"],
    "drums": ["train", "boom_chick", "rock", "shuffle", "brush_swing", "waltz", "none"],
    "lead": [],
}
QUALITIES = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10),
             "maj7": (0, 4, 7, 11), "6": (0, 4, 7, 9), "m6": (0, 3, 7, 9), "9": (0, 4, 7, 10, 14),
             "dim": (0, 3, 6), "dim7": (0, 3, 6, 9), "aug": (0, 4, 8), "sus4": (0, 5, 7), "sus2": (0, 2, 7)}
PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
# General MIDI drum notes
KICK, STICK, SNARE, CLAP, HAT, PEDAL_HAT, OPEN_HAT, CRASH, RIDE, TAMB = 36, 37, 38, 39, 42, 44, 46, 49, 51, 54


class ScoreError(ValueError):
    pass


def parse_chord(sym):
    m = re.fullmatch(r"([A-G])([#b]?)(.*?)(?:/([A-G][#b]?))?", sym.strip())
    if not m or m.group(3) not in QUALITIES:
        raise ScoreError(f"unknown chord {sym!r}; qualities: {', '.join(repr(q) for q in QUALITIES)}")
    root = (PC[m.group(1)] + {"#": 1, "b": -1, "": 0}[m.group(2)]) % 12
    bass = root
    if m.group(4):
        bass = (PC[m.group(4)[0]] + {"#": 1, "b": -1}.get(m.group(4)[1:], 0)) % 12
    return root, QUALITIES[m.group(3)], bass


def note_number(n):
    """'E4', 'F#3', 'Bb2', 60 -> MIDI number (C4 = 60). 'r' -> None."""
    if isinstance(n, int):
        return n
    if n.lower() in ("r", "rest"):
        return None
    m = re.fullmatch(r"([A-G])([#b]?)(-?\d)", n.strip())
    if not m:
        raise ScoreError(f"bad note {n!r}; use names like E4, F#3, Bb2 or 'r' for a rest")
    return 12 * (int(m.group(3)) + 1) + PC[m.group(1)] + {"#": 1, "b": -1, "": 0}[m.group(2)]


def guitar_voicing(root, ivs):
    """A strummed-guitar shape: bass root low, chord tones stacked above (about E2-E4)."""
    r = 40 + (root - 4) % 12                        # root between E2 and D#3
    fifth = next((i for i in ivs if i in (6, 7, 8)), 7)
    third = next((i for i in ivs if i in (2, 3, 4, 5)), 4)
    tones = {r, r + fifth, r + 12, r + 12 + third, r + 12 + fifth}
    for i in ivs:
        if i >= 9:                                  # 6th, 7th, 9th
            tones.add(r + 12 + i if i < 12 else r + i + 12)
    if len(ivs) == 3:
        tones.add(r + 24)
    return sorted(t for t in tones if t <= 72)


def bass_root(pc):
    return 28 + (pc - 4) % 12                       # E1 .. D#2: upright bass range


# ---- loading and checking ------------------------------------------------------------

def load(path_or_dict):
    s = path_or_dict if isinstance(path_or_dict, dict) else json.loads(Path(path_or_dict).read_text("utf-8"))
    return check(s)


def check(s):
    """Validate a score dict; raise ScoreError naming every problem at once. Returns s."""
    errs = []
    if not isinstance(s, dict):
        raise ScoreError("a score is a JSON object")
    num = (int, float)
    if not isinstance(s.get("tempo"), num) or not 30 <= s["tempo"] <= 300:
        errs.append("tempo: a number of beats per minute, 30-300")
    bpb = s.setdefault("beats_per_bar", 4)
    if bpb not in (2, 3, 4):
        errs.append("beats_per_bar: 2, 3 or 4 (quarter-note beats; write 6/8 as 2 with swing, or 3)")
    if not isinstance(s.get("count_in_bars", 0), int) or not 0 <= s.get("count_in_bars", 0) <= 4:
        errs.append("count_in_bars: a whole number 0-4")
    if s.get("count_in_bars", 0) and not any(isinstance(t, dict) and t.get("part") == "drums"
                                             for t in (s.get("tracks") or {}).values() if isinstance(s.get("tracks"), dict)):
        errs.append("count_in_bars: the count-in is played on the drums track; add one or set 0")
    if not isinstance(s.get("swing", 0), num) or not 0 <= s.get("swing", 0) <= 1:
        errs.append("swing: 0 (straight) to 1 (full triplet)")
    tracks = s.get("tracks")
    if not isinstance(tracks, dict) or not tracks or not all(isinstance(v, dict) for v in tracks.values()):
        errs.append("tracks: an object of name -> {instrument, part, style}")
        tracks = {}
    for name, t in tracks.items():
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", name):
            errs.append(f"track name {name!r}: letters, digits, _ or - only")
        if t.get("instrument") not in INSTRUMENTS:
            errs.append(f"track {name}: instrument {t.get('instrument')!r} unknown (see list_instruments)")
        part = t.get("part")
        if part not in PARTS:
            errs.append(f"track {name}: part must be one of {list(PARTS)}")
        elif part != "lead" and t.get("style", PARTS[part][0]) not in PARTS[part]:
            errs.append(f"track {name}: style {t.get('style')!r} not in {PARTS[part]}")
        elif t.get("style") == "waltz" and bpb != 3:
            errs.append(f"track {name}: waltz styles need beats_per_bar 3")
        for k, lo, hi in (("level_db", -60, 12), ("pan", -1, 1), ("reverb", 0, 1), ("drive", 0, 1), ("legato", 0.05, 1)):
            if k in t and (not isinstance(t[k], num) or not lo <= t[k] <= hi):
                errs.append(f"track {name}: {k} must be a number {lo}..{hi}")
    secs = s.get("sections")
    if not isinstance(secs, list) or not secs or not all(isinstance(x, dict) for x in secs):
        errs.append("sections: a list of {name, chords, ...}")
        secs = []
    names = set()
    for i, sec in enumerate(secs):
        label = f"section {sec.get('name', i)}"
        if sec.get("name") in names:
            errs.append(f"{label}: two sections share this name")
        names.add(sec.get("name"))
        if not isinstance(sec.get("repeat", 1), int) or not 1 <= sec.get("repeat", 1) <= 16:
            errs.append(f"{label}: repeat must be a whole number 1-16")
        chords = sec.get("chords")
        if not isinstance(chords, list) or not chords:
            errs.append(f"{label}: chords is a list, one entry per bar ('E', 'A E' splits a bar, '%' repeats)")
            continue
        if str(chords[0]).split()[:1] == ["%"]:
            errs.append(f"{label}: the first bar cannot be '%' (nothing to repeat yet)")
        for c in chords:
            syms = str(c).split()
            if not syms or (len(syms) > 1 and "%" in syms):
                errs.append(f"{label}: bar {c!r}: use one '%' alone, or chord names")
            for sym in syms:
                if sym != "%":
                    try:
                        parse_chord(sym)
                    except ScoreError as e:
                        errs.append(f"{label}: {e}")
        for tname, styl in (sec.get("styles") or {}).items():
            t = tracks.get(tname)
            if t is None:
                errs.append(f"{label}: styles names unknown track {tname!r}")
            elif t.get("part") in PARTS and styl not in PARTS[t["part"]]:
                errs.append(f"{label}: style {styl!r} not valid for {tname} ({t['part']})")
            elif styl == "waltz" and bpb != 3:
                errs.append(f"{label}: waltz styles need beats_per_bar 3")
        for tname in sec.get("mute") or []:
            if tname not in tracks:
                errs.append(f"{label}: mute names unknown track {tname!r}")
        for tname, notes in (sec.get("lead") or {}).items():
            if tname in (sec.get("mute") or []):
                errs.append(f"{label}: {tname} is muted here but has lead notes; drop one")
            if tracks.get(tname, {}).get("part") != "lead":
                errs.append(f"{label}: lead notes for {tname!r}, which is not a lead track")
                continue
            total = 0.0
            for k, ev in enumerate(notes):
                try:
                    if not isinstance(ev, list) or len(ev) not in (2, 3):
                        raise ScoreError("use [note, beats] or [note, beats, velocity]")
                    for n in str(ev[0]).split("+") if isinstance(ev[0], str) else [ev[0]]:
                        m = note_number(n)
                        if m is not None and not 0 <= m <= 127:
                            raise ScoreError("note out of MIDI range 0-127")
                    if not isinstance(ev[1], num) or not ev[1] > 0:
                        raise ScoreError("beats must be a number > 0")
                    if len(ev) == 3 and (not isinstance(ev[2], int) or not 1 <= ev[2] <= 127):
                        raise ScoreError("velocity must be a whole number 1-127")
                    total += ev[1]
                except ScoreError as e:
                    errs.append(f"{label}: {tname} note {k} {ev!r}: {e}")
            if total > len(chords) * bpb + 1e-6:
                errs.append(f"{label}: {tname} notes last {total} beats but the section is {len(chords) * bpb}")
    form = s.get("form") or []
    if not isinstance(form, list):
        errs.append("form: a list of section names")
        form = []
    for f in form:
        if f not in names:
            errs.append(f"form names unknown section {f!r}")
    if errs:
        raise ScoreError("; ".join(errs))
    return s


def arrangement(s):
    """Sections in play order (expanding form and repeat)."""
    by_name = {sec.get("name"): sec for sec in s["sections"]}
    order = [by_name[f] for f in s["form"]] if s.get("form") else s["sections"]
    return [sec for sec in order for _ in range(int(sec.get("repeat", 1)))]


def bar_chords(chords):
    """['E', '%', 'A E'] -> per bar, a list of chord symbols splitting the bar evenly."""
    out, prev = [], None
    for c in chords:
        syms = str(c).split()
        bar = [prev if x == "%" else x for x in syms] if syms != ["%"] else list(out[-1]) if out else [prev]
        out.append(bar)
        prev = bar[-1]
    return out


def song_beats(s):
    return s.get("count_in_bars", 0) * s["beats_per_bar"] + sum(
        len(sec["chords"]) * s["beats_per_bar"] for sec in arrangement(s))


def duration_seconds(s):
    return song_beats(s) * 60.0 / s["tempo"]


# ---- rhythm-section patterns: each returns [(beat, length_beats, [notes], velocity)] per bar

def _swing(beat, amount):
    """Time-warp each beat so its off-beat eighth lands later (amount 1 = triplet feel).
    Everything in the beat moves with it - sixteenths and lead notes too - so parts stay together."""
    whole, f = divmod(beat, 1.0)
    s = 0.5 + amount / 6
    return whole + (f * s / 0.5 if f < 0.5 else s + (f - 0.5) * (1 - s) / 0.5)


def comp_bar(style, chords_in_bar, bpb):
    ev = []
    per = bpb / len(chords_in_bar)
    def chord_at(b):
        root, ivs, _ = parse_chord(chords_in_bar[min(int(b // per), len(chords_in_bar) - 1)])
        return guitar_voicing(root, ivs)
    if style == "boom_chick":
        for b in range(1, bpb, 2):
            ev.append((b, .55, chord_at(b)[1:], 78))
    elif style == "strum":
        for b in range(bpb):
            ev.append((b, .8, chord_at(b), 82 if b % 2 else 70))
    elif style == "train":
        for k in range(bpb * 2):
            b = k / 2
            v = chord_at(b)
            ev.append((b, .3, v if k % 2 == 0 else v[::-1][:3], (84 if int(b) % 2 else 66) if k % 2 == 0 else 58))
    elif style == "sustain":
        for i, _ in enumerate(chords_in_bar):
            ev.append((i * per, per - .05, chord_at(i * per), 70))
    elif style == "arpeggio":
        for k in range(bpb * 2):
            v = chord_at(k / 2)
            ev.append((k / 2, .45, [v[k % len(v)]], 72))
    elif style == "waltz":
        for b in range(1, bpb):
            ev.append((b, .5, chord_at(b)[1:], 74))
    return ev


def bass_bar(style, chords_in_bar, next_root, bpb):
    ev = []
    per = bpb / len(chords_in_bar)
    def idx(b):
        return min(int(b // per), len(chords_in_bar) - 1)
    def at(b):
        return parse_chord(chords_in_bar[idx(b)])
    if style == "root_fifth":
        prev = None
        for b in range(0, bpb, 2):
            root, ivs, bass = at(b)
            change = idx(b) != prev
            prev = idx(b)
            n = bass_root(bass) if change else bass_root(root) + next((i for i in ivs if i in (6, 7, 8)), 7)
            ev.append((b, 1.6, [n], 96 if change else 86))
    elif style == "walking":
        since = 0
        for b in range(bpb):
            root, ivs, bass = at(b)
            since = 0 if b == 0 or idx(b) != idx(b - 1) else since + 1
            if b == bpb - 1 and next_root is not None and since > 0:
                tgt = bass_root(next_root)
                n = tgt - 1 if tgt - 1 >= 28 else tgt + 1     # chromatic approach to the next bar
            elif since == 0:
                n = bass_root(bass)                            # the chord's bass note (slash bass if given)
            else:
                n = bass_root(root) + (0, ivs[1], ivs[2], ivs[1])[since % 4]
            ev.append((b, .9, [n], 92 if b % 2 == 0 else 84))
    elif style == "root":
        for i in range(len(chords_in_bar)):
            ev.append((i * per, per - .1, [bass_root(at(i * per)[2])], 92))
    elif style == "root_eighths":
        for k in range(bpb * 2):
            ev.append((k / 2, .4, [bass_root(at(k / 2)[2])], 92 if k % 2 == 0 else 80))
    elif style == "waltz":
        ev.append((0, 1.8, [bass_root(at(0)[2])], 94))
    return ev


def drum_bar(style, bpb):
    ev = []
    def hit(b, n, v, ln=.25):
        ev.append((b, ln, [n], v))
    if style == "train":
        for k in range(bpb * 4):
            b = k / 4
            v = 96 if (k % 4 == 0 and int(b) % 2 == 1) else (58 if k % 2 == 0 else 40)
            hit(b, SNARE, v)
        for b in range(0, bpb, 2):
            hit(b, KICK, 70)
    elif style == "boom_chick":
        for b in range(bpb):
            hit(b, KICK if b % 2 == 0 else SNARE, 88 if b % 2 == 0 else 80)
    elif style == "rock":
        for k in range(bpb * 2):
            hit(k / 2, HAT, 70 if k % 2 == 0 else 52)
        for b in range(bpb):
            hit(b, KICK if b % 2 == 0 else SNARE, 100 if b % 2 else 96)
        hit(2.5, KICK, 80) if bpb == 4 else None
    elif style == "shuffle":
        for k in range(bpb * 2):
            hit(k / 2, RIDE, 72 if k % 2 == 0 else 50)
        for b in range(bpb):
            hit(b, KICK if b % 2 == 0 else SNARE, 84 if b % 2 else 78)
    elif style == "brush_swing":
        for b in range(bpb):
            hit(b, RIDE, 64)
            if b % 2:
                hit(b, SNARE, 70); hit(b, PEDAL_HAT, 60)
            hit(b + .5, RIDE, 46)
    elif style == "waltz":
        hit(0, KICK, 86); hit(1, SNARE, 62); hit(2, SNARE, 62)
    return ev


# ---- MIDI writing ----------------------------------------------------------------------

def _write_midi(path, s, channel, bank, program, notes, reverb, tail_beats):
    """notes: [(start_beat, length_beats, midi_note, velocity)] -> a type-0 MIDI file."""
    tpb = PPQ
    msgs = [(0, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(s["tempo"]))),
            (0, mido.Message("control_change", channel=channel, control=91, value=int(127 * reverb)))]
    if channel != 9:
        msgs.append((0, mido.Message("control_change", channel=channel, control=0, value=bank)))
    msgs.append((0, mido.Message("program_change", channel=channel, program=program)))
    # per pitch: a note must end before the next one on that pitch starts (jitter and
    # back-to-back drum hits would otherwise cut off or swallow the next note)
    spans = sorted((n, max(0, round(st * tpb)), max(0, round((st + ln) * tpb)), v) for st, ln, n, v in notes)
    for k, (n, t0, t1, v) in enumerate(spans):
        nxt = spans[k + 1] if k + 1 < len(spans) and spans[k + 1][0] == n else None
        if nxt and nxt[1] == t0:
            continue                                          # same pitch, same tick: keep one
        t1 = max(t0 + 1, min(t1, nxt[1]) if nxt else t1)
        msgs.append((t0, mido.Message("note_on", channel=channel, note=n, velocity=max(1, min(127, v)))))
        msgs.append((t1, mido.Message("note_off", channel=channel, note=n, velocity=0)))
    msgs.sort(key=lambda m: (m[0], m[1].type == "note_on"))   # offs before ons at the same tick
    track, last = mido.MidiTrack(), 0
    for t, m in msgs:
        track.append(m.copy(time=t - last)); last = t
    end = round((song_beats(s) + tail_beats) * tpb)
    track.append(mido.MetaMessage("end_of_track", time=max(0, end - last)))
    f = mido.MidiFile(type=0, ticks_per_beat=tpb)
    f.tracks.append(track)
    f.save(path)


def to_midi(s, out_dir, tail_beats=4):
    """Write <out_dir>/<track>.mid for each track; return {track: path}."""
    s = check(s)
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    bpb, swing = s["beats_per_bar"], float(s.get("swing", 0))
    rng = random.Random(s.get("seed", 1))
    secs = arrangement(s)
    lead_in = s.get("count_in_bars", 0) * bpb
    paths = {}
    drum_track = next((n for n, t in s["tracks"].items() if t["part"] == "drums"), None)
    for name, t in s["tracks"].items():
        bank, prog = INSTRUMENTS[t["instrument"]]
        part = t["part"]
        channel = 9 if bank == 128 else 0
        notes = []
        if name == drum_track and lead_in:
            notes += [(b, .2, STICK, 100 if b % bpb == 0 else 80) for b in range(lead_in)]
        beat0 = lead_in
        for si, sec in enumerate(secs):
            bars = bar_chords(sec["chords"])
            if name not in (sec.get("mute") or []):
                style = (sec.get("styles") or {}).get(name, t.get("style", PARTS[part][0] if PARTS[part] else None))
                if part == "lead":
                    b = beat0
                    for ev in (sec.get("lead") or {}).get(name, []):
                        vel = ev[2] if len(ev) > 2 else 90
                        for nn in (str(ev[0]).split("+") if isinstance(ev[0], str) else [ev[0]]):
                            m = note_number(nn)
                            if m is not None:
                                st, en = _swing(b, swing), _swing(b + ev[1], swing)
                                notes.append((st, (en - st) * float(t.get("legato", .92)), m, vel))
                        b += ev[1]
                else:
                    for bi, bar in enumerate(bars):
                        if bi + 1 < len(bars):
                            nxt = parse_chord(bars[bi + 1][0])[2]
                        elif si + 1 < len(secs):
                            nxt = parse_chord(bar_chords(secs[si + 1]["chords"])[0][0])[2]
                        else:
                            nxt = None
                        pat = (comp_bar(style, bar, bpb) if part == "comp" else
                               bass_bar(style, bar, nxt, bpb) if part == "bass" else drum_bar(style, bpb))
                        for b, ln, ns, v in pat:
                            at = beat0 + bi * bpb + _swing(b, swing)
                            for k, nn in enumerate(ns):
                                strum = k * .012 * s["tempo"] / 60 if part == "comp" else 0   # 12 ms per string
                                notes.append((at + strum + rng.uniform(-.008, .008), ln,
                                              nn, v + rng.randint(-6, 6)))
            beat0 += len(bars) * bpb
        p = out_dir / f"{name}.mid"
        _write_midi(p, s, channel, bank if channel != 9 else 0, prog, notes,
                    float(t.get("reverb", .15 if part == "drums" else .3)), tail_beats)
        paths[name] = p
    return paths
