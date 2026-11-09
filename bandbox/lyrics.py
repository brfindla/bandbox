"""Lyrics -> syllables on beats -> a few original tunes to choose from, and a lyric sheet.

The order follows how a songwriter works: the words come first, the stressed syllables go on the
beat, then a tune is written to fit. Each line of lyric fills `bars_per_line` bars. Unstressed
words lead into the next stress as pickups (eighths that end on its beat, from the bar before if
the line has room); the unstressed end of a word follows its stress. Syllable splitting and
stress are rule-of-thumb English; mark a line by hand to override them:
"*Lights *out, and it's *run-nin'" ('-' splits syllables, '*' marks the stressed ones).

The three tunes are deliberately different, not one tune nudged:
  hook   - talky; the first line is the hook and falls home; a line sung again with the same
           words keeps its rhythm and notes (a held note moves to the nearest tone if the chord
           under it changed); the second-last line climbs; the last falls home like the hook
           (the "hook three times, then the payoff" shape).
  climb  - sung; stressed syllables held a full beat; each line starts higher than the last, the
           top comes near the end, the last line comes down home.
  answer - backbeat; stressed syllables land on 2 and 4 (in 3/4, held like climb); lines go in
           pairs, a rising question that stops on the fifth and a falling answer that comes home.
A note that lands on a beat or lasts a beat or more is always a tone of the chord under it.
"""
import copy
import html
import math
import re

from . import score as sc
from .styles import FLAT, FLAT_KEYS, SHARP, key_tonic

FUNCTION = set("a an the and or but nor of to in on at by for with from as if so than that this these those "
               "is it it's its i i'm i've i'll i'd me my we we're our us you you're your he he's his him she "
               "her they they're them their be been am are was were has have had can will would "
               "could should".split())
# two-syllable-or-more words stressed on the second syllable (a-SLEEP, be-HIND, to-NIGHT)
WEAK_FIRST = set("asleep alone away about around again against ago ahead along alive awake aware because "
                 "before behind below beside between beyond begin become believe belong today tonight "
                 "tomorrow together forget forgive forgot forgotten decide deny delay depend receive "
                 "remember return report repeat release remain enough until upon machine guitar hotel "
                 "forever".split())
DIGRAPHS = ("th", "sh", "ch", "ph", "wh", "ck", "ng", "gh")
ONSETS = {"bl", "br", "cl", "cr", "dr", "fl", "fr", "gl", "gr", "pl", "pr", "sc", "sk", "sl", "sm", "sn",
          "sp", "st", "sw", "tr", "tw", "qu"}
MAJOR = [0, 2, 4, 5, 7, 9, 11]
SHAPES = {"hook": "talky; the hook falls home, repeated words keep their notes; climbs before the payoff",
          "climb": "sung, long stressed notes; each line starts higher, comes down home at the end",
          "answer": "on the backbeat; lines in pairs, a rising question then a falling answer"}
RHYTHM = {"hook": "talk", "climb": "sing", "answer": "backbeat"}
# stand-in "lyrics" that give an instrumental lead its phrasing (arrange() uses them)
INSTRUMENTAL = {True: "*da *da da da *da *da", False: "da *da da *da da *da da *da"}
INSTRUMENTAL_SHORT = "*da da *da da"                   # a one-bar phrase


# ---- syllables and stress ---------------------------------------------------------------

def _split_word(w):
    """'runnin'' -> ['run', 'nin''], by vowel groups. Rule of thumb; '-' in the lyric overrides it."""
    low = w.lower()
    groups = [m.span() for m in re.finditer(r"[aeiouy]+", low)]
    if len(groups) > 1:                                   # a silent final e: line, writes, worked
        i = groups[-1][0]
        tail, prev = low[i:], low[i - 1]
        sounded = (prev == "l" and low[i - 2] not in "aeiouy") or (tail.startswith("ed") and prev in "td")
        if re.fullmatch(r"e(s|d|'s)?[^a-z]*", tail) and not sounded:   # (ta-ble, want-ed keep theirs)
            groups.pop()
    cuts = []
    for (_, e), (s, _) in zip(groups, groups[1:]):
        cl, units, i = low[e:s], [], 0
        while i < len(cl):
            u = cl[i:i + 2] if cl[i:i + 2] in DIGRAPHS else cl[i]
            units.append(u); i += len(u)
        if units in (["ck"], ["ng"]):                     # these close a syllable: truck-er, sing-er
            cuts.append(s)
        elif len(units) <= 1 or (len(units) == 2 and "".join(units) in ONSETS):
            cuts.append(e)
        else:
            cuts.append(e + len(units[0]))
    return [w[a:b] for a, b in zip([0] + cuts, cuts + [len(w)])]


