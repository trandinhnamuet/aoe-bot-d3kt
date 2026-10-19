"""Update check and one-click update (20/10): the launcher asks GitHub for the latest release at start; when it
is newer, the window shows a button; one click downloads AoESolo.zip, swaps the exe (the running exe is renamed
AoESolo.old.exe - Windows allows that - and the new one takes its name) and restarts the launcher."""
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

from version import REPO, VERSION

API = "https://api.github.com/repos/%s/releases/latest" % REPO
UA = {"User-Agent": "AoESolo/" + VERSION, "Accept": "application/vnd.github+json"}


def parse(v):
    out = []
    for part in v.strip().lstrip("vV").split("."):
        try:
            out.append(int(part))
        except ValueError:
            out.append(0)
    return tuple(out)


def check(timeout=8):
    """The latest release when it is newer than this build: {"version", "url", "notes", "page"}; else None."""
    req = urllib.request.Request(API, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        rel = json.loads(r.read().decode("utf-8"))
    tag = rel.get("tag_name") or ""
    if parse(tag) <= parse(VERSION):
        return None
    asset = next((a for a in rel.get("assets", []) if a.get("name", "").lower().endswith(".zip")), None)
    if not asset:
        return None
    return {"version": tag.lstrip("vV"), "url": asset["browser_download_url"], "notes": rel.get("body") or "",
            "page": rel.get("html_url") or ""}


def download(url, dest, progress=None, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    return dest


def swap(zip_path, exe_path):
    """Puts the zip's AoESolo.exe in place of exe_path (the running one is renamed .old.exe); other files of the
    zip (the guide) are written next to it. Returns the path of the new exe."""
    folder = os.path.dirname(exe_path)
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        exe_name = next((n for n in names if n.lower().endswith("aoesolo.exe")), None)
        if not exe_name:
            raise RuntimeError("AoESolo.exe không có trong gói tải về")
        new_exe = exe_path + ".new"
        with z.open(exe_name) as src, open(new_exe, "wb") as dst:
            while True:
                b = src.read(1024 * 1024)
                if not b:
                    break
                dst.write(b)
        for n in names:
            if n == exe_name or n.endswith("/"):
                continue
            target = os.path.join(folder, os.path.basename(n))
            try:
                with z.open(n) as src, open(target, "wb") as dst:
                    dst.write(src.read())
            except OSError:
                pass
    old = exe_path[:-4] + ".old.exe" if exe_path.lower().endswith(".exe") else exe_path + ".old"
    if os.path.exists(old):
        os.remove(old)
    os.rename(exe_path, old)
    os.rename(new_exe, exe_path)
    return exe_path


def cleanup_old(exe_path):
    """The previous exe left by a swap is deleted at the next start (it may still be closing for a moment)."""
    old = exe_path[:-4] + ".old.exe" if exe_path.lower().endswith(".exe") else exe_path + ".old"
    try:
        if os.path.exists(old):
            os.remove(old)
    except OSError:
        pass


def restart(exe_path):
    subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path), close_fds=True,
                     creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))


def temp_zip():
    return os.path.join(tempfile.gettempdir(), "AoESolo-update.zip")


def running_exe():
    return sys.executable if getattr(sys, "frozen", False) else None
