"""Gates for the arranger and checker. Each test is a defect a reviewer found on 2026-11-08,
written so it fails on the old code. Run: .venv/Scripts/python -m pytest tests -q
(or .venv/Scripts/python tests/test_score.py)."""
import copy
import json
import sys
import tempfile
from pathlib import Path

import mido
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bandbox import beat, hum, render, sampler, score as sc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE = json.loads((ROOT / "songs" / "lights_out_v3.json").read_text("utf-8"))


def _bad(mutate):
    s = copy.deepcopy(BASE)
    mutate(s)
    try:
        sc.check(s)
    except sc.ScoreError:
        return True
    return False


def test_check_refuses_what_render_cannot_play():
    cases = {
        "count_in 1.5": lambda s: s.update(count_in_bars=1.5),
        "repeat x": lambda s: s["sections"][0].update(repeat="x"),
        "note 130": lambda s: s["sections"][1]["lead"]["harmonica"].__setitem__(0, [130, 1]),
        "velocity loud": lambda s: s["sections"][1]["lead"]["harmonica"].__setitem__(0, ["C4", 1, "loud"]),
        "null track": lambda s: s["tracks"].update(x=None),
        "swing x": lambda s: s.update(swing="x"),
        "waltz in 4/4": lambda s: s["tracks"]["drums"].update(style="waltz"),
        "% mixed in a bar": lambda s: s["sections"][0]["chords"].__setitem__(1, "A %"),
        "duplicate section": lambda s: s["sections"].append(copy.deepcopy(s["sections"][0])),
    }
    missed = [k for k, f in cases.items() if not _bad(f)]
    assert not missed, f"accepted bad scores: {missed}"
    sc.check(copy.deepcopy(BASE))                          # and the good one still passes


def _notes(mid_path):
    """[(start_tick, pitch)] and the count of note_ons that hit an already-sounding pitch."""
    on, clashes, t, starts = set(), 0, 0, []
    for m in mido.MidiFile(mid_path).tracks[0]:
        t += m.time
        if m.type == "note_on" and m.velocity > 0:
            clashes += m.note in on
            on.add(m.note); starts.append((t, m.note))
        elif m.type in ("note_off", "note_on"):
            on.discard(m.note)
    return starts, clashes


def test_no_same_pitch_overlap():
    with tempfile.TemporaryDirectory() as d:
        paths = sc.to_midi(copy.deepcopy(BASE), d)
        for name, p in paths.items():
            assert _notes(p)[1] == 0, f"{name}: a note started on a pitch still sounding"


def _bass_pitches(chords, style, bpb=4):
    return [ns[0] for _, _, ns, _ in sc.bass_bar(style, chords, None, bpb)]


def test_walking_bass_slash_chord_mid_bar():
    got = _bass_pitches(["C", "D/F#"], "walking")
    # C bar half: C, E ; D/F# half: F# (the slash bass), then D's third F#
    assert got[2] % 12 == 6, got                          # F#
    assert got[3] % 12 in (2, 6, 9), got                  # a D-chord tone, not A# or C#


def test_root_fifth_change_in_three_four():
    got = _bass_pitches(["A", "E"], "root_fifth", bpb=3)
    assert got[1] % 12 == 4, got                          # beat 3 plays E (the new root), not B


def test_hard_pan_keeps_stem_and_moves_it():
    with tempfile.TemporaryDirectory() as d:
        x = 0.1 * np.sin(2 * np.pi * 220 * np.arange(44100) / 44100)
        sf.write(f"{d}/s.wav", np.stack([x, x], 1), 44100)
        rep = render.mix({"s": f"{d}/s.wav"}, Path(d) / "m", pans={"s": -1}, mp3=False, target_lufs=-20)
        y, _ = sf.read(rep["wav"])
        assert np.abs(y[:, 1]).max() < 1e-3 < np.abs(y[:, 0]).max()


