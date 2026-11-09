"""End-to-end over the real MCP stdio transport: spawn the server, call every tool.
Usage: .venv/Scripts/python tests/e2e_stdio.py"""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent


async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "bandbox.server"], cwd=str(ROOT))
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        tools = [t.name for t in (await s.list_tools()).tools]
        print("tools:", tools)

        async def call(tool, **args):
            res = await s.call_tool(tool, args)
            text = res.content[0].text if res.content else ""
            print(f"{tool}: {'ERROR ' if res.is_error else ''}{text[:600]}")
            return res, text

        await call("list_instruments", soundfont="musescore")
        score = json.loads((ROOT / "songs" / "lights_out_v3.json").read_text("utf-8"))
        bad = json.loads(json.dumps(score)); bad["sections"][0]["chords"][0] = "H7"
        res, _ = await call("write_score", name="e2e_bad", score=bad)
        assert res.is_error, "a bad chord must be refused"
        res, _ = await call("write_score", name="e2e_lights_out", score=score)
        assert not res.is_error
        res, text = await call("render", name="e2e_lights_out")
        assert not res.is_error and Path(json.loads(text)["mp3"]).exists()
        res, text = await call("mix", name="e2e_lights_out", levels_db={"harmonica": -60}, out_name="no_harp")
        assert not res.is_error
        res, text = await call("analyse_beat", wav_path=str(ROOT / "out" / "e2e_lights_out" / "stems" / "drums.wav"))
        assert abs(json.loads(text)["tempo_bpm"] - 160) < 4
        res, text = await call("hum_to_notes", wav_path=str(ROOT / "out" / "e2e_lights_out" / "stems" / "harmonica.wav"), tempo=160)
        assert not res.is_error
        lead = [n for n in json.loads(text)["lead"] if n[0] != "r"]
        # a harmonica takes no breath between quick repeats, so only pitch order and count are firm here;
        # note-for-note accuracy on a real hum is gated in tests/test_score.py
        changes = [n[0] for k, n in enumerate(lead) if k == 0 or n[0] != lead[k - 1][0]]
        assert changes[:5] == ["B4", "G#4", "F#4", "E4", "B4"] and 0.85 * 84 <= len(lead) <= 1.15 * 84, lead[:8]
        res, _ = await call("mix", name="e2e_lights_out", levels_db={"harp": -60})
        assert res.is_error, "a misspelled track name must be refused"

        res, text = await call("list_styles")
        assert "trucker" in json.loads(text)
        res, text = await call("arrange", name="e2e_trucker", style="trucker", grit=0.85)
        assert not res.is_error and Path(json.loads(text)["render"]["mp3"]).exists()
        res, _ = await call("arrange", name="e2e_x", style="polka")
        assert res.is_error, "an unknown style must be refused"
        words = "Lights out, and it's runnin'.\nI'm asleep, and nothin's lost."
        res, text = await call("set_lyrics", lyrics=words)
        assert json.loads(text)["lines"][0]["syllables"].startswith("LIGHTS OUT")
        res, text = await call("melody_options", name="e2e_tunes", lyrics=words, n=2, chords=["E", "B7 E"])
        out = json.loads(text)
        assert not res.is_error and len(out["tunes"]) == 2 and Path(out["sheet"]).exists()
        assert all(Path(t["mp3"]).exists() for t in out["tunes"])

        res, text = await call("arrange", name="e2e_teentaal", style="teentaal", key="D")
        out = json.loads(text)
        assert not res.is_error and Path(out["render"]["mp3"]).exists() and Path(out["render"]["bols_sheet"]).exists()
        tihai = json.loads((ROOT / "songs" / "teentaal_tihai.json").read_text("utf-8"))
        bad = json.loads(json.dumps(tihai)); bad["sections"][1]["bols"]["tabla"] = "dha dhom"
        res, text = await call("write_score", name="e2e_bad_bols", score=bad)
        assert res.is_error and "dhom" in text, "an unknown bol must be refused by name"
        res, _ = await call("write_score", name="e2e_tihai", score=tihai)
        assert not res.is_error
        print("E2E PASS")


asyncio.run(main())
