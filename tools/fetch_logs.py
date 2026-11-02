"""Logs sent by launchers ("Gửi log cho dev" + automatic after a match / a failed room) - list and download.

    python tools/fetch_logs.py            the newest 20 (id, time VN, kind, version, machine, CPU/RAM, note)
    python tools/fetch_logs.py 12         download log 12 to tools/remote_logs/12_<kind>.log (gunzipped)
    python tools/fetch_logs.py new        download every log not downloaded yet

The password is the stats page's (C:\\Users\\<you>\\.cf-aoesolo\\stats_password.txt, or env AOESOLO_STATS_PW)."""
import gzip
import json
import os
import sys
import time
import urllib.request

BASE = "https://aoesolo-telemetry.aoebotd3kt.workers.dev"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "remote_logs")


def password():
    pw = os.environ.get("AOESOLO_STATS_PW")
    if pw:
        return pw.strip()
    p = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), ".cf-aoesolo", "stats_password.txt")
    with open(p, encoding="utf-8") as f:
        return f.read().strip()


def get(path):
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Bearer " + password(), "User-Agent": "aoesolo-dev/1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def vn(ms):
    return time.strftime("%d/%m %H:%M:%S", time.gmtime(ms / 1000 + 7 * 3600))


def listing():
    return json.loads(get("/api/logs"))["logs"]


def download(row):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "%d_%s.log" % (row["id"], row["kind"]))
    with open(path, "wb") as f:
        f.write(gzip.decompress(get("/api/logs/%d" % row["id"])))
    print("saved", path, "(%d KB)" % (os.path.getsize(path) // 1024))
    return path


def main(argv):
    rows = listing()
    if len(argv) < 2:
        for r in rows[:20]:
            sysinfo = json.loads(r["sys"] or "{}")
            print("%4d %s %-13s v%-7s %s %s | %s cores %s GB %s | %s" % (
                r["id"], vn(r["ts"]), r["kind"], r["version"], r["install"][:8], r["name"] or "", sysinfo.get("cores"),
                sysinfo.get("ram_gb"), (sysinfo.get("cpu") or "")[:40], r["note"] or ""))
        return 0
    if argv[1] == "new":
        have = set(os.listdir(OUT)) if os.path.isdir(OUT) else set()
        for r in rows:
            if "%d_%s.log" % (r["id"], r["kind"]) not in have:
                download(r)
        return 0
    want = int(argv[1])
    row = next((r for r in rows if r["id"] == want), None)
    if not row:
        print("no log", want)
        return 1
    download(row)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
