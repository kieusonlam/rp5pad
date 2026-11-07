"""pad_tray.py: pad_server in the Windows notification area, no window and no extra packages (Shell_NotifyIcon through ctypes).

Run with pythonw. Left click: the tester. Right click: status, tester, Allow WiFi, Forget, Start with Windows, Quit. The icon is cyan while the RP5 is connected.
"""
import ctypes
import json
import os
import queue
import subprocess
import sys
import threading
import winreg
from ctypes import wintypes as w

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pad_server  # noqa: E402
import pad_tester  # noqa: E402

FROZEN = getattr(sys, "frozen", False)   # the installed exe: its own folder may be read-only, and USB needs adb, so WiFi (which needs pairing) starts on
CONFIG = os.path.join(os.path.dirname(pad_server.state_path()), "pad_app.json") if FROZEN else os.path.join(HERE, "pad_app.json")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "RP5 Pad"
CLASS = "RP5PadTray"
WM_DESTROY, WM_COMMAND, WM_LBUTTONUP, WM_RBUTTONUP, WM_NULL = 0x2, 0x111, 0x202, 0x205, 0
WM_TRAY, WM_STATUS = 0x8001, 0x8002
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 1, 2, 4, 0x10
MF_STRING, MF_GRAYED, MF_CHECKED, MF_SEPARATOR = 0, 1, 8, 0x800
TPM_RETURNCMD, TPM_RIGHTBUTTON = 0x100, 0x2
ID_WIFI, ID_START, ID_QUIT, ID_STATUS, ID_FORGET, ID_TEST = 2, 3, 4, 1, 5, 6
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", w.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", w.HINSTANCE), ("hIcon", w.HANDLE), ("hCursor", w.HANDLE), ("hbrBackground", w.HANDLE), ("lpszMenuName", w.LPCWSTR), ("lpszClassName", w.LPCWSTR)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", w.DWORD), ("hWnd", w.HWND), ("uID", w.UINT), ("uFlags", w.UINT), ("uCallbackMessage", w.UINT), ("hIcon", w.HANDLE), ("szTip", w.WCHAR * 128), ("dwState", w.DWORD), ("dwStateMask", w.DWORD), ("szInfo", w.WCHAR * 256), ("uVersion", w.UINT), ("szInfoTitle", w.WCHAR * 64), ("dwInfoFlags", w.DWORD), ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", w.HANDLE)]


u32 = ctypes.WinDLL("user32", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
s32 = ctypes.WinDLL("shell32", use_last_error=True)
u32.DefWindowProcW.restype, u32.DefWindowProcW.argtypes = LRESULT, [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
u32.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
u32.RegisterClassW.restype, u32.RegisterClassW.argtypes = w.ATOM, [ctypes.POINTER(WNDCLASSW)]
u32.CreateWindowExW.restype = w.HWND
u32.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID]
u32.LoadImageW.restype, u32.LoadImageW.argtypes = w.HANDLE, [w.HINSTANCE, w.LPCWSTR, w.UINT, ctypes.c_int, ctypes.c_int, w.UINT]
u32.CreatePopupMenu.restype = w.HMENU
u32.AppendMenuW.argtypes = [w.HMENU, w.UINT, ctypes.c_size_t, w.LPCWSTR]
u32.TrackPopupMenu.argtypes = [w.HMENU, w.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HWND, w.LPVOID]
u32.DestroyMenu.argtypes = [w.HMENU]
u32.SetForegroundWindow.argtypes = [w.HWND]
u32.DestroyWindow.argtypes = [w.HWND]
u32.MessageBoxW.argtypes = [w.HWND, w.LPCWSTR, w.LPCWSTR, w.UINT]
u32.MessageBoxTimeoutW.argtypes = [w.HWND, w.LPCWSTR, w.LPCWSTR, w.UINT, w.WORD, w.DWORD]
u32.GetMessageW.argtypes = [ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT]
k32.GetModuleHandleW.restype, k32.GetModuleHandleW.argtypes = w.HMODULE, [w.LPCWSTR]
k32.CreateMutexW.restype, k32.CreateMutexW.argtypes = w.HANDLE, [w.LPVOID, w.BOOL, w.LPCWSTR]
k32.CloseHandle.argtypes = [w.HANDLE]
s32.Shell_NotifyIconW.argtypes = [w.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]


def load_cfg():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def start_command():
    if FROZEN:
        return f'"{sys.executable}" --startup'
    exe = sys.executable.replace("python.exe", "pythonw.exe")
    return f'"{exe}" "{os.path.abspath(__file__)}" --startup'


def startup_on(key=RUN_KEY):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            winreg.QueryValueEx(k, RUN_NAME)
        return True
    except OSError:
        return False


def startup_set(on, key=RUN_KEY):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
        if on:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, start_command())
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass


