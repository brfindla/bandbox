"""Download the third-party pieces bandbox plays through, from their original sources, and
check each against the SHA-256 recorded here. bandbox ships none of them (see THIRD_PARTY.md).

Usage:  .venv/Scripts/python -m bandbox.fetch_vendor [--only fluidsynth,generaluser,musescore,gogodze] [--check]
--check downloads nothing: it re-hashes each file and checks every file unpacked from an archive
is there at its full size. A download whose hash does not match is deleted, nothing unpacked.

GeneralUser GS is the one manual step: its author asks that his download files not be linked
to directly, so this script tells you where to get it and then checks what you put in place.
"""
import argparse
import hashlib
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor"
MS = "https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General"
GU_PAGE = "https://www.schristiancollins.com/generaluser.php"

# name -> files: (url or None for a manual step, path under vendor/, size bytes, sha256,
#                 (unpack into dir under vendor/, drop the archive's top folder) or None)
ITEMS = {
    "fluidsynth": [
        ("https://github.com/FluidSynth/fluidsynth/releases/download/v2.6.1/fluidsynth-v2.6.1-win10-x64-cpp11.zip",
         "downloads/fluidsynth-v2.6.1-win10-x64-cpp11.zip", 2727529,
         "fab7a2e4b85675b66970f97a39bbc239729c5e0f237198b5922a6a73cbc8677c", ("fluidsynth", True))],
    "generaluser": [
        (None, "soundfonts/GeneralUser-GS.sf2", 32319396,
         "9575028c7a1f589f5770fccc8cff2734566af40cd26ed836944e9a5152688cfe", None),
        (None, "soundfonts/GeneralUser-GS_LICENSE.txt", 2317,
         "7b32efefdf95ce38a043799f0659853ddc00fbaa14d8c50f0aca16b9b8b405be", None)],
    "musescore": [
        (f"{MS}/MuseScore_General.sf3", "soundfonts/MuseScore_General.sf3", 39900972,
         "5b85b6c2c61d10b2b91cddd41efcce7b25cd31c8271d511c73afafbef20b6fa3", None),
        (f"{MS}/MuseScore_General_License.md", "soundfonts/MuseScore_General_License.md", 3419,
         "5ad8d737e13c7f01f5b9674872a82a92b4ba253603e8ed14b9db12293550b4b9", None)],
    "gogodze": [
        ("https://github.com/sfzinstruments/karoryfer.gogodze-phu-vol-ii/releases/download/v1.001/"
         "Karoryfer_Gogodze_Phu_vol_II.v1.001.zip",
         "drumkits/Karoryfer_Gogodze_Phu_vol_II.v1.001.zip", 139517148,
         "3ff7728f82001af2144e42d94c29770cded57389018e27d4a281f1a0496f7d49", ("drumkits", False))],
}
MANUAL = {"generaluser": f"GeneralUser GS 2.0.3: download it from {GU_PAGE} (it leads to the author's GitHub; "
                         "'Code > Download ZIP' there). Put GeneralUser-GS.sf2 in vendor/soundfonts/, and its "
                         "documentation/LICENSE.txt beside it as GeneralUser-GS_LICENSE.txt, then run --check."}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _ok(p, size, digest):
    return p.exists() and p.stat().st_size == size and sha256(p) == digest


def _members(zpath, dest, strip):
    """(zip entry, where it lands) for every file in the archive; refuses paths outside dest (zip-slip)."""
    dest = dest.resolve()
    with zipfile.ZipFile(zpath) as z:
        out = []
        for i in z.infolist():
            if i.is_dir():
                continue
            to = (dest / (i.filename.split("/", 1)[1] if strip else i.filename)).resolve()
            if not to.is_relative_to(dest):
                raise ValueError(f"{zpath}: unsafe path in archive: {i.filename}")
            out.append((i, to))
    return out


def _unpacked(zpath, dest, strip):
    return all(to.is_file() and to.stat().st_size == i.file_size for i, to in _members(zpath, dest, strip))


def _unzip(zpath, dest, strip):
    members = _members(zpath, dest, strip)               # every path checked before anything is written
    with zipfile.ZipFile(zpath) as z:
        for i, to in members:
            to.parent.mkdir(parents=True, exist_ok=True)
            with z.open(i) as src, open(to, "wb") as f:
                shutil.copyfileobj(src, f)


def fetch(name, check_only=False):
    for url, rel, size, digest, unpack in ITEMS[name]:
        p = VENDOR / rel
        if url is None:                                   # a manual step: check what is there
            if not p.exists():
                raise FileNotFoundError(f"{name}: {p} missing. {MANUAL[name]}")
            if not _ok(p, size, digest):
                print(f"{name}: {p.name} is not the tested file (sha256 {digest[:12]}...); it should still play")
                continue
        elif check_only:
            if not _ok(p, size, digest):
                raise ValueError(f"{name}: {p} missing or its sha256 differs from {digest}")
        elif not _ok(p, size, digest):
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(p.suffix + ".part")
            print(f"{name}: downloading {url} ({size / 1e6:.1f} MB)")
            with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f)
            if not _ok(tmp, size, digest):
                got, n = sha256(tmp), tmp.stat().st_size
                tmp.unlink()
                raise ValueError(f"{name}: download from {url} has sha256 {got} / {n} bytes, expected {digest} / "
                                 f"{size}. Deleted, nothing unpacked. Retry, or check the source has not changed.")
            tmp.replace(p)
        print(f"{name}: {p.name} OK (sha256 matches)")
        if unpack and not _unpacked(p, VENDOR / unpack[0], unpack[1]):
            if check_only:
                raise FileNotFoundError(f"{name}: files unpacked from {p.name} are missing or damaged; "
                                        f"run fetch_vendor --only {name}")
            print(f"{name}: unpacking into vendor/{unpack[0]}")
            _unzip(p, VENDOR / unpack[0], unpack[1])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", default=",".join(ITEMS))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    todo = []
    for name in a.only.split(","):
        if name not in ITEMS:
            sys.exit(f"unknown item {name}; choose from {list(ITEMS)}")
        try:
            fetch(name, a.check)
        except FileNotFoundError as e:
            if name not in MANUAL:
                raise
            todo.append(str(e))
    if todo:
        sys.exit("One step is yours:\n" + "\n".join(todo))


if __name__ == "__main__":
    main()
