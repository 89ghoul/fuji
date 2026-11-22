#!/usr/bin/env python3
"""
fuji - a quiet view of Mount Fuji in black & white ASCII.

A still evening: moon, faint stars, slow clouds and mist, a lake that
mirrors the mountain. Every minute or two a small flock of birds
drifts across the sky.

Pure Python 3 (standard library only). Works in any terminal.
  q / Esc / Ctrl-C   quit
  b                  call the birds right now
"""
import argparse
import math
import os
import random
import select
import shutil
import signal
import sys
import time

RAMP = " .:-=+*#%@"
_B = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
BAY = [[(_B[y][x] + 0.5) / 16.0 for x in range(4)] for y in range(4)]


# --------------------------------------------------------------- noise ----
def _h(ix, iy, seed):
    n = (ix * 374761393 + iy * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    n ^= n >> 16
    return n / 4294967295.0


def vnoise(x, y, seed=0, px=0):
    ix = math.floor(x)
    iy = math.floor(y)
    fx = x - ix
    fy = y - iy
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)
    x0, x1 = ix, ix + 1
    if px:
        x0 %= px
        x1 %= px
    a = _h(x0, iy, seed)
    b = _h(x1, iy, seed)
    c = _h(x0, iy + 1, seed)
    d = _h(x1, iy + 1, seed)
    top = a + (b - a) * fx
    bot = c + (d - c) * fx
    return top + (bot - top) * fy


def fbm(x, y, seed=0, octaves=4, px=0):
    v = 0.0
    amp = 0.5
    tot = 0.0
    for o in range(octaves):
        v += amp * vnoise(x, y, seed + o * 17, px)
        tot += amp
        x *= 2
        y *= 2
        amp *= 0.5
        if px:
            px *= 2
    return v / tot


def smooth(x):
    x = 0.0 if x < 0 else 1.0 if x > 1 else x
    return x * x * (3 - 2 * x)


def shade(v, c, r):
    """luminance 0..1 -> (char, xterm gray code), ordered-dithered."""
    if v < 0.02:
        return " ", 0
    if v > 1.0:
        v = 1.0
    idx = int(v * 9 + 0.5 + (_h(c, r, 9) - 0.5) * 0.55)
    if idx <= 0:
        return " ", 0
    if idx > 9:
        idx = 9
    return RAMP[idx], 238 + int(v * 17.99)


# --------------------------------------------------------------- birds ----
NEAR = ["\\_/", "-_-", "/^\\", "-^-"]   # wings up, mid, down, mid
NEAR_GLIDE = "_^_"
FAR = ["v", "-", "^", "-"]
FAR_GLIDE = "-"


class Flock:
    def __init__(self, rng, W, H, t0):
        self.t0 = t0
        self.W = W
        self.dir = rng.choice((-1, 1))
        self.speed = W / rng.uniform(17.0, 23.0)          # cols / second
        self.y0 = H * rng.uniform(0.07, 0.27)
        self.vy = rng.uniform(-0.22, 0.22)                # rows / second
        n = rng.randint(6, 10)
        self.birds = []
        for i in range(n):
            if i == 0:
                back, side = 0.0, 0.0
            else:
                k = (i + 1) // 2
                back = k * rng.uniform(3.0, 4.6)
                side = (1 if i % 2 else -1) * k * rng.uniform(0.7, 1.4)
            self.birds.append(dict(
                back=back + rng.uniform(-0.8, 0.8),
                side=side + rng.uniform(-0.4, 0.4),
                ph=rng.uniform(0, 6.283),
                rate=rng.uniform(1.9, 2.7),
                far=rng.random() < 0.3,
                bob=rng.uniform(0.25, 0.6),
            ))

    def alive(self, t):
        return (t - self.t0) * self.speed < self.W + 45

    def cells(self, t):
        dt = t - self.t0
        lx = (-16.0 + self.speed * dt) if self.dir > 0 else (self.W + 16.0 - self.speed * dt)
        out = []
        for b in self.birds:
            x = lx - self.dir * b["back"]
            y = self.y0 + self.vy * dt + b["side"] + b["bob"] * math.sin(0.8 * dt + b["ph"])
            gliding = math.sin(dt * 0.27 + b["ph"] * 2.3) > 0.6
            if b["far"]:
                g = FAR_GLIDE if gliding else FAR[int(dt * b["rate"] + b["ph"]) % 4]
                out.append((int(round(x)), int(round(y)), g, 247))
            else:
                g = NEAR_GLIDE if gliding else NEAR[int(dt * b["rate"] + b["ph"]) % 4]
                out.append((int(round(x)) - 1, int(round(y)), g, 255))
        return out


