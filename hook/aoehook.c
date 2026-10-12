// aoehook.dll - injected into a bot-controlled AoE instance only.
// Gives the bot a virtual mouse/keyboard (never touches the real cursor),
// keeps the window hidden, and can call game functions on the main thread.
// Control channel: named pipe \\.\pipe\aoehook_<pid>, one text command per line.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <psapi.h>

static HWND g_hwnd = NULL;
static volatile LONG g_virtual = 0;      // 1 = game sees only virtual input
static volatile LONG g_hidden = 0;       // 1 = keep game window hidden
static volatile LONG g_vx = 0, g_vy = 0; // virtual cursor, client coords
static BYTE g_keys[256];                 // virtual key state (0x80 = down)
static volatile LONG g_mode = 0;         // 0 = call game wndproc directly, 1 = post to message queue
static volatile LONG st_gcp = 0, st_drain = 0, st_msghook = 0, st_gaks = 0, st_dlg = 0;
static HHOOK g_msghook = NULL;

typedef BOOL(WINAPI *GetCursorPos_t)(LPPOINT);
typedef BOOL(WINAPI *SetCursorPos_t)(int, int);
typedef SHORT(WINAPI *GetAsyncKeyState_t)(int);
typedef SHORT(WINAPI *GetKeyState_t)(int);
typedef BOOL(WINAPI *GetKeyboardState_t)(PBYTE);
typedef HWND(WINAPI *HwndVoid_t)(void);
typedef BOOL(WINAPI *BoolHwnd_t)(HWND);
typedef HWND(WINAPI *SetFocus_t)(HWND);
typedef BOOL(WINAPI *ShowWindow_t)(HWND, int);
typedef BOOL(WINAPI *PeekMessageA_t)(LPMSG, HWND, UINT, UINT, UINT);
typedef BOOL(WINAPI *GetMessageA_t)(LPMSG, HWND, UINT, UINT);
typedef BOOL(WINAPI *SetWindowPos_t)(HWND, HWND, int, int, int, int, UINT);
typedef BOOL(WINAPI *PtConv_t)(HWND, LPPOINT);
typedef LONG(WINAPI *RegSetValueExA_t)(HKEY, LPCSTR, DWORD, DWORD, const BYTE *, DWORD);
static RegSetValueExA_t o_RegSetValueExA;
static volatile LONG g_noreg = 0;   // 1 = bot instance: never write settings back to the registry
static LONG WINAPI h_RegSetValueExA(HKEY k, LPCSTR name, DWORD r, DWORD t, const BYTE *d, DWORD n) {
    if (g_noreg) return ERROR_SUCCESS;
    return o_RegSetValueExA(k, name, r, t, d, n);
}

static GetCursorPos_t o_GetCursorPos;
static SetCursorPos_t o_SetCursorPos;
static GetAsyncKeyState_t o_GetAsyncKeyState;
static GetKeyState_t o_GetKeyState;
static GetKeyboardState_t o_GetKeyboardState;
static HwndVoid_t o_GetForegroundWindow, o_GetActiveWindow, o_GetFocus, o_GetCapture;
static BoolHwnd_t o_SetForegroundWindow, o_BringWindowToTop;
static SetFocus_t o_SetFocus;
static ShowWindow_t o_ShowWindow;
static PeekMessageA_t o_PeekMessageA;
static GetMessageA_t o_GetMessageA;
static SetWindowPos_t o_SetWindowPos;
static PtConv_t o_ScreenToClient, o_ClientToScreen;

// ---------------------------------------------------------------- main-thread call queue
typedef struct {
    int conv;        // 0 = thiscall, 1 = stdcall, 2 = cdecl, 3 = window message to the game's own wndproc
    DWORD addr, ecx;
    int argc;
    DWORD args[10];
    DWORD result;
    HANDLE done;
} CallReq;

static CRITICAL_SECTION g_qlock;
static CallReq *g_queue[64];
static int g_qn = 0;

