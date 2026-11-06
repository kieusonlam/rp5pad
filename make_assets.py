"""make_assets.py: the one logo, as Android vector drawables and Windows .ico files. Needs Pillow: run with _Dev\\tools\\d2r-python. Outputs are kept in the repo, so normal builds do not need this."""
import os
import re

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ACCENT, IDLE, ERROR = "#22D3EE", "#A3AEBB", "#F87171"
GRAD = ("#4F46E5", "#06B6D4")
BODY = "M30 22 L70 22 C84 22 90 30 93 44 L96 62 C98 74 90 80 83 78 C77 76 73 69 68 63 L32 63 C27 69 23 76 17 78 C10 80 2 74 4 62 L7 44 C10 30 16 22 30 22 Z"


def circle(x, y, r):
    k = r * 0.5523
    return f"M{x + r} {y} C{x + r} {y + k} {x + k} {y + r} {x} {y + r} C{x - k} {y + r} {x - r} {y + k} {x - r} {y} C{x - r} {y - k} {x - k} {y - r} {x} {y - r} C{x + k} {y - r} {x + r} {y - k} {x + r} {y} Z"


def plus(x, y, a, t):
    return f"M{x - t} {y - a} L{x + t} {y - a} L{x + t} {y - t} L{x + a} {y - t} L{x + a} {y + t} L{x + t} {y + t} L{x + t} {y + a} L{x - t} {y + a} L{x - t} {y + t} L{x - a} {y + t} L{x - a} {y - t} L{x - t} {y - t} Z"


HOLES = [plus(29, 43, 9, 3), circle(66, 49, 5), circle(76, 38, 5)]
GLYPH = " ".join([BODY] + HOLES)


def polys(d):
    """Subpaths of an M/L/C/Z path as point lists."""
    out, cur, pos = [], [], (0, 0)
    for cmd, args in re.findall(r"([MLCZ])([^MLCZ]*)", d):
        n = [float(v) for v in args.split()]
        if cmd == "M":
            cur = [(n[0], n[1])]
            pos = cur[0]
        elif cmd == "L":
            pos = (n[0], n[1])
            cur.append(pos)
        elif cmd == "C":
            for i in range(1, 25):
                t = i / 24
                u = 1 - t
                pos2 = tuple(u ** 3 * p + 3 * u * u * t * a + 3 * u * t * t * b + t ** 3 * q for p, a, b, q in zip(pos, n[0:2], n[2:4], n[4:6]))
                cur.append(pos2)
            pos = (n[4], n[5])
        else:
            out.append(cur)
    return out


def mask(size, scale=1.0, holes=True):
    """The glyph as an 8-bit mask, centred (it is drawn in a 100 x 100 box)."""
    s = size * 8
    m = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(m)
    f = s / 100 * scale
    ox = s / 2 - 50 * f
    oy = s / 2 - 51 * f
    for i, p in enumerate(polys(GLYPH)):
        if i and not holes:
            break
        d.polygon([(x * f + ox, y * f + oy) for x, y in p], fill=0 if i else 255)
    return m.resize((size, size), Image.LANCZOS)


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def tinted(size, color):
    im = Image.new("RGBA", (size, size), rgb(color) + (0,))
    im.putalpha(mask(size))
    return im


def app_icon(size):
    a, b = rgb(GRAD[0]), rgb(GRAD[1])
    grad = Image.new("RGBA", (size, size))
    px = grad.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * size - 2 or 1)
            px[x, y] = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)
    r = Image.new("L", (size * 8, size * 8), 0)
    ImageDraw.Draw(r).rounded_rectangle((0, 0, size * 8 - 1, size * 8 - 1), radius=size * 8 * 0.23, fill=255)
    grad.putalpha(r.resize((size, size), Image.LANCZOS))
    grad.paste((255, 255, 255, 255), (0, 0), mask(size, 0.76))
    return grad


def ico(path, make, sizes):
    ims = [make(s) for s in sizes]
    ims[-1].save(path, format="ICO", sizes=[(s, s) for s in sizes], append_images=ims[:-1])