def syllables(line):
    """-> [(text, stressed, starts_a_word)] for a lyric line."""
    marked = "*" in line
    out = []
    for word in line.split():
        if re.search(r"\d", word):
            raise ValueError(f"lyric {word!r}: spell numbers out (eighteen, not 18) so they can be sung")
        if not re.search(r"[a-z]", word.lower()):
            continue                                       # a dash or dots: punctuation, not a syllable
        parts = [p for p in word.split("-") if p] if "-" in word.strip("-") else _split_word(word)
        if marked:
            parts = [p for p in parts if p.lstrip("*")]
            out += [(p.lstrip("*"), p.startswith("*"), k == 0) for k, p in enumerate(parts)]
            continue
        bare = re.sub(r"[^a-z']", "", word.lower())
        if bare in FUNCTION:
            stress = [False] * len(parts)
        elif len(parts) >= 2 and bare in WEAK_FIRST:
            stress = [k == 1 for k in range(len(parts))]
        else:
            stress = [k == 0 for k in range(len(parts))]
        out += [(p, s, k == 0) for k, (p, s) in enumerate(zip(parts, stress))]
    if not out:
        raise ValueError(f"lyric line {line!r} has no words")
    return out


def _grid(bpb, bars_per_line, lines=()):
    if bpb not in (2, 3, 4):
        raise ValueError("beats_per_bar: 2, 3 or 4")
    if not isinstance(bars_per_line, int) or not 1 <= bars_per_line <= 8:
        raise ValueError("bars_per_line: a whole number 1-8")
    if lines != () and not 1 <= len(lines) <= 64:
        raise ValueError("lyrics: 1-64 lines")


def place(sylls, bpb, bars, rhythm, lead_in=False):
    """Onset beat of each syllable in a line of `bars` bars -> (onsets, rhythm used).
    Stressed syllables start on a beat ('backbeat': on 2 and 4). Unstressed words before a stress
    lead into it in eighths; with lead_in they may start before the line's first bar line (negative
    onsets: pickups sung over the end of the line before). The unstressed end of a word follows its
    stress. Falls back to a quicker rhythm if the line would not fit."""
    span, n = bpb * bars, len(sylls)
    stresses = [k for k, s in enumerate(sylls) if s[1]]
    for r in [rhythm] + [x for x in ("talk", "tight") if x != rhythm]:
        u = 0.25 if r == "tight" else 0.5
        hold = 1.0 if r == "sing" else u
        back = r == "backbeat" and bpb == 4
        snap = (lambda t: 1 + 2 * math.ceil((t - 1) / 2 - 1e-9)) if back else (lambda t: math.ceil(t - 1e-9))
        on = [0.0] * n
        if not stresses:
            on = [k * u for k in range(n)]
        else:
            first = stresses[0]
            s = snap(0) if lead_in and first * u <= 1.5 else snap(first * u)
            for j in range(first):
                on[j] = s - u * (first - j)
            on[first], prev = s, first
            for k in stresses[1:] + [n]:
                t = on[prev] + hold
                j = prev + 1
                while j < k and not sylls[j][2]:           # the rest of the stressed word follows it
                    on[j] = t; t += u; j += 1
                if k == n:                                 # after the last stress, everything follows
                    while j < n:
                        on[j] = t; t += u; j += 1
                    break
                s = snap(t + u * (k - j))                  # words before the next stress lead into it
                for m in range(j, k):
                    on[m] = s - u * (k - m)
                on[k], prev = s, k
        if on[-1] <= span - 1:
            return on, r
    raise ValueError(f"line too long for {bars} bars ({n} syllables); use more bars_per_line or split it")


