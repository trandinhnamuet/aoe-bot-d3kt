"""The release zips, each with one folder AoESolo\\ so extracting gives a folder instead of loose files (07/11):

    AoESolo.zip       AoESolo.exe + HUONG_DAN.txt (the in-app updater downloads this one)
    AoESolo-full.zip  the same + the Games folder (the game, next to AoESolo.exe: the launcher finds it there; 12/11)

    python tools/package.py [out_dir]        (default: the repo root, from dist\\AoESolo\\AoESolo.exe)

launcher/updater.py takes AoESolo.zip and its entry ending in AoESolo.exe. Older launchers take the first .zip
asset of the release and write every other entry by its base name - so AoESolo.zip must be uploaded FIRST and
must never hold the Games folder."""
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = "AoESolo"
FILES = [(os.path.join(ROOT, "dist", "AoESolo", "AoESolo.exe"), "AoESolo.exe"),
         (os.path.join(ROOT, "HUONG_DAN.txt"), "HUONG_DAN.txt")]
GAMES = os.path.join(ROOT, "Games")


def write(out, with_games):
    tmp = out + ".tmp"
    n = 0
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr(zipfile.ZipInfo(FOLDER + "/"), b"")
        for src, name in FILES:
            z.write(src, FOLDER + "/" + name)
        if with_games:
            for d, dirs, names in os.walk(GAMES):
                dirs.sort()
                rel = os.path.relpath(d, ROOT).replace(os.sep, "/")
                z.writestr(zipfile.ZipInfo(FOLDER + "/" + rel + "/"), b"")
                for f in sorted(names):
                    z.write(os.path.join(d, f), FOLDER + "/" + rel + "/" + f)
                    n += 1
    os.replace(tmp, out)
    print(out, os.path.getsize(out), "bytes", "(+ %d files of Games)" % n if with_games else "")


def main(argv):
    out_dir = argv[1] if len(argv) > 1 else ROOT
    write(os.path.join(out_dir, "AoESolo.zip"), False)
    if os.path.isdir(GAMES):
        write(os.path.join(out_dir, "AoESolo-full.zip"), True)
    else:
        print("no Games folder: AoESolo-full.zip skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
