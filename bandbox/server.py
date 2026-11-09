"""bandbox MCP server: Claude writes a score, bandbox plays it with sampled instruments.

Run:  .venv/Scripts/python -m bandbox.server     (stdio transport)
Tools: list_styles, arrange, set_lyrics, melody_options, list_instruments, write_score, get_score,
render, mix, analyse_beat, hum_to_notes.
Inspired by github.com/Digital-Physics/mcp-server-synth (no code taken: it has no licence).
"""
import functools
import json
import os
import re
import shutil
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import beat, hum, lyrics as lyrics_mod, render as rd, sampler, score as sc, styles
from .soundfont import presets

ROOT = Path(__file__).resolve().parent.parent
SONGS = Path(os.environ.get("BANDBOX_SONGS", ROOT / "songs"))
OUT = Path(os.environ.get("BANDBOX_OUT", ROOT / "out"))

mcp = MCPServer("bandbox", instructions=(
    "A band in a box. From a plain brief ('a 4/4 trucker song, drums, bass and guitars, rough'): read "
    "list_styles, pick the closest style, then arrange (it writes and renders the track). From lyrics: "
    "set_lyrics shows where each syllable lands; melody_options writes up to three tunes for the words "
    "and renders each, with a lyric sheet. For full control write a score yourself with write_score and "
    "render it. mix re-balances the last render without re-rendering. Everything is rendered to files."))


def _plain_errors(fn):
    """The server masks ordinary exceptions as 'Error executing tool'; Claude needs the real
    message to fix a score, so expected failures are re-raised as ToolError with their text."""
    @functools.wraps(fn)
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except (ValueError, KeyError, TypeError, AttributeError, OSError, RuntimeError) as e:
            raise ToolError(f"{type(e).__name__}: {e}") from e
    return wrapper


def _name(name):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name or ""):
        raise ValueError("name: 1-64 letters, digits, _ or -")
    return name


def _render_named(name, s, soundfont):
    SONGS.mkdir(parents=True, exist_ok=True)
    (SONGS / f"{name}.json").write_text(json.dumps(s, indent=1), "utf-8")
    return rd.render(s, OUT / name, "mix", soundfont)


@mcp.tool()
@_plain_errors
def list_styles() -> dict:
    """Genre recipes for arrange and melody_options: what each sounds like, tempo range, beat, bass, comp
    and lead instruments, default grit (0 clean .. 1 rough), chord plan in Roman numerals, and song form."""
    return styles.list_styles()


@mcp.tool()
@_plain_errors
def arrange(name: str, style: str, key: str = "E", tempo: float | None = None, grit: float | None = None,
            title: str | None = None, chords: dict[str, str | list[str]] | None = None,
            form: list[str] | None = None, instruments: dict[str, str] | None = None,
            lead: dict[str, list] | None = None, render: bool = True, soundfont: str = "generaluser") -> dict:
    """Plain brief -> finished track. Pick the style from list_styles, then set only what the brief asks.
    Example: "a 4/4 trucker song with drums and bass and guitars, rough" ->
    arrange(name="trucker_rough", style="trucker", grit=0.85).
    key: a major key (E, A, Bb...). grit: 0 clean .. 1 rough (scales the drive on the electric
    guitars, drums and lead; acoustic guitar and bass stay clean).
    chords: {section: "I % IV % V7 % I %"} (numerals or chord names, one per bar) replaces or adds a section.
    form: play order of section names. instruments: {track: instrument} swaps one (see list_instruments).
    lead: {section: [[note, beats], ...]} gives the lead's notes; otherwise the lead plays an original
    generated line. Saves songs/<name>.json (edit it with get_score/write_score) and renders out/<name>/mix.mp3."""
    s = styles.arrange(style, key, tempo, grit, title or name, chords, form, instruments, lead)
    rep = {"score": s["title"], "tempo": s["tempo"], "grit": s["grit"], "form": s["form"],
           "tracks": {k: t["instrument"] for k, t in s["tracks"].items()}, **({"note": s["note"]} if "note" in s else {})}
    if render:
        rep["render"] = _render_named(_name(name), s, soundfont)
    else:
        SONGS.mkdir(parents=True, exist_ok=True)
        (SONGS / f"{_name(name)}.json").write_text(json.dumps(s, indent=1), "utf-8")
    return rep


