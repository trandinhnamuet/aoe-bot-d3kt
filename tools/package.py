"""The release zip: AoESolo.zip with one folder AoESolo\\ (AoESolo.exe + HUONG_DAN.txt), so extracting it
gives a folder instead of loose files (07/11, 1.2.30).

    python tools/package.py [out.zip]        (default: AoESolo.zip at the repo root, from dist\\AoESolo\\AoESolo.exe)

The in-app updater (launcher/updater.py swap) takes any entry ending in AoESolo.exe and writes the other files by
their base name, so older launchers update from this layout too."""
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = "AoESolo"
FILES = [(os.path.join(ROOT, "dist", "AoESolo", "AoESolo.exe"), "AoESolo.exe"),
         (os.path.join(ROOT, "HUONG_DAN.txt"), "HUONG_DAN.txt")]


def main(argv):
    out = argv[1] if len(argv) > 1 else os.path.join(ROOT, "AoESolo.zip")
    tmp = out + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr(zipfile.ZipInfo(FOLDER + "/"), b"")
        for src, name in FILES:
            z.write(src, FOLDER + "/" + name)
    os.replace(tmp, out)
    with zipfile.ZipFile(out) as z:
        for i in z.infolist():
            print("%-28s %10d" % (i.filename, i.file_size))
    print(out, os.path.getsize(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