class Birds:
    def __init__(self, rng, first=(15.0, 30.0), interval=(60.0, 120.0)):
        self.rng = rng
        self.interval = interval
        self.next = rng.uniform(*first)
        self.flocks = []

    def update(self, t, W, H):
        if t >= self.next:
            self.flocks.append(Flock(self.rng, W, H, t))
            self.next = t + self.rng.uniform(*self.interval)
        self.flocks = [f for f in self.flocks if f.alive(t)]

    def call(self, t, W, H):
        self.flocks.append(Flock(self.rng, W, H, t))

    def clear(self):
        self.flocks = []


# --------------------------------------------------------------- scene ----
class Scene:
    def __init__(self, W, H, seed=7):
        self.W, self.H, self.seed = W, H, seed
        self._build()

    # -- static picture ---------------------------------------------------
    def _build(self):
        W, H, seed = self.W, self.H, self.seed
        rng = random.Random(seed)
        hy = min(int(H * 0.72), H - 5)          # shoreline / mountain base
        self.hy = hy
        Hm = min(hy * 0.84, H * 0.62)           # mountain height (rows)
        w = min(W * 0.50, 2.9 * Hm)             # half width at the base (cols)
        cx = W * 0.5
        self.cx = cx
        summit = hy - Hm

        # skyline of the mountain
        top = []
        for c in range(W):
            d = c + 0.5 - cx
            ww = w * (0.96 if d < 0 else 1.06)
            t = min(abs(d) / ww, 1.0)
            h = Hm * (1 - t) ** 2.0
            cap = Hm * 0.95
            if h > cap:
                h = cap
            cr = 0.05 * w
            if abs(d) < cr:
                h -= Hm * 0.03 * (1 - abs(d) / cr)
            h += (fbm(c * 0.05, 3.1, seed, 3) - 0.5) * 0.06 * Hm * min(1.0, t * 5)
            top.append(hy - max(h, 0.0))

        base = [[0.0] * W for _ in range(hy)]
        glyph = {}

        # sky glow near the horizon
        for r in range(hy):
            sky = 0.10 * ((r + 0.5) / hy) ** 3.0
            row = base[r]
            for c in range(W):
                row[c] = sky

        # moon
        mc, mr = W * 0.17, H * 0.15
        rx = max(4.0, W * 0.04)
        ry = rx / 2.0
        self.moon = (mc, mr)
        for r in range(max(0, int(mr - ry * 5)), min(hy, int(mr + ry * 5) + 1)):
            for c in range(max(0, int(mc - rx * 5)), min(W, int(mc + rx * 5) + 1)):
                dx = (c + 0.5 - mc) / rx
                dy = (r + 0.5 - mr) / ry
                dd = dx * dx + dy * dy
                v = 0.10 * math.exp(-dd * 0.30)
                if dd < 1.0:
                    disc = 0.97 - 0.22 * dd + (vnoise(c * 0.5, r * 0.9, seed + 4) - 0.5) * 0.08
                    k = smooth((1 - dd) * 6)
                    v = v * (1 - k) + disc * k
                base[r][c] = min(1.0, base[r][c] + v)

        # stars
        self.stars = []
        for r in range(int(hy * 0.55)):
            for c in range(W):
                if rng.random() < 0.014:
                    dx = (c + 0.5 - mc) / rx
                    dy = (r + 0.5 - mr) / ry
                    if dx * dx + dy * dy > 12:
                        self.stars.append((c, r, rng.uniform(0, 6.283), rng.uniform(0.4, 1.0)))

        # the mountain
        for c in range(W):
            tc = top[c]
            if tc >= hy - 0.01:
                continue
            s = (c + 0.5 - cx) / w
            light = -math.tanh(4.5 * s)           # +1 lit (left), -1 shadow (right)
            r_out = max(0, int(math.floor(tc)))
            f = tc - r_out
            sl_ = (top[min(c + 1, W - 1)] - top[max(c - 1, 0)]) / (2.0 if 0 < c < W - 1 else 1.0)
            if sl_ < -0.8:
                oc = "/"
            elif sl_ > 0.8:
                oc = "\\"
            elif f < 0.34:
                oc = "'"
            elif f < 0.67:
                oc = "-"
            else:
                oc = "_"
            for r in range(r_out, hy):
                rr = r + 0.5
                hh = hy - rr
                rb = max(rr - summit, 0.0)
                u = (c + 0.5 - cx) / (rb + 2.5)
                g = fbm(u * 16 + 40, 0.0, seed + 3, 3)          # radial gullies
                crag = fbm(c * 0.22, rr * 0.55, seed + 5, 3)
                rock = 0.40 + 0.33 * light
                rock += (g - 0.5) * 0.85 * min(1.0, rb / (Hm * 0.25 + 0.01))
                rock += (crag - 0.5) * 0.22
                # snow
                jag = (fbm(c * 0.12, rr * 0.4, seed + 9, 3) - 0.5) * 0.10 * Hm
                sl = Hm * 0.70 + (g - 0.5) * 0.50 * Hm + jag
                sf = smooth(0.5 + (hh - sl) / (0.05 * Hm + 0.5))
                sn = 0.72 + 0.28 * (0.5 + 0.5 * light) + (g - 0.5) * 0.25
                sn = min(1.0, max(0.45, sn))
                v = rock * (1 - sf) + sn * sf
                # haze toward the foot
                haze = 0.5 * max(0.0, 1 - hh / Hm) ** 2.2
                v = v * (1 - haze) + 0.22 * haze
                v = max(0.15, v)
                base[r][c] = v
                if r == r_out:
                    glyph[(r, c)] = oc

        # far hills
        for c in range(W):
            d = abs(c + 0.5 - cx) / W
            t1 = hy - H * (0.05 + 0.07 * fbm(c * 0.035, 11.3, seed, 3)) - H * 0.6 * max(0.0, d - 0.30)
            for r in range(max(0, int(math.ceil(t1))), hy):
                glyph.pop((r, c), None)
                base[r][c] = 0.15 + 0.08 * vnoise(c * 0.35, r * 0.9, seed + 30)

        # near tree line
        for c in range(W):
            d = abs(c + 0.5 - cx) / W
            t2 = hy - H * (0.018 + 0.04 * fbm(c * 0.06, 23.7, seed, 3)) - H * 0.9 * max(0.0, d - 0.30)
            hsh = _h(c, 91, seed)
            ext = 0 if hsh < 0.62 else 1
            r0 = int(math.floor(t2)) - ext
            for r in range(max(0, r0), hy):
                glyph.pop((r, c), None)
                base[r][c] = 0.22 + 0.08 * vnoise(c * 0.5, r * 1.2, seed + 41)
                if r == r0 and ext > 0:
                    glyph[(r, c)] = "^"

        self.base = base
        self.glyph = glyph

        # pre-shaded static layer
        self.sc = [[" "] * W for _ in range(self.H)]
        self.sg = [[0] * W for _ in range(self.H)]
        for r in range(hy):
            for c in range(W):
                ch, gr = shade(base[r][c], c, r)
                if (r, c) in glyph:
                    ch = glyph[(r, c)]
                    gr = 238 + int(min(1.0, base[r][c] + 0.30) * 17.99)
                self.sc[r][c] = ch
                self.sg[r][c] = gr

        # reflection (source rows for the lake)
        K = 1.9
        self.lake_rows = H - hy
        self.refl = []
        for r in range(hy, H):
            dd = r - hy + 0.5
            s = hy - dd * K - 0.5
            i0 = int(math.floor(s))
            fr = s - i0
            fade = 0.85 * (1 - 0.30 * min(1.0, dd / max(1, self.lake_rows)))
            row = []
            for c in range(W):
                a = base[i0][c] if 0 <= i0 < hy else 0.0
                b = base[i0 + 1][c] if 0 <= i0 + 1 < hy else 0.0
                row.append((a * (1 - fr) + b * fr) * fade)
            self.refl.append(row)

        # clouds / mist: periodic textures that scroll sideways
        self.layers = []
        T = 3 * W

        def mk(r0, r1, speed, cval, fx, fy, thr, soft, maxa, sd):
            r0 = max(0, r0)
            r1 = min(hy, r1)
            if r1 - r0 < 2:
                return
            P0 = max(2, int(round(T * fx)))
            fxx = P0 / float(T)
            rows = []
            for r in range(r0, r1):
                vf = math.sin(math.pi * (r - r0 + 0.5) / (r1 - r0)) ** 0.8
                row = []
                for c in range(T):
                    n = fbm(c * fxx, r * fy, sd, 4, P0)
                    row.append(smooth((n - thr) / soft) * vf * maxa)
                rows.append(row)
            self.layers.append(dict(r0=r0, rows=rows, speed=speed, cval=cval, T=T))

        mk(int(H * 0.04), int(H * 0.28), 1.1, 0.50, 0.022, 0.26, 0.60, 0.16, 0.80, 101)
        mk(int(H * 0.28), int(H * 0.40), 0.7, 0.42, 0.018, 0.30, 0.64, 0.14, 0.70, 202)
        mk(hy - int(H * 0.17), hy - 1, 0.35, 0.28, 0.020, 0.35, 0.52, 0.20, 0.55, 303)
        self.cloud_rows = {}
        for li, L in enumerate(self.layers):
            for k in range(len(L["rows"])):
                self.cloud_rows.setdefault(L["r0"] + k, []).append((li, k))

    # -- one frame ----------------------------------------------------------
    def frame(self, t, flocks=()):
        W, H, hy = self.W, self.H, self.hy
        chars = [row[:] for row in self.sc]
        grays = [row[:] for row in self.sg]

        # clouds
        offs = [int(t * L["speed"]) % L["T"] for L in self.layers]
        for r, entries in self.cloud_rows.items():
            base_row = self.base[r]
            for c in range(W):
                v = base_row[c]
                touched = False
                strong = 0.0
                for li, k in entries:
                    L = self.layers[li]
                    a = L["rows"][k][(c - offs[li]) % L["T"]]
                    if a > 0.012:
                        v = v * (1 - a) + L["cval"] * a
                        touched = True
                        strong = max(strong, a)
                if touched:
                    if (r, c) in self.glyph and strong < 0.3:
                        continue
                    ch, gr = shade(v, c, r)
                    chars[r][c] = ch
                    grays[r][c] = gr

        # twinkling stars (only in clear sky)
        for c, r, ph, b in self.stars:
            if chars[r][c] == " ":
                tw = b * (0.55 + 0.45 * math.sin(t * 0.5 + ph))
                if tw > 0.80:
                    chars[r][c], grays[r][c] = "*", 250
                elif tw > 0.48:
                    chars[r][c], grays[r][c] = "+", 245
                elif tw > 0.30:
                    chars[r][c], grays[r][c] = ".", 241

        # lake
        mc = self.moon[0]
        lake = H - hy
        for r in range(hy, H):
            dd = r - hy + 0.5
            amp = min(0.3 + 0.25 * dd, 2.6)
            shift = int(round(math.sin(t * 0.7 + dd * 0.9) * amp))
            src = self.refl[r - hy]
            for c in range(W):
                cs = c + shift
                cs = 0 if cs < 0 else W - 1 if cs >= W else cs
                sh = 0.5 + 0.5 * math.sin(c * 0.09 + dd * 0.7 - t * 0.8)
                v = max(0.0, src[cs] * (0.72 + 0.28 * sh) - 0.05) * 1.2
                dm = abs(c + 0.5 - mc)
                if dm < 14:
                    gl = 0.60 * math.exp(-(dm / (2.5 + 0.4 * dd)) ** 2) * (0.25 + 0.75 * sh)
                    v += gl * max(0.0, 1 - dd / (lake + 2.0))
                ch, gr = shade(v, c, r)
                if ch == " ":
                    rp = math.sin(c * 0.31 + dd * 2.3 - t * 0.9) * math.sin(c * 0.047 + dd * 0.9 + t * 0.15)
                    if rp > 0.80:
                        ch, gr = ("~" if dd > 2 else "-"), 239
                chars[r][c] = ch
                grays[r][c] = gr

        # birds
        for f in flocks:
            for x, y, g, gr in f.cells(t):
                if 0 <= y < H:
                    for i, ch in enumerate(g):
                        xx = x + i
                        if 0 <= xx < W:
                            chars[y][xx] = ch
                            grays[y][xx] = gr
        return chars, grays


