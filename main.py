#!/usr/bin/env python3
"""THE WORLD IN ONE DAY — a one-image newspaper front page.

Renders a designed broadsheet front page summing up one day's world news and
writes it to /output/entry.png (or $MAKEFUN_OUTPUT_DIR/entry.png).
Pure Python standard library: no network, no fonts on disk, deterministic —
two runs write identical bytes. Glyph bitmaps live in fontdata.py (baked from
DejaVu/Liberation at build time); the day's stories live in data.py.
"""
import os, struct, zlib

from fontdata import FONTS
import data as D

W = H = 1024


class LCG:
    def __init__(self, seed):
        self.s = seed & 0x7FFFFFFF

    def next(self, n):
        self.s = (1103515245 * self.s + 12345) & 0x7FFFFFFF
        return self.s % n


class Canvas:
    def __init__(self, w, h, color):
        self.w, self.h = w, h
        self.buf = bytearray(bytes(color) * (w * h))

    def px(self, x, y, color, alpha=255):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            if alpha == 255:
                self.buf[i:i + 3] = bytes(color)
            elif alpha:
                ia = 255 - alpha
                self.buf[i] = (color[0] * alpha + self.buf[i] * ia) // 255
                self.buf[i + 1] = (color[1] * alpha + self.buf[i + 1] * ia) // 255
                self.buf[i + 2] = (color[2] * alpha + self.buf[i + 2] * ia) // 255

    def rect(self, x, y, w, h, color, alpha=255):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        if alpha == 255:
            row = bytes(color) * (x1 - x0)
            for yy in range(y0, y1):
                i = (yy * self.w + x0) * 3
                self.buf[i:i + len(row)] = row
        else:
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    self.px(xx, yy, color, alpha)

    def vgrad(self, x, y, w, h, top, bot):
        for j in range(h):
            t = j / max(1, h - 1)
            c = tuple(round(top[k] + (bot[k] - top[k]) * t) for k in range(3))
            self.rect(x, y + j, w, 1, c)

    def hline(self, x, y, w, color, thick=1):
        self.rect(x, y, w, thick, color)

    def vline(self, x, y, h, color, thick=1):
        self.rect(x, y, thick, h, color)

    def circle(self, cx, cy, r, color, alpha=255):
        for yy in range(cy - r, cy + r + 1):
            dx = int((r * r - (yy - cy) ** 2) ** 0.5) if abs(yy - cy) <= r else 0
            self.rect(cx - dx, yy, 2 * dx + 1, 1, color, alpha)

    def poly(self, pts, color, alpha=255):
        ys = [p[1] for p in pts]
        y0, y1 = max(0, min(ys)), min(self.h - 1, max(ys))
        n = len(pts)
        for yy in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x1, y1p = pts[i]
                x2, y2p = pts[(i + 1) % n]
                if (y1p <= yy < y2p) or (y2p <= yy < y1p):
                    xs.append(x1 + (yy - y1p) * (x2 - x1) / (y2p - y1p))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.rect(int(xs[i]), yy, max(1, int(xs[i + 1]) - int(xs[i])), 1, color, alpha)

    def line(self, x1, y1, x2, y2, color, thick=2, alpha=255):
        steps = max(abs(x2 - x1), abs(y2 - y1), 1)
        r = max(1, thick // 2)
        for i in range(steps + 1):
            t = i / steps
            self.circle(int(x1 + (x2 - x1) * t), int(y1 + (y2 - y1) * t), r, color, alpha)

    def dotted_curve(self, p0, p1, p2, color, dots=26, r=3):
        for i in range(dots + 1):
            t = i / dots
            x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
            y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
            self.circle(int(x), int(y), r, color)

    def starburst(self, cx, cy, r1, r2, color, spikes=12, alpha=255):
        import math
        pts = []
        for i in range(spikes * 2):
            ang = math.pi * i / spikes
            r = r1 if i % 2 == 0 else r2
            pts.append((int(cx + r * math.cos(ang)), int(cy + r * math.sin(ang))))
        self.poly(pts, color, alpha)

    def blit(self, src, dx, dy):
        for yy in range(src.h):
            if 0 <= dy + yy < self.h:
                si = yy * src.w * 3
                di = ((dy + yy) * self.w + dx) * 3
                self.buf[di:di + src.w * 3] = src.buf[si:si + src.w * 3]


# ---------------- text ----------------

_cache = {}

def _glyph(fontkey, ch):
    key = (fontkey, ch)
    g = _cache.get(key)
    if g is None:
        adv, w, h, x0, y0, enc = FONTS[fontkey]["glyphs"].get(ch, FONTS[fontkey]["glyphs"]["?"])
        raw = zlib.decompress(base64.b85decode(enc)) if enc else b""
        g = (adv, w, h, x0, y0, raw)
        _cache[key] = g
    return g


import base64

def text_w(fontkey, s, tracking=0):
    total = 0.0
    for ch in s:
        total += FONTS[fontkey]["glyphs"].get(ch, FONTS[fontkey]["glyphs"]["?"])[0] + tracking
    return total - (tracking if s else 0)


def draw_text(cv, x, ybase, s, fontkey, color, tracking=0):
    pen = float(x)
    for ch in s:
        adv, w, h, x0, y0, raw = _glyph(fontkey, ch)
        if raw:
            gx, gy = int(pen) + x0, ybase + y0
            for row in range(h):
                yy = gy + row
                if 0 <= yy < cv.h:
                    base = row * w
                    for col in range(w):
                        a = raw[base + col]
                        if a:
                            cv.px(gx + col, yy, color, a)
        pen += adv + tracking
    return pen


def draw_text_c(cv, cx, ybase, s, fontkey, color, tracking=0):
    return draw_text(cv, int(cx - text_w(fontkey, s, tracking) / 2), ybase, s, fontkey, color, tracking)


def wrap(s, fontkey, maxw):
    words, lines, cur = s.split(), [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if text_w(fontkey, trial) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def png_bytes(cv):
    raw = bytearray()
    stride = cv.w * 3
    for yy in range(cv.h):
        raw.append(0)
        raw += cv.buf[yy * stride:(yy + 1) * stride]

    def chunk(tag, payload):
        c = struct.pack(">I", len(payload)) + tag + payload
        return c + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


# ---------------- lead art ----------------

INK = (20, 18, 14)
PAPER = (247, 242, 230)
RED = (178, 34, 27)
GOLD = (198, 148, 44)
BLUE = (29, 74, 104)
GRAY = (96, 90, 78)


def art_summit(w, h):
    """APEC Shenzhen: skyline, sun, and the three leaders' flags."""
    cv = Canvas(w, h, (22, 48, 72))
    cv.vgrad(0, 0, w, h, (18, 42, 66), (86, 128, 152))
    cv.circle(int(w * 0.80), int(h * 0.34), 44, (240, 196, 92))
    cv.circle(int(w * 0.80), int(h * 0.34), 56, (240, 196, 92), 60)
    rng = LCG(20261118)
    # distant hills
    hills = [(0, int(h * 0.72))]
    x = 0
    while x < w:
        x += 60 + rng.next(70)
        hills.append((min(x, w), int(h * (0.60 + rng.next(12) / 100))))
    hills.append((w, h))
    hills.append((0, h))
    cv.poly(hills, (30, 56, 76))
    # skyline
    base = h
    x = -10
    while x < w:
        bw = 26 + rng.next(38)
        bh = int(h * (0.22 + rng.next(30) / 100))
        if abs(x - w * 0.60) < 40:  # the tall tower
            bh = int(h * 0.62)
            cv.poly([(x, base), (x + bw, base), (x + bw // 2 + 6, base - bh), (x + bw // 2 - 6, base - bh)], (12, 24, 36))
        else:
            cv.rect(x, base - bh, bw, bh, (14, 27, 41))
        for wy in range(base - bh + 8, base - 8, 13):
            for wx in range(x + 5, x + bw - 5, 10):
                if rng.next(3) == 0:
                    cv.rect(wx, wy, 4, 5, (250, 214, 130))
        x += bw + 4 + rng.next(14)
    # plaza band
    cv.rect(0, h - 16, w, 16, (8, 15, 22))
    # three flags on poles, foreground left-of-centre
    def flag(px, kind):
        cv.vline(px, 26, h - 42, (210, 208, 198), 3)
        cv.circle(px + 1, 24, 4, GOLD)
        fw, fh, fy = 118, 66, 30
        wave = [(px + 3, fy), (px + 3 + fw // 2, fy - 5), (px + 3 + fw, fy + 2),
                (px + 3 + fw, fy + fh - 4), (px + 3 + fw // 2, fy + fh + 4), (px + 3, fy + fh)]
        if kind == "cn":
            cv.poly(wave, (206, 42, 34))
            cv.circle(px + 26, fy + 22, 7, (250, 205, 60))
            for dx, dy in [(46, 10), (52, 22), (52, 35), (45, 46)]:
                cv.circle(px + dx, fy + dy, 3, (250, 205, 60))
        elif kind == "ru":
            cv.poly(wave, (238, 238, 238))
            mid = [(px + 3, fy + fh // 3), (px + 3 + fw // 2, fy + fh // 3 - 2), (px + 3 + fw, fy + fh // 3 + 1),
                   (px + 3 + fw, fy + 2 * fh // 3), (px + 3 + fw // 2, fy + 2 * fh // 3 + 3), (px + 3, fy + 2 * fh // 3)]
            cv.poly(mid, (32, 84, 160))
            low = [(px + 3, fy + 2 * fh // 3), (px + 3 + fw // 2, fy + 2 * fh // 3 + 3), (px + 3 + fw, fy + 2 * fh // 3 + 1),
                   (px + 3 + fw, fy + fh - 4), (px + 3 + fw // 2, fy + fh + 4), (px + 3, fy + fh)]
            cv.poly(low, (200, 48, 44))
        else:  # us
            cv.poly(wave, (240, 238, 234))
            for i in range(4):
                yy = fy + 8 + i * 15
                cv.poly([(px + 3, yy), (px + 3 + fw // 2, yy - 2), (px + 3 + fw, yy + 1),
                         (px + 3 + fw, yy + 8), (px + 3 + fw // 2, yy + 10), (px + 3, yy + 8)], (178, 44, 52))
            cv.poly([(px + 3, fy), (px + 52, fy - 2), (px + 58, fy + 1), (px + 58, fy + 32),
                     (px + 30, fy + 35), (px + 3, fy + 34)], (44, 54, 116))
            for ry in range(4):
                for rx in range(5):
                    cv.circle(px + 10 + rx * 10, fy + 6 + ry * 8, 2, (245, 245, 245))
    flag(int(w * 0.06), "cn")
    flag(int(w * 0.235), "ru")
    flag(int(w * 0.41), "us")
    return cv


def art_strait(w, h):
    """Qeshm Island: night sea, island silhouette, missile arcs, bursts."""
    cv = Canvas(w, h, (10, 18, 32))
    horizon = int(h * 0.52)
    cv.vgrad(0, 0, w, horizon, (8, 14, 28), (26, 44, 66))
    cv.vgrad(0, horizon, w, h - horizon, (16, 36, 54), (6, 14, 24))
    rng = LCG(20261117)
    for _ in range(130):  # stars
        cv.px(rng.next(w), rng.next(horizon - 8), (220, 228, 240), 120 + rng.next(120))
    # moon crescent
    cv.circle(70, 44, 20, (232, 230, 210))
    cv.circle(80, 38, 17, (14, 24, 40))
    # island silhouette
    isl = [(int(w * 0.30), horizon + 4)]
    x = int(w * 0.30)
    for px, py in [(0.38, 0.40), (0.46, 0.30), (0.55, 0.36), (0.63, 0.27), (0.70, 0.38)]:
        isl.append((int(w * px), int(h * py)))
    isl += [(int(w * 0.76), horizon + 4), (int(w * 0.76), horizon + 26), (int(w * 0.30), horizon + 26)]
    cv.poly(isl, (6, 10, 16))
    cv.rect(int(w * 0.30), horizon + 20, int(w * 0.46), 8, (10, 22, 34))  # reflection
    # ships at left
    for sx, ss in [(int(w * 0.05), 1.0), (int(w * 0.16), 0.7)]:
        sy = horizon + int(10 * ss)
        bw = int(120 * ss)
        cv.poly([(sx, sy), (sx + bw, sy), (sx + bw - 14, sy - int(10 * ss)), (sx + 10, sy - int(10 * ss))], (5, 8, 13))
        cv.rect(sx + int(bw * 0.35), sy - int(26 * ss), int(28 * ss), int(16 * ss), (5, 8, 13))
        cv.vline(sx + int(bw * 0.62), sy - int(40 * ss), int(16 * ss), (5, 8, 13), 2)
        cv.circle(sx + int(bw * 0.4), sy - int(30 * ss), 2, (255, 190, 90))
    # missile arcs from ships to island
    for (sx, sy), (tx, ty), bend in [((int(w * 0.10), horizon - 26), (int(w * 0.47), int(h * 0.33)), -70),
                                     ((int(w * 0.19), horizon - 14), (int(w * 0.62), int(h * 0.29)), -96),
                                     ((int(w * 0.07), horizon - 8), (int(w * 0.55), int(h * 0.37)), -52)]:
        cv.dotted_curve((sx, sy), ((sx + tx) // 2, min(sy, ty) + bend), (tx, ty), (255, 166, 66), dots=24, r=3)
    # bursts on the island
    for bx, by, r in [(int(w * 0.47), int(h * 0.33), 30), (int(w * 0.62), int(h * 0.29), 38), (int(w * 0.55), int(h * 0.38), 24)]:
        cv.circle(bx, by, r + 16, (255, 120, 40), 46)
        cv.starburst(bx, by, r, r // 3, (255, 176, 66))
        cv.starburst(bx, by, r // 2, r // 5, (255, 226, 150))
    # burning tanker, right
    tx, ty = int(w * 0.84), horizon + 12
    cv.poly([(tx - 62, ty), (tx + 66, ty), (tx + 50, ty - 12), (tx - 48, ty - 12)], (5, 8, 13))
    cv.rect(tx - 16, ty - 26, 30, 14, (5, 8, 13))
    cv.starburst(tx + 4, ty - 34, 17, 6, (255, 140, 50))
    cv.circle(tx + 4, ty - 44, 6, (255, 200, 110))
    for i in range(6):  # smoke
        cv.circle(tx + 10 + i * 7, ty - 56 - i * 12, 8 + i * 2, (120, 124, 130), 60)
    # sea shimmer
    for _ in range(240):
        sx, sy = rng.next(w), horizon + 6 + rng.next(h - horizon - 10)
        cv.rect(sx, sy, 6 + rng.next(14), 1, (140, 170, 200), 50)
    return cv


ART = {"summit": art_summit, "strait": art_strait}


# ---------------- page ----------------

def render():
    cv = Canvas(W, H, PAPER)
    cv.vgrad(0, 0, W, H, (248, 243, 231), (240, 232, 212))
    rng = LCG(42)
    for _ in range(1500):  # paper speckle
        cv.px(rng.next(W), rng.next(H), (198, 188, 164), 70)
    M, CW = 46, W - 92

    # masthead
    cv.hline(M, 30, CW, INK, 3)
    cv.hline(M, 37, CW, INK, 1)
    draw_text(cv, M, 58, "ONE IMAGE", "sans_bold:11", GRAY, 2)
    r = "ALL THE NEWS"
    draw_text(cv, M + CW - int(text_w("sans_bold:11", r, 2)), 58, r, "sans_bold:11", GRAY, 2)
    draw_text_c(cv, W // 2, 120, D.MASTHEAD, "serif_bold:68", INK)
    # date band
    cv.rect(M, 136, CW, 32, INK)
    draw_text_c(cv, W // 2, 159, D.DATE_LINE, "sans_bold:17", (245, 240, 226), 1)
    draw_text(cv, M, 188, D.EDITION_LEFT, "sans_bold:11", GRAY, 1)
    r = D.EDITION_RIGHT
    draw_text(cv, M + CW - int(text_w("sans_bold:11", r, 1)), 188, r, "sans_bold:11", GRAY, 1)

    # lead story
    draw_text(cv, M, 216, D.LEAD_KICKER, "sans_bold:13", RED, 2)
    y = 216
    for ln in D.LEAD_HEADLINE:
        y += 56
        draw_text(cv, M, y, ln, "serif_bold:57", INK)
    art = ART[D.LEAD_ART](CW, 168)
    cv.blit(art, M, 344)
    cv.rect(M, 344, CW, 2, INK)
    cv.rect(M, 510, CW, 2, INK)
    draw_text(cv, M, 534, D.LEAD_CAPTION, "serif_it:13", GRAY)
    y = 536
    for ln in wrap(D.LEAD_SUMMARY, "serif:19", CW)[:2]:
        y += 24
        draw_text(cv, M, y, ln, "serif:19", (38, 34, 26))
    cv.hline(M, 602, CW, INK, 2)
    cv.hline(M, 607, CW, INK, 1)

    # story cards, 2 x 2
    colw = (CW - 30) // 2
    for row in range(2):
        cy = 624 + row * 148
        for col in range(2):
            st = D.STORIES[row * 2 + col]
            cx = M + col * (colw + 30)
            cv.rect(cx, cy, 26, 3, st["color"])
            draw_text(cv, cx, cy + 18, st["kicker"], "sans_bold:12", st["color"], 1)
            hy = cy + 22
            for ln in st["headline"]:
                hy += 26
                draw_text(cv, cx, hy, ln, "serif_bold:24", INK)
            by = hy + 19
            for ln in wrap(st["body"], "sans:15", colw)[:3]:
                draw_text(cv, cx, by, ln, "sans:15", (56, 51, 42))
                by += 18
        if row == 0:
            cv.hline(M, cy + 140, CW, (178, 168, 146), 1)

    # in brief band
    by0 = 917
    cv.rect(M, by0, CW, 80, INK)
    draw_text(cv, M + 16, by0 + 24, "IN BRIEF", "sans_bold:13", GOLD, 2)
    by = by0 + 2
    for item in D.BRIEFS:
        by += 22
        draw_text(cv, M + 110, by, "•", "sans:14", GOLD)
        draw_text(cv, M + 126, by, item, "sans:14", (238, 233, 218))
    # footer
    cv.hline(M, 1009, CW, INK, 1)
    draw_text_c(cv, W // 2, 1022, D.FOOTER, "sans_bold:11", GRAY, 1)
    return cv


def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    blob = png_bytes(render())
    with open(os.path.join(outdir, "entry.png"), "wb") as f:
        f.write(blob)
    print("wrote", os.path.join(outdir, "entry.png"), len(blob), "bytes")


if __name__ == "__main__":
    main()
