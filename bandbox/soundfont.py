"""Read the preset list (bank, program, name) out of a .sf2 / .sf3 SoundFont.

Why this exists: list_instruments must show what a SoundFont really holds (a
General MIDI name is a promise, not a guarantee - a bank may lack the brush kit).
Pure RIFF walk, no dependencies; sf3 differs from sf2 only in sample coding, so
the preset header chunk ("phdr") is read the same way for both.
"""
import struct
from pathlib import Path


def _chunks(buf, start, end):
    i = start
    while i + 8 <= end:
        cid, size = buf[i:i + 4], struct.unpack_from("<I", buf, i + 4)[0]
        yield cid, i + 8, size
        i += 8 + size + (size & 1)


def presets(path):
    """Return a sorted list of (bank, program, name). Reads the whole file."""
    buf = Path(path).read_bytes()
    if buf[:4] != b"RIFF" or buf[8:12] != b"sfbk":
        raise ValueError(f"{path}: not a SoundFont (no RIFF sfbk header)")
    for cid, off, size in _chunks(buf, 12, len(buf)):
        if cid == b"LIST" and buf[off:off + 4] == b"pdta":
            for sid, soff, ssize in _chunks(buf, off + 4, off + size):
                if sid == b"phdr":
                    out = []
                    for r in range(ssize // 38 - 1):          # last record is the EOP terminator
                        name, prog, bank = struct.unpack_from("<20sHH", buf, soff + r * 38)
                        out.append((bank, prog, name.split(b"\0")[0].decode("latin-1").strip()))
                    return sorted(out)
    raise ValueError(f"{path}: no preset header (phdr) chunk")
