"""analyse_beat: find the claps/taps in a WAV and the tempo they imply.

Numpy only, on purpose: librosa is installed on this machine but cannot import
(numba refuses numpy 2.5), and a clap track needs nothing cleverer than spectral
flux plus the median gap between hits.
"""
import numpy as np
import soundfile as sf


def onsets(x, sr, hop=256, frame=1024, sensitivity=1.5, min_gap=0.08):
    """Return onset times (s): peaks of positive spectral flux above an adaptive threshold."""
    if x.ndim > 1:
        x = x.mean(axis=1)
    x = np.concatenate([x[:frame][::-1], x])          # mirror pad: a hit at t=0 still shows as a rise,
                                                      # and room noise does not (zeros -> noise would)
    if len(x) < 2 * frame:
        return np.array([])
    win = np.hanning(frame)
    n = 1 + (len(x) - frame) // hop
    frames = np.lib.stride_tricks.as_strided(x, (n, frame), (x.strides[0] * hop, x.strides[0]))
    mag = np.log1p(100 * np.abs(np.fft.rfft(frames * win, axis=1)))
    flux = np.maximum(np.diff(mag, axis=0), 0).sum(axis=1)
    flux = np.concatenate([[0], flux])
    k = max(1, int(0.5 * sr / hop))                  # half-second local threshold
    pad = np.pad(flux, k, mode="edge")
    local = np.array([np.median(pad[i:i + 2 * k + 1]) for i in range(len(flux))])
    thr = local + sensitivity * flux.std()
    out, last = [], -1e9
    for i in range(1, len(flux) - 1):
        if flux[i] > thr[i] and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1]:
            t = max(0.0, (i * hop - frame / 2) / sr)    # frame centre, in the unpadded signal
            if t - last >= min_gap:
                out.append(t); last = t
    return np.array(out)


def analyse(path, low_bpm=60, high_bpm=200):
    x, sr = sf.read(str(path), always_2d=False)
    t = onsets(np.asarray(x, dtype=np.float64), sr)
    rep = {"seconds": round(len(x) / sr, 2), "onsets": [round(float(v), 3) for v in t], "count": len(t)}
    if len(t) >= 3:
        gaps = np.diff(t)
        beat = float(np.median(gaps))
        bpm = raw = 60 / beat
        while bpm < low_bpm:
            bpm *= 2
        while bpm > high_bpm:
            bpm /= 2
        good = gaps[np.abs(gaps - beat) <= 0.25 * beat]     # a missed or doubled clap is not unsteadiness
        rep.update(tempo_bpm=round(bpm, 1), median_gap_s=round(beat, 3),
                   steadiness_ms=round(1000 * float(np.std(good)), 1),
                   odd_gaps=int(len(gaps) - len(good)))
        if bpm != raw:
            rep["folded_from_bpm"] = round(raw, 1)          # claps were half or double time
    else:
        rep["tempo_bpm"] = None
        rep["why"] = "fewer than 3 hits found; clap louder or closer to the mic"
    return rep
