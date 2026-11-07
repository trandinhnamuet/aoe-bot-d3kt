"""GitHub release through the REST API with the token from `git credential fill` (never printed).

    python tools/release.py <tag> <name> <notes.txt> <asset.zip> [--draft]
    e.g. python tools/release.py v1.2.24 "AoE Bot D3KT v1.2.24" notes.txt AoESolo.zip
    python tools/release.py --replace-asset <tag> <asset.zip>     (new file for an existing release)

Run it from the repo (the release points at HEAD, which must be pushed first)."""
import json
import os
import subprocess
import sys
import urllib.request

REPO = "trandinhnamuet/aoe-bot-d3kt"


def token():
    cred = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                          capture_output=True, text=True, check=True).stdout
    return next(ln.split("=", 1)[1].strip() for ln in cred.splitlines() if ln.startswith("password="))


def call(url, tok, data=None, method="GET", ctype="application/json"):
    body = data if isinstance(data, (bytes, type(None))) else json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json",
        "User-Agent": "aoe-bot-d3kt-release", "Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def replace_asset(tag, asset):
    """Swaps the release's asset of the same name for a new file (the release and its notes stay)."""
    tok = token()
    rel = call("https://api.github.com/repos/%s/releases/tags/%s" % (REPO, tag), tok)
    name = os.path.basename(asset)
    for a in rel.get("assets", []):
        if a.get("name") == name:
            call("https://api.github.com/repos/%s/releases/assets/%d" % (REPO, a["id"]), tok, method="DELETE")
            print("deleted old", name, a.get("size"))
    up = rel["upload_url"].split("{")[0] + "?name=" + name
    with open(asset, "rb") as f:
        a = call(up, tok, f.read(), method="POST", ctype="application/zip")
    print("asset", a.get("browser_download_url"), a.get("size"))
    return 0


def main(argv):
    if len(argv) == 4 and argv[1] == "--replace-asset":
        return replace_asset(argv[2], argv[3])
    if len(argv) < 5:
        print(__doc__)
        return 2
    tag, name, notes_path, asset = argv[1:5]
    tok = token()
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    with open(notes_path, encoding="utf-8") as f:
        body = f.read()
    rel = call("https://api.github.com/repos/%s/releases" % REPO, tok,
               {"tag_name": tag, "target_commitish": sha, "name": name, "body": body,
                "draft": "--draft" in argv, "prerelease": False}, method="POST")
    print("release", rel.get("html_url"))
    up = rel["upload_url"].split("{")[0] + "?name=" + os.path.basename(asset)
    with open(asset, "rb") as f:
        a = call(up, tok, f.read(), method="POST", ctype="application/zip")
    print("asset", a.get("browser_download_url"), a.get("size"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
