import sys, subprocess, time, os
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import gamewin as gw
game = r'D:\Game\AoE-HD'
p = subprocess.Popen([os.path.join(game, 'EMPIRESX.EXE'), 'nostartup'], cwd=game)
hwnd = gw.main_window(p.pid, 30)
print('pid', p.pid, 'hwnd', hwnd)
time.sleep(8)
print('windows', gw.windows_of_pid(p.pid))
print('rects', gw.rects(hwnd))
style = gw.user32.GetWindowLongW(hwnd, -16)
print('style', hex(style & 0xffffffff), 'caption', bool(style & 0x00C00000))
mods = [m for m in gw.modules32(p.pid) if 'AoE-HD' in m or 'ddraw' in m.lower() or 'dplay' in m.lower() or 'wndmode' in m.lower()]
print('modules', mods)
img = gw.screenshot(hwnd, r'C:\Users\Admin\AppData\Local\Temp\claude\d--Game\5df957f6-ab3a-4ec0-9648-22af3ce0ffa2\scratchpad\shot1.png')
print('shot', img.size)
open(r'D:\Game\AoESolo\tools\probe.pid','w').write(str(p.pid))
