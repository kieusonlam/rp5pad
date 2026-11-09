"""pad_tester.py: a window showing the virtual pad as Windows sees it, read through XInput as games do, with the connection's numbers. Same layout as the Android app's PadView. Runs on its own thread inside pad_tray.py; `python pad_tester.py` opens it alone for a look."""
import ctypes
import os
import threading
import tkinter as tk
import traceback

import pad_server

HERE = os.path.dirname(os.path.abspath(__file__))
BG, TEXT, MUTED, LIT = "#0B0F14", "#E6EBF0", "#8A97A6", "#22D3EE"
BUTTONS = {"up": 1, "down": 2, "left": 4, "right": 8, "start": 0x10, "back": 0x20, "l3": 0x40, "r3": 0x80, "lb": 0x100, "rb": 0x200, "a": 0x1000, "b": 0x2000, "x": 0x4000, "y": 0x8000}


class XState(ctypes.Structure):
    _fields_ = [("packet", ctypes.c_ulong), ("buttons", ctypes.c_ushort), ("lt", ctypes.c_ubyte), ("rt", ctypes.c_ubyte), ("lx", ctypes.c_short), ("ly", ctypes.c_short), ("rx", ctypes.c_short), ("ry", ctypes.c_short)]


def read_xinput(slot):
    """(slot used, state) or (None, None). The slot the driver gave our pad; with none known, the first pad present."""
    get = ctypes.windll.xinput1_4.XInputGetState
    for i in ([slot] if slot is not None else range(4)):
        s = XState()
        if get(i, ctypes.byref(s)) == 0:
            return i, s
    return None, None


def work_area():
    """(left, top, right, bottom) of the screen under the mouse, without the taskbar."""
    class RECT(ctypes.Structure):
        _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]

    class INFO(ctypes.Structure):
        _fields_ = [("size", ctypes.c_ulong), ("monitor", RECT), ("work", RECT), ("flags", ctypes.c_ulong)]

    u = ctypes.windll.user32
    pt = (ctypes.c_long * 2)()
    u.GetCursorPos(pt)
    u.MonitorFromPoint.restype = ctypes.c_void_p
    mon = u.MonitorFromPoint(ctypes.c_longlong(pt[0] & 0xFFFFFFFF | pt[1] << 32), 2)   # POINT by value; 2: the nearest screen
    info = INFO(size=ctypes.sizeof(INFO))
    if not mon or not u.GetMonitorInfoW(ctypes.c_void_p(mon), ctypes.byref(info)):
        return 0, 0, u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    w = info.work
    return w.l, w.t, w.r, w.b


