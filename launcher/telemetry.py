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
import ssl  # noqa: F401

import netssl
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
        conn = _IPv4HTTPSConnection(u.hostname, u.port or 443, timeout=timeout, context=netssl.context())
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


# ---------------------------------------------------------------- logs for remote debugging (02/11/2026)
LOG_ENDPOINT = "https://aoesolo-telemetry.aoebotd3kt.workers.dev/v1/log"
LOG_TAIL = 8 * 1024 * 1024          # at most the last 8 MB of the session (gzip ~ 1 MB)


def system_info():
    """CPU, RAM and Windows of this machine (a slow internet-café PC is the usual suspect)."""
    import platform
    info = {"cores": os.cpu_count()}
    try:
        import psutil
        info["phys"] = psutil.cpu_count(logical=False)
        info["ram_gb"] = round(psutil.virtual_memory().total / 2 ** 30, 1)
        f = psutil.cpu_freq()
        if f:
            info["mhz"] = int(f.max or f.current or 0)
    except Exception:  # noqa: BLE001
        pass
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        info["cpu"] = winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()[:60]
    except Exception:  # noqa: BLE001
        info["cpu"] = platform.processor()[:60]
    info["win"] = platform.platform()[:40]
    return info


def send_log(path, start=0, kind="manual", name="", note="", cfg_enabled=True, log=None, wait=False, done=None):
    """aoesolo.log from byte `start` (this session) gzip-ed to the receiver, in the background. Sent whenever the
    statistics box is on - also from source when AOESOLO_TELEMETRY=1. done(ok, msg) is called when finished."""
    env = os.environ.get("AOESOLO_TELEMETRY")
    if env is not None and env.strip() in ("0", "false", "no", ""):
        return None
    if not cfg_enabled and kind != "manual":
        return None                              # (the button always sends: the player asked for it)

    def job():
        ok, msg = False, ""
        try:
            import gzip
            size = os.path.getsize(path)
            begin = max(start, size - LOG_TAIL)
            with open(path, "rb") as f:
                f.seek(begin)
                raw = f.read()
            data = gzip.compress(raw, 6)
            q = urllib.parse.urlencode({"id": install_id(), "v": VERSION, "kind": kind, "name": (name or "")[:40],
                                        "sys": json.dumps(system_info(), ensure_ascii=True), "note": (note or "")[:500],
                                        "raw": len(raw)})
            url = (os.environ.get("AOESOLO_LOG_URL") or LOG_ENDPOINT) + "?" + q
            u = urllib.parse.urlsplit(url)
            conn = _IPv4HTTPSConnection(u.hostname, u.port or 443, timeout=60, context=netssl.context()) \
                if u.scheme == "https" else http.client.HTTPConnection(u.hostname, u.port or 80, timeout=60)
            try:
                conn.request("POST", u.path + "?" + u.query, body=data,
                             headers={"content-type": "application/gzip", "user-agent": "AoESolo/" + VERSION})
                r = conn.getresponse()
                body = r.read(2048).decode("utf-8", "replace")
                ok = r.status == 200
                msg = "%d KB sent" % (len(data) // 1024) if ok else "server %s %s" % (r.status, body[:80])
            finally:
                conn.close()
        except Exception as e:  # noqa: BLE001
            msg = "%s: %s" % (e.__class__.__name__, e)
        if log:
            log("log upload (%s): %s" % (kind, msg))
        if done:
            done(ok, msg)
    t = threading.Thread(target=job, name="logupload", daemon=True)
    t.start()
    if wait:
        t.join(70)
    return t
