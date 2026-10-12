"""Build dist/AoESolo: AoESolo.exe (+ embedded hook DLL) next to a copy of the AoE-HD game folder.

Usage:  .venv\\Scripts\\python build.py [--no-game]
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
GAME_SRC = os.path.join(os.path.dirname(ROOT), "AoE-HD")
DIST = os.path.join(ROOT, "dist", "AoESolo")
SKIP_DIRS = {"Screenshot", "Screenshots"}


def run(cmd, **kw):
    print(">", " ".join(cmd))
    subprocess.check_call(cmd, **kw)


def build_dll():
    run([PY, "-m", "ziglang", "cc", "-target", "x86-windows-gnu", "-shared", "-O2", "-o",
         os.path.join(ROOT, "hook", "aoehook.dll"), os.path.join(ROOT, "hook", "aoehook.c"),
         "-luser32", "-lkernel32", "-lpsapi", "-ladvapi32"])


def build_exe():
    policy = os.path.join(ROOT, "launcher", "rl", "policies", "herd_push.json")   # the learned herd push (optional)
    data = ["--add-data", policy + os.pathsep + os.path.join("rl", "policies")] if os.path.exists(policy) else []
    run([PY, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed", "--name", "AoESolo",
         "--paths", os.path.join(ROOT, "launcher"),
         "--hidden-import", "psutil", *data,
         "--add-binary", os.path.join(ROOT, "hook", "aoehook.dll") + os.pathsep + "bin",
         "--add-binary", os.path.join(ROOT, "hook", "dplaunch.exe") + os.pathsep + "bin",
         "--distpath", DIST, "--workpath", os.path.join(ROOT, "build"), "--specpath", os.path.join(ROOT, "build"),
         os.path.join(ROOT, "launcher", "main.py")], cwd=ROOT)


def copy_game():
    dst = os.path.join(DIST, "AoE-HD")
    if os.path.exists(dst):
        shutil.rmtree(dst)

    def ignore(d, names):
        return [n for n in names if n in SKIP_DIRS and os.path.isdir(os.path.join(d, n))]

    shutil.copytree(GAME_SRC, dst, ignore=ignore)
    for n in SKIP_DIRS:
        os.makedirs(os.path.join(dst, n), exist_ok=True)
    # the bot copy of the executable must exist and match
    shutil.copyfile(os.path.join(dst, "EMPIRESX.EXE"), os.path.join(dst, "AOEBOT.EXE"))
    print("game copied to", dst)


if __name__ == "__main__":
    os.makedirs(DIST, exist_ok=True)
    if "--no-dll" not in sys.argv:
        build_dll()
    build_exe()
    if "--no-game" not in sys.argv:
        copy_game()
    print("done:", os.path.join(DIST, "AoESolo.exe"))