typedef DWORD(__thiscall *T0)(DWORD);
typedef DWORD(__thiscall *T1)(DWORD, DWORD);
typedef DWORD(__thiscall *T2)(DWORD, DWORD, DWORD);
typedef DWORD(__thiscall *T3)(DWORD, DWORD, DWORD, DWORD);
typedef DWORD(__thiscall *T4)(DWORD, DWORD, DWORD, DWORD, DWORD);
typedef DWORD(__thiscall *T5)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD);
typedef DWORD(__thiscall *T6)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD);
typedef DWORD(__thiscall *T7)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD);
typedef DWORD(__thiscall *T8)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD);
typedef DWORD(__thiscall *T9)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD);
typedef DWORD(__thiscall *T10)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD);
typedef DWORD(__stdcall *S0)(void);
typedef DWORD(__stdcall *S1)(DWORD);
typedef DWORD(__stdcall *S2)(DWORD, DWORD);
typedef DWORD(__stdcall *S3)(DWORD, DWORD, DWORD);
typedef DWORD(__stdcall *S4)(DWORD, DWORD, DWORD, DWORD);
typedef DWORD(__stdcall *S5)(DWORD, DWORD, DWORD, DWORD, DWORD);
typedef DWORD(__stdcall *S6)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD);
typedef DWORD(__cdecl *C0)(void);
typedef DWORD(__cdecl *C1)(DWORD);
typedef DWORD(__cdecl *C2)(DWORD, DWORD);
typedef DWORD(__cdecl *C3)(DWORD, DWORD, DWORD);
typedef DWORD(__cdecl *C4)(DWORD, DWORD, DWORD, DWORD);
typedef DWORD(__cdecl *C5)(DWORD, DWORD, DWORD, DWORD, DWORD);
typedef DWORD(__cdecl *C6)(DWORD, DWORD, DWORD, DWORD, DWORD, DWORD);

static WNDPROC g_gameproc = NULL;

static DWORD do_call(CallReq *r) {
    DWORD *a = r->args, f = r->addr, c = r->ecx;
    if (r->conv == 3) {
        if (!g_gameproc) g_gameproc = (WNDPROC)GetClassLongA(g_hwnd, GCL_WNDPROC);
        return (DWORD)CallWindowProcA(g_gameproc, g_hwnd, (UINT)f, (WPARAM)a[0], (LPARAM)a[1]);
    }
    if (r->conv == 0) {
        switch (r->argc) {
        case 0: return ((T0)f)(c);
        case 1: return ((T1)f)(c, a[0]);
        case 2: return ((T2)f)(c, a[0], a[1]);
        case 3: return ((T3)f)(c, a[0], a[1], a[2]);
        case 4: return ((T4)f)(c, a[0], a[1], a[2], a[3]);
        case 5: return ((T5)f)(c, a[0], a[1], a[2], a[3], a[4]);
        case 6: return ((T6)f)(c, a[0], a[1], a[2], a[3], a[4], a[5]);
        case 7: return ((T7)f)(c, a[0], a[1], a[2], a[3], a[4], a[5], a[6]);
        case 8: return ((T8)f)(c, a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7]);
        case 9: return ((T9)f)(c, a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8]);
        default: return ((T10)f)(c, a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8], a[9]);
        }
    } else if (r->conv == 1) {
        switch (r->argc) {
        case 0: return ((S0)f)();
        case 1: return ((S1)f)(a[0]);
        case 2: return ((S2)f)(a[0], a[1]);
        case 3: return ((S3)f)(a[0], a[1], a[2]);
        case 4: return ((S4)f)(a[0], a[1], a[2], a[3]);
        case 5: return ((S5)f)(a[0], a[1], a[2], a[3], a[4]);
        default: return ((S6)f)(a[0], a[1], a[2], a[3], a[4], a[5]);
        }
    } else {
        switch (r->argc) {
        case 0: return ((C0)f)();
        case 1: return ((C1)f)(a[0]);
        case 2: return ((C2)f)(a[0], a[1]);
        case 3: return ((C3)f)(a[0], a[1], a[2]);
        case 4: return ((C4)f)(a[0], a[1], a[2], a[3]);
        case 5: return ((C5)f)(a[0], a[1], a[2], a[3], a[4]);
        default: return ((C6)f)(a[0], a[1], a[2], a[3], a[4], a[5]);
        }
    }
}


static volatile LONG g_draining = 0;
static DWORD g_main_tid = 0;

static void drain_queue(void) {
    if (!g_qn) return;
    if (g_main_tid && GetCurrentThreadId() != g_main_tid) return;
    if (InterlockedExchange(&g_draining, 1)) return;     // no re-entrancy
    st_drain++;
    EnterCriticalSection(&g_qlock);
    int n = g_qn;
    CallReq *local[64];
    memcpy(local, g_queue, n * sizeof(CallReq *));
    g_qn = 0;
    LeaveCriticalSection(&g_qlock);
    for (int i = 0; i < n; i++) {
        CallReq *r = local[i];
        r->result = do_call(r);
        SetEvent(r->done);
    }
    g_draining = 0;
}

