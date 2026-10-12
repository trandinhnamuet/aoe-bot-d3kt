import sys, subprocess, time, os
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import gamewin as gw, inject
SH = r'C:\Users\Admin\AppData\Local\Temp\claude\d--Game\5df957f6-ab3a-4ec0-9648-22af3ce0ffa2\scratchpad'
game = r'D:\Game\AoE-HD'
p = subprocess.Popen([os.path.join(game, 'EMPIRESX.EXE'), 'nostartup'], cwd=game)
hwnd = gw.main_window(p.pid, 30); time.sleep(4)
inject.inject(p.pid, r'D:\Game\AoESolo\hook\aoehook.dll')
h = inject.Hook(p.pid)
open(r'D:\Game\AoESolo\tools\probe.pid', 'w').write(str(p.pid))
print(h.cmd('ping')); print(h.cmd('stat'))
t=time.time(); print(h.cmd('vin 1'), round(time.time()-t,2), 's')
print(h.cmd('stat'))
t=time.time(); print(h.click(683, 317), round(time.time()-t,2), 's'); time.sleep(2)
print(h.cmd('stat'))
gw.screenshot(hwnd, SH + r'\h2.png')
print('fg is game?', gw.user32.GetForegroundWindow() == hwnd)
