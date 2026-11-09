"""Genre recipes and arrange(): a plain-words brief ("a 4/4 trucker song, drums, bass and guitars,
rough") becomes a full score. The calling model picks the recipe, key, grit and (if it likes) the
chords; the recipe supplies tempo, beat, bass, comp, instruments and a song form.

Chords in recipes are Roman numerals (I, IV, V7, vi, bVII...) so one recipe plays in any major key.
Progressions are the common public ones (I-IV-V, the 12-bar blues); no song's tune is in here.
"""
import copy
import math
import re

from . import sampler, score as sc, tabla

SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
FLAT_KEYS = {"F", "Bb", "Eb", "Ab", "Db", "Gb"}
NUMERAL = {"I": 0, "II": 2, "III": 4, "IV": 5, "V": 7, "VI": 9, "VII": 11}


def T(instrument, part, style=None, **kw):
    return {"instrument": instrument, "part": part, **({"style": style} if style else {}), **kw}


STYLES = {
    "trucker": {
        "about": "Truck-driving country: the train beat on the snare, boom-chick electric guitar, strummed "
                 "acoustic, upright bass on root and fifth, harmonica lead.",
        "tempo": [130, 170, 150], "beats_per_bar": 4, "swing": 0, "grit": 0.5,
        "tracks": {"electric": T("clean_guitar", "comp", "boom_chick", pan=-0.35, drive=0.5),
                   "acoustic": T("steel_guitar", "comp", "strum", pan=0.35, level_db=-6),
                   "bass": T("upright_bass", "bass", "root_fifth"),
                   "drums": T("gogodze_kit", "drums", "train", drive=0.35),
                   "lead": T("harmonica", "lead", pan=0.2, drive=0.15)},
        "sections": {"verse": "I % % % IV % I % V7 % % % I % % %", "chorus": "I % IV % V7 % I %"},
        "form": ["verse", "chorus", "verse", "chorus"]},
    "boom_chicka": {
        "about": "Country two-beat: kick on 1 and 3, snare on 2 and 4, boom-chick guitar, fiddle lead.",
        "tempo": [100, 135, 118], "beats_per_bar": 4, "swing": 0.15, "grit": 0.3,
        "tracks": {"guitar": T("steel_guitar", "comp", "boom_chick", pan=-0.3),
                   "electric": T("clean_guitar", "comp", "arpeggio", pan=0.3, level_db=-7, drive=0.3),
                   "bass": T("upright_bass", "bass", "root_fifth"),
                   "drums": T("gogodze_kit", "drums", "boom_chick", drive=0.2),
                   "lead": T("fiddle", "lead", pan=0.15)},
        "sections": {"verse": "I % IV I V7 % I %", "chorus": "IV % I % V7 % I %"},
        "form": ["verse", "chorus", "verse", "chorus"]},
    "outlaw": {
        "about": "Outlaw country: a rock backbeat, driven strummed electric, eighth-note picked bass, harmonica.",
        "tempo": [90, 125, 104], "beats_per_bar": 4, "swing": 0, "grit": 0.65,
        "tracks": {"electric": T("clean_guitar", "comp", "strum", pan=-0.35, drive=0.6),
                   "acoustic": T("steel_guitar", "comp", "boom_chick", pan=0.35, level_db=-5),
                   "bass": T("picked_bass", "bass", "root_eighths", level_db=-2),
                   "drums": T("gogodze_kit", "drums", "rock", drive=0.4),
                   "lead": T("harmonica", "lead", pan=0.2, drive=0.25)},
        "sections": {"verse": "I % bVII % IV % I %", "chorus": "IV % I % V % I %"},
        "form": ["verse", "chorus", "verse", "chorus"]},
    "rockabilly": {
        "about": "Rockabilly: fast, a little swung, walking upright bass, slap-back boom-chick, twangy lead guitar.",
        "tempo": [160, 210, 180], "beats_per_bar": 4, "swing": 0.35, "grit": 0.5,
        "tracks": {"rhythm": T("clean_guitar", "comp", "boom_chick", pan=-0.3, drive=0.45),
                   "bass": T("upright_bass", "bass", "walking"),
                   "drums": T("gogodze_kit", "drums", "boom_chick", drive=0.3),
                   "lead": T("jazz_guitar", "lead", pan=0.25, drive=0.4)},
        "sections": {"verse": "I % % % IV % I % V7 IV7 I V7", "chorus": "IV % I % IV % V7 %"},
        "form": ["verse", "chorus", "verse", "verse"]},
    "blues_shuffle": {
        "about": "12-bar blues shuffle: swung ride, walking bass, boom-chick guitar, harmonica.",
        "tempo": [80, 125, 100], "beats_per_bar": 4, "swing": 0.7, "grit": 0.45,
        "tracks": {"guitar": T("clean_guitar", "comp", "boom_chick", pan=-0.3, drive=0.4),
                   "piano": T("honky_tonk_piano", "comp", "sustain", pan=0.3, level_db=-9),
                   "bass": T("upright_bass", "bass", "walking"),
                   "drums": T("gogodze_kit", "drums", "shuffle", drive=0.25),
                   "lead": T("harmonica", "lead", pan=0.15, drive=0.3)},
        "sections": {"verse": "I7 IV7 I7 % IV7 % I7 % V7 IV7 I7 V7"},
        "form": ["verse", "verse", "verse"]},
    "country_waltz": {
        "about": "Country waltz in 3/4: bass on 1, guitar on 2 and 3, brushes, fiddle lead.",
        "tempo": [90, 150, 120], "beats_per_bar": 3, "swing": 0, "grit": 0.15,
        "tracks": {"guitar": T("steel_guitar", "comp", "waltz", pan=-0.25),
                   "bass": T("upright_bass", "bass", "waltz"),
                   "drums": T("brush_kit", "drums", "waltz"),
                   "lead": T("fiddle", "lead", pan=0.2)},
        "sections": {"verse": "I % IV I V7 % I %", "chorus": "IV % I % V7 % I %"},
        "form": ["verse", "chorus", "verse", "chorus"]},
}