// ---------------------------------------------------------------- hooks
// In virtual mode the game sees cursor positions directly in its own client coordinates and
// screen<->client conversions are identity. This is independent of window position and of
// cnc-ddraw stretching (fullscreen upscaling would otherwise rescale our coordinates).
static BOOL WINAPI h_GetCursorPos(LPPOINT p) {
    st_gcp++;
    drain_queue();
    if (g_virtual && p) { p->x = g_vx; p->y = g_vy; return TRUE; }
    return o_GetCursorPos(p);
}
static BOOL WINAPI h_SetCursorPos(int x, int y) {
    if (g_virtual) { g_vx = x; g_vy = y; return TRUE; }
    return o_SetCursorPos(x, y);
}
static BOOL WINAPI h_ScreenToClient(HWND h, LPPOINT p) {
    if (g_virtual && h == g_hwnd) return TRUE;
    return o_ScreenToClient(h, p);
}
static BOOL WINAPI h_ClientToScreen(HWND h, LPPOINT p) {
    if (g_virtual && h == g_hwnd) return TRUE;
    return o_ClientToScreen(h, p);
}
static SHORT WINAPI h_GetAsyncKeyState(int vk) {
    st_gaks++;
    if (g_virtual) return (g_keys[vk & 0xFF] & 0x80) ? (SHORT)0x8000 : 0;
    return o_GetAsyncKeyState(vk);
}
static SHORT WINAPI h_GetKeyState(int vk) {
    if (g_virtual) return (g_keys[vk & 0xFF] & 0x80) ? (SHORT)0xFF80 : 0;
    return o_GetKeyState(vk);
}
static BOOL WINAPI h_GetKeyboardState(PBYTE k) {
    if (g_virtual && k) { memcpy(k, g_keys, 256); return TRUE; }
    return o_GetKeyboardState(k);
}
static HWND WINAPI h_GetForegroundWindow(void) { return (g_virtual && g_hwnd) ? g_hwnd : o_GetForegroundWindow(); }
static HWND WINAPI h_GetActiveWindow(void) { return (g_virtual && g_hwnd) ? g_hwnd : o_GetActiveWindow(); }
static HWND WINAPI h_GetFocus(void) { return (g_virtual && g_hwnd) ? g_hwnd : o_GetFocus(); }
static HWND WINAPI h_GetCapture(void) {
    if (g_virtual) return (g_keys[VK_LBUTTON] & 0x80 || g_keys[VK_RBUTTON] & 0x80) ? g_hwnd : NULL;
    return o_GetCapture();
}
static BOOL WINAPI h_SetForegroundWindow(HWND h) { return (g_virtual || g_hidden) ? TRUE : o_SetForegroundWindow(h); }
static BOOL WINAPI h_BringWindowToTop(HWND h) { return (g_virtual || g_hidden) ? TRUE : o_BringWindowToTop(h); }
static HWND WINAPI h_SetFocus(HWND h) { return g_virtual ? g_hwnd : o_SetFocus(h); }
static BOOL WINAPI h_ShowWindow(HWND h, int cmd) {
    if (g_hidden && (h == g_hwnd || !g_hwnd)) return o_ShowWindow(h, SW_HIDE);
    return o_ShowWindow(h, cmd);
}
static BOOL WINAPI h_SetWindowPos(HWND h, HWND after, int x, int y, int cx, int cy, UINT f) {
    if (g_hidden && h == g_hwnd) { f &= ~SWP_SHOWWINDOW; f |= SWP_NOACTIVATE; }
    return o_SetWindowPos(h, after, x, y, cx, cy, f);
}
static BOOL WINAPI h_PeekMessageA(LPMSG m, HWND h, UINT a, UINT b, UINT r) {
    drain_queue();
    return o_PeekMessageA(m, h, a, b, r);
}
static BOOL WINAPI h_GetMessageA(LPMSG m, HWND h, UINT a, UINT b) {
    drain_queue();
    return o_GetMessageA(m, h, a, b);
}

static LRESULT CALLBACK getmsg_proc(int code, WPARAM w, LPARAM l) {
    st_msghook++;
    if (code >= 0 && g_virtual && l) {
        // while the launcher drives the game, real mouse/keyboard input must not interfere
        MSG *m = (MSG *)l;
        if ((m->message >= WM_MOUSEFIRST && m->message <= WM_MOUSELAST) ||
            (m->message >= WM_KEYFIRST && m->message <= WM_KEYLAST) ||
            m->message == WM_NCMOUSEMOVE || m->message == WM_SETCURSOR) {
            m->message = WM_NULL;
        }
    }
    drain_queue();
    return CallNextHookEx(g_msghook, code, w, l);
}

static void ensure_msghook(void) {
    if (g_hwnd && !g_main_tid) g_main_tid = GetWindowThreadProcessId(g_hwnd, NULL);
    if (g_msghook || !g_hwnd) return;
    HMODULE self = NULL;
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)getmsg_proc, &self);
    DWORD tid = GetWindowThreadProcessId(g_hwnd, NULL);
    g_msghook = SetWindowsHookExA(WH_GETMESSAGE, getmsg_proc, self, tid);
}