# ------------------------------------------------------------ terminal ----
def to_ansi(chars, grays, color=True):
    lines = []
    for row, grow in zip(chars, grays):
        if not color:
            lines.append("".join(row).rstrip())
            continue
        parts, buf, cur = [], [], None
        for ch, gr in zip(row, grow):
            if ch == " ":
                buf.append(ch)
                continue
            if gr != cur:
                if buf:
                    parts.append("".join(buf))
                    buf = []
                parts.append("\x1b[38;5;%dm" % gr)
                cur = gr
            buf.append(ch)
        if buf:
            parts.append("".join(buf))
        lines.append("".join(parts))
    return lines


def main():
    ap = argparse.ArgumentParser(description="A quiet ASCII view of Mount Fuji.")
    ap.add_argument("--fps", type=float, default=12.0)
    ap.add_argument("--interval", type=float, nargs=2, default=(60.0, 120.0),
                    metavar=("MIN", "MAX"), help="seconds between bird flocks (default 60 120)")
    ap.add_argument("--first", type=float, nargs=2, default=(15.0, 30.0),
                    metavar=("MIN", "MAX"), help="delay before the first flock (default 15 30)")
    ap.add_argument("--plain", action="store_true", help="no colour, characters only")
    ap.add_argument("--seed", type=int, default=7, help="changes the cloud/mountain details")
    args = ap.parse_args()

    if not sys.stdout.isatty():
        sys.exit("fuji: run me in a terminal")
    term = os.environ.get("TERM", "")
    color = not args.plain and "NO_COLOR" not in os.environ and (
        "256" in term or "color" in term or os.environ.get("COLORTERM"))

    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd) if sys.stdin.isatty() else None
    out = sys.stdout

    def bye(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, bye)
    rng = random.Random()
    birds = Birds(rng, tuple(args.first), tuple(args.interval))
    scene, size = None, None
    t0 = time.monotonic()
    try:
        if old:
            tty.setcbreak(fd)
        out.write("\x1b[?1049h\x1b[?25l" + ("\x1b[48;5;16m" if color else "") + "\x1b[2J")
        while True:
            frame_start = time.monotonic()
            sz = shutil.get_terminal_size((80, 24))
            W, H = min(sz.columns, 300), min(sz.lines, 100)
            if (W, H) != size:
                size = (W, H)
                if W < 40 or H < 14:
                    scene = None
                else:
                    scene = Scene(W, H, args.seed)
                birds.clear()
                out.write("\x1b[2J")
            t = frame_start - t0
            if scene is None:
                out.write("\x1b[H terminal too small - please enlarge")
            else:
                birds.update(t, W, H)
                chars, grays = scene.frame(t, birds.flocks)
                out.write("\x1b[H" + "\r\n".join(to_ansi(chars, grays, color)))
            out.flush()
            wait = max(0.0, 1.0 / args.fps - (time.monotonic() - frame_start))
            if old:
                r, _, _ = select.select([sys.stdin], [], [], wait)
                if r:
                    k = os.read(fd, 32)
                    if k in (b"q", b"Q", b"\x1b", b"\x03"):
                        break
                    if k in (b"b", b"B") and scene is not None:
                        birds.call(time.monotonic() - t0, W, H)
            else:
                time.sleep(wait)
    except KeyboardInterrupt:
        pass
    finally:
        out.write("\x1b[0m\x1b[?25h\x1b[?1049l")
        out.flush()
        if old:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


if __name__ == "__main__":
    main()
