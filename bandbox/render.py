"""Render: MIDI per track -> WAV stems (FluidSynth, offline) -> mix -> loudness -> MP3.

Each track is rendered to its own stem so mix() can re-balance a song without
re-rendering. FluidSynth runs as a command-line program (LGPL, unmodified, in
vendor/); nothing here links against it.
"""
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pyloudnorm
import soundfile as sf
from scipy.signal import lfilter

from . import sampler, score as sc, tabla
from .soundfont import presets

ROOT = Path(__file__).resolve().parent.parent
VENDOR = Path(os.environ.get("BANDBOX_VENDOR", ROOT / "vendor"))
FLUIDSYNTH = VENDOR / "fluidsynth" / "bin" / "fluidsynth.exe"
SOUNDFONTS = {"generaluser": "GeneralUser-GS.sf2", "musescore": "MuseScore_General.sf3"}
SR = 44100


def soundfont_path(name):
    if name not in SOUNDFONTS:
        raise ValueError(f"soundfont {name!r} unknown; choose from {list(SOUNDFONTS)}")
    p = VENDOR / "soundfonts" / SOUNDFONTS[name]
    if not p.exists():
        raise FileNotFoundError(f"{p} missing - see README 'Install'")
    return p


def _fluidsynth(sf2, mid, wav):
    exe = FLUIDSYNTH if FLUIDSYNTH.exists() else "fluidsynth"
    r = subprocess.run([str(exe), "-ni", "-q", "-g", "0.5", "-r", str(SR), "-R", "1", "-C", "0", "-O", "float",
                        "-F", str(wav), "-T", "wav", str(sf2), str(mid)],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0 or not Path(wav).exists():
        raise RuntimeError(f"fluidsynth failed on {mid}: {r.stderr.strip()[-400:]}")


def render_stems(s, out_dir, soundfont="generaluser"):
    """Score dict -> out_dir/stems/<track>.wav. Returns {track: wav path}."""
    out_dir = Path(out_dir)
    mids = sc.to_midi(s, out_dir / "midi")
    stems = out_dir / "stems"; stems.mkdir(parents=True, exist_ok=True)
    sf2 = soundfont_path(soundfont)
    have = {(b, p) for b, p, _ in presets(sf2)}        # FluidSynth would substitute silently
    missing = sorted({t["instrument"] for t in s["tracks"].values()
                      if sc.INSTRUMENTS[t["instrument"]] and sc.INSTRUMENTS[t["instrument"]] not in have})
    if missing:
        raise ValueError(f"soundfont {soundfont} has no preset for {missing}; pick another soundfont or instrument")
    jobs = {name: stems / f"{name}.wav" for name in mids}
    def one(n):
        kit = s["tracks"][n]["instrument"]
        if kit == "tabla":
            tabla.render_track(mids[n], jobs[n], s.get("key"), s.get("seed", 1), s["tracks"][n].get("reverb", .15))
        elif kit in sampler.KITS:
            sampler.render_track(mids[n], jobs[n], kit, lambda m, w: _fluidsynth(sf2, m, w))
        else:
            _fluidsynth(sf2, mids[n], jobs[n])
    with ThreadPoolExecutor(max_workers=min(4, len(jobs))) as ex:
        list(ex.map(one, jobs))
    return jobs


def _limit(x, ceiling=0.89, block=256, release_s=0.08):
    """Peak limiter, no waveshaping: gain per 256-sample block = ceiling / block peak, held over
    the blocks either side (look-ahead), released over 80 ms, interpolated per sample. Each sample's
    gain is at most its own block's, so no peak passes the ceiling (-1 dBFS)."""
    n, ch = x.shape
    nb = -(-n // block)
    pad = np.zeros((nb * block, ch)); pad[:n] = x
    g = np.minimum(1.0, ceiling / np.maximum(np.abs(pad).reshape(nb, block * ch).max(axis=1), 1e-12))
    g = np.minimum(g, np.minimum(np.r_[g[1:], 1.0], np.r_[1.0, g[:-1]]))
    step = block / (release_s * SR)
    for i in range(1, nb):
        g[i] = min(g[i], g[i - 1] + step)
    edges = np.minimum(np.r_[g[0], g], np.r_[g, g[-1]])
    gs = np.interp(np.arange(nb * block), np.arange(nb + 1) * block, edges)[:n]
    return x * gs[:, None]


# Starting balance by role, in LUFS per stem, before level_db. Without it, swapping a
# harmonica for a whistle moved the lead 11 dB (sample banks are not level-matched).
ROLE_LUFS = {"lead": -20.0, "bass": -23.0, "comp": -24.0, "drums": -25.0, "tabla": -21.0}


def drive(x, amount):
    """Grit: tanh saturation (amount 0..1), then a gentle 8 kHz one-pole low-pass so the
    added odd harmonics read as warm dirt rather than fizz. The saturation point moves from the
    stem's peak (amount 0) down towards three times its sounding RMS (amount 1), so the body of a
    plucked or sustained note distorts too, not only its attack. Loudness is restored by the role
    balance in mix(), so drive changes colour, not level."""
    if amount <= 0:
        return x
    peak = np.max(np.abs(x)) + 1e-12
    sounding = np.abs(x)[np.abs(x) > peak * 0.003]
    body = 3 * np.sqrt(np.mean(sounding ** 2)) if sounding.size else peak
    ref = peak / (1 + (max(peak / body, 1) - 1) * amount)
    k = 1 + 4 * amount
    y = np.tanh(k * x / ref) / np.tanh(k * peak / ref) * peak
    a = np.exp(-2 * np.pi * 8000 / SR)
    return lfilter([1 - a], [1, -a], y, axis=0)


def mix(stem_paths, out_base, levels_db=None, pans=None, target_lufs=-16.0, mp3=True, roles=None, drives=None):
    """Sum stems with per-track level (dB) and pan (-1 left .. +1 right), normalise loudness,
    limit peaks to -1 dBFS, write <out_base>.wav and .mp3. Returns a report dict.
    roles {track: part}: first bring each stem to ROLE_LUFS[part], so level_db is relative to a sane start."""
    levels_db, pans, roles, drives = levels_db or {}, pans or {}, roles or {}, drives or {}
    meter = pyloudnorm.Meter(SR)
    loaded = {}
    for name, p in stem_paths.items():
        x, sr = sf.read(str(p), always_2d=True)
        if sr != SR:
            raise ValueError(f"{p}: sample rate {sr}, expected {SR}")
        loaded[name] = drive(x if x.shape[1] == 2 else np.repeat(x[:, :1], 2, axis=1), drives.get(name, 0.0))
    n = max(len(x) for x in loaded.values())
    bus = np.zeros((n, 2))
    for name, x in loaded.items():
        db = levels_db.get(name, 0.0)
        if roles.get(name) in ROLE_LUFS:
            own = meter.integrated_loudness(x)
            if np.isfinite(own):
                db += ROLE_LUFS[roles[name]] - own
        g = 10 ** (db / 20)
        p = max(-1.0, min(1.0, pans.get(name, 0.0)))
        theta = (p + 1) * np.pi / 4                       # equal-power pan of the mid;
        mid, side = (x[:, 0] + x[:, 1]) / 2, (x[:, 0] - x[:, 1]) / 2   # the side (reverb width) stays
        bus[:len(x), 0] += g * (mid * np.cos(theta) * np.sqrt(2) + side)
        bus[:len(x), 1] += g * (mid * np.sin(theta) * np.sqrt(2) - side)
    lufs = meter.integrated_loudness(bus)
    if not np.isfinite(lufs):
        raise ValueError("the mix is silent")
    raw = bus * 10 ** ((target_lufs - lufs) / 20)
    bus = _limit(raw)
    got = meter.integrated_loudness(bus)                  # limiting a peaky mix lowers its loudness:
    if np.isfinite(got) and 0.3 < target_lufs - got:      # one corrective push (at most +3 dB), limit again
        bus = _limit(raw * 10 ** (min(3.0, target_lufs - got) / 20))
    out_base = Path(out_base); out_base.parent.mkdir(parents=True, exist_ok=True)
    wav = out_base.with_suffix(".wav")
    sf.write(str(wav), bus, SR, subtype="PCM_16")
    report = {"wav": str(wav), "seconds": round(n / SR, 1),
              "limiter_max_reduction_db": round(max(0.0, float(20 * np.log10(np.max(np.abs(raw)) / 0.89 + 1e-12))), 1),
              "lufs": round(float(meter.integrated_loudness(bus)), 1),
              "peak_dbfs": round(float(20 * np.log10(np.max(np.abs(bus)) + 1e-12)), 1)}
    if mp3:
        m = out_base.with_suffix(".mp3")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "192k", str(m)], check=True)
        report["mp3"] = str(m)
    return report


