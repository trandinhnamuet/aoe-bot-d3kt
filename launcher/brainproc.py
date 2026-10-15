"""One brain per PROCESS (15/10): the bots' brains used to be threads of the launcher's process and shared its
GIL - 7 bots meant 1-4 s ticks. Each brain now runs in its own child process (multiprocessing, spawn), opening its
own memory handle and hook pipe to its game; the parent only drains a log queue and raises a stop event.
AOESOLO_BRAIN_PROCS=0 keeps the old in-process threads."""
import multiprocessing as mp
import os
import threading
import time

_LOGQ = None
_DRAIN = None
_SINKS = []          # (log callable, prefix) per start(); the drain thread calls every sink's log for its own lines


def enabled():
    return os.environ.get("AOESOLO_BRAIN_PROCS", "1") != "0"


def _child(pid, me, enemies, logq, stop_ev, period, pop_limit, limit_s, tag):
    """The child process: its own Mem / Hook on the game, the brain loop until the stop event or the game-time
    limit; every log line goes to the parent's queue."""
    import aoemem
    import inject

    def log(m):
        try:
            logq.put((tag, m))
        except Exception:  # noqa: BLE001
            pass
    try:
        os.environ["AOESOLO_CUT_WORKERS"] = "1"      # one wall-cut worker per brain process
        g = aoemem.Game(inject.Mem(pid), inject.Hook(pid))
        import d3kt

        def stop():
            if stop_ev.is_set():
                return True
            if limit_s:
                try:
                    w = g.world()
                    return bool(w) and (g.m.u32(w + 4) or 0) / 1000.0 > limit_s
                except Exception:  # noqa: BLE001
                    return False
            return False
        d3kt.run(g, me, enemies, log=log, stop=stop, period=period, pop_limit=pop_limit)
    except Exception as e:  # noqa: BLE001
        log("bot %d stopped: %r" % (me, e))
    finally:
        try:
            logq.put((tag, None))
        except Exception:  # noqa: BLE001
            pass


class BrainProc:
    """Handle of one brain process: alive(), stop(), join(timeout), kill()."""

    def __init__(self, proc, stop_ev, me):
        self.proc, self.stop_ev, self.me = proc, stop_ev, me

    def alive(self):
        return self.proc.is_alive()

    is_alive = alive

    def stop(self):
        self.stop_ev.set()

    def join(self, timeout=None):
        self.proc.join(timeout)

    def kill(self):
        try:
            if self.proc.is_alive():
                self.proc.terminate()
        except Exception:  # noqa: BLE001
            pass


def _drain():
    while True:
        try:
            tag, m = _LOGQ.get()
        except Exception:  # noqa: BLE001
            time.sleep(0.2)
            continue
        if m is None:
            continue
        for log, t in list(_SINKS):
            if t == tag:
                try:
                    log(m)
                except Exception:  # noqa: BLE001
                    pass
                break


def start(pid, me, enemies, log, period=0.6, pop_limit=200, limit_s=0.0):
    """Starts the brain of player `me` (whose game is process `pid`) in a child process. `log(line)` is called
    on the parent's drain thread. Returns a BrainProc."""
    global _LOGQ, _DRAIN
    if _LOGQ is None:
        _LOGQ = mp.Queue()
        _DRAIN = threading.Thread(target=_drain, daemon=True, name="brain-log-drain")
        _DRAIN.start()
    tag = "%d-%d" % (pid, me)
    _SINKS.append((log, tag))
    ev = mp.Event()
    p = mp.Process(target=_child, args=(pid, me, list(enemies), _LOGQ, ev, period, pop_limit, limit_s, tag),
                   name="brain-P%d" % me, daemon=True)
    p.start()
    return BrainProc(p, ev, me)
