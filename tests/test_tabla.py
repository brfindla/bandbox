"""Gates for talas, bols and the tabla sampler (tabla.py, tabla.json, the tala parts of score.py).
Run: .venv/Scripts/python tests/test_tabla.py   (needs no samples: the sampler tests make their own)"""
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bandbox import score as sc, styles, tabla  # noqa: E402

TEENTAAL = tabla.TALAS["teentaal"]["theka"]


def _raises(fn, *words):
    try:
        fn()
    except ValueError as e:
        assert all(w in str(e) for w in words), e
        return
    raise AssertionError("should have been refused")


def test_four_talas_and_their_thekas():
    for name, beats, vibhag in (("teentaal", 16, [4, 4, 4, 4]), ("keherwa", 8, [4, 4]),
                                ("dadra", 6, [3, 3]), ("rupak", 7, [3, 2, 2])):
        t = tabla.TALAS[name]
        assert t["beats"] == beats and t["vibhag"] == vibhag and sum(vibhag) == beats
        assert tabla.parse(t["theka"], name)[0] == beats
    assert tabla.TALAS["rupak"]["marks"][0] == "0", "rupak starts on khali"


def test_bols_map_to_bayan_and_dayan():
    _, ev = tabla.parse(TEENTAAL, "teentaal")
    at = {b: s for b, s, _ in ev}
    assert at[0] == ["ge", "na"] and at[1] == ["ge", "tin"]           # dha, dhin
    assert at[8] == ["ge", "na"] and all("ge" not in at[b] for b in range(9, 12)), "khali: the bayan drops out after dha"
    assert at[12] == ["na"] and at[15] == ["ge", "na"]


def test_beats_split_evenly_and_compounds_share_their_beat():
    beats, ev = tabla.parse("dha.ge tirakita - dhin")
    assert beats == 4
    assert [(b, s) for b, s, _ in ev] == [(0, ["ge", "na"]), (0.5, ["ge"]), (1, ["te"]), (1.25, ["re"]),
                                          (1.5, ["ke"]), (1.75, ["na"]), (3, ["ge", "tin"])]
    assert tabla.parse("dha.- dha")[1][0][0] == 0 and len(tabla.parse("dha.- dha")[1]) == 2


def test_wrong_bols_and_misplaced_vibhag_are_refused_plainly():
    _raises(lambda: tabla.parse("dha dhom"), "dhom", "dhin")
    _raises(lambda: tabla.parse("dha dhin dhin | dha", "teentaal"), "beat 3", "4+4+4+4")
    _raises(lambda: tabla.parse("dha..ge"), "empty")
    tabla.parse("tin tin na | dhi na | dhi na", "rupak")
    _raises(lambda: tabla.parse("tin tin | na dhi na | dhi na", "rupak"), "3+2+2")


def test_accents_follow_sam_tali_khali():
    t = tabla.TALAS["teentaal"]
    sam, tali, khali, plain, off = (tabla.accent(0, True, t), tabla.accent(4, True, t),
                                    tabla.accent(8, True, t), tabla.accent(5, True, t), tabla.accent(-1, False, t))
    assert sam > tali > plain > khali > off


def _score(**kw):
    s = {"tempo": 112, "tala": "teentaal", "count_in_bars": 0,
         "tracks": {"tabla": {"instrument": "tabla", "part": "tabla"},
                    "drone": {"instrument": "sitar", "part": "comp", "style": "drone"}},
         "sections": [{"name": "a", "chords": ["C#", "%"]}]}
    s.update(kw)
    return s


def test_tala_scores_check_and_four_four_still_rules_without_one():
    s = sc.check(_score())
    assert s["beats_per_bar"] == 16 and sc.song_beats(s) == 32
    _raises(lambda: sc.check(_score(beats_per_bar=4)), "16 beats")
    _raises(lambda: sc.check(_score(tala="jhaptal")), "jhaptal")
    _raises(lambda: sc.check(_score(tala=None, beats_per_bar=16)), "2, 3 or 4")
    _raises(lambda: sc.check(_score(tala=None, beats_per_bar=4)), "needs a tala")
    bad = _score(); bad["tracks"]["drone"]["instrument"] = "tabla"
    _raises(lambda: sc.check(bad), "tabla part")
    bad = _score(); bad["sections"][0]["bols"] = {"tabla": "dha dhin dhin"}
    _raises(lambda: sc.check(bad), "3 beats", "divide")
    bad = _score(); bad["sections"][0]["bols"] = {"drone": "dha"}
    _raises(lambda: sc.check(bad), "not a tabla track")
    # tabla in an ordinary 4/4 song: keherwa's 8 beats over two bars
    ok = _score(tala=None, beats_per_bar=4)
    ok["sections"] = [{"name": "a", "chords": ["E", "%"], "bols": {"tabla": "dha ge na ti | na ka dhi na"}}]
    sc.check(ok)