@mcp.tool()
@_plain_errors
def set_lyrics(lyrics: str | list[str], beats_per_bar: int = 4, bars_per_line: int = 2,
               rhythm: str = "talk") -> dict:
    """Put each lyric line's syllables on beats, before any tune is written, so you and the person can
    check the stresses. One line per list item (or newline). Stressed syllables come back in CAPITALS
    and start on a beat. rhythm: talk (eighths), sing (stressed held a beat), backbeat (stresses on 2
    and 4; 4/4 only). If a stress is wrong, mark the line: "*Lights *out, and it's *run-nin'" ('*'
    stressed, '-' splits). For a 3/4 style (country_waltz) pass beats_per_bar=3 to see its layout."""
    lines = lyrics.splitlines() if isinstance(lyrics, str) else lyrics
    return lyrics_mod.layout([x for x in lines if x.strip()], beats_per_bar, bars_per_line, rhythm)


@mcp.tool()
@_plain_errors
def melody_options(name: str, lyrics: str | list[str], style: str = "trucker", key: str = "E",
                   chords: list[str] | None = None, n: int = 3, tempo: float | None = None,
                   grit: float | None = None, bars_per_line: int = 2, lead_instrument: str | None = None,
                   soundfont: str = "generaluser") -> dict:
    """Lyrics in, up to three original tunes out, each over the same chords and band, each rendered to
    its own MP3, plus a lyric sheet (chords and note names per line) to learn the one you pick.
    The tunes differ on purpose: A 'hook' (talky; the first line is the hook, repeated words keep their
    notes, climbs before a payoff that falls home), B 'climb' (sung, long notes, rises line by line),
    C 'answer' (backbeat; a rising question line, then a falling answer).
    chords: one per lyric line (a chord or numeral for the line, or one per bar like "A E"); default is
    the style's chorus progression. lead_instrument: the voice stand-in, e.g. harmonica, voice_oohs.
    Writes songs/<name>_tune_a.json ... and out/<name>/tune_a.mp3 ..., out/<name>/sheet.html."""
    lines = [x for x in (lyrics.splitlines() if isinstance(lyrics, str) else lyrics) if x.strip()]
    made = lyrics_mod.scores(lines, style, key, chords, n, tempo, grit, bars_per_line, lead_instrument, name)
    folder = OUT / _name(name)
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("tune_*.mp3"):                  # a smaller n must not leave old tunes behind
        old.unlink()
    tunes, s = [], None
    for k, (t, s) in enumerate(made):
        tag = chr(97 + k)
        rep = _render_named(f"{name}_tune_{tag}", s, soundfont)
        shutil.copy(rep["mp3"], folder / f"tune_{tag}.mp3")
        tunes.append({**t, "mp3": f"tune_{tag}.mp3", "score": f"{name}_tune_{tag}", "lufs": rep["lufs"]})
    sheet = folder / "sheet.html"
    sheet.write_text(lyrics_mod.sheet(name, key, s["tempo"], lines, tunes), "utf-8")
    return {"sheet": str(sheet), "folder": str(folder), "tunes": [
        {"tune": chr(65 + k), "shape": t["shape"], "about": t["about"], "mp3": str(folder / t["mp3"]),
         "score": t["score"], "lines": [{"text": x, "notes": " ".join(n[0] for n in ln["notes"])}
                                        for x, ln in zip(lines, t["lines"])]} for k, t in enumerate(tunes)]}


@mcp.tool()
@_plain_errors
def list_instruments(soundfont: str = "generaluser") -> dict:
    """Instrument names, part styles, chord qualities and the soundfonts you can render with.
    Each instrument shows the preset the chosen soundfont really has at that slot."""
    have = {(b, p): n for b, p, n in presets(rd.soundfont_path(soundfont))}
    return {
        "soundfonts": list(rd.SOUNDFONTS),
        "instruments": {k: (sampler.KITS[k]["credit"] + ("" if sampler.available(k) else " - NOT INSTALLED")
                            if k in sampler.KITS else have.get(v, "MISSING in this soundfont"))
                        for k, v in sc.INSTRUMENTS.items()},
        "parts_and_styles": sc.PARTS,
        "chord_qualities": list(sc.QUALITIES),
        "notes": "Notes are names like E4, F#3, Bb2 (C4 = middle C) or 'r' for a rest; 'E4+G#4' plays two at once.",
    }


