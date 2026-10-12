import sys, time
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import gamewin as gw
pid = int(open(r'D:\Game\AoESolo\tools\probe.pid').read())
hwnd = gw.main_window(pid, 5)
shots = r'C:\Users\Admin\AppData\Local\Temp\claude\d--Game\5df957f6-ab3a-4ec0-9648-22af3ce0ffa2\scratchpad'
args = sys.argv[1:]
i = 0
while i < len(args):
    a = args[i]
    if a == 'click':
        gw.post_click(hwnd, int(args[i+1]), int(args[i+2])); i += 3
    elif a == 'rclick':
        gw.post_click(hwnd, int(args[i+1]), int(args[i+2]), 'right'); i += 3
    elif a == 'real':
        print('real', gw.real_click(hwnd, int(args[i+1]), int(args[i+2]))); i += 3
    elif a == 'key':
        gw.key(hwnd, int(args[i+1], 0)); i += 2
    elif a == 'wait':
        time.sleep(float(args[i+1])); i += 2
    elif a == 'shot':
        gw.screenshot(hwnd, f'{shots}\{args[i+1]}.png'); i += 2
    else:
        raise SystemExit('bad arg ' + a)
print('ok')