def test_tabla_notes_repeat_the_theka_and_land_on_the_beat():
    s = sc.check(_score())
    with tempfile.TemporaryDirectory() as d:
        import mido
        m = mido.MidiFile(sc.to_midi(s, d)["tabla"])
        t, ons = 0.0, []
        for x in m:
            t += x.time
            if x.type == "note_on" and x.velocity:
                ons.append((t * 112 / 60, tabla.NOTE_STROKE[x.note], x.velocity))
    assert len(ons) == 2 * 28                                    # 28 strokes per teentaal cycle
    assert all(abs(b - round(b)) < .02 for b, _, _ in ons)       # theka bols on whole beats
    sams = [v for b, s_, v in ons if round(b) % 16 == 0]
    assert min(sams) > max(v for b, _, v in ons if round(b) % 16 in (4, 8, 12)), "sam louder than tali and khali"
    ok = _score(tala=None, beats_per_bar=4)                      # no tala: the bols' own length is the cycle
    ok["sections"] = [{"name": "a", "chords": ["E", "%"], "bols": {"tabla": "dha ge na ti | na ka dhi na"}}]
    with tempfile.TemporaryDirectory() as d:
        import mido
        m = mido.MidiFile(sc.to_midi(sc.check(ok), d)["tabla"])
        t, vel = 0, {}
        for x in m.tracks[0]:
            t += x.time
            if x.type == "note_on" and x.velocity:
                vel.setdefault(round(t / 480), []).append(x.velocity)
    assert min(vel[0]) > max(vel[4]), "beat 1 of a 4/4 bar is not sam when the bols run two bars"


def test_every_tala_recipe_arranges():
    for n in ("teentaal", "keherwa", "dadra", "rupak"):
        s = styles.arrange(n, "C#")
        assert s["tala"] == n and s["beats_per_bar"] == tabla.TALAS[n]["beats"] and s["count_in_bars"] == 0
        assert styles.list_styles()[n]["theka"] == tabla.TALAS[n]["theka"]


def test_the_demo_tihai_lands_on_sam():
    """Three equal phrases, equal gaps; the third phrase's last bol is beat 1 of the next cycle."""
    s = sc.load(Path(__file__).resolve().parent.parent / "songs" / "teentaal_tihai.json")
    by = {x["name"]: x for x in s["sections"]}
    toks = by["tihai"]["bols"]["tabla"].replace("|", " ").split()
    starts = [i for i, x in enumerate(toks) if x == "tirakita"]
    phrase = toks[starts[0]:starts[0] + 4]
    assert len(starts) == 3 and starts[1] - starts[0] == starts[2] - starts[1] == 5
    assert toks[starts[1]:starts[1] + 4] == phrase and toks[starts[2]:] == phrase[:3]
    assert starts[2] + 3 == 16 and phrase[3] == by["sam"]["bols"]["tabla"].split()[0] == "dha"
    with tempfile.TemporaryDirectory() as d:                     # and in the MIDI: the last dha on sam
        import mido
        m = mido.MidiFile(sc.to_midi(s, d)["tabla"])
        t, ons = 0, []
        for x in m.tracks[0]:
            t += x.time
            if x.type == "note_on" and x.velocity:
                ons.append((t, x.note))
    last = [n for tk, n in ons if tk == ons[-1][0]]
    by_tick = {}
    for tk, n in ons:
        by_tick.setdefault(tk, set()).add(n)
    lone_ge = [tk for tk, ns in by_tick.items() if 36 in ns and not ns & {60, 61, 62, 63, 64}
               and any(abs(tk - o) <= 8 and by_tick[o] & {60, 61} for o in by_tick if o != tk)]
    assert not lone_ge, f"dha/dhin strokes flam apart at ticks {lone_ge[:3]}: both hands strike together"
    assert abs(ons[-1][0] - 80 * 480) <= 4 and sorted(last) == [36, 60], (ons[-3:], 80 * 480)   # ge+na together