@mcp.tool()
@_plain_errors
def write_score(name: str, score: dict | str) -> dict:
    """Check a score and save it as songs/<name>.json. Errors come back all at once.

    Format (JSON):
    {"title": "...", "tempo": 160, "beats_per_bar": 2|3|4 (quarter-note beats; waltz styles need 3),
     "count_in_bars": 1 (played on the drums track), "swing": 0 (0-1), "seed": 1,
     "tracks": {"<track>": {"instrument": "steel_guitar", "part": "comp|bass|drums|lead",
                "style": "<see list_instruments>", "level_db": 0, "pan": -1..1, "reverb": 0..1, "drive": 0..1 (grit), "legato": 0.92}},
     "sections": [{"name": "verse", "chords": ["E", "%", "A E", ...],   # one entry per bar; "A E" splits a bar; "%" repeats
                   "lead": {"<lead track>": [["B4", 1], ["G#4", 0.5], ["r", 0.5], ...]},   # [note, beats(, velocity)]
                   "styles": {"<track>": "<style for this section>"}, "mute": ["<track>"], "repeat": 1}],
     "form": ["verse", "chorus", ...]}   # optional play order by section name
    Comp, bass and drum tracks play the chords by style; lead tracks play the notes given, starting at
    the section's first beat. A pickup (notes before the bar line) goes at the end of the previous
    section's lead list, after a rest."""
    s = json.loads(score) if isinstance(score, str) else score
    sc.check(s)
    SONGS.mkdir(parents=True, exist_ok=True)
    p = SONGS / f"{_name(name)}.json"
    p.write_text(json.dumps(s, indent=1), "utf-8")
    secs = sc.arrangement(s)
    return {"saved": str(p), "bars": sum(len(x["chords"]) for x in secs) + s.get("count_in_bars", 0),
            "seconds": round(sc.duration_seconds(s), 1), "play_order": [x.get("name") for x in secs]}


@mcp.tool()
@_plain_errors
def get_score(name: str) -> dict:
    """Return a saved score."""
    return json.loads((SONGS / f"{_name(name)}.json").read_text("utf-8"))


@mcp.tool()
@_plain_errors
def render(name: str, soundfont: str = "generaluser", mute: list[str] | None = None,
           target_lufs: float = -16.0) -> dict:
    """Render songs/<name>.json to out/<name>/mix.mp3 (and .wav), with one WAV stem per track
    in out/<name>/stems. mute leaves tracks out of the mix (they are still rendered as stems)."""
    s = sc.load(SONGS / f"{_name(name)}.json")
    return rd.render(s, OUT / name, "mix", soundfont, tuple(mute or ()), target_lufs=target_lufs)


@mcp.tool()
@_plain_errors
def mix(name: str, levels_db: dict[str, float] | None = None, pans: dict[str, float] | None = None,
        drives: dict[str, float] | None = None,
        mute: list[str] | None = None, target_lufs: float = -16.0, out_name: str = "remix") -> dict:
    """Re-balance the last render of <name> from its stems, without re-rendering.
    levels_db, pans and drives override the score's per track (dB; -1 left .. +1 right; grit 0..1). Writes out/<name>/<out_name>.mp3."""
    last = json.loads((OUT / _name(name) / "mix.json").read_text("utf-8"))
    lv = {**last["levels_db"], **(levels_db or {})}
    dv = {**last.get("drives", {}), **(drives or {})}
    pn = {**last["pans"], **(pans or {})}
    for what, keys in (("levels_db", levels_db or {}), ("pans", pans or {}), ("drives", drives or {}), ("mute", mute or [])):
        unknown = sorted(set(keys) - set(last["stems"]))
        if unknown:
            raise ValueError(f"{what} names unknown tracks {unknown}; tracks are {sorted(last['stems'])}")
    muted = set(last.get("mute", [])) | set(mute or [])
    stems = {k: v for k, v in last["stems"].items() if k not in muted}
    rep = rd.mix(stems, OUT / name / _name(out_name), lv, pn, target_lufs, roles=last.get("roles"), drives=dv)
    rep.update(levels_db=lv, pans=pn, drives=dv, mute=sorted(muted))
    return rep


@mcp.tool()
@_plain_errors
def analyse_beat(wav_path: str) -> dict:
    """Find claps or taps in a WAV file; return the hit times and the tempo (bpm) they imply,
    plus how steady they were (standard deviation of the gaps, ms)."""
    return beat.analyse(wav_path)


@mcp.tool()
@_plain_errors
def hum_to_notes(wav_path: str, tempo: float = 120.0, grid_beats: float = 0.25) -> dict:
    """Turn a hummed or sung melody (one voice, WAV) into lead notes for a score: 'lead' is
    [[note, beats], ...] at the given tempo, quantised to grid_beats (0.25 = sixteenths at 4/4).
    Hum each note with a small breath between repeats of the same pitch. Check the result by
    rendering it; humming is loose, so expect to tidy a note or two."""
    return hum.transcribe(wav_path, tempo, grid_beats)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