// ---------------------------------------------------------------- function tracing (RE aid)
typedef struct {
    DWORD fn, edi, esi, ebp, esp, ebx, edx, ecx, eax, eflags;  // esp = esp at function entry
    DWORD stack[48];
} TraceRec;
#define TRACE_N 256
static TraceRec g_trace[TRACE_N];
static volatile LONG g_trace_n = 0;

static void __cdecl trace_log(DWORD *p) {
    LONG i = InterlockedIncrement(&g_trace_n) - 1;
    TraceRec *r = &g_trace[i % TRACE_N];
    r->fn = p[0];
    memcpy(&r->edi, p + 1, 9 * sizeof(DWORD));
    r->esp += 4;  // pushad saw esp after pushfd
    DWORD *sp = (DWORD *)r->esp;
    if (!IsBadReadPtr(sp, sizeof r->stack)) memcpy(r->stack, sp, sizeof r->stack);
    else memset(r->stack, 0, sizeof r->stack);
}

// stub: push fn; pushfd; pushad -> regs; call trace_log(esp); popad; popfd; add esp,4; stolen; jmp back
static int install_trace(DWORD addr, int stolen) {
    BYTE *stub = (BYTE *)VirtualAlloc(NULL, 64, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!stub || stolen < 5 || stolen > 16) return 0;
    BYTE *q = stub;
    *q++ = 0x9C;                                   // pushfd
    *q++ = 0x60;                                   // pushad
    *q++ = 0x68; *(DWORD *)q = addr; q += 4;       // push addr
    *q++ = 0x54;                                   // push esp
    *q++ = 0xE8; *(DWORD *)q = (DWORD)trace_log - (DWORD)(q + 4); q += 4;  // call trace_log
    *q++ = 0x83; *q++ = 0xC4; *q++ = 0x08;         // add esp, 8
    *q++ = 0x61;                                   // popad
    *q++ = 0x9D;                                   // popfd
    memcpy(q, (void *)addr, stolen); q += stolen;  // original instructions
    *q++ = 0xE9; *(DWORD *)q = (addr + stolen) - (DWORD)(q + 4); q += 4;
    DWORD old;
    VirtualProtect((void *)addr, stolen, PAGE_EXECUTE_READWRITE, &old);
    BYTE *t = (BYTE *)addr;
    t[0] = 0xE9; *(DWORD *)(t + 1) = (DWORD)stub - (addr + 5);
    for (int i = 5; i < stolen; i++) t[i] = 0x90;
    VirtualProtect((void *)addr, stolen, old, &old);
    FlushInstructionCache(GetCurrentProcess(), (void *)addr, stolen);
    return 1;
}


// ---------------------------------------------------------------- DirectPlay "Locate Session" dialog automation
static char g_dlg_ip[64] = "";
static volatile LONG g_dlg_auto = 0;
static HHOOK g_cbthook = NULL;

static LRESULT CALLBACK cbt_proc(int code, WPARAM w, LPARAM l) {
    if (code == HCBT_CREATEWND) {
        CBT_CREATEWNDA *cw = (CBT_CREATEWNDA *)l;
        char cls[16] = "";
        GetClassNameA((HWND)w, cls, sizeof cls);
        int is_dialog = !strcmp(cls, "#32770") && cw->lpcs->hwndParent == NULL;
        if (!is_dialog && cw->lpcs->hwndParent) {
            // top-level owned dialogs report their owner as parent
            is_dialog = !strcmp(cls, "#32770") && !(cw->lpcs->style & WS_CHILD);
        }
        if (is_dialog && (g_dlg_auto || g_hidden)) {
            cw->lpcs->x = -32000;
            cw->lpcs->y = -32000;
            cw->lpcs->dwExStyle |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE;
        }
    } else if (code == HCBT_ACTIVATE) {
        if (g_hidden) return 1;  // never let a hidden bot window take activation
    }
    return CallNextHookEx(g_cbthook, code, w, l);
}

static BOOL CALLBACK dlg_enum(HWND h, LPARAM lp) {
    (void)lp;
    DWORD pid;
    GetWindowThreadProcessId(h, &pid);
    if (pid != GetCurrentProcessId()) return TRUE;
    char cls[16] = "", title[64] = "";
    GetClassNameA(h, cls, sizeof cls);
    if (strcmp(cls, "#32770")) return TRUE;
    GetWindowTextA(h, title, sizeof title);
    if (!strstr(title, "Locate Session")) return TRUE;
    SetWindowPos(h, HWND_BOTTOM, -32000, -32000, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE);
    HWND ed = GetDlgItem(h, 1000);
    if (ed) SendMessageA(ed, WM_SETTEXT, 0, (LPARAM)g_dlg_ip);
    PostMessageA(h, WM_COMMAND, MAKEWPARAM(IDOK, BN_CLICKED), (LPARAM)GetDlgItem(h, IDOK));
    InterlockedIncrement(&st_dlg);
    return TRUE;
}

