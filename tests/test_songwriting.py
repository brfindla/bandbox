"""Gates for the brief-to-track and lyrics-to-tunes features (styles.py, lyrics.py).
Run: .venv/Scripts/python tests/test_songwriting.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bandbox import lyrics as ly, score as sc, styles  # noqa: E402

CHORUS = ["Lights out, and it's runnin'."] * 3 + ["It does the job and writes it down,",
                                                   "what it did, and why, and what it cost.",
                                                   "I'm asleep, and nothin's lost."]
CHORDS = ["E", "E", "E", "A", "B7", "E"]


def test_numerals_land_in_the_key():
    assert styles.chords_in("I IV V7 vi ii bVII", "E") == ["E", "A", "B7", "C#m", "F#m", "D"]
    assert styles.chords_in("I vi ii7 V7", "Bb") == ["Bb", "Gm", "Cm7", "F7"]
    assert styles.chords_in(["I", "A E", "%"], "E") == ["E", "A E", "%"]


def test_every_style_arranges_and_grit_scales_drive():
    for name in styles.STYLES:
        s = styles.arrange(name, "G")                 # checked by score.check inside
        for sec in s["sections"]:
            lead = next(iter(sec.get("lead", {}).values()), [])
            assert sum(e[1] for e in lead) <= len(sec["chords"]) * s["beats_per_bar"] + 1e-9
    clean, rough = styles.arrange("trucker", grit=0), styles.arrange("trucker", grit=1)
    assert clean["tracks"]["electric"]["drive"] == 0 and rough["tracks"]["electric"]["drive"] == 1.0


def test_syllables_and_stress():
    assert [t for t, *_ in ly.syllables("truckin' runnin' asleep")] == ["truck", "in'", "run", "nin'", "a", "sleep"]
    assert [s for _, s, _ in ly.syllables("the diesel -- forty")] == [False, True, False, True, False]
    assert ly.syllables("*lights *out and it's *run-nin'")[-2:] == [("run", True, True), ("nin'", False, False)]
    try:
        ly.syllables("18 wheels")
        raise AssertionError("digits must be refused")
    except ValueError:
        pass


def test_stressed_syllables_start_on_the_beat_and_weak_words_lead_in():
    sy = ly.syllables(CHORUS[3])
    for rhythm, beats in (("talk", {0, 1, 2, 3}), ("sing", {0, 1, 2, 3}), ("backbeat", {1, 3})):
        on, used = ly.place(sy, 4, 2, rhythm, lead_in=True)
        assert used == rhythm
        assert all(o % 4 in beats for o, (_, st, _) in zip(on, sy) if st), (rhythm, on)
    on, _ = ly.place(ly.syllables(CHORUS[0]), 4, 2, "talk")            # LIGHTS OUT, and it's RUN nin'
    assert on[2:5] == [2.0, 2.5, 3.0], "'and it's' lead into RUN, not hang off OUT"
    on, _ = ly.place(sy, 4, 2, "talk", lead_in=True)                    # It DOES ...
    assert on[0] < 0 and on[1] == 0, "a line's opening weak word is a pickup before the bar"


def _firm_notes_on_chord_tones(tunes, bars, bpb=4):
    """Every note that starts on a beat or lasts a beat or more is a tone of the chord under it."""
    for t in tunes:
        at = 0.0
        for name, d in (x for ln in t["lines"] for x in ln["notes"]):
            if name != "r" and (at % 1 == 0 or d >= 1):
                root, ivs, _ = sc.parse_chord(bars[int(at // bpb)][0])
                assert sc.note_number(name) % 12 in {(root + v) % 12 for v in ivs}, (t["shape"], at, name)
            at += d


def test_three_real_tunes_that_fit_words_and_chords():
    bars = sc.bar_chords(CHORDS)
    bars = [b for c in bars for b in (c, c)]                   # each line's chord for both its bars
    tunes = ly.options(CHORUS, bars, "E")
    pitches = [[p for ln in t["lines"] for p in ln["pitches"]] for t in tunes]
    assert len({tuple(p) for p in pitches}) == 3, "the three tunes must differ"
    hook = tunes[0]["lines"]
    assert hook[0]["pitches"] == hook[1]["pitches"] == hook[2]["pitches"], "the hook repeats on the same notes"
    assert hook[0]["notes"][:-1] == hook[1]["notes"][:-1] == hook[2]["notes"][:-1], "...in the same rhythm"
    assert hook[-1]["pitches"][-1] % 12 == 4 and hook[0]["pitches"][-1] % 12 == 4, "hook and payoff end on E"
    for t in tunes:
        assert abs(sum(n[1] for ln in t["lines"] for n in ln["notes"]) - 48) < 1e-9   # six lines, two bars each
        for i, ln in enumerate(t["lines"]):
            sy = ly.syllables(CHORUS[i])
            assert len([n for n in ln["notes"] if n[0] != "r"]) == len(sy)        # one note per syllable
            root, ivs, _ = sc.parse_chord(CHORDS[i])
            for (_, st, _), p in zip(sy, ln["pitches"]):
                assert not st or p % 12 in {(root + v) % 12 for v in ivs}, (t["shape"], CHORUS[i])
    _firm_notes_on_chord_tones(tunes, bars)                # on-beat and long notes too, not just stresses


def test_the_hook_over_a_new_chord_keeps_its_rhythm_and_bends_to_fit():
    chords = ["E", "E", "B7", "B7", "E", "E", "B7", "B7", "B7", "B7", "E", "E"]
    bars = sc.bar_chords(chords)
    hook = ly.options(CHORUS, bars, "E", n=1)
    lines = hook[0]["lines"]
    assert [d for _, d in lines[0]["notes"][:-1]] == [d for _, d in lines[1]["notes"][:-1]]
    assert lines[0]["pitches"] != lines[1]["pitches"], "the held E must move over B7"
    _firm_notes_on_chord_tones(hook, bars)


def test_three_four_answer_tune_is_not_a_copy_of_the_hook_rhythm():
    bars = sc.bar_chords(["G"] * 12)
    a, _, c = ly.options(CHORUS, bars, "G", bpb=3)
    assert [d for ln in a["lines"] for _, d in ln["notes"]] != [d for ln in c["lines"] for _, d in ln["notes"]]
    assert "3/4" in c["about"]


def test_numerals_refuse_what_they_cannot_spell_and_arrange_reports_bad_chords_plainly():
    assert styles.chords_in("viio vii7", "E") in (["D#dim", "D#m7"],)
    for bad in ("ii9", "iimaj7"):
        try:
            styles.chords_in(bad, "E")
            raise AssertionError(f"{bad} must be refused")
        except ValueError:
            pass
    for chords in ({"verse": "% I"}, {"verse": 5}):
        try:
            styles.arrange("trucker", chords=chords)
            raise AssertionError(f"{chords} must be refused")
        except (ValueError, sc.ScoreError) as e:
            assert "NoneType" not in str(e) and "not iterable" not in str(e), e


def test_review_fixes_odd_sections_repeats_range_and_bounds():
    s = styles.arrange("trucker", chords={"verse": "I IV V"})
    for sec in s["sections"]:                      # the 3-bar verse too: a lead line through every bar
        assert sum(e[1] for e in sec["lead"]["lead"]) == len(sec["chords"]) * 4, sec["name"]
    t = ly.options(["Hello old friend", "Walk on by", "Walk on by", "Home"], sc.bar_chords(["E"] * 8), "E", n=1)
    assert t[0]["lines"][1]["notes"] == t[0]["lines"][2]["notes"], "any repeated line keeps its notes"
    for key in ("C", "E", "F#", "G", "B", "Bb"):
        bars = sc.bar_chords([styles.numeral("I", key)] * 12)
        ps = [p for tune in ly.options(CHORUS, bars, key) for ln in tune["lines"] for p in ln["pitches"]]
        assert 50 <= min(ps) and max(ps) <= 77, (key, min(ps), max(ps))     # D3..F5: a voice's range
    for bad in (dict(bars_per_line=10 ** 9), dict(chords=["%"] + CHORDS[1:])):
        try:
            ly.scores(CHORUS, **bad)
            raise AssertionError(f"{bad} must be refused")
        except ValueError:
            pass


def test_lyric_scores_render_ready_and_sheet_lists_every_line():
    out = ly.scores(CHORUS, "trucker", "E", CHORDS, n=3, tempo=160)
    assert len(out) == 3
    for t, s in out:
        assert s["form"] == ["song"] and len(s["sections"][0]["chords"]) == 12
    html = ly.sheet("x", "E", 160, CHORUS, [dict(t, mp3="a.mp3") for t, _ in out])
    assert html.count("nothin&#x27;s lost") == 3 and "B7" in html
    try:
        ly.scores(CHORUS, "trucker", "E", CHORDS[:5])
        raise AssertionError("a chord list one short must be refused")
    except ValueError:
        pass


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); print("PASS", k)
