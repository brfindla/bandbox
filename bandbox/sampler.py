"""One-shot drum sampler: plays a drums track from a multi-mic sampled kit (SFZ mappings).

Why our own and not sfizz (BSD-2): its Windows release ships plug-ins, not a renderer we
can call, and drums need only a fraction of SFZ - one-shot samples picked by key, velocity
layer and round robin. This reads exactly that subset of the kit's own mapping files
(<group>/<region>, key/lokey/hikey, lovel/hivel, seq_position, sample) and ignores the rest.
Hits the kit has no sample for (ride, crash, tambourine) are rendered by FluidSynth with the
General MIDI kit and summed in, so every drum style still plays in full.
"""
import os
import re
from pathlib import Path

import mido
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

SR = 44100
ROOT = Path(__file__).resolve().parent.parent
KIT_ROOT = Path(os.environ.get("BANDBOX_VENDOR", ROOT / "vendor")) / "drumkits"

# name -> kit folder, mics as {mic: (gain, pan -1 left..+1 right)}, and credit line. The blend is the
# kit's own default in Kit.sfz: close, front and an equal hard-left/right side + overhead pair.
# (Its mic delays scale to zero at the default "Fi" setting, so there are none here.)
KITS = {
    "gogodze_kit": {"dir": "Gogodze_Phu_vol_II",
                    "mics": {"kick": (1.0, 0), "snare": (1.0, 0), "front": (1.0, 0), "oh": (1.0, 1), "side": (1.0, -1)},
                    "credit": "Gogodze Phu Vol II by Karoryfer Samples (CC0)"},
    "gogodze_retro_kit": {"dir": "Gogodze_Phu_vol_II", "mics": {"retro": (1.0, 0)},
                          "credit": "Gogodze Phu Vol II by Karoryfer Samples (CC0), retro mic"},
}
# General MIDI drum note -> the kit's piece (mapping file prefix)
# (no open hat: the kit chokes it with a closed hat through rules this sampler does not copy, so
# note 46 plays from the General MIDI kit, which chokes it itself)
PIECES = {36: "kick", 37: "snare", 38: "snare", 40: "snare", 41: "toml", 43: "tomm", 45: "tomh",
          42: "ht", 44: "hf"}
RETRO_HPF = {p: butter(2, 200 if p in ("ht", "hf") else 150, "highpass", fs=SR, output="sos") for p in set(PIECES.values())}


def _gain(piece, mic):
    """Kit.sfz levels: the kick in every mic but its own at 60%, the toms in the retro mic at 60%."""
    return 0.6 if (piece == "kick" and mic != "kick") or (piece.startswith("tom") and mic == "retro") else 1.0


def available(kit):
    return (KIT_ROOT / KITS[kit]["dir"] / "Programs").is_dir()


def _parse(path):
    """SFZ mapping file -> list of region dicts (group opcodes inherited)."""
    text = re.sub(r"//[^\n]*", "", path.read_text("utf-8", errors="replace"))
    regions, group, cur = [], {}, None
    for tok in re.findall(r"<\w+>|\w+=\S+", text):
        if tok == "<group>":
            group, cur = {}, None
        elif tok == "<region>":
            cur = dict(group); regions.append(cur)
        elif tok.startswith("<"):
            group, cur = {}, None
        else:
            k, v = tok.split("=", 1)
            (cur if cur is not None else group)[k] = v
    for r in regions:
        if "key" in r:
            r["lokey"] = r["hikey"] = r["key"]
    return regions