static DWORD WINAPI dlg_thread(LPVOID p) {
    (void)p;
    for (;;) {
        if (g_dlg_auto) EnumWindows(dlg_enum, 0);
        Sleep(5);
    }
    return 0;
}

static void ensure_cbthook(void) {
    if (g_cbthook || !g_hwnd) return;
    HMODULE self = NULL;
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)cbt_proc, &self);
    g_cbthook = SetWindowsHookExA(WH_CBT, cbt_proc, self, GetWindowThreadProcessId(g_hwnd, NULL));
}

// ---------------------------------------------------------------- IAT patching
static void *patch_iat(HMODULE mod, const char *dll, const char *fn, void *hook) {
    BYTE *base = (BYTE *)mod;
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)base;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(base + dos->e_lfanew);
    IMAGE_DATA_DIRECTORY dir = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    if (!dir.VirtualAddress) return NULL;
    IMAGE_IMPORT_DESCRIPTOR *imp = (IMAGE_IMPORT_DESCRIPTOR *)(base + dir.VirtualAddress);
    for (; imp->Name; imp++) {
        if (_stricmp((char *)(base + imp->Name), dll) != 0) continue;
        if (!imp->OriginalFirstThunk && mod != GetModuleHandleA(NULL)) continue;  // bound imports: no name table
        IMAGE_THUNK_DATA *names = (IMAGE_THUNK_DATA *)(base + (imp->OriginalFirstThunk ? imp->OriginalFirstThunk : imp->FirstThunk));
        IMAGE_THUNK_DATA *iat = (IMAGE_THUNK_DATA *)(base + imp->FirstThunk);
        for (; names->u1.AddressOfData; names++, iat++) {
            if (names->u1.Ordinal & IMAGE_ORDINAL_FLAG) continue;
            IMAGE_IMPORT_BY_NAME *ibn = (IMAGE_IMPORT_BY_NAME *)(base + names->u1.AddressOfData);
            if (IsBadReadPtr(ibn, 4) || strcmp((char *)ibn->Name, fn) != 0) continue;
            DWORD old;
            void *orig = (void *)iat->u1.Function;
            VirtualProtect(&iat->u1.Function, sizeof(void *), PAGE_READWRITE, &old);
            iat->u1.Function = (ULONG_PTR)hook;
            VirtualProtect(&iat->u1.Function, sizeof(void *), old, &old);
            return orig;
        }
    }
    return NULL;
}

#define HOOK(name)                                                                  \
    do {                                                                            \
        void *o = patch_iat(exe, "USER32.dll", #name, (void *)h_##name);            \
        o_##name = o ? (void *)o : (void *)GetProcAddress(u32, #name);              \
    } while (0)

// Window-visibility hooks are also applied to every non-system module (cnc-ddraw shows/activates the window itself).
// These call the real user32 functions directly: the EXE's own IAT entries may point into cnc-ddraw, which would recurse.
static ShowWindow_t r_ShowWindow;
static SetWindowPos_t r_SetWindowPos;
static BoolHwnd_t r_SetForegroundWindow, r_BringWindowToTop;
static BOOL WINAPI hm_ShowWindow(HWND h, int cmd) {
    if (g_hidden && (h == g_hwnd || !g_hwnd)) return r_ShowWindow(h, SW_HIDE);
    return r_ShowWindow(h, cmd);
}
static BOOL WINAPI hm_SetWindowPos(HWND h, HWND after, int x, int y, int cx, int cy, UINT f) {
    if (g_hidden && h == g_hwnd) { f &= ~SWP_SHOWWINDOW; f |= SWP_NOACTIVATE; }
    return r_SetWindowPos(h, after, x, y, cx, cy, f);
}
static BOOL WINAPI hm_SetForegroundWindow(HWND h) { return (g_virtual || g_hidden) ? TRUE : r_SetForegroundWindow(h); }
static BOOL WINAPI hm_BringWindowToTop(HWND h) { return (g_virtual || g_hidden) ? TRUE : r_BringWindowToTop(h); }
typedef BOOL(WINAPI *SetActiveWindow_t)(HWND);
static void patch_all_modules_dll(const char *dll, const char *fn, void *hook);
static void patch_all_modules(const char *fn, void *hook) {
    patch_all_modules_dll("USER32.dll", fn, hook);
    patch_all_modules_dll("user32.dll", fn, hook);
}
static void patch_all_modules_dll(const char *dll, const char *fn, void *hook) {
    HMODULE mods[256];
    DWORD need = 0;
    if (!EnumProcessModules(GetCurrentProcess(), mods, sizeof mods, &need)) return;
    char sysdir[MAX_PATH];
    GetSystemWindowsDirectoryA(sysdir, sizeof sysdir);
    size_t sl = strlen(sysdir);
    HMODULE self = NULL;
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)patch_all_modules, &self);
    for (DWORD i = 0; i < need / sizeof(HMODULE); i++) {
        char path[MAX_PATH];
        if (mods[i] == self || mods[i] == GetModuleHandleA(NULL)) continue;
        GetModuleFileNameA(mods[i], path, sizeof path);
        if (_strnicmp(path, sysdir, sl) == 0) continue;
        patch_iat(mods[i], dll, fn, hook);
    }
}