def ask_pair(name, ip, code):
    """Runs on the server's thread. Unanswered after a minute counts as No, which is also the default button."""
    text = f"A device wants to connect over WiFi.\n\nDevice: {name}\nAddress: {ip}\nCode: {code[:3]} {code[3:]}\n\nAllow it only if your device is showing the same code."
    return u32.MessageBoxTimeoutW(None, text, "RP5 Pad: allow this device?", 0x4 | 0x20 | 0x100 | 0x10000 | 0x40000, 0, 60000) == 6   # YESNO, QUESTION, DEFBUTTON2, SETFOREGROUND, TOPMOST; IDYES


class Tray:
    def __init__(self, quiet):
        self.lan = bool(load_cfg().get("lan", FROZEN))
        self.q = queue.Queue()
        self.tester = pad_tester.Tester()
        self.status = "Starting…"
        self.recreated = u32.RegisterWindowMessageW("TaskbarCreated")
        self.proc = WNDPROC(self.wndproc)   # kept: the window calls it for as long as it lives
        inst = k32.GetModuleHandleW(None)
        wc = WNDCLASSW(lpfnWndProc=self.proc, hInstance=inst, lpszClassName=CLASS)
        u32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = u32.CreateWindowExW(0, CLASS, "RP5 Pad", 0, 0, 0, 0, 0, None, None, inst, None)
        size = u32.GetSystemMetrics(49)   # SM_CXSMICON: the tray's size, at this screen's scale
        self.icons = {n: u32.LoadImageW(None, os.path.join(HERE, "assets", f"tray_{n}.ico"), 1, size, size, 0x10) for n in ("on", "off", "err")}   # IMAGE_ICON, LR_LOADFROMFILE
        self.icon = "off"
        self.notify(NIM_ADD)
        if not quiet:
            self.balloon("RP5 Pad is running", "Find it in the notification area. Right click for options.")
        pad_server.report = self.on_report
        pad_server.ask_pair = ask_pair
        threading.Thread(target=self.serve, daemon=True).start()

    def data(self, flags):
        d = NOTIFYICONDATAW(cbSize=ctypes.sizeof(NOTIFYICONDATAW), hWnd=self.hwnd, uID=1, uFlags=flags, uCallbackMessage=WM_TRAY, hIcon=self.icons[self.icon])
        d.szTip = ("RP5 Pad: " + self.status)[:127]
        return d

    def notify(self, op):
        s32.Shell_NotifyIconW(op, ctypes.byref(self.data(NIF_MESSAGE | NIF_ICON | NIF_TIP)))

    def balloon(self, title, text):
        d = self.data(NIF_INFO)
        d.szInfoTitle, d.szInfo = title[:63], text[:255]
        s32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(d))

    def on_report(self, *a, **k):   # from the server's thread
        self.q.put(" ".join(str(x) for x in a))
        u32.PostMessageW(self.hwnd, WM_STATUS, 0, 0)

    def serve(self):
        try:
            pad_server.run(pad_server.Pad(), self.lan, pad_server.PORT)
        except OSError:
            self.on_report("!Port 7878 is busy: is another copy of RP5 Pad running?")
        except Exception as e:
            self.on_report(f"!Cannot use the virtual pad driver: {e}")

    def drain(self):
        while not self.q.empty():
            m = self.q.get()
            if m.startswith("!"):
                self.status, self.icon = m[1:], "err"
                self.balloon("RP5 Pad", m[1:])
            elif m.startswith("waiting") or m.startswith("disconnected") or m.startswith("connection lost"):
                self.status, self.icon = "Waiting for the RP5", "off"
            elif m.startswith("connected:"):
                self.status, self.icon = "Connected over " + ("USB" if m.endswith("127.0.0.1") else "WiFi"), "on"
        self.notify(NIM_MODIFY)

    def menu(self):
        m = u32.CreatePopupMenu()
        u32.AppendMenuW(m, MF_STRING | MF_GRAYED, ID_STATUS, self.status)
        u32.AppendMenuW(m, MF_SEPARATOR, 0, None)
        u32.AppendMenuW(m, MF_STRING, ID_TEST, "Open tester")
        u32.AppendMenuW(m, MF_SEPARATOR, 0, None)
        u32.AppendMenuW(m, MF_STRING | (MF_CHECKED if self.lan else 0), ID_WIFI, "Allow WiFi connections")
        n = len(pad_server.Pairing().devices)
        u32.AppendMenuW(m, MF_STRING | (0 if n else MF_GRAYED), ID_FORGET, f"Forget paired devices ({n})")
        u32.AppendMenuW(m, MF_STRING | (MF_CHECKED if startup_on() else 0), ID_START, "Start with Windows")
        u32.AppendMenuW(m, MF_SEPARATOR, 0, None)
        u32.AppendMenuW(m, MF_STRING, ID_QUIT, "Quit")
        p = w.POINT()
        u32.GetCursorPos(ctypes.byref(p))
        u32.SetForegroundWindow(self.hwnd)   # or the menu stays open after a click elsewhere
        cmd = u32.TrackPopupMenu(m, TPM_RETURNCMD | TPM_RIGHTBUTTON, p.x, p.y, 0, self.hwnd, None)
        u32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        u32.DestroyMenu(m)
        if cmd:
            self.command(cmd)

    def command(self, cmd):
        if cmd == ID_TEST:
            self.tester.open()
        elif cmd == ID_START:
            startup_set(not startup_on())
        elif cmd == ID_WIFI:   # the listening socket changes: start again
            cfg = load_cfg()
            cfg["lan"] = not self.lan
            os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
            with open(CONFIG, "w", encoding="utf-8") as f:
                json.dump(cfg, f)
            self.restart = True
            u32.DestroyWindow(self.hwnd)
        elif cmd == ID_FORGET:
            if u32.MessageBoxW(self.hwnd, "Forget all paired devices? They will have to be allowed again to connect over WiFi.", "RP5 Pad", 0x4 | 0x30 | 0x100) == 6:
                pad_server.Pairing().forget_all()
                self.restart = True   # drops a device connected right now
                u32.DestroyWindow(self.hwnd)
        elif cmd == ID_QUIT:
            u32.DestroyWindow(self.hwnd)

    def wndproc(self, h, msg, wp, lp):
        if msg == WM_TRAY and lp == WM_RBUTTONUP:
            self.menu()
        elif msg == WM_TRAY and lp == WM_LBUTTONUP:
            self.tester.open()
        elif msg == WM_STATUS:
            self.drain()
        elif msg == WM_COMMAND:
            self.command(wp & 0xffff)
        elif msg == self.recreated:   # Explorer restarted
            self.notify(NIM_ADD)
        elif msg == WM_DESTROY:
            self.notify(NIM_DELETE)
            u32.PostQuitMessage(0)
        else:
            return u32.DefWindowProcW(h, msg, wp, lp)
        return 0

    restart = False

    def loop(self):
        m = w.MSG()
        while u32.GetMessageW(ctypes.byref(m), None, 0, 0) > 0:
            u32.TranslateMessage(ctypes.byref(m))
            u32.DispatchMessageW(ctypes.byref(m))


def main():
    ctypes.windll.shcore.SetProcessDpiAwareness(1)   # crisp icons and tester on scaled screens
    mutex = k32.CreateMutexW(None, False, "RP5PadTraySingle")
    if ctypes.get_last_error() == 183:   # ERROR_ALREADY_EXISTS
        u32.MessageBoxW(None, "RP5 Pad is already running. Look in the notification area.", "RP5 Pad", 0x40)
        return
    t = Tray("--startup" in sys.argv)
    t.loop()
    if t.restart:
        k32.CloseHandle(mutex)
        subprocess.Popen([sys.executable, "--startup"] if FROZEN else [sys.executable, os.path.abspath(__file__), "--startup"])
    os._exit(0)   # the server's threads are blocked in accept; the virtual pad goes with the process


if __name__ == "__main__":
    main()
