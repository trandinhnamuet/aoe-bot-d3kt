import sys, subprocess, time, os
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import gamewin as gw, inject
SH = r'C:\Users\Admin\AppData\Local\Temp\claude\d--Game\5df957f6-ab3a-4ec0-9648-22af3ce0ffa2\scratchpad'
game = r'D:\Game\AoE-HD'
p = subprocess.Popen([os.path.join(game, 'EMPIRESX.EXE'), 'nostartup'], cwd=game)
hwnd = gw.main_window(p.pid, 30); time.sleep(4)
fg_before = gw.user32.GetForegroundWindow()
inject.inject(p.pid, r'D:\Game\AoESolo\hook\aoehook.dll')
h = inject.Hook(p.pid)
print(h.cmd('ping'))
print(h.cmd('vin 1'))
time.sleep(0.5)
print('game is foreground?', gw.user32.GetForegroundWindow() == hwnd)
cur0 = None
print(h.click(683, 317)); time.sleep(2)


gw.screenshot(hwnd, SH + r'\h1.png')
open(r'D:\Game\AoESolo\tools\probe.pid', 'w').write(str(p.pid))