static void install_hooks(void) {
    HMODULE exe = GetModuleHandleA(NULL);
    HMODULE u32 = GetModuleHandleA("user32.dll");
    HOOK(GetCursorPos);
    HOOK(SetCursorPos);
    HOOK(GetAsyncKeyState);
    HOOK(GetKeyState);
    HOOK(GetKeyboardState);
    HOOK(GetForegroundWindow);
    HOOK(GetActiveWindow);
    HOOK(GetFocus);
    HOOK(GetCapture);
    HOOK(SetForegroundWindow);
    HOOK(BringWindowToTop);
    HOOK(SetFocus);
    HOOK(ShowWindow);
    HOOK(SetWindowPos);
    HOOK(PeekMessageA);
    HOOK(GetMessageA);
    HOOK(ScreenToClient);
    HOOK(ClientToScreen);
    r_ShowWindow = (ShowWindow_t)GetProcAddress(u32, "ShowWindow");
    r_SetWindowPos = (SetWindowPos_t)GetProcAddress(u32, "SetWindowPos");
    r_SetForegroundWindow = (BoolHwnd_t)GetProcAddress(u32, "SetForegroundWindow");
    r_BringWindowToTop = (BoolHwnd_t)GetProcAddress(u32, "BringWindowToTop");
    patch_all_modules("ShowWindow", (void *)hm_ShowWindow);
    patch_all_modules("SetWindowPos", (void *)hm_SetWindowPos);
    patch_all_modules("SetForegroundWindow", (void *)hm_SetForegroundWindow);
    patch_all_modules("BringWindowToTop", (void *)hm_BringWindowToTop);
}

// ---------------------------------------------------------------- window lookup
static BOOL CALLBACK enum_cb(HWND h, LPARAM lp) {
    DWORD pid;
    GetWindowThreadProcessId(h, &pid);
    if (pid == GetCurrentProcessId() && GetWindow(h, GW_OWNER) == NULL) {
        char cls[64];
        GetClassNameA(h, cls, sizeof cls);
        if (strstr(cls, "Age of Empires")) { *(HWND *)lp = h; return FALSE; }
    }
    return TRUE;
}
static HWND find_game_window(void) {
    HWND h = NULL;
    EnumWindows(enum_cb, (LPARAM)&h);
    return h;
}

// ---------------------------------------------------------------- input helpers
static DWORD run_on_main(CallReq *r);

static void deliver(UINT msg, WPARAM w, LPARAM l) {
    if (g_mode == 1) { PostMessageA(g_hwnd, msg, w, l); return; }
    CallReq r;
    memset(&r, 0, sizeof r);
    r.conv = 3;
    r.addr = msg;
    r.args[0] = (DWORD)w;
    r.args[1] = (DWORD)l;
    r.argc = 2;
    run_on_main(&r);
}
static LPARAM lp_xy(void) { return MAKELPARAM((WORD)g_vx, (WORD)g_vy); }
static WPARAM mk_flags(void) {
    WPARAM w = 0;
    if (g_keys[VK_LBUTTON] & 0x80) w |= MK_LBUTTON;
    if (g_keys[VK_RBUTTON] & 0x80) w |= MK_RBUTTON;
    if (g_keys[VK_SHIFT] & 0x80) w |= MK_SHIFT;
    if (g_keys[VK_CONTROL] & 0x80) w |= MK_CONTROL;
    return w;
}
static void mouse_move(int x, int y) {
    g_vx = x; g_vy = y;
    deliver(WM_MOUSEMOVE, mk_flags(), lp_xy());
}
static void mouse_button(int right, int down) {
    int vk = right ? VK_RBUTTON : VK_LBUTTON;
    g_keys[vk] = down ? 0x80 : 0;
    UINT msg = right ? (down ? WM_RBUTTONDOWN : WM_RBUTTONUP) : (down ? WM_LBUTTONDOWN : WM_LBUTTONUP);
    deliver(msg, mk_flags(), lp_xy());
}
static void key_event(int vk, int down) {
    UINT sc = MapVirtualKeyA(vk, 0);
    LPARAM lp = 1 | (sc << 16);
    if (!down) lp |= 0xC0000000;
    g_keys[vk & 0xFF] = down ? 0x80 : 0;
    if (vk == VK_LSHIFT || vk == VK_RSHIFT) g_keys[VK_SHIFT] = g_keys[vk & 0xFF];
    if (vk == VK_LCONTROL || vk == VK_RCONTROL) g_keys[VK_CONTROL] = g_keys[vk & 0xFF];
    deliver(down ? WM_KEYDOWN : WM_KEYUP, vk, lp);
}