def layout(lines, bpb=4, bars_per_line=2, rhythm="talk"):
    """What a model or a person checks before any notes are picked: each syllable and where it lands."""
    _grid(bpb, bars_per_line, lines)
    if rhythm not in RHYTHM.values():
        raise ValueError(f"rhythm: one of {sorted(RHYTHM.values())}")
    if rhythm == "backbeat" and bpb != 4:
        raise ValueError("rhythm backbeat needs 4 beats a bar")
    out = []
    for i, line in enumerate(lines):
        sy = syllables(line)
        on, used = place(sy, bpb, bars_per_line, rhythm, lead_in=i > 0)
        out.append({"line": line,
                    "syllables": " ".join(t.upper() if s else t for t, s, _ in sy),
                    "beats": [[t, f"{int(o // bpb) + 1}:{o % bpb + 1:g}" if o >= 0 else f"pickup {o:g}"]
                              for (t, _, _), o in zip(sy, on)],
                    **({"rhythm_used": used} if used != rhythm else {})})
    return {"bars_per_line": bars_per_line, "beats_per_bar": bpb, "rhythm": rhythm,
            "how_to_read": "CAPITALS are stressed; '2:3' = bar 2, beat 3; 'pickup -0.5' = half a beat before "
                           "the line's first bar. Fix a line by marking it: '*Lights *out, and it's *run-nin''",
            "lines": out}


# ---- tunes ------------------------------------------------------------------------------