class Kit:
    def __init__(self, name):
        spec = KITS[name]
        self.base = KIT_ROOT / spec["dir"] / "Programs"
        self.mics = spec["mics"]
        self._layers = {}           # note -> [(lovel, hivel, [[(mic, sample path)] per round robin])]
        self._wav = {}              # (note, layer, rr) -> mixed stereo float32 (n, 2)
        self._rr = {}

    def layers(self, note):
        if note not in self._layers:
            out = {}
            for mic in self.mics:
                f = self.base / "mappings" / f"{PIECES[note]}_{mic}_mic.sfz"
                for r in _parse(f):
                    if int(r.get("lokey", -1)) <= note <= int(r.get("hikey", -1)) and "locc4" not in r and "hicc4" not in r:
                        key = (int(r.get("lovel", 0)), int(r.get("hivel", 127)))
                        rr = int(r.get("seq_position", 1)) - 1
                        slots = out.setdefault(key, {})
                        slots.setdefault(rr, []).append((mic, (self.base / r["sample"]).resolve()))   # paths are relative to Programs/
            self._layers[note] = [(lo, hi, [slots[k] for k in sorted(slots)]) for (lo, hi), slots in sorted(out.items())]
            if not self._layers[note]:
                raise ValueError(f"kit has no samples for note {note} in {self.base}")
        return self._layers[note]

    def hit(self, note, vel):
        """Stereo float32 (n, 2) for one hit: velocity layer, then the next round robin."""
        lays = self.layers(note)
        li = next((i for i, (lo, hi, _) in enumerate(lays) if lo <= vel <= hi), len(lays) - 1)
        lo, hi, rrs = lays[li]
        k = self._rr.get((note, li), 0) % len(rrs)
        self._rr[(note, li)] = k + 1
        if (note, li, k) not in self._wav:
            parts = []
            for mic, p in rrs[k]:
                gain, pan = self.mics[mic]
                x, sr = sf.read(str(p), dtype="float32", always_2d=True)
                if sr != SR:
                    raise ValueError(f"{p}: {sr} Hz, expected {SR}")
                x = x.mean(axis=1)
                if mic == "retro":                                # Kit.sfz: hpf_2p at 150 Hz (hats 200)
                    x = sosfilt(RETRO_HPF[PIECES[note]], x)
                a = (pan + 1) * np.pi / 4                         # equal-power pan
                parts.append(gain * _gain(PIECES[note], mic) * x[:, None] * [np.cos(a), np.sin(a)])
            mix = np.zeros((max(len(x) for x in parts), 2), np.float32)
            for x in parts:
                mix[:len(x)] += x
            self._wav[(note, li, k)] = mix
        return self._wav[(note, li, k)] * min(1.0, vel / max(hi, 1))      # Kit.sfz amp_velcurve: linear


CYMBALS_UNDER_KIT_DB = -8.0     # GM ride/crash level relative to the sampled kit


def _match(y, ref, offset_db):
    """Gain that puts y's level (RMS over its sounding part) offset_db from ref's.
    FluidSynth and the kit's samples are not level-matched: unscaled, the ride came out 32 dB under."""
    def level(v):
        v = np.abs(v.reshape(len(v), -1)).max(axis=1)
        act = v[v > 1e-4]
        return np.sqrt(np.mean(act ** 2)) if len(act) else 0.0
    ly, lr = level(y), level(ref)
    if not lr:
        return 1.0                  # no kit hits to match (a ride-only part): play the cymbals as rendered
    return 0.0 if not ly else lr / ly * 10 ** (offset_db / 20)


def render_track(mid_path, wav_path, kit_name, fallback):
    """Drums MIDI -> stereo float WAV. fallback(mid, wav) renders the notes the kit lacks."""
    if not available(kit_name):
        raise FileNotFoundError(f"drum kit {kit_name} not installed under {KIT_ROOT} - run fetch_vendor.py")
    kit = Kit(kit_name)
    src = mido.MidiFile(mid_path)
    hits, t = [], 0.0
    for m in src:                                     # iterating a MidiFile yields seconds
        t += m.time
        if m.type == "note_on" and m.velocity > 0 and m.note in PIECES:
            hits.append((t, m.note, m.velocity))
    out = np.zeros((int((src.length + 3) * SR), 2), np.float32)
    for t, note, vel in hits:
        x = kit.hit(note, vel)
        i = int(t * SR); j = min(len(out), i + len(x))
        out[i:j] += x[:j - i]
    # the rest (ride, crash, tambourine...) through the General MIDI kit
    rest = mido.MidiFile(type=0, ticks_per_beat=src.ticks_per_beat)
    trk, carry = mido.MidiTrack(), 0
    for m in src.tracks[0]:
        if m.type in ("note_on", "note_off") and m.note in PIECES:
            carry += m.time
            continue
        trk.append(m.copy(time=m.time + carry)); carry = 0
    rest.tracks.append(trk)
    if any(m.type == "note_on" and m.velocity > 0 for m in trk):
        rest_mid = Path(wav_path).with_suffix(".rest.mid")
        rest_wav = Path(wav_path).with_suffix(".rest.wav")
        rest.save(rest_mid)
        fallback(rest_mid, rest_wav)
        y, _ = sf.read(str(rest_wav), dtype="float32", always_2d=True)
        n = max(len(out), len(y))
        mix = np.zeros((n, 2), np.float32)
        mix[:len(out)] += out
        mix[:len(y)] += y * _match(y, out, CYMBALS_UNDER_KIT_DB)
        rest_mid.unlink(); rest_wav.unlink()
    else:
        mix = out
    sf.write(str(wav_path), mix, SR, subtype="FLOAT")
