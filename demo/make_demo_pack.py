"""Demo pack: the "Lights Out" v3b chorus played by different line-ups, so a listener can pick one.

Usage:  .venv/Scripts/python demo/make_demo_pack.py [out_dir]
Each clip = one-bar count-in + the 12-bar chorus + the 2-bar turnaround at 160 bpm.
"""
import copy
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bandbox import render, score  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "demo_pack"
BASE = score.load(ROOT / "songs" / "lights_out_v3b.json")
BASE["form"] = ["chorus", "turnaround"]


def variant(**tracks):
    """variant(guitar={...}, drums={...}): override fields of named tracks; lead=<instrument> swaps the lead."""
    s = copy.deepcopy(BASE)
    lead = tracks.pop("lead", None)
    for name, fields in tracks.items():
        s["tracks"][name].update(fields)
    if lead:
        s["tracks"][lead] = dict(s["tracks"].pop("harmonica"), instrument=lead)
        for sec in s["sections"]:
            if "lead" in sec:
                sec["lead"] = {lead: sec["lead"]["harmonica"]}
    return score.check(s)


A, B = "generaluser", "musescore"
DIRTY_GTR = {"instrument": "clean_guitar", "drive": 0.5}
CLIPS = [  # (file, soundfont, score, what it is)
    ("01_gritty_A", A, variant(), "Twangy electric guitar with some dirt, upright bass, real drum kit (sticks, train beat, a bit driven), harmonica. Set A."),
    ("02_gritty_B", B, variant(), "Same line-up, set B."),
    ("03_brushes_A", A, variant(drums={"instrument": "brush_kit", "drive": 0.3}), "Real brushes on the train beat instead of sticks. Set A."),
    ("04_brushes_B", B, variant(drums={"instrument": "brush_kit", "drive": 0.3}), "Brushes, set B."),
    ("05_slap_bass_A", A, variant(bass={"instrument": "slap_bass"}), "Slap bass instead of upright. Set A."),
    ("06_more_dirt_B", B, variant(guitar={"drive": 0.85}, drums={"drive": 0.6}, harmonica={"drive": 0.35}),
     "Everything pushed harder: more dirt on guitar, drums and harmonica. Set B."),
    ("07_overdrive_guitar_A", A, variant(guitar={"instrument": "overdrive_guitar", "drive": 0.2}, drums={"style": "boom_chick"}),
     "Overdriven guitar, plain boom-chick drums: more rock. Set A."),
    ("08_room_kit_boomchick_B", B, variant(drums={"instrument": "room_kit", "style": "boom_chick", "drive": 0.5}),
     "Room drum kit, boom-chick beat, driven. Set B."),
    ("09_fiddle_lead_A", A, variant(lead="fiddle"), "Fiddle plays the tune. Set A."),
    ("10_steel_acoustic_A", A, variant(guitar={"instrument": "steel_guitar", "drive": 0.0}, drums={"instrument": "brush_kit", "drive": 0}),
     "The clean acoustic version (first demo pack style), for comparison. Set A."),
    ("11_sampled_kit_train_A", A, variant(drums={"instrument": "gogodze_kit", "drive": 0.3}),
     "NEW: real sampled drum kit (Gogodze Phu Vol II, close + overhead mics) on the train beat. Set A."),
    ("12_sampled_kit_retro_B", B, variant(drums={"instrument": "gogodze_retro_kit", "drive": 0.4}),
     "NEW: same kit through its lo-fi retro mic, more dirt. Set B."),
    ("13_sampled_kit_boomchick_slap_A", A, variant(drums={"instrument": "gogodze_kit", "style": "boom_chick", "drive": 0.4},
                                                   bass={"instrument": "slap_bass"}, guitar={"drive": 0.7}),
     "NEW: sampled kit, boom-chick, slap bass, dirtier guitar. Set A."),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    work = ROOT / "out" / "_demo_work"
    index = []
    for name, font, s, what in CLIPS:
        rep = render.render(s, work / name, name, soundfont=font)
        shutil.copy(rep["mp3"], OUT / f"{name}.mp3")
        (OUT / f"{name}.score.json").write_text(json.dumps(s, indent=1), "utf-8")
        index.append((name, what))
        print(name, rep["seconds"], "s", rep["lufs"], "LUFS")
    rows = "\n".join(f'<div class="c"><b>{n}</b><br>{w}<br><audio controls preload="none" src="{n}.mp3"></audio></div>'
                     for n, w in index)
    (OUT / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Lights Out demo pack</title><style>'
        'body{font:16px system-ui;max-width:640px;margin:20px auto;padding:0 16px;background:#fff;color:#111}'
        '.c{margin:14px 0;padding:10px;border:1px solid #ccc;border-radius:6px}audio{width:100%;margin-top:6px}'
        '@media(prefers-color-scheme:dark){body{background:#111;color:#eee}.c{border-color:#444}}</style>'
        '<h1>Lights Out v3b: pick your band</h1><p>Set A = GeneralUser GS 2.0.3. Set B = MuseScore General 0.2. '
        'Each clip: count-in, the chorus, then the new 2-bar harmonica turnaround, at 160 bpm (about 27 s).</p>'
        + rows, "utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