def test_drive_adds_grit_and_zero_is_clean():
    sr = 44100
    x = 0.5 * np.sin(2 * np.pi * 220 * np.arange(sr) / sr)[:, None].repeat(2, 1)
    def h3(y):                                        # 3rd harmonic level relative to the fundamental, dB
        sp = np.abs(np.fft.rfft(y[:, 0] * np.hanning(sr)))
        return 20 * np.log10(sp[660] / sp[220])
    assert np.array_equal(render.drive(x, 0), x)
    assert h3(render.drive(x, 0.5)) > -30 > h3(x)
    # A real stem: one loud attack, then a long quiet note. Drive must dirty the note, not just the attack.
    y = 0.05 * np.sin(2 * np.pi * 220 * np.arange(sr) / sr)[:, None].repeat(2, 1)
    y[100:110] = 0.9
    tail = np.concatenate([np.zeros((sr // 2, 2)), render.drive(y, 0.85)[sr // 2:]])
    assert h3(tail) > -26, "grit must reach the body of a quiet note, not only its peak"


def test_hum_to_notes_on_a_sung_line():
    """A voice-like tone (harmonics, vibrato, breath between notes, 3 % timing wobble) singing the
    v3 chorus must come back note for note."""
    want = BASE["sections"][1]["lead"]["harmonica"]
    sr, rng, y = 44100, np.random.default_rng(5), []
    for n, d in want:
        m = sc.note_number(n); L = int(d * 60 / 160 * sr * (1 + rng.normal(0, .03))); tt = np.arange(L) / sr
        f = 440 * 2 ** ((m - 69) / 12) * (1 + .008 * np.sin(2 * np.pi * 5.5 * tt))
        ph = 2 * np.pi * np.cumsum(f) / sr
        env = np.minimum(1, tt / .03) * np.minimum(1, (L / sr - tt) / .05)
        y.append(env * (np.sin(ph) + .5 * np.sin(2 * ph) + .25 * np.sin(3 * ph)) * .3)
    y = np.concatenate([np.zeros(sr // 2)] + y + [np.zeros(sr // 2)]) + .003 * rng.standard_normal(sr + sum(map(len, y)))
    with tempfile.TemporaryDirectory() as d:
        sf.write(f"{d}/hum.wav", y, sr)
        got = [n for n in hum.transcribe(f"{d}/hum.wav", 160)["lead"] if n[0] != "r"]
    assert [n[0] for n in got] == [n for n, _ in want]
    assert sum(abs(a[1] - b[1]) < 1e-6 for a, b in zip(got, want)) >= 38


def test_swing_moves_lead_and_drums_together():
    s = copy.deepcopy(BASE)
    s.update(swing=0.6, form=["chorus"])
    s["tracks"]["drums"]["style"] = "shuffle"
    with tempfile.TemporaryDirectory() as d:
        paths = sc.to_midi(s, d)
        tpb = sc.PPQ
        ride = {round(t / tpb, 2) for t, n in _notes(paths["drums"])[0] if n == sc.RIDE}
        lead_off = [t / tpb for t, _ in _notes(paths["harmonica"])[0] if abs((t / tpb) % 1 - 0.5) > 0.05 and (t / tpb) % 1 > 0.3]
        assert lead_off, "no swung lead off-beats found"
        for t in lead_off:                                 # every lead off-beat sits on a ride off-beat
            assert min(abs(t - r) for r in ride) < 0.03, (t, sorted(ride)[:6])


def test_limiter_holds_ceiling_without_touching_quiet_audio():
    x = 0.3 * np.sin(2 * np.pi * 110 * np.arange(44100) / 44100)[:, None].repeat(2, 1)
    assert np.allclose(render._limit(x), x)
    loud = x.copy(); loud[20000:20050] *= 7               # a 2.1 peak
    y = render._limit(loud)
    assert np.abs(y).max() <= 0.89 + 1e-9 and np.allclose(y[:15000], x[:15000])


def test_no_phantom_onset_on_room_noise():
    sr, rng = 44100, np.random.default_rng(1)
    x = 0.002 * rng.standard_normal(sr * 10)
    for k in range(19):
        i = int((0.5 + k * 0.5) * sr); x[i:i + 800] += 0.6 * rng.standard_normal(800) * np.exp(-np.arange(800) / 150)
    with tempfile.TemporaryDirectory() as d:
        sf.write(f"{d}/c.wav", x, sr)
        r = beat.analyse(f"{d}/c.wav")
    assert r["count"] == 19 and abs(r["tempo_bpm"] - 120) < 2, r


def test_sampled_kit_plays_in_time_with_round_robins_and_audible_cymbals():
    s = copy.deepcopy(BASE)
    s.update(form=["chorus"])
    s["tracks"]["drums"].update(instrument="gogodze_kit", style="shuffle")
    with tempfile.TemporaryDirectory() as d:
        mid = sc.to_midi(s, d)["drums"]
        full, kit_only = Path(d) / "full.wav", Path(d) / "kit.wav"
        sampler.render_track(mid, full, "gogodze_kit", lambda m, w: render._fluidsynth(render.soundfont_path("generaluser"), m, w))
        sampler.render_track(mid, kit_only, "gogodze_kit", lambda m, w: sf.write(str(w), np.zeros((10, 2)), 44100))
        assert abs(beat.analyse(full)["tempo_bpm"] - 160) < 4
        y, _ = sf.read(str(kit_only)); z, _ = sf.read(str(full))
    n = min(len(y), len(z))
    db = lambda v: 20 * np.log10(np.sqrt(np.mean(v ** 2)) + 1e-12)
    gap = db(y[:n]) - db(z[:n] - y[:n])               # kit level minus GM cymbal level
    assert 5 < gap < 16, f"cymbals {gap:.1f} dB under the kit"
    k = sampler.Kit("gogodze_kit")
    hits = [k.hit(38, 100).tobytes() for _ in range(5)]
    assert len(set(hits[:4])) == 4 and hits[0] == hits[4]


def test_sampled_kit_is_stereo_and_a_ride_only_part_is_not_silent():
    k = sampler.Kit("gogodze_kit")
    x = k.hit(38, 100)
    assert x.shape[1] == 2 and not np.allclose(x[:, 0], x[:, 1]), "overhead/side mics must pan, not dual-mono"
    with tempfile.TemporaryDirectory() as d:
        mid = mido.MidiFile(type=0); t = mido.MidiTrack(); mid.tracks.append(t)
        t += [mido.Message("note_on", channel=9, note=sc.RIDE, velocity=90, time=0),
              mido.Message("note_off", channel=9, note=sc.RIDE, velocity=0, time=480)]
        mid.save(f"{d}/ride.mid")
        sampler.render_track(f"{d}/ride.mid", f"{d}/ride.wav", "gogodze_kit",
                             lambda m, w: render._fluidsynth(render.soundfont_path("generaluser"), m, w))
        y, _ = sf.read(f"{d}/ride.wav")
    assert np.abs(y).max() > 0.01, "ride-only drums came out silent"


def test_retro_mic_has_the_kits_low_cut():
    x = sampler.Kit("gogodze_retro_kit").hit(36, 100)[:, 0]
    spec = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), 1 / 44100)
    low = 10 * np.log10(spec[f < 80].sum() / spec.sum())
    assert low < -18, f"retro kick has {low:.1f} dB of its energy under 80 Hz; Kit.sfz cuts it at 150 Hz"


def test_missing_kit_is_a_clear_error():
    old = sampler.KIT_ROOT
    sampler.KIT_ROOT = Path(tempfile.gettempdir()) / "no_such_kits_here"
    try:
        sampler.render_track("x.mid", "x.wav", "gogodze_kit", None)
        raise AssertionError("no error")
    except FileNotFoundError as e:
        assert "fetch_vendor" in str(e)
    finally:
        sampler.KIT_ROOT = old


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); print("PASS", k)
