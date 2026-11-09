"""hum_to_notes: a hummed or sung melody (WAV) -> notes the band can play.

YIN pitch tracking in numpy (de Cheveigne & Kawahara, 2002), then notes are cut at
pitch changes and at loudness dips (so two hums on the same pitch stay two notes),
then quantised to a beat grid and written as score lead notes [["E4", 1], ["r", 0.5], ...].
Monophonic only: one voice at a time, which is what humming is.

Why not basic-pitch (Spotify, Apache-2.0): it brings a neural-network runtime (TensorFlow
or ONNX) for a job that one voice does not need; this needs nothing beyond numpy.
"""
import numpy as np
import soundfile as sf

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_name(m):
    return f"{NAMES[m % 12]}{m // 12 - 1}"


def yin(x, sr, fmin=70.0, fmax=1000.0, hop=256, win=1024, threshold=0.15):
    """Return (times, f0 Hz or nan, aperiodicity) per frame."""
    tmin, tmax = int(sr / fmax), int(sr / fmin)
    span = win + tmax
    n_fr = max(0, 1 + (len(x) - span) // hop)
    if n_fr == 0:
        return np.array([]), np.array([]), np.array([])
    fr = np.lib.stride_tricks.as_strided(x, (n_fr, span), (x.strides[0] * hop, x.strides[0]))
    nfft = 1 << int(np.ceil(np.log2(span + win)))
    r = np.fft.irfft(np.conj(np.fft.rfft(fr[:, :win], nfft)) * np.fft.rfft(fr, nfft), nfft)[:, :tmax + 1]
    cs = np.concatenate([np.zeros((n_fr, 1)), np.cumsum(fr ** 2, axis=1)], axis=1)
    lag = np.arange(tmax + 1)
    e_tau = cs[:, lag + win] - cs[:, lag]                      # energy of x[tau:tau+win]
    d = cs[:, [win]] + e_tau - 2 * r                           # difference function
    cm = np.ones_like(d)
    cm[:, 1:] = d[:, 1:] * lag[1:] / np.maximum(np.cumsum(d[:, 1:], axis=1), 1e-12)
    f0 = np.full(n_fr, np.nan); ap = np.ones(n_fr)
    for i in range(n_fr):
        c = cm[i]
        below = np.nonzero(c[tmin:tmax] < threshold)[0]
        t = tmin + below[0] if len(below) else tmin + int(np.argmin(c[tmin:tmax]))
        while t + 1 < tmax and c[t + 1] < c[t]:
            t += 1
        ap[i] = c[t]
        if 0 < t < tmax:                                       # parabolic interpolation
            a, b, g = c[t - 1], c[t], c[t + 1]
            den = a - 2 * b + g
            t = t + (0.5 * (a - g) / den if den else 0)
        f0[i] = sr / t
    times = (np.arange(n_fr) * hop + win / 2) / sr
    return times, f0, ap


def transcribe(path, tempo=120.0, grid=0.25, min_note=0.07, voicing=0.25, quiet_db=-40, dip_db=4.0):
    """WAV -> {'lead': [[name, beats], ...], 'notes': [[name, start_s, dur_s], ...]}."""
    x, sr = sf.read(str(path), always_2d=True)
    x = x.mean(axis=1).astype(np.float64)
    if not len(x):
        return {"lead": [], "notes": [], "why": "the file is empty"}
    times, f0, ap = yin(x, sr)
    hop_s = times[1] - times[0] if len(times) > 1 else 0.01
    # loudness gate: frames far below the loudest part are silence
    rms = np.array([np.sqrt(np.mean(x[max(0, int((t - .012) * sr)):int((t + .012) * sr) + 1] ** 2) + 1e-12)
                    for t in times])
    loud = 20 * np.log10(rms / (rms.max() + 1e-12)) > quiet_db
    voiced = loud & (ap < voicing) & np.isfinite(f0)
    midi = np.where(voiced, 69 + 12 * np.log2(np.where(voiced, f0, 440) / 440), np.nan)
    # 5-frame median smooth, then round to the nearest semitone
    pad = np.pad(midi, 2, mode="edge")
    sm = np.array([np.nanmedian(pad[i:i + 5]) if np.isfinite(pad[i:i + 5]).sum() >= 3 else np.nan
                   for i in range(len(midi))])
    q = np.where(np.isfinite(sm), np.round(sm), -1).astype(int)
    # cut into notes: a change must hold ~45 ms to count, so wobble and scoops do not split notes
    hold = max(1, int(0.045 / hop_s))
    notes, cur, start, i = [], -1, 0, 0
    while i < len(q):
        if q[i] != cur and np.all(q[i:i + hold] == q[i]):
            if cur >= 0:
                notes.append([cur, times[start], times[i]])
            cur, start = q[i], i
        i += 1
    if cur >= 0:
        notes.append([cur, times[start], times[-1]])
    # two hums on one pitch: split where loudness dips >= dip_db below both sides
    env = 20 * np.log10(rms + 1e-12)
    k = max(1, int(0.06 / hop_s))
    split = []
    for m, a, b in notes:
        i0, i1 = np.searchsorted(times, [a, b])
        cuts = [a]
        for i in range(i0 + k, i1 - k):
            seg = env[i - k:i + k + 1]
            if env[i] == seg.min() and env[i - k:i].max() - env[i] >= dip_db and env[i + 1:i + k + 1].max() - env[i] >= dip_db:
                if times[i] - cuts[-1] >= min_note:
                    cuts.append(times[i])
        cuts.append(b)
        split += [[m, cuts[j], cuts[j + 1]] for j in range(len(cuts) - 1)]
    notes = [[m, a, b - a] for m, a, b in split if m >= 0 and b - a >= min_note]
    # quantise to the beat grid; each note runs to the next one unless the gap is a real rest
    bps = tempo / 60.0
    lead, t_beats = [], None
    for k, (m, a, dur) in enumerate(notes):
        st = round(a * bps / grid) * grid
        if t_beats is None:
            t_beats = st
        elif st > t_beats:
            lead.append(["r", st - t_beats]); t_beats = st
        own = max(grid, round(dur * bps / grid) * grid)
        nxt = round(notes[k + 1][1] * bps / grid) * grid if k + 1 < len(notes) else None
        ln = own if nxt is None or nxt - st - own >= 0.5 else max(grid, nxt - st)
        if lead and lead[-1][0] != "r" and st < t_beats:      # overlap after rounding: shorten
            continue
        lead.append([note_name(m), ln]); t_beats = st + ln
    return {"tempo": tempo, "grid_beats": grid, "lead": lead,
            "notes": [[note_name(m), round(a, 3), round(d, 3)] for m, a, d in notes]}
