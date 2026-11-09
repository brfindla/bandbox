"""Tabla for bandbox: talas (rhythm cycles of any length), bols (the spoken stroke syllables) and
a one-shot sampler that plays them.

The table of talas, thekas, strokes and bols is data, in tabla.json beside this file; correct it
there. Not yet checked by a tabla player.

Bol text, as a model or a person writes it:
    "dha dhin dhin dha | dha dhin dhin dha | dha tin tin ta | ta dhin dhin dha"
- one word = one beat (matra); '|' marks a vibhag and is checked against the tala
- 'dha.ge' splits a beat into two (or more) equal parts
- '-' is a silent beat or part
- compound bols ('tirakita') share their beat or part evenly
"""
import json
import random
import re
from pathlib import Path

import numpy as np

DATA = json.loads((Path(__file__).with_name("tabla.json")).read_text("utf-8"))
TALAS, STROKES, BOLS, COMPOUNDS = DATA["talas"], DATA["strokes"], DATA["bols"], DATA["compounds"]
# MIDI note per stroke in the tabla track (never sent to a synth; the sampler reads them back)
STROKE_NOTE = {"ge": 36, "ke": 37, "na": 60, "tin": 61, "tun": 62, "te": 63, "re": 64}
NOTE_STROKE = {v: k for k, v in STROKE_NOTE.items()}


class BolError(ValueError):
    pass


def tala(name):
    if name not in TALAS:
        raise BolError(f"tala {name!r} unknown; talas: {list(TALAS)}")
    return TALAS[name]


def _strokes(bol):
    if bol not in BOLS:
        raise BolError(f"bol {bol!r} unknown; bols: {' '.join(sorted(BOLS))}, compounds: "
                       f"{' '.join(sorted(COMPOUNDS))}, '-' for silence")
    return BOLS[bol]


def parse(text, tala_name=None):
    """Bol text -> (beats, [(beat, [strokes], whole_beat)]). Raises BolError naming the problem."""
    if not isinstance(text, str) or not text.strip():
        raise BolError("bols: a string like 'dha dhin dhin dha | ...'; to play the tala's theka, "
                       "leave the track out of this section's bols")
    toks = text.replace("|", " | ").lower().split()
    t = tala(tala_name) if tala_name else None
    bounds = set()
    if t:
        acc = 0
        for v in t["vibhag"]:
            bounds.add(acc); acc += v
    events, beat = [], 0
    for tok in toks:
        if tok == "|":
            if t and beat % t["beats"] not in bounds:
                raise BolError(f"'|' after beat {beat} does not start a vibhag of {tala_name} "
                               f"({'+'.join(map(str, t['vibhag']))})")
            continue
        parts = tok.split(".")
        for k, part in enumerate(parts):
            if not part:
                raise BolError(f"{tok!r}: an empty part; write 'dha.ge', '-' for silence")
            if part == "-":
                continue
            seq = COMPOUNDS.get(part, [part])
            for j, bol in enumerate(seq):
                at = beat + (k + j / len(seq)) / len(parts)
                events.append((at, _strokes(bol), k == 0 and j == 0))
        beat += 1
    if not beat:
        raise BolError("bols: no beats")
    return beat, events


def accent(beat_in_cycle, whole_beat, t):
    """Velocity for a stroke: sam strongest, tali vibhags next, khali softest; off-beats lighter."""
    if not whole_beat:
        return 74
    if beat_in_cycle == 0:                            # sam; in rupak it is also khali, so lighter
        return 94 if t and t["marks"][0] == "0" else 118
    acc = 0
    for v, mark in zip(t["vibhag"], t["marks"]) if t else ():
        if beat_in_cycle == acc:
            return 84 if mark == "0" else 100
        acc += v
    return 88


