import sys, time, threading, ctypes
sys.path.insert(0, r'D:\Game\AoESolo\launcher')
import gamewin as gw, procs
u=ctypes.windll.user32
fg0=u.GetForegroundWindow()
events=[]; stop=False
def watch():
    last=None
    while not stop:
        f=u.GetForegroundWindow()
        if f!=last: events.append((round(time.time()-t0,2),f)); last=f
        time.sleep(0.01)
t0=time.time(); th=threading.Thread(target=watch, daemon=True); th.start()
gp=procs.start(r'D:\Game\AoE-HD','AOEBOT.EXE',r'D:\Game\AoESolo\hook\aoehook.dll',True)
time.sleep(3); stop=True; th.join()
print('foreground changes', [(t, f==fg0, f==gp.hwnd) for t,f in events])
print('visible', u.IsWindowVisible(gp.hwnd), 'rect', gw.rects(gp.hwnd))
print(gp.hook.cmd('stat'))
open('probe.pid','w').write(str(gp.pid))
