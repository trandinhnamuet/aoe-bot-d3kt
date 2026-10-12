"""Send hook commands to the probe game: hk.py "click 683 317" "wait 2" "shot name" ..."""
import sys, time, os
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import gamewin as gw, inject
SH = r'C:\Users\Admin\AppData\Local\Temp\claude\d--Game\5df957f6-ab3a-4ec0-9648-22af3ce0ffa2\scratchpad'
pid = int(sys.argv[1]) if sys.argv[1].isdigit() else int(open(r'D:\Game\AoESolo\tools\probe.pid').read())
args = sys.argv[2:] if sys.argv[1].isdigit() else sys.argv[1:]
hwnd = gw.main_window(pid, 5)
h = inject.Hook(pid)
for a in args:
    if a.startswith('wait '): time.sleep(float(a.split()[1]))
    elif a.startswith('shot '): gw.screenshot(hwnd, os.path.join(SH, a.split()[1] + '.png')); print('shot', a.split()[1])
    elif a.startswith('type '): h.type_text(a[5:]); print('typed')
    else: print(a, '->', h.cmd(a))