def render(s, out_dir, name="mix", soundfont="generaluser", mute=(), levels_db=None, pans=None,
           target_lufs=-16.0):
    """Whole job: stems + mix. Track levels/pans default to the score's level_db / pan fields."""
    s = sc.check(s)
    for what, keys in (("mute", mute), ("levels_db", levels_db or {}), ("pans", pans or {})):
        unknown = sorted(set(keys) - set(s["tracks"]))
        if unknown:
            raise ValueError(f"{what} names unknown tracks {unknown}; tracks are {sorted(s['tracks'])}")
    stems = render_stems(s, out_dir, soundfont)
    lv = {k: t.get("level_db", 0.0) for k, t in s["tracks"].items()}
    pn = {k: t.get("pan", 0.0) for k, t in s["tracks"].items()}
    lv.update(levels_db or {}); pn.update(pans or {})
    use = {k: v for k, v in stems.items() if k not in mute}
    roles = {k: t["part"] for k, t in s["tracks"].items()}
    dv = {k: t.get("drive", 0.0) for k, t in s["tracks"].items()}
    rep = mix(use, Path(out_dir) / name, lv, pn, target_lufs, roles=roles, drives=dv)
    rep["stems"] = {k: str(v) for k, v in stems.items()}
    if any(t["part"] == "tabla" for t in s["tracks"].values()):
        bols = Path(out_dir) / "bols.html"
        bols.write_text(tabla.sheet(s, sc.arrangement(s)), "utf-8", newline="\n")
        rep["bols_sheet"] = str(bols)
    rep["soundfont"] = soundfont
    (Path(out_dir) / f"{name}.json").write_text(json.dumps({"levels_db": lv, "pans": pn, "drives": dv, "mute": list(mute), "roles": roles,
                                                            **rep}, indent=2), "utf-8")
    return rep
