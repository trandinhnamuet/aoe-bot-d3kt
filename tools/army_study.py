"""What a player's army was made of over a recorded game, and when the military techs came.

python army_study.py PLAYER_NAME [N_LATEST=12]       (system python)

Per game: for every military unit type the player owned, first time seen and the peak count; the
military buildings in order; the Wheel / bow / armour techs with their times; the enemies' main units."""
import collections
import os
import sys

sys.path.insert(0, r"D:\Game\AoE-MapCap")
from mapcap.rawrec import iter_records  # noqa: E402

RAW = r"D:\Game\AoE-MapCap\dist\Video\Raw"
WHO = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 12
BUILD = {12: "barracks", 87: "range", 101: "stable", 0: "academy", 49: "siege", 104: "temple", 84: "market", 103: "pit", 68: "granary", 45: "dock"}
TECH = {28: "Wheel", 55: "?55", 56: "Improved Bow", 57: "Composite Bow", 46: "Tool Working", 51: "Metal Working",
        41: "Leather Archers", 44: "Scale Archers", 42: "Leather Mounted", 45: "Scale Cavalry", 101: "Tool Age",
        102: "Bronze Age", 103: "Iron Age", 107: "Wood Working", 108: "Gold Mining", 32: "Artisanship"}


def study(path):
    defs, hdr, units = {}, None, {}
    seen_first, peak, enemy_peak = {}, collections.Counter(), collections.Counter()
    blds = []
    techs = {}
    me = None
    t = 0
    for tag, pl in iter_records(path):
        if tag == b"H":
            hdr = pl
            me = next((p[0] for p in hdr["players"] if p[3] == WHO), None)
            if me is None:
                return None
        elif tag == b"D":
            for rec in pl:
                defs[rec[0]] = (rec[2], rec[3], rec[4], rec[5])
        elif tag == b"F" and hdr is not None:
            t = pl["t"]
            if pl["full_units"]:
                units = {int(r["uid"]): r for r in pl["units"]}
            else:
                for u in pl["removed"].tolist():
                    units.pop(int(u), None)
                for r in pl["units"]:
                    units[int(r["uid"])] = r
            for idx, (a, tt) in (pl.get("pstate") or {}).items():
                if idx == me and tt is not None:
                    for tid in tt:
                        techs.setdefault(tid, t)
            prs = pl.get("prs") or {}
            for idx, d in prs.items():
                if idx == me:
                    for tid, sec in d.items():
                        if sec and tid not in techs:
                            techs[tid] = t
            if t % 5000 > 100:
                continue
            cnt, ecnt = collections.Counter(), collections.Counter()
            for uid, r in units.items():
                d = defs.get(int(r["def"]))
                if not d or int(r["status"]) > 2:
                    continue
                utype, name, dat, cls = d
                owner = int(r["owner"])
                if utype == 70 and cls not in (4, 18, 19, 58, 21, 2, 20) and owner > 0 and "Artifact" not in name:
                    (cnt if owner == me else ecnt)[name] += 1
                if utype == 80 and owner == me and dat in BUILD and uid not in [b[2] for b in blds]:
                    blds.append((round(t / 1000), BUILD[dat], uid))
            for k, n in cnt.items():
                seen_first.setdefault(k, round(t / 1000))
                peak[k] = max(peak[k], n)
            for k, n in ecnt.items():
                enemy_peak[k] = max(enemy_peak[k], n)
    if hdr is None or me is None:
        return None
    civ = next((p[7] if len(p) > 7 else None) for p in hdr["players"] if p[0] == me)
    return dict(units={k: (seen_first[k], peak[k]) for k in peak}, buildings=[b[:2] for b in blds],
                techs=sorted((round(v / 1000), TECH.get(k, k)) for k, v in techs.items() if k in TECH),
                enemy=enemy_peak.most_common(6), end=round(t / 1000), civ=civ)


def main():
    files = sorted([f for f in os.listdir(RAW) if f.endswith(".aoerec")], reverse=True)[:N]
    for f in files:
        r = study(os.path.join(RAW, f))
        if r is None:
            continue
        print("== %s (%d s, civ %s)" % (f, r["end"], r["civ"]))
        print("   army: " + ", ".join("%s x%d (from %d s)" % (k, v[1], v[0]) for k, v in sorted(r["units"].items(), key=lambda kv: kv[1][0])))
        print("   buildings: " + ", ".join("%s %d s" % (b, t) for t, b in r["buildings"]))
        print("   techs: " + ", ".join("%s %d s" % (n, t) for t, n in r["techs"]))
        print("   enemy peak: " + ", ".join("%s x%d" % kv for kv in r["enemy"]))


if __name__ == "__main__":
    main()