def _decay(f, secs=1.0, tau=.25):
    t = np.arange(int(secs * tabla.SR)) / tabla.SR
    return (np.sin(2 * np.pi * f * t) * np.exp(-t / tau)).astype(np.float32)


def test_sampler_damps_tunes_and_varies_takes():
    import mido
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "tabla"
        freqs = {"ge": 90, "ke": 120, "na": 300, "tin": 300, "tun": 300, "te": 500, "re": 520}   # dayan's note 300 Hz
        for st, f in freqs.items():
            (root / st).mkdir(parents=True)
            for k in range(2):                                  # two takes: slightly different
                ring = _decay(f * (1 + .02 * k), secs=3, tau=2 if st == "ge" else .25)   # ge rings on
                sf.write(str(root / st / f"drum_{k}.wav"), ring * (1 - .2 * k), tabla.SR)
        old = tabla.SAMPLE_ROOT
        tabla.SAMPLE_ROOT = root
        try:
            mid = mido.MidiFile(type=0, ticks_per_beat=480)
            tr = mido.MidiTrack(); mid.tracks.append(tr)
            tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(60)))
            for k, note in enumerate([36, 37] + [60] * 6):      # ge, ke 1 s later, then six na
                tr.append(mido.Message("note_on", note=note, velocity=100, time=0 if k == 0 else 470))
                tr.append(mido.Message("note_off", note=note, velocity=0, time=10))
            mp = Path(d) / "t.mid"; mid.save(mp)
            wav = Path(d) / "t.wav"
            tabla.render_track(mp, wav, key=None, reverb=0)   # dry: the room would hold the ge
            y, sr = sf.read(str(wav)); y = y.mean(axis=1)
            def band(seg, f):
                sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
                fr = np.fft.rfftfreq(len(seg), 1 / sr)
                return sp[(fr > f - 5) & (fr < f + 5)].max()
            after_ke = y[int(1.05 * sr):int(1.5 * sr)]
            assert band(after_ke, 90) < 0.05 * band(after_ke, 120), "ke must damp the ringing ge"
            hits = [y[int((2 + k) * sr):int((2 + k) * sr) + 4000] for k in range(1, 6)]   # each after a na
            assert all(np.abs(h1 - h2).max() > .05 for h1, h2 in zip(hits, hits[1:])), "never the same take twice running"
            tabla.render_track(mp, wav, key="D", reverb=0)      # dayan re-tuned from ~300 Hz to D (293.7)
            y2, _ = sf.read(str(wav)); y2 = y2.mean(axis=1)
            assert abs(tabla.pitch_hz(y2[int(2 * sr):int(2.9 * sr)]) - 293.7) < 6
        finally:
            tabla.SAMPLE_ROOT = old


def test_review_fixes_overrides_bad_input_rupak_and_the_sheet():
    bad = _score(tala=None, beats_per_bar=4)
    bad["tracks"]["tabla"]["style"] = "none"
    bad["sections"][0]["bols"] = {"tabla": "dha dhin dhin dha"}
    bad["sections"].append({"name": "b", "chords": ["E"], "styles": {"tabla": "theka"}})
    _raises(lambda: sc.check(bad), "section b", "needs a tala")
    _raises(lambda: sc.check(_score(tala=["teentaal"])), "unknown")
    bad = _score(); bad["sections"][0]["bols"] = "dha"
    _raises(lambda: sc.check(bad), "bols is an object")
    s = _score(); s["sections"].append({"name": "quiet", "chords": ["C#"], "styles": {"tabla": "none"}})
    s = sc.check(s)
    html = tabla.sheet(s, sc.arrangement(s))
    assert "<h2>a</h2>" in html and "<h2>quiet</h2>" not in html, "the sheet plays what the MIDI plays"
    r, t = tabla.TALAS["rupak"], tabla.TALAS["teentaal"]
    assert tabla.accent(0, True, r) < tabla.accent(3, True, r) < tabla.accent(0, True, t), "rupak's sam is khali"


