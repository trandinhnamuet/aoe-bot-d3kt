"""Start a hidden hooked game instance via procs.start. Usage: rig.py <pidfile> [sp] [emp]"""
import sys, time
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import procs
pidfile = sys.argv[1]
exe = 'EMPIRESX.EXE' if 'emp' in sys.argv[2:] else 'AOEBOT.EXE'
gp = procs.start(r'D:\Game\AoE-HD', exe, r'D:\Game\AoESolo\hook\aoehook.dll', True, job=False)
open(pidfile, 'w').write(str(gp.pid))
time.sleep(2)
if 'sp' in sys.argv[2:]:
    for x, y, w in ((683, 317, 2), (683, 221, 3), (405, 728, 15)):
        gp.hook.click(x, y); time.sleep(w)
print('pid', gp.pid)