// ---------------------------------------------------------------- command processing
// Queue a request for the game's main thread and wait. Returns 1 on success.
static DWORD run_on_main(CallReq *r) {
    r->done = CreateEventA(NULL, TRUE, FALSE, NULL);
    EnterCriticalSection(&g_qlock);
    g_queue[g_qn++] = r;
    LeaveCriticalSection(&g_qlock);
    PostMessageA(g_hwnd, WM_NULL, 0, 0);
    DWORD w = WaitForSingleObject(r->done, 10000);
    DWORD ok = 1;
    if (w != WAIT_OBJECT_0) {
        EnterCriticalSection(&g_qlock);
        for (int k = 0; k < g_qn; k++) if (g_queue[k] == r) { g_queue[k] = g_queue[--g_qn]; break; }
        LeaveCriticalSection(&g_qlock);
        ok = 0;
    }
    CloseHandle(r->done);
    return ok;
}

static void reply(HANDLE pipe, const char *s) {
    DWORD w;
    WriteFile(pipe, s, (DWORD)strlen(s), &w, NULL);
    WriteFile(pipe, "\n", 1, &w, NULL);
}

static void handle(HANDLE pipe, char *line) {
    char out[256];
    char *tok[16];
    int n = 0;
    for (char *t = strtok(line, " \t\r"); t && n < 16; t = strtok(NULL, " \t\r")) tok[n++] = t;
    if (!n) { reply(pipe, "err empty"); return; }
    if (!g_hwnd) g_hwnd = find_game_window();
    ensure_msghook();
    ensure_cbthook();
    const char *c = tok[0];
    if (!strcmp(c, "ping")) {
        sprintf(out, "ok hwnd=%lu virtual=%ld hidden=%ld", (unsigned long)(ULONG_PTR)g_hwnd, g_virtual, g_hidden);
        reply(pipe, out);
    } else if (!strcmp(c, "stat")) {
        sprintf(out, "ok dlg=%ld gcp=%ld gaks=%ld drain=%ld msghook=%ld hook=%p proc=%p wproc=%p tid=%lu", st_dlg, st_gcp, st_gaks, st_drain, st_msghook,
                (void *)g_msghook, (void *)GetClassLongA(g_hwnd, GCL_WNDPROC), (void *)GetWindowLongA(g_hwnd, GWL_WNDPROC),
                GetWindowThreadProcessId(g_hwnd, NULL));
        reply(pipe, out);
    } else if (!strcmp(c, "trace") && n > 2) {
        int ok = install_trace(strtoul(tok[1], NULL, 0), atoi(tok[2]));
        reply(pipe, ok ? "ok" : "err trace");
    } else if (!strcmp(c, "traceinfo")) {
        sprintf(out, "ok buf=%lu n=%ld cap=%d recsize=%d", (unsigned long)(DWORD)g_trace, g_trace_n, TRACE_N, (int)sizeof(TraceRec));
        reply(pipe, out);
    } else if (!strcmp(c, "fglock") && n > 1) {
        BOOL ok = LockSetForegroundWindow(atoi(tok[1]));   // only works when called by the foreground process
        reply(pipe, ok ? "ok" : "err fglock");
    } else if (!strcmp(c, "noreg") && n > 1) {
        g_noreg = atoi(tok[1]);
        static int reg_hooked = 0;
        if (g_noreg && !reg_hooked) {     // only bot processes ever get this hook
            reg_hooked = 1;
            o_RegSetValueExA = (RegSetValueExA_t)GetProcAddress(GetModuleHandleA("advapi32.dll"), "RegSetValueExA");
            patch_iat(GetModuleHandleA(NULL), "ADVAPI32.dll", "RegSetValueExA", (void *)h_RegSetValueExA);
            patch_all_modules_dll("ADVAPI32.dll", "RegSetValueExA", (void *)h_RegSetValueExA);
        }
        reply(pipe, "ok");
    } else if (!strcmp(c, "autodlg") && n > 1) {
        strncpy(g_dlg_ip, tok[1], sizeof g_dlg_ip - 1);
        if (!strcmp(g_dlg_ip, "-")) g_dlg_ip[0] = 0;
        g_dlg_auto = 1;
        reply(pipe, "ok");
    } else if (!strcmp(c, "mode") && n > 1) {
        g_mode = atoi(tok[1]);
        reply(pipe, "ok");
    } else if (!strcmp(c, "vin") && n > 1) {
        g_virtual = atoi(tok[1]);
        if (g_virtual) { memset(g_keys, 0, sizeof g_keys); deliver(WM_ACTIVATEAPP, TRUE, 0); deliver(WM_ACTIVATE, WA_ACTIVE, 0); }
        reply(pipe, "ok");
    } else if (!strcmp(c, "hide") && n > 1) {
        g_hidden = atoi(tok[1]);
        r_ShowWindow(g_hwnd, g_hidden ? SW_HIDE : SW_SHOWNOACTIVATE);
        reply(pipe, "ok");
    } else if (!strcmp(c, "move") && n > 2) {
        mouse_move(atoi(tok[1]), atoi(tok[2]));
        reply(pipe, "ok");
    } else if ((!strcmp(c, "down") || !strcmp(c, "up")) && n > 1) {
        mouse_button(tok[1][0] == 'r', c[0] == 'd');
        reply(pipe, "ok");
    } else if (!strcmp(c, "click") && n > 2) {
        int right = n > 3 && tok[3][0] == 'r';
        mouse_move(atoi(tok[1]), atoi(tok[2]));
        Sleep(30);
        mouse_button(right, 1);
        Sleep(60);
        mouse_button(right, 0);
        reply(pipe, "ok");
    } else if (!strcmp(c, "key") && n > 2) {
        key_event(strtol(tok[1], NULL, 0), tok[2][0] == 'd');
        reply(pipe, "ok");
    } else if (!strcmp(c, "tap") && n > 1) {
        int vk = strtol(tok[1], NULL, 0);
        key_event(vk, 1); Sleep(40); key_event(vk, 0);
        reply(pipe, "ok");
    } else if (!strcmp(c, "char") && n > 1) {
        deliver(WM_CHAR, (WPARAM)strtol(tok[1], NULL, 0), 1);
        reply(pipe, "ok");
    } else if ((!strcmp(c, "thiscall") || !strcmp(c, "stdcall") || !strcmp(c, "cdecl")) && n > 1) {
        CallReq r;
        memset(&r, 0, sizeof r);
        r.conv = c[0] == 't' ? 0 : (c[0] == 's' ? 1 : 2);
        r.addr = strtoul(tok[1], NULL, 0);
        int i = 2;
        if (r.conv == 0) { r.ecx = n > 2 ? strtoul(tok[2], NULL, 0) : 0; i = 3; }
        for (; i < n && r.argc < 10; i++) r.args[r.argc++] = strtoul(tok[i], NULL, 0);
        DWORD ok = run_on_main(&r);
        if (!ok) reply(pipe, "err timeout");
        else { sprintf(out, "ok %lu", (unsigned long)r.result); reply(pipe, out); }
    } else {
        reply(pipe, "err unknown");
    }
}