def section_notes(text, tala_name, bpb, n_bars, beat0, rng, swing=lambda b: b):
    """Bols repeated to fill a section of n_bars bars -> [(beat, length, midi_note, velocity)]."""
    beats, events = parse(text, tala_name)
    total = n_bars * bpb
    if total % beats:
        raise BolError(f"bols last {beats} beats; the section is {total}, which they must divide")
    t = TALAS.get(tala_name)
    cycle = t["beats"] if t else beats              # no tala: the bols' own length is the cycle
    out = []
    for rep in range(total // beats):
        for at, strokes, whole in events:
            b = rep * beats + at
            at_cycle = round(b, 6) % cycle if whole else -1
            v = accent(at_cycle, whole, t) + rng.randint(0 if at_cycle == 0 else -5, 5)   # sam never drops
            at = beat0 + swing(b) + rng.uniform(-.006, .006)   # both hands of a bol strike together
            for s in strokes:
                out.append((at, .25, STROKE_NOTE[s], v))
    return out


def sheet(s, arrangement):
    """Bol sheet (HTML) for a score's tabla tracks: one row per cycle, the clap signs over the
    vibhags. arrangement: the sections in play order (score.arrangement)."""
    from html import escape
    t = TALAS.get(s.get("tala"))
    cycle = t["beats"] if t else s["beats_per_bar"]
    groups = list(zip(t["vibhag"], t["marks"])) if t else [(cycle, "")]
    head = (f"<h1>{escape(str(s.get('title', 'Tabla')))}</h1><p>{escape(s.get('tala') or '')} "
            f"{cycle} beats &middot; {s['tempo']} beats a minute &middot; key {escape(str(s.get('key', '')))}</p>")
    rows = []
    for name, tr in s["tracks"].items():
        if tr["part"] != "tabla":
            continue
        for sec in arrangement:
            style = (sec.get("styles") or {}).get(name, tr.get("style", "theka"))   # as to_midi chooses
            text = (sec.get("bols") or {}).get(name) or (t["theka"] if t and style == "theka" else "")
            if not text or name in (sec.get("mute") or []):
                continue
            toks = [x for x in text.replace("|", " ").split()]
            total = len(sec["chords"]) * s["beats_per_bar"]
            toks = (toks * (total // len(toks)))[:total]
            rows.append(f"<h2>{escape(str(sec.get('name', '')))}</h2>")
            for c in range(0, total, cycle):
                cells, k = [], c
                for size, mark in groups:
                    beat = " ".join(f"<td>{escape(x.replace('.', ' '))}</td>" for x in toks[k:k + size])
                    cells.append(f"<td class=m>{escape(mark)}</td>{beat}")
                    k += size
                rows.append("<table><tr>" + "<td class=g></td>".join(cells) + "</tr></table>")
    css = ("body{font:16px/1.5 Georgia,serif;max-width:60em;margin:2em auto;padding:0 1em}"
           "table{border-collapse:collapse;margin:.3em 0}td{border:1px solid #bbb;padding:.2em .5em;min-width:3.2em}"
           "td.m{border:none;font-weight:bold;min-width:1.2em;color:#a33}td.g{border:none;min-width:.6em}")
    foot = ("<p>X = sam (beat 1, clapped), a number = tali (clapped), 0 = khali (a wave). "
            "Not yet checked by a tabla player; corrections welcome.</p>")
    return f"<!doctype html><meta charset=utf-8><title>{escape(str(s.get('title', 'Tabla')))}</title><style>{css}</style>" +         head + "".join(rows) + foot


# ---- the sampler ------------------------------------------------------------------------

SR = 44100
ROOT = Path(__file__).resolve().parent.parent
SAMPLE_ROOT = Path(__import__("os").environ.get("BANDBOX_VENDOR", ROOT / "vendor")) / "tabla"
EXTS = (".wav", ".flac", ".ogg")


def available():
    return all(_takes(s) for s in STROKES)


def _source(path):
    """Takes are named <source>_<id>: each source is one drum, tuned on its own."""
    return path.stem.split("_")[0]


def _takes(stroke):
    d = SAMPLE_ROOT / stroke
    return sorted(p for p in d.glob("*") if p.suffix.lower() in EXTS) if d.is_dir() else []


def _load(path):
    import soundfile as sf
    from scipy.signal import resample_poly
    x, sr = sf.read(str(path), dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    if sr != SR:
        x = resample_poly(x, SR, sr).astype(np.float32)
    i = int(np.argmax(np.abs(x) > 0.05 * np.abs(x).max()))   # trim lead-in silence to the attack
    x = x[max(0, i - 32):]
    return x / (np.abs(x).max() + 1e-9)


def _shift(x, semitones):
    """Re-tune by resampling (the ring gets a little shorter or longer, as on a re-tuned drum)."""
    if not semitones:
        return x
    r = 2 ** (semitones / 12)
    idx = np.arange(0, len(x) - 1, r)
    return np.interp(idx, np.arange(len(x)), x).astype(np.float32)


def pitch_hz(x):
    """The dayan's tuned note: the strongest spectral peak, 150-1000 Hz, of a ringing stroke."""
    seg = x[int(.02 * SR):int(.4 * SR)]
    if len(seg) < 2048:                               # a very short take: use all of it
        seg = np.pad(x, (0, max(0, 2048 - len(x))))
    sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 1 << 16))
    f = np.fft.rfftfreq(1 << 16, 1 / SR)
    band = (f > 150) & (f < 1000)
    return float(f[band][np.argmax(sp[band])])


def tuning(key, takes):
    """Semitones (-6..+6, fractional) that move a dayan's note to the key note, as a player tunes
    the dayan to Sa. takes: that drum's 'tun' strokes, which ring at the drum's own note."""
    if not key:
        return 0
    m = re.fullmatch(r"([A-G])([#b]?)m?", key)      # a minor key: tune to its tonic too
    if not m:
        return 0
    pc = ({"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[m.group(1)] + {"#": 1, "b": -1, "": 0}[m.group(2)]) % 12
    have = 12 * np.log2(np.median([pitch_hz(x) for x in takes]) / 440) + 69
    return float((pc - have + 6) % 12 - 6)


def _room(x, amount, seed):
    """A small room behind the dry samples: decaying noise, a different tail per side."""
    if amount <= 0:
        return np.stack([x, x], axis=1)
    from scipy.signal import fftconvolve
    r = np.random.default_rng(seed)
    t = np.arange(int(1.2 * SR)) / SR
    out = []
    for _ in range(2):
        ir = r.standard_normal(len(t)) * np.exp(-t / .28)
        ir[: int(.008 * SR)] = 0                      # 8 ms before the first reflections
        wet = fftconvolve(x, ir / np.sqrt(np.sum(ir ** 2)))[:len(x)]
        out.append(x + amount * .5 * wet)
    return np.stack(out, axis=1).astype(np.float32)


def render_track(mid_path, wav_path, key=None, seed=1, reverb=.15):
    """Tabla MIDI (STROKE_NOTE notes) -> stereo float WAV. The dayan is re-tuned to the key note.
    Each drum damps its own last stroke, as a hand on the head does; takes are chosen at random
    (seeded) so repeats differ."""
    import mido
    import soundfile as sf
    if not available():
        missing = [s for s in STROKES if not _takes(s)]
        raise FileNotFoundError(f"tabla samples missing for {missing} under {SAMPLE_ROOT} - run fetch_vendor.py")
    rng = random.Random(seed)
    files = {s: _takes(s) for s in STROKES}
    tun = {}
    for p in files["tun"] + _takes("_tune"):          # _tune: a take kept only to measure its drum's note
        tun.setdefault(_source(p), []).append(_load(p))
    every = [x for xs in tun.values() for x in xs]
    takes = {}
    for s, ps in files.items():                       # only the dayan is tuned to the song, each drum on its own
        takes[s] = [_shift(_load(p), tuning(key, tun.get(_source(p), every)) if STROKES[s]["drum"] == "dayan" else 0)
                    for p in ps]
    src = mido.MidiFile(mid_path)
    hits, t = [], 0.0
    for m in src:
        t += m.time
        if m.type == "note_on" and m.velocity > 0 and m.note in NOTE_STROKE:
            hits.append((t, NOTE_STROKE[m.note], m.velocity))
    out = {"bayan": np.zeros(int((src.length + 3) * SR), np.float32)}
    out["dayan"] = np.zeros_like(out["bayan"])
    last = {"bayan": None, "dayan": None}
    prev_take = {}
    fade = int(0.012 * SR)
    for t, stroke, vel in sorted(hits):
        i = int(t * SR)
        drum = STROKES[stroke]["drum"]
        buf = out[drum]
        if last[drum] is not None and STROKES[stroke].get("damps"):   # a closed stroke stops the ring
            p0, xp = last[drum]
            if p0 < i < p0 + len(xp):
                seg = xp[i - p0:i - p0 + len(buf) - i]
                env = np.zeros(len(seg), np.float32)
                env[:fade] = np.linspace(1, 0, fade, dtype=np.float32)[:len(seg)]
                buf[i:i + len(seg)] -= seg * (1 - env)
        pick = rng.choice([k for k in range(len(takes[stroke])) if k != prev_take.get(stroke)] or [0])
        prev_take[stroke] = pick                      # never the same take twice running
        x = takes[stroke][pick] * (vel / 127) ** 1.6 * STROKES[stroke].get("gain", 1.0)
        if len(takes[stroke]) == 1:                   # one take only: vary it a hair, as a hand would
            x = _shift(x, rng.uniform(-.08, .08)) * rng.uniform(.9, 1.1)
        j = min(len(buf), i + len(x))
        buf[i:j] += x[:j - i]
        last[drum] = (i, x)
    # the player sits facing you: bayan a little left, dayan a little right
    b, d = _room(out["bayan"], reverb, seed), _room(out["dayan"], reverb, seed + 1)
    mix = b * [.58, .42] + d * [.42, .58]
    sf.write(str(wav_path), mix, SR, subtype="FLOAT")