def _tala_recipe(name, tempo):
    t = tabla.TALAS[name]
    return {"about": f"{t['about']} Tabla plays the theka '{t['theka']}' (bandbox's tabla is not yet "
                     "checked by a tabla player); a sitar plays a tanpura-like drone on the key note.",
            "tala": name, "theka": t["theka"],
            "tempo": tempo, "beats_per_bar": t["beats"], "swing": 0, "grit": 0,
            "tracks": {"tabla": T("tabla", "tabla", "theka"),
                       "drone": T("sitar", "comp", "drone", level_db=-5, reverb=.45)},
            "sections": {"theka": "I % % %"}, "form": ["theka"]}


# Hindustani talas: one 'bar' (chord entry) is one cycle. Tempo = matras per minute.
STYLES.update({"teentaal": _tala_recipe("teentaal", [60, 200, 112]),
               "keherwa": _tala_recipe("keherwa", [70, 180, 104]),
               "dadra": _tala_recipe("dadra", [70, 200, 126]),
               "rupak": _tala_recipe("rupak", [60, 180, 100])})


def key_tonic(key):
    m = re.fullmatch(r"([A-G])([#b]?)", key or "")
    if not m:
        raise ValueError(f"key {key!r}: a major key like E, A, Bb or F#")
    return (sc.PC[m.group(1)] + {"#": 1, "b": -1, "": 0}[m.group(2)]) % 12


def numeral(sym, key):
    """'IV' in E -> 'A'; 'vi' -> 'C#m'; 'bVII' -> 'D'; 'V7' -> 'B7'; '%' stays."""
    if sym == "%":
        return sym
    m = re.fullmatch(r"([b#]?)(VII|VI|V|IV|III|II|I|vii|vi|v|iv|iii|ii|i)(.*)", sym)
    if not m:
        raise ValueError(f"chord numeral {sym!r}: use I ii iii IV V vi bVII, with 7, maj7, 6 ... after it")
    pc = (key_tonic(key) + NUMERAL[m.group(2).upper()] + {"b": -1, "#": 1, "": 0}[m.group(1)]) % 12
    qual = m.group(3)
    if m.group(2).islower():                              # lower case = minor; 'o' = diminished
        lower = {"": "m", "7": "m7", "6": "m6", "o": "dim", "o7": "dim7", "dim": "dim", "dim7": "dim7"}
        if qual not in lower:
            raise ValueError(f"chord numeral {sym!r}: a lower-case (minor) numeral takes '', 7, 6, o or o7")
        qual = lower[qual]
    name = (FLAT if key in FLAT_KEYS or m.group(1) == "b" else SHARP)[pc] + qual
    sc.parse_chord(name)
    return name


def chords_in(prog, key):
    """'I % IV V7' or ['I', 'E', 'A E'] -> chord names per bar. Numerals and chord names both work;
    a bar with two symbols ('IV I') splits the bar."""
    bars = prog.split() if isinstance(prog, str) else list(prog)
    return [" ".join(x if re.match(r"[A-G%]", x) else numeral(x, key) for x in str(bar).split()) for bar in bars]


