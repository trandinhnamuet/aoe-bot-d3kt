import sys, subprocess, time, os
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import gamewin as gw, inject
game = r'D:\Game\AoE-HD'
p = subprocess.Popen([os.path.join(game, 'EMPIRESX.EXE'), 'nostartup'], cwd=game)
hwnd = gw.main_window(p.pid, 30); time.sleep(3)
inject.inject(p.pid, r'D:\Game\AoESolo\hook\aoehook.dll')
h = inject.Hook(p.pid)
print(h.cmd('vin 1')); print(h.cmd('hide 1'))
open(r'D:\Game\AoESolo\tools\probe2.pid', 'w').write(str(p.pid))
print('pid', p.pid)