def note_name(m, key):
    return (FLAT if key in FLAT_KEYS else SHARP)[m % 12] + str(m // 12 - 1)


def _target(shape, i, n, p, same_as_hook):
    """Where the tune is heading (scale steps above the key note) at fraction p of line i of n."""
    p, last = min(1.0, max(0.0, p)), n - 1
    if shape == "hook":
        if i == 0 or same_as_hook or i == last:
            return 4 - 4 * p                              # the hook: down from the fifth to home
        if i == last - 1:
            return 5 * p                                  # climb before the payoff
        return 1 + 2 * p if i % 2 else 3 - 1.5 * p        # other lines rise and fall in turn
    if shape == "climb":
        if i == last and n > 1:
            return 5 - 5 * p
        start = min(i, 3)
        return start + 3 * math.sin(math.pi * min(1, p * 1.2))
    if i % 2 == 0 and i != last:                          # answer: question rises to the fifth
        return -2 + 6 * p
    return 4 - 4 * p


def melody(lines_sylls, bars, key, shape="hook", bpb=4, bars_per_line=2, texts=None, rhythm=None):
    """lines_sylls: [[(text, stressed, starts_word)]] per line; bars: chord symbols per bar
    (score.bar_chords). -> per line {"notes": [[name, beats]], "pitches", "chords", "rhythm"}.
    A line's notes run from its first syllable (a pickup may start in the bar before) to the next
    line's first syllable; the first line starts with a rest if its first syllable is late."""
    if shape not in SHAPES:
        raise ValueError(f"shape {shape!r}: one of {list(SHAPES)}")
    n, span = len(lines_sylls), bpb * bars_per_line
    if len(bars) < n * bars_per_line:
        raise ValueError(f"{n} lines x {bars_per_line} bars need {n * bars_per_line} bars of chords, got {len(bars)}")
    rhythm = rhythm or RHYTHM[shape]
    pc = key_tonic(key)
    tonic = 60 + pc - (12 if pc >= 6 else 0)          # key note C4..F4 or F#3..B3: a singable middle
    deg = lambda d: tonic + MAJOR[d % 7] + 12 * (d // 7)
    lo, hi = max(deg(-3), 50), min(deg(9), 77)          # never past D3..F5, a voice's range
    scale = [m for m in range(lo, hi + 1) if (m - tonic) % 12 in MAJOR]
    texts = texts or [None] * n

    def tones(at):                                    # chord tones (pitch classes) at a song beat
        bar = bars[min(max(0, int(at // bpb)), len(bars) - 1)]
        root, ivs, _ = sc.parse_chord(bar[min(int((at % bpb) / (bpb / len(bar))), len(bar) - 1)])
        return {(root + v) % 12 for v in ivs}

    # 1. rhythm: onsets per line (song beats); a repeat of a line's words copies its rhythm
    seen, onsets, used = {}, [], []
    for i, sy in enumerate(lines_sylls):
        if shape == "hook" and texts[i] is not None and texts[i] in seen:
            j = seen[texts[i]]
            local = [o - j * span for o in onsets[j]]
            r = used[j]
        else:
            seen.setdefault(texts[i], i)
            local, r = place(sy, bpb, bars_per_line, rhythm, lead_in=i > 0)
        if i and local[0] < 0 and onsets[-1][-1] + 1 > i * span + local[0]:
            local, r = place(sy, bpb, bars_per_line, rhythm)            # no room for a pickup
        onsets.append([i * span + o for o in local])
        used.append(r)
    flat = [o for line in onsets for o in line]
    ends = flat[1:] + [n * span]
    dur = dict(zip(flat, (b - a for a, b in zip(flat, ends))))

    # 2. pitches: stressed, on-beat, long and line-final notes are chord tones; the rest scale tones
    out = []
    for i, sy in enumerate(lines_sylls):
        same = texts[i] is not None and texts[i] == texts[0]
        j = seen.get(texts[i], i) if shape == "hook" else i
        pitches = []
        for k, ((_, stressed, _), at) in enumerate(zip(sy, onsets[i])):
            end = k == len(sy) - 1
            firm = stressed or end or at % 1 == 0 or dur[at] >= 1
            if j != i:                                # the same words again: same note, bent if it must
                was = out[j]["pitches"][k]
                pool = [m for m in range(lo, hi + 1) if m % 12 in tones(at)] if firm and was % 12 not in tones(at) else [was]
                pitches.append(min(pool, key=lambda m: (abs(m - was), m)))
                continue
            goal = deg(round(_target(shape, i, n, 1.0 if end else (at - i * span) / span, same)))
            pool = [m for m in range(lo, hi + 1) if m % 12 in tones(at)] if firm else scale
            pitches.append(min(pool, key=lambda m: (abs(m - goal), m)))
        first = onsets[i][0]
        notes = ([["r", first]] if i == 0 and first > 0 else []) + \
                [[note_name(m, key), dur[at]] for m, at in zip(pitches, onsets[i])]
        out.append({"notes": notes, "pitches": pitches, "rhythm": used[i],
                    "chords": bars[i * bars_per_line:(i + 1) * bars_per_line]})
    return out


def options(lines, bars, key, bpb=4, bars_per_line=2, n=3):
    """Up to three different tunes for the same words over the same chords."""
    if not isinstance(n, int) or not 1 <= n <= len(SHAPES):
        raise ValueError(f"n: 1-{len(SHAPES)} tunes")
    _grid(bpb, bars_per_line, lines)
    sy = [syllables(x) for x in lines]
    norm = [re.sub(r"[^a-z' ]", "", x.lower()).strip() for x in lines]
    tunes = []
    for sh in list(SHAPES)[:n]:
        rhythm = "sing" if RHYTHM[sh] == "backbeat" and bpb != 4 else RHYTHM[sh]
        t = {"shape": sh, "about": SHAPES[sh] + (" (in 3/4: held stresses, not the backbeat)" if rhythm != RHYTHM[sh] else ""),
             "lines": melody(sy, bars, key, sh, bpb, bars_per_line, norm, rhythm)}
        quick = [k + 1 for k, ln in enumerate(t["lines"]) if ln["rhythm"] != rhythm]
        if quick:
            t["note"] = f"line(s) {', '.join(map(str, quick))} too long for this rhythm; sung quicker"
        tunes.append(t)
    return tunes


# ---- lyric sheet ------------------------------------------------------------------------

def sheet(title, key, tempo, lines, tunes):
    """HTML lyric sheet: per tune, each line with its chords and the note names to sing."""
    esc = html.escape
    parts = []
    for k, t in enumerate(tunes):
        rows = "".join(
            f'<tr><td class="c">{esc(" ".join(dict.fromkeys(" | ".join(" ".join(b) for b in ln["chords"]).split(" | "))))}</td>'
            f'<td>{esc(text)}</td><td class="m">{esc(" ".join(x[0][:-1] for x in ln["notes"] if x[0] != "r"))}</td></tr>'
            for text, ln in zip(lines, t["lines"]))
        audio = f'<audio controls preload="none" src="{esc(t["mp3"])}"></audio>' if t.get("mp3") else ""
        note = f'<p class="m">{esc(t["note"])}</p>' if t.get("note") else ""
        parts.append(f'<h2>Tune {chr(65 + k)}: {esc(t["shape"])}</h2><p class="m">{esc(t["about"])}</p>{note}{audio}<table>{rows}</table>')
    return ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title><style>'
            ':root{--bg:#fafaf7;--fg:#222;--muted:#666;--chord:#b0400b;--line:#ddd}'
            '@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#1b1b1b;--fg:#eee;--muted:#aaa;--chord:#ffb07a;--line:#444}}'
            'body{font:18px/1.5 Georgia,serif;max-width:820px;margin:24px auto;padding:0 16px;background:var(--bg);color:var(--fg)}'
            'h2{font-size:21px;margin:28px 0 4px;border-bottom:1px solid var(--line)} .m{color:var(--muted);font-size:15px}'
            'td{padding:3px 12px 3px 0;vertical-align:top} .c{color:var(--chord);font-weight:bold;white-space:nowrap} audio{width:100%}'
            f'</style></head><body><h1>{esc(title)}</h1><p class="m">Key of {esc(key)}, {tempo:g} beats a minute. '
            'Each tune is played by a lead instrument standing in for the voice. Note names are the sung line, '
            'one per syllable.</p>' + "".join(parts) + '</body></html>')


# ---- lyrics -> scores, one per tune ----------------------------------------------------------

def scores(lines, style="trucker", key="E", chords=None, n=3, tempo=None, grit=None, bars_per_line=2,
           lead_instrument=None, title=None):
    """-> [(tune, score)]: the style's band under each tune. chords: one entry per lyric line, a chord
    or numeral for the whole line, or one per bar ('A E'); default is the style's chorus progression."""
    from .styles import arrange, chords_in
    if not lines:
        raise ValueError("lyrics: at least one line")
    _grid(4, bars_per_line, lines)
    base = arrange(style, key, tempo, grit, title or "Song", melody=False)
    bpb = base["beats_per_bar"]
    lead = next(k for k, t in base["tracks"].items() if t["part"] == "lead")
    if lead_instrument:
        base["tracks"][lead]["instrument"] = lead_instrument
    if chords is None:
        prog = next((x["chords"] for x in base["sections"] if x["name"] == "chorus"), base["sections"][0]["chords"])
        bars = [prog[i % len(prog)] for i in range(len(lines) * bars_per_line)]
    else:
        if len(chords) != len(lines):
            raise ValueError(f"chords: one entry per lyric line ({len(lines)}), got {len(chords)}")
        bars = []
        if str(chords[0]).split()[:1] == ["%"]:
            raise ValueError("chords: the first line cannot be '%' (nothing to repeat yet)")
        for c in chords:
            syms = chords_in(str(c).split(), key)
            if len(syms) not in (1, bars_per_line):
                raise ValueError(f"chords {c!r}: one chord for the line, or {bars_per_line} (one per bar)")
            bars += syms * bars_per_line if len(syms) == 1 else syms
    tunes = options(lines, sc.bar_chords(bars), key, bpb, bars_per_line, n)
    out = []
    for k, t in enumerate(tunes):
        s = copy.deepcopy(base)
        s["title"] = f"{s['title']} - tune {chr(65 + k)} ({t['shape']})"
        s["sections"] = [{"name": "song", "chords": bars, "lyrics": list(lines),
                          "lead": {lead: [ev for ln in t["lines"] for ev in ln["notes"]]}}]
        s["form"] = ["song"]
        out.append((t, sc.check(s)))
    return out
