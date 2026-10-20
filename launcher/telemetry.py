"""Usage statistics (20/10): one record when the launcher opens (with a network) and one when a match against the
bots starts, sent to a Cloudflare Worker (telemetry/ in the repo, its own Cloudflare account - telemetry/README.md).

Sent: a machine id (random UUID made on first run, kept in %APPDATA%\\AoESolo\\install_id so a new zip or an update
keeps it), app "aoesolo", the version, the kind (open / match), the player's name in the room, and for a match the
number of bots, the player's civ ("Random" when the game draws it) and the map size. The IP is recorded by the
receiver; the connection is IPv4 so the recorded IP is an IPv4 one. Nothing else: no files, no game content.
Runs in the background and waits at most 6 s; no network / an error is ignored. Off with the "Gửi thống kê sử dụng"
box in the launcher or AOESOLO_TELEMETRY=0. Run from source (not the packaged exe) it sends nothing unless
AOESOLO_TELEMETRY=1; AOESOLO_TELEMETRY_URL replaces the receiver (tests)."""
import http.client
import json
import os
import socket
import ssl
import sys
import threading
import urllib.parse
import uuid

from version import VERSION

ENDPOINT = "https://aoesolo-telemetry.aoebotd3kt.workers.dev/v1/e"   # Cloudflare Worker (telemetry/)
TIMEOUT = 6
APP = "aoesolo"


def endpoint():
    return os.environ.get("AOESOLO_TELEMETRY_URL") or ENDPOINT


def enabled(cfg_enabled=True):
    env = os.environ.get("AOESOLO_TELEMETRY")
    if env is not None:
        return env.strip() not in ("0", "false", "no", "")
    if not getattr(sys, "frozen", False):
        return False                            # from source / tests: real numbers stay clean
    return bool(cfg_enabled)


def _id_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "AoESolo", "install_id")


def install_id():
    """The machine id from %APPDATA%\\AoESolo\\install_id; a new random UUID, saved, when there is none."""
    p = _id_path()
    try:
        with open(p, encoding="ascii") as f:
            v = f.read().strip()
        uuid.UUID(v)
        return v
    except (OSError, ValueError):
        pass
    v = str(uuid.uuid4())
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="ascii") as f:
            f.write(v)
    except OSError:
        pass                                    # cannot save: still sent, the next run gets another id
    return v


class _IPv4HTTPSConnection(http.client.HTTPSConnection):
    """HTTPS over IPv4 only (so the receiver records an IPv4 address), the certificate still checked by host name."""

    def connect(self):
        infos = socket.getaddrinfo(self.host, self.port, socket.AF_INET, socket.SOCK_STREAM)
        err = None
        for _fam, _t, _p, _c, addr in infos:
            try:
                sock = socket.create_connection(addr, self.timeout)
                break
            except OSError as e:
                err = e
        else:
            raise err or OSError("no IPv4 address")
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _post(url, payload, timeout=TIMEOUT):
    u = urllib.parse.urlsplit(url)
    data = json.dumps(payload).encode("utf-8")
    headers = {"content-type": "application/json", "user-agent": "AoESolo/" + VERSION}
    if u.scheme == "https":
        conn = _IPv4HTTPSConnection(u.hostname, u.port or 443, timeout=timeout, context=ssl.create_default_context())
    else:
        conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=timeout)
    try:
        conn.request("POST", u.path or "/", body=data, headers=headers)
        r = conn.getresponse()
        r.read(4096)
        return r.status
    finally:
        conn.close()


def send(ev="open", cfg_enabled=True, log=None, wait=False, name="", bots=None, civ=None, size=None):
    """One record in the background. ev: "open" | "match"; for a match: bots (1..7), civ (name or "Random"),
    size (map size). wait=True blocks until sent (tests). Returns the thread, or None when sending is off."""
    if not enabled(cfg_enabled):
        return None
    payload = {"id": install_id(), "app": APP, "v": VERSION, "ev": ev, "name": (name or "").strip()[:40]}
    if ev == "match":
        payload.update({"bots": bots, "civ": civ, "size": size})

    def job():
        try:
            st = _post(endpoint(), payload)
            if log and st != 200:
                log("telemetry: the server answered %s" % st)
        except Exception as e:  # noqa: BLE001  - no network / blocked: ignored, the launcher is not affected
            if log:
                log("telemetry: not sent (%s)" % e.__class__.__name__)
    t = threading.Thread(target=job, name="telemetry", daemon=True)
    t.start()
    if wait:
        t.join(TIMEOUT + 2)
    return t