def list_styles():
    return {k: {"about": v["about"], "tempo_range": v["tempo"][:2], "default_tempo": v["tempo"][2],
                "beats_per_bar": v["beats_per_bar"], "swing": v["swing"], "grit": v["grit"],
                "tracks": {n: {x: y for x, y in t.items() if x in ("instrument", "part", "style")}
                           for n, t in v["tracks"].items()},
                "sections": v["sections"], "form": v["form"],
                **({"tala": v["tala"], "theka": v["theka"]} if "tala" in v else {})} for k, v in STYLES.items()}


def arrange(style, key="E", tempo=None, grit=None, title=None, chords=None, form=None,
            instruments=None, lead=None, melody=True, seed=1):
    """Recipe -> checked score. chords: {section: 'I IV V7' numerals or ['E', 'A', ...]} replaces or
    adds sections; instruments: {track: instrument} swaps one; lead: {section: [[note, beats], ...]}
    gives the lead's notes; otherwise (melody=True) the lead gets an original generated line.
    grit scales the drive of the tracks that have some (in the recipes: electric guitars, drums,
    lead); acoustic guitar and bass stay clean."""
    if style not in STYLES:
        raise ValueError(f"style {style!r} unknown; styles: {list(STYLES)}")
    r = copy.deepcopy(STYLES[style])
    lo, hi, default = r["tempo"]
    tempo = default if tempo is None else tempo
    grit = r["grit"] if grit is None else grit
    if not 0 <= grit <= 1:
        raise ValueError("grit: 0 (clean) to 1 (rough)")
    tracks = r["tracks"]
    for name, inst in (instruments or {}).items():
        if name not in tracks:
            raise ValueError(f"instruments names unknown track {name!r}; tracks are {list(tracks)}")
        tracks[name]["instrument"] = inst
    for t in tracks.values():
        if "drive" in t:                                  # grit 0.5 = the recipe's own drive; 1 doubles it
            t["drive"] = round(min(1.0, t["drive"] * grit / 0.5), 2)
        if t["instrument"] in sampler.KITS and not sampler.available(t["instrument"]):
            t["instrument"] = "standard_kit"              # sampled kit not fetched: General MIDI kit
    secs = {n: chords_in(p, key) for n, p in r["sections"].items()}
    for n, p in (chords or {}).items():
        if not isinstance(p, (str, list)):
            raise ValueError(f"chords for {n!r}: a string like 'I % IV V7' or a list of bars")
        secs[n] = chords_in(p, key)
    drums = any(t["part"] == "drums" for t in tracks.values())
    s = {"title": title or f"{style} in {key}", "tempo": tempo, "beats_per_bar": r["beats_per_bar"],
         **({"tala": r["tala"]} if "tala" in r else {}),
         "swing": r["swing"], "key": key, "count_in_bars": 1 if drums else 0, "seed": seed, "style": style, "grit": grit,
         "tracks": tracks, "sections": [{"name": n, "chords": c} for n, c in secs.items()],
         "form": form or [f for f in r["form"] if f in secs] or list(secs)}
    sc.check(copy.deepcopy(s))                            # report bad chords plainly, before writing a lead
    lead_track = next((n for n, t in tracks.items() if t["part"] == "lead"), None)
    if lead_track:
        from . import lyrics                               # generated tunes live with the lyric tools
        for i, sec in enumerate(s["sections"]):
            if lead and sec["name"] in lead:
                sec["lead"] = {lead_track: lead[sec["name"]]}
            elif melody:                                   # two-bar phrases; one-bar if the count is odd
                bpl = 2 if len(sec["chords"]) % 2 == 0 else 1
                line = lyrics.INSTRUMENTAL[sec["name"] == "chorus"] if bpl == 2 else lyrics.INSTRUMENTAL_SHORT
                tune = lyrics.melody([lyrics.syllables(line)] * (len(sec["chords"]) // bpl),
                                     sc.bar_chords(sec["chords"]), key, ("hook", "climb")[i % 2],
                                     s["beats_per_bar"], bpl)
                sec["lead"] = {lead_track: [ev for ln in tune for ev in ln["notes"]]}
        if lead and set(lead) - set(secs):
            raise ValueError(f"lead names unknown sections {sorted(set(lead) - set(secs))}")
    if not lo <= tempo <= hi:
        s["note"] = f"tempo {tempo} is outside the usual {lo}-{hi} for {style}"
    return sc.check(s)
