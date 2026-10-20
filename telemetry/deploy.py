r"""Wrangler for the AoE Bot D3KT telemetry worker with ITS OWN Cloudflare account (README.md): the login lives in
C:\Users\Admin\.cf-aoesolo so the AoE-MapCap login in ~/.config is untouched.
    python deploy.py            deploy
    python deploy.py secret     set STATS_PASSWORD from stats_password.txt next to the login
    python deploy.py schema     apply schema.sql to the remote D1
    python deploy.py sql "..."  run SQL on the remote D1
    python deploy.py login      log in again (browser)"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CF_HOME = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), ".cf-aoesolo")
DB = "aoesolo-telemetry"


def wrangler(*args, stdin=None):
    env = dict(os.environ, XDG_CONFIG_HOME=CF_HOME)
    cmd = ["npx.cmd" if os.name == "nt" else "npx", "wrangler", *args]
    return subprocess.run(cmd, cwd=HERE, env=env, input=stdin, text=True).returncode


def main(argv):
    what = argv[1] if len(argv) > 1 else "deploy"
    if what == "deploy":
        return wrangler("deploy")
    if what == "secret":
        with open(os.path.join(CF_HOME, "stats_password.txt"), encoding="utf-8") as f:
            pw = f.read().strip()
        return wrangler("secret", "put", "STATS_PASSWORD", stdin=pw)
    if what == "schema":
        return wrangler("d1", "execute", DB, "--remote", "--file", "schema.sql", "-y")
    if what == "sql":
        return wrangler("d1", "execute", DB, "--remote", "--command", argv[2], "-y")
    if what == "login":
        return wrangler("login")
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