static DWORD WINAPI client_thread(LPVOID p) {
    HANDLE pipe = (HANDLE)p;
    char buf[1024];
    int len = 0;
    for (;;) {
        DWORD rd;
        if (!ReadFile(pipe, buf + len, 1, &rd, NULL) || rd == 0) break;
        if (buf[len] == '\n') { buf[len] = 0; handle(pipe, buf); len = 0; }
        else if (len < (int)sizeof(buf) - 2) len++;
    }
    DisconnectNamedPipe(pipe);
    CloseHandle(pipe);
    return 0;
}

static DWORD WINAPI pipe_thread(LPVOID p) {
    (void)p;
    char name[64];
    sprintf(name, "\\\\.\\pipe\\aoehook_%lu", GetCurrentProcessId());
    for (;;) {
        HANDLE pipe = CreateNamedPipeA(name, PIPE_ACCESS_DUPLEX, PIPE_TYPE_BYTE | PIPE_WAIT, PIPE_UNLIMITED_INSTANCES, 4096, 4096, 0, NULL);
        if (pipe == INVALID_HANDLE_VALUE) { Sleep(200); continue; }
        if (!ConnectNamedPipe(pipe, NULL) && GetLastError() != ERROR_PIPE_CONNECTED) { CloseHandle(pipe); continue; }
        CreateThread(NULL, 0, client_thread, pipe, 0, NULL);
    }
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID res) {
    (void)res;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(inst);
        InitializeCriticalSection(&g_qlock);
        memset(g_keys, 0, sizeof g_keys);
        install_hooks();
        g_hwnd = find_game_window();
        CreateThread(NULL, 0, pipe_thread, NULL, 0, NULL);
        CreateThread(NULL, 0, dlg_thread, NULL, 0, NULL);
    }
    return TRUE;
}