class Tester:
    def __init__(self):
        self.thread = None
        self.front = False

    def open(self):
        if self.thread and self.thread.is_alive():
            self.front = True
            return
        self.thread = threading.Thread(target=self.guarded, daemon=True, name="tester")
        self.thread.start()

    def guarded(self):
        try:
            self.run()
        except Exception:
            os.makedirs(os.path.expanduser(r"~\.rp5pad"), exist_ok=True)
            with open(os.path.expanduser(r"~\.rp5pad\tester.log"), "a", encoding="utf-8") as f:
                traceback.print_exc(file=f)

    def run(self):
        r = tk.Tk()
        r.withdraw()
        self.S = 2 if r.winfo_fpixels("1i") / 96 >= 1.5 else 1
        S = self.S
        self.r, self.images = r, {}
        r.title("RP5 Pad tester")
        r.configure(bg=BG)
        r.resizable(False, False)
        r.protocol("WM_DELETE_WINDOW", r.withdraw)   # hidden, not destroyed: Tk cannot safely start again on a new thread
        r.iconbitmap(os.path.join(HERE, "assets", "app.ico"))
        self.c = tk.Canvas(r, width=956 * S, height=572 * S, bg=BG, highlightthickness=0)
        self.c.pack()
        self.build()
        self.last, self.last_info = None, None
        r.update_idletasks()
        try:   # the dark title bar of Windows 10 and 11
            ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.windll.user32.GetParent(r.winfo_id()), 20, ctypes.byref(ctypes.c_int(1)), 4)
        except OSError:
            pass
        self.center()
        r.deiconify()
        r.lift()
        r.focus_force()
        self.tick()
        r.mainloop()

    def center(self):
        """Puts the window, title bar included, in the middle of the screen under the mouse."""
        r, m = self.r, ctypes.windll.user32.GetSystemMetrics
        r.update_idletasks()
        frame = m(33) + m(92)   # sizing frame + padded border, on each side
        w, h = r.winfo_reqwidth() + 2 * frame, r.winfo_reqheight() + m(4) + 2 * frame   # 4: the title bar
        left, top, right, bottom = work_area()
        r.geometry(f"+{left + max(0, (right - left - w) // 2)}+{top + max(0, (bottom - top - h) // 2)}")

    def img(self, name):
        if name not in self.images:
            self.images[name] = tk.PhotoImage(file=os.path.join(HERE, "assets", "tester", str(self.S), name + ".png"))
        return self.images[name]

    def font(self, size, bold=False):
        return ("Segoe UI Semibold" if bold else "Segoe UI", -round(size * self.S))

    # Pad coordinates are the Android view's: units of 6 logical pixels, from the pad area's corner
    def px(self, x, y):
        return (336 + x * 6) * self.S, (16 + y * 6) * self.S

    def sprite(self, name, x, y):
        return self.c.create_image(*self.px(x, y), image=self.img(name))

    def label(self, s, x, y, size):
        return self.c.create_text(*self.px(x, y), text=s, fill=MUTED, font=self.font(size * 6, True))

    def build(self):
        c, S = self.c, self.S
        c.create_image(40 * S, 96 * S, image=self.img("logo"))
        c.create_text(72 * S, 96 * S, text="RP5 Pad", anchor="w", fill=TEXT, font=self.font(24, True))
        c.create_image(170 * S, 180 * S, image=self.img("card_status"))
        self.dot = c.create_image(42 * S, 180 * S, image=self.img("status_wait"))
        self.title = c.create_text(62 * S, 166 * S, text="", anchor="w", fill=TEXT, font=self.font(17, True))
        self.sub = c.create_text(62 * S, 194 * S, text="", anchor="w", fill=MUTED, font=self.font(13), width=240 * S)
        c.create_image(170 * S, 333 * S, image=self.img("card_stats"))
        self.values = {}
        for i, (key, name) in enumerate((("link", "Connection"), ("rtt", "Round trip"), ("pps", "Updates per second"), ("slot", "Windows slot"))):
            y = (264 + i * 36) * S
            c.create_text(36 * S, y, text=name, anchor="w", fill=MUTED, font=self.font(14))
            self.values[key] = c.create_text(304 * S, y, text="–", anchor="e", fill=TEXT, font=self.font(14, True))
        c.create_text(36 * S, 438 * S, text="Read through XInput, the same way games see it.", anchor="w", fill=MUTED, font=self.font(12), width=280 * S)

        self.sprite("body", 50, 49)
        self.parts = {}
        self.trig = {"lt": self.sprite("trigL_0", 26, 8.5), "rt": self.sprite("trigR_0", 74, 8.5)}
        self.trig_label = {"lt": self.label("LT", 26, 8.5, 2.5), "rt": self.label("RT", 74, 8.5, 2.5)}

        def part(key, shape, x, y, text=None, size=2.5):
            self.parts[key] = (self.sprite(shape + "_off", x, y), shape, self.label(text, x, y, size) if text else None)

        part("lb", "pill", 26, 15.5, "LB")
        part("rb", "pill", 74, 15.5, "RB")
        dx, dy = 21, 37
        part("up", "dv", dx, dy - 3.9)
        part("down", "dv", dx, dy + 3.9)
        part("left", "dh", dx - 3.9, dy)
        part("right", "dh", dx + 3.9, dy)
        fx, fy, o = 79, 37, 5.4
        part("y", "face", fx, fy - o, "Y", 3)
        part("a", "face", fx, fy + o, "A", 3)
        part("x", "face", fx - o, fy, "X", 3)
        part("b", "face", fx + o, fy, "B", 3)
        part("back", "mini", 44.75, 31.5)
        part("start", "mini", 55.25, 31.5)
        self.sprite("ring", 36, 49)
        self.sprite("ring", 64, 49)
        self.knobs = {"l": self.sprite("knob_off", 36, 49), "r": self.sprite("knob_off", 64, 49)}
        self.knob_at = {"l": (36, 49), "r": (64, 49)}

    def draw_pad(self, b, lt, rt, lx, ly, rx, ry):
        c = self.c
        for key, (item, shape, text) in self.parts.items():
            on = bool(b & BUTTONS[key])
            c.itemconfig(item, image=self.img(shape + ("_on" if on else "_off")))
            if text:
                c.itemconfig(text, fill=BG if on else MUTED)
        for key, side, v in (("lt", "L", lt), ("rt", "R", rt)):
            c.itemconfig(self.trig[key], image=self.img(f"trig{side}_{round(v / 255 * 12)}"))
            c.itemconfig(self.trig_label[key], fill=BG if v > 127 else MUTED)
        for key, sx, sy, press in (("l", lx, ly, b & BUTTONS["l3"]), ("r", rx, ry, b & BUTTONS["r3"])):
            cx, cy = self.knob_at[key]
            moved = abs(sx) > 3276 or abs(sy) > 3276
            c.coords(self.knobs[key], *self.px(cx + sx / 32767 * 3.4, cy - sy / 32767 * 3.4))   # XInput: up is positive
            c.itemconfig(self.knobs[key], image=self.img("knob_on" if press or moved else "knob_off"))

    def tick(self):
        if self.front:
            self.front = False
            if self.r.state() == "withdrawn":   # reopened: centred again; already open: left where it is
                self.center()
            self.r.deiconify()
            self.r.lift()
            self.r.focus_force()
        if self.r.state() == "withdrawn":
            self.r.after(150, self.tick)
            return
        st = pad_server.stats
        ip = st.get("ip")
        slot, x = read_xinput(st.get("slot")) if ip else (None, None)
        now = (x.buttons, x.lt, x.rt, x.lx, x.ly, x.rx, x.ry) if x else (0, 0, 0, 0, 0, 0, 0)
        if now != self.last:
            self.last = now
            self.draw_pad(*now)
        rtt = st.get("rtt")
        info = (ip, slot, None if rtt is None else round(rtt), st.get("pps", 0))
        if info != self.last_info:
            self.last_info = info
            c = self.c
            if ip:
                usb = ip == "127.0.0.1"
                c.itemconfig(self.dot, image=self.img("status_on"))
                c.itemconfig(self.title, text="Connected")
                c.itemconfig(self.sub, text="Press something on the RP5: it lights up here if Windows received it.")
                c.itemconfig(self.values["link"], text="USB" if usb else "WiFi")
            else:
                c.itemconfig(self.dot, image=self.img("status_wait"))
                c.itemconfig(self.title, text="Waiting for the RP5")
                c.itemconfig(self.sub, text="Open RP5 Pad on the device. The pad appears in Windows once it connects.")
                c.itemconfig(self.values["link"], text="–")
            c.itemconfig(self.values["rtt"], text="–" if info[2] is None else f"{info[2]} ms")
            c.itemconfig(self.values["pps"], text=str(info[3]) if ip else "–")
            c.itemconfig(self.values["slot"], text="–" if slot is None else f"Player {slot + 1}")
        self.r.after(16, self.tick)


if __name__ == "__main__":
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    t = Tester()
    t.guarded()