def write(rel, text):
    p = os.path.join(HERE, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


NS = 'xmlns:android="http://schemas.android.com/apk/res/android"'
write("app/res/drawable/ic_fg.xml", f'''<vector {NS} android:width="108dp" android:height="108dp" android:viewportWidth="100" android:viewportHeight="100">
    <group android:scaleX="0.58" android:scaleY="0.58" android:translateX="21" android:translateY="20.4">
        <path android:fillColor="#FFFFFF" android:fillType="evenOdd" android:pathData="{GLYPH}" />
    </group>
</vector>
''')
write("app/res/drawable/ic_bg.xml", f'''<shape {NS} android:shape="rectangle">
    <gradient android:angle="315" android:startColor="{GRAD[0]}" android:endColor="{GRAD[1]}" />
</shape>
''')
write("app/res/drawable/pad_body.xml", f'''<vector {NS} android:width="100dp" android:height="100dp" android:viewportWidth="100" android:viewportHeight="100">
    <path android:fillColor="#FFFFFF" android:pathData="{BODY}" />
</vector>
''')
write("app/res/mipmap-anydpi-v26/ic_launcher.xml", f'''<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon {NS}>
    <background android:drawable="@drawable/ic_bg" />
    <foreground android:drawable="@drawable/ic_fg" />
</adaptive-icon>
''')
os.makedirs(os.path.join(HERE, "assets"), exist_ok=True)
ICON = [16, 20, 24, 32, 40, 48, 64]
for name, color in (("on", ACCENT), ("off", IDLE), ("err", ERROR)):
    ico(os.path.join(HERE, "assets", f"tray_{name}.ico"), lambda s, c=color: tinted(s, c), ICON)
ico(os.path.join(HERE, "assets", "app.ico"), app_icon, [16, 24, 32, 48, 64, 128, 256])



# ---------- the tester's pictures: the Android PadView's shapes and sizes, in units of 6 logical pixels ----------
LIT, FACE, BODYC, MARK = "#22D3EE", "#2A3440", "#182029", "#10161C"
CARD = "#141A22"
SS = 4


def rrect(w, h, r, layers):
    """A picture w x h pixels; layers: (x0, x1, y0, y1, radius, colour), drawn in order, smooth edges."""
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for x0, x1, y0, y1, rad, col in layers:
        m = Image.new("L", (w * SS, h * SS), 0)
        ImageDraw.Draw(m).rounded_rectangle((x0 * SS, y0 * SS, x1 * SS - 1, y1 * SS - 1), radius=rad * SS, fill=255)
        c = Image.new("RGBA", (w, h), rgb(col) + (255,))
        im.paste(c, (0, 0), m.resize((w, h), Image.LANCZOS))
    return im


def tester_set(S):
    d = os.path.join(HERE, "assets", "tester", str(S))
    os.makedirs(d, exist_ok=True)
    U = 6 * S

    def save(name, im):
        im.save(os.path.join(d, name + ".png"))

    def shape(name, wu, hu, col):
        w, h = round(wu * U), round(hu * U)
        save(name, rrect(w, h, 0, [(0, w, 0, h, min(w, h) / 2, col)]))

    for name, wu, hu in (("pill", 24, 5), ("dv", 3.8, 5.8), ("dh", 5.8, 3.8), ("face", 5.4, 5.4), ("mini", 5.5, 3), ("knob", 7.6, 7.6)):
        shape(name + "_off", wu, hu, FACE)
        shape(name + "_on", wu, hu, LIT)
    shape("ring", 14.4, 14.4, MARK)
    w, h = round(24 * U), round(5 * U)
    for k in range(13):
        fill = 0 if k == 0 else max(h, round(w * k / 12))
        save(f"trigL_{k}", rrect(w, h, 0, [(0, w, 0, h, h / 2, FACE)] + ([(0, fill, 0, h, h / 2, LIT)] if k else [])))
        save(f"trigR_{k}", rrect(w, h, 0, [(0, w, 0, h, h / 2, FACE)] + ([(w - fill, w, 0, h, h / 2, LIT)] if k else [])))
    size = 100 * U
    m = Image.new("L", (size * SS // 2, size * SS // 2), 0)
    f = size * SS / 2 / 100
    ImageDraw.Draw(m).polygon([(x * f, y * f) for x, y in polys(BODY)[0]], fill=255)
    body = Image.new("RGBA", (size, size), rgb(BODYC) + (255,))
    body.putalpha(m.resize((size, size), Image.LANCZOS))
    save("body", body)
    save("logo", app_icon(40 * S))
    for name, h in (("card_status", 110), ("card_stats", 176)):
        save(name, rrect(300 * S, h * S, 0, [(0, 300 * S, 0, h * S, 16 * S, CARD)]))
    dot = 10 * S
    save("status_on", rrect(dot, dot, 0, [(0, dot, 0, dot, dot / 2, LIT)]))
    save("status_wait", rrect(dot, dot, 0, [(0, dot, 0, dot, dot / 2, "#F5B83D")]))


for S in (1, 2):
    tester_set(S)

sheet = Image.new("RGB", (720, 280), (24, 28, 34))
sheet.paste(*(lambda i: (i, (20, 12), i))(app_icon(256)))
x = 300
for color in (ACCENT, IDLE, ERROR):
    sheet.paste(*(lambda i: (i, (x, 20), i))(tinted(128, color)))
    i = tinted(16, color).resize((64, 64), Image.NEAREST)
    sheet.paste(i, (x + 30, 170), i)
    x += 140
sheet.save(os.path.join(HERE, "build_preview.png"))
print("assets written")