def test_each_source_drum_is_tuned_on_its_own_and_reverb_is_heard():
    import mido
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "tabla"
        for st in tabla.STROKES:
            (root / st).mkdir(parents=True)
            for src, f in (("a", 300.0), ("b", 330.0)):       # two drums, tuned a semitone and a half apart
                ff = {"ge": 90, "ke": 120, "te": 500, "re": 520}.get(st, f)
                sf.write(str(root / st / f"{src}_1.wav"), _decay(ff), tabla.SR)
        old = tabla.SAMPLE_ROOT
        tabla.SAMPLE_ROOT = root
        try:
            mid = mido.MidiFile(type=0, ticks_per_beat=480)
            tr = mido.MidiTrack(); mid.tracks.append(tr)
            tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(60)))
            for k in range(6):
                tr.append(mido.Message("note_on", note=60, velocity=100, time=0 if k == 0 else 470))
                tr.append(mido.Message("note_off", note=60, velocity=0, time=10))
            mp = Path(d) / "t.mid"; mid.save(mp)
            wav = Path(d) / "t.wav"
            tabla.render_track(mp, wav, key="Dm", reverb=0)    # a minor key tunes to its tonic
            y, sr = sf.read(str(wav)); y = y.mean(axis=1)
            got = [tabla.pitch_hz(y[int(k * sr):int(k * sr + .9 * sr)]) for k in range(6)]
            assert all(abs(g - 293.7) < 5 for g in got), got
            tail = lambda yy: np.sqrt(np.mean(yy[int(6.6 * sr):int(7.5 * sr)] ** 2))   # after the last dry take ends
            tabla.render_track(mp, wav, key="D", reverb=.6)
            y2, _ = sf.read(str(wav)); y2 = y2.mean(axis=1)
            assert tail(y) < 1e-7 and tail(y2) > 1e-5, "reverb must reach the tabla"
        finally:
            tabla.SAMPLE_ROOT = old


def test_open_strokes_ring_on_closed_strokes_damp_and_one_take_still_varies():
    import mido
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "tabla"
        for st in tabla.STROKES:
            (root / st).mkdir(parents=True)
            f = {"ge": 90, "ke": 120, "te": 500, "re": 520, "tun": 300, "na": 600}.get(st, 300)
            if st != "tin":
                sf.write(str(root / st / f"a_1.wav"), _decay(f, tau=1 if st == "tun" else .25), tabla.SR)
        sf.write(str(root / "tin" / "c_1.wav"), _decay(350), tabla.SR)      # one take, from another drum,
        (root / "_tune").mkdir()                                            # whose note is measured from _tune
        sf.write(str(root / "_tune" / "c_1.wav"), _decay(350), tabla.SR)
        old = tabla.SAMPLE_ROOT
        tabla.SAMPLE_ROOT = root
        try:
            def run(notes):                                    # [(seconds, note)] -> mono render
                mid = mido.MidiFile(type=0, ticks_per_beat=480)
                tr = mido.MidiTrack(); mid.tracks.append(tr)
                tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(60)))
                now = 0
                for sec, n in notes:
                    tk = round(sec * 480)
                    tr.append(mido.Message("note_on", note=n, velocity=100, time=tk - now))
                    tr.append(mido.Message("note_off", note=n, velocity=0, time=5)); now = tk + 5
                mp = Path(d) / "t.mid"; mid.save(mp)
                tabla.render_track(mp, Path(d) / "t.wav", key="D", reverb=0)
                y, sr = sf.read(str(Path(d) / "t.wav")); return y.mean(axis=1), sr
            def band(seg, f, sr):
                sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
                fr = np.fft.rfftfreq(len(seg), 1 / sr)
                return sp[(fr > f - 8) & (fr < f + 8)].max()
            y_open, sr = run([(0, 62), (.3, 60)])               # tun, then na: tun rings on
            y_shut, _ = run([(0, 62), (.3, 63)])                # tun, then te: te damps it
            w = slice(int(.6 * sr), int(1.2 * sr))
            assert band(y_open[w], 293.7, sr) > 10 * band(y_shut[w], 293.7, sr)
            y, sr = run([(0, 36), (1, 37)])                     # ge then ke: ke sits at its gain, 0.6
            ratio = np.abs(y[int(1 * sr):int(1.2 * sr)]).max() / np.abs(y[:int(.2 * sr)]).max()
            assert abs(ratio - tabla.STROKES["ke"]["gain"] / tabla.STROKES["ge"]["gain"]) < .08, ratio
            y, sr = run([(k, 61) for k in range(5)])            # five tins from the single take
            hits = [y[int(k * sr):int(k * sr) + 8000] for k in range(5)]
            assert all(np.abs(h1 - h2).max() > .02 for h1, h2 in zip(hits, hits[1:])), "one take must still vary"
            assert all(abs(tabla.pitch_hz(h) - 293.7) < 6 for h in hits), "_tune measures that drum's note"
        finally:
            tabla.SAMPLE_ROOT = old


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); print("PASS", k)
