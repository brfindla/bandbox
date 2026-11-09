"""Download the third-party pieces bandbox plays through, from their original sources, and
check each against the SHA-256 recorded here. bandbox ships none of them (see THIRD_PARTY.md).

Usage:  .venv/Scripts/python -m bandbox.fetch_vendor [--only fluidsynth,generaluser,musescore,gogodze,tabla] [--check]
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
FS_UID = {"mmiron": 1565498, "ajaysm": 2385996}


def FS(user, sound):
    """A Freesound sound's public HQ preview (OGG); the original WAV needs a Freesound login."""
    return f"https://cdn.freesound.org/previews/{sound // 1000}/{sound}_{FS_UID[user]}-hq.ogg"


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
    # tabla strokes, one file per take: mmiron "tabla bols" (CC0) and ajaysm "Tabla Strokes" (CC BY 4.0).
    # tabla/_tune/ holds a take used only to measure that drum's note.
    "tabla": [
        (FS("mmiron", 130404), "tabla/ge/mmiron_130404.ogg", 28248, "728685d12f9c252ee329199d61cc530d8d389ef877388f26dff4c99634f4843e", None),
        (FS("mmiron", 130405), "tabla/ge/mmiron_130405.ogg", 30711, "2a1a2af88716c845cc7cc4d7e52bb619245f1426aaeb668cf5f644b4d08f4cb4", None),
        (FS("mmiron", 130406), "tabla/ge/mmiron_130406.ogg", 10323, "5be5737a224c5be5a56b5ef26fa11e8dd02770f5e496f63f1563c3b1c3b13a9f", None),
        (FS("mmiron", 130408), "tabla/ge/mmiron_130408.ogg", 25574, "0a647f47ae47bc6a27524d414aff9e88d227520a2bdc79c8e936ab8e98e4b14f", None),
        (FS("mmiron", 130409), "tabla/ge/mmiron_130409.ogg", 39504, "d579a0cfb0e39ea2b87d8a52c1ada0d51c97bd9d3d1a0984c27ebc6715d42703", None),
        (FS("mmiron", 130410), "tabla/ge/mmiron_130410.ogg", 39152, "4ceea873677063ac39738254bfcff37ce4dfa9bab210a3ffb1bab773c70f54e8", None),
        (FS("mmiron", 130411), "tabla/ge/mmiron_130411.ogg", 12072, "5bbea145e755271deac976b93a32cceedcd64910ec77b09430870164a9e43689", None),
        (FS("mmiron", 130414), "tabla/ge/mmiron_130414.ogg", 10053, "525592d12f38d0193755e0822a265b62892f0d505bee7f490a74a3a7cf0d37fb", None),
        (FS("mmiron", 130413), "tabla/ke/mmiron_130413.ogg", 4879, "627a9ad863145db9f6258631ef3db745a9c50dd13da7cdb9fc096201c4e060a9", None),
        (FS("mmiron", 130423), "tabla/ke/mmiron_130423.ogg", 5154, "443a8efd29fa896c0058dd34c7a729a3e8c7a854b2cd347d8f006c6603b75c2c", None),
        (FS("mmiron", 130424), "tabla/ke/mmiron_130424.ogg", 4935, "ea7cf993edabd3d860a8b44e76c4932454189baa7afda2d5ee10267385a4b4d9", None),
        (FS("ajaysm", 171901), "tabla/ke/ajaysm_171901.ogg", 6840, "29f43eda70206fafcfe9c96331ee1a07d810c8444fa00505ae030117b7428c14", None),
        (FS("ajaysm", 171906), "tabla/ke/ajaysm_171906.ogg", 9061, "47afcab94c40348adfdeb814582d4a3e894ef69f06c4f08978a51bc115e9df95", None),
        (FS("mmiron", 130421), "tabla/na/mmiron_130421.ogg", 11258, "adb244e66c871cb87f4949196d6fbb345b75a3f7ad298248ed27813694052d82", None),
        (FS("mmiron", 130428), "tabla/na/mmiron_130428.ogg", 6750, "63b8fb599d337a037cd77374dcbba1cddf0e29bc90c392b109cd82542c101254", None),
        (FS("ajaysm", 171905), "tabla/na/ajaysm_171905.ogg", 11057, "c881f871ceb62b77972d76816650c62f0be13c0bc49e60b985563868e70197a8", None),
        (FS("ajaysm", 171911), "tabla/tin/ajaysm_171911.ogg", 11548, "b2761ca03418eb2fd4c214643571b7cead0f926cb14ee2a667ba912002300dd0", None),
        (FS("mmiron", 130416), "tabla/tun/mmiron_130416.ogg", 25942, "72805cbf910ed15dbaa8d14f12af136c28ee06763c0a75291665115fb1e7f4ed", None),
        (FS("mmiron", 130419), "tabla/tun/mmiron_130419.ogg", 29729, "972225489f3c30c056988ce3166ae47f49987045be8629348dcbc1e3385f73e5", None),
        (FS("mmiron", 130420), "tabla/tun/mmiron_130420.ogg", 23729, "6362fc36a658630117b6b209ae17ca266a7a9bc2638e17b00e3acd956744245a", None),
        (FS("ajaysm", 171909), "tabla/_tune/ajaysm_171909.ogg", 10208, "bb9291568793f13c550280f1f3556e985fe96be9b89c2f3b463cf939d7629591", None),
        (FS("mmiron", 130429), "tabla/te/mmiron_130429.ogg", 6139, "b009be9e98ceb47f7270d781a91010e284b099ef920e55b218b4bd2602093c76", None),
        (FS("mmiron", 130418), "tabla/te/mmiron_130418.ogg", 7906, "ad6310f0e62c5b4ada0cfac35957f7e2e71140bec836b6d9c6426a7769e87bd4", None),
        (FS("mmiron", 130415), "tabla/te/mmiron_130415.ogg", 7078, "9d9a85021b4f66823ce7fe154f1f48f9ed7a31ad0502fccb26ef824fc718262e", None),
        (FS("mmiron", 130417), "tabla/te/mmiron_130417.ogg", 5931, "55199488583945f1f84b46c4f49be6116f97b79b697849e6ca973d1f5f84cc04", None),
        (FS("ajaysm", 171913), "tabla/te/ajaysm_171913.ogg", 6755, "1bc4e8454a2fe1021884ebe3fd236af6225518b0341a5085ea23e98cb9e74212", None),
        (FS("mmiron", 130427), "tabla/re/mmiron_130427.ogg", 7410, "2ab1e0675d474ab94d1ba1e1b7796d6e4209fb431c84d62fd5285326808bc427", None),
        (FS("ajaysm", 171907), "tabla/re/ajaysm_171907.ogg", 7547, "c0f37d8ecd3c0882ad94cd50d41fba133909ac3c424bf5015a77e3a0c48e3427", None),

    ],
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
