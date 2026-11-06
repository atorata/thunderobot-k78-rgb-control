"""
k78effects - K78 stok efektlerinin yazılımda yeniden yapılmış hali.

Adlar OpenRGB'nin SinoWealth/F11 mod listesinden alınmıştır (K78'in mod numaralarıyla
birebir örtüştüğü doğrulanmadı; görünümler stok efektlere yakın olacak şekilde tasarlandı).

Her efekt:  fx(ctx, f)  ->  f[satır][sütun] = (r, g, b)  (f önceden arka plan rengiyle dolu gelir)
ctx alanları: t (s), speed, color, colorful, presses [(poz, t0)], state (efekte özel kalıcı dict), rng
"""
import math
import random

from k78layout import CENTERS, CX, CY, HEIGHT, SNAKE_PATH, WIDTH

KEYS = list(CENTERS.items())          # [((r, c), (x, y)), ...]
POS_BY_ROW = {}
for (_r, _c), (_x, _y) in KEYS:
    POS_BY_ROW.setdefault(_r, []).append(((_r, _c), _x))


def hsv(h, s=1.0, v=1.0):
    h %= 1.0
    i = int(h * 6) % 6
    f = (h * 6) % 1
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r, g, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]
    return int(r * 255), int(g * 255), int(b * 255)


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def scale(c, k):
    k = max(0.0, min(1.0, k))
    return tuple(int(x * k) for x in c)


def tint(ctx, h):
    """Renkli modda tonu h olan renk, değilse seçili tek renk."""
    return hsv(h) if ctx.colorful else ctx.color


class Ctx:
    __slots__ = ("t", "speed", "color", "colorful", "bg", "presses", "state", "rng", "groups")


# ------------------------------------------------------------------ tuş grupları
# (anahtar, Türkçe ad, varsayılan renk)
GROUPS = [
    ("letters", "Harfler", (0, 150, 255)),
    ("numbers", "Rakamlar", (255, 150, 0)),
    ("punct", "Noktalama", (170, 70, 255)),
    ("mods", "Kontrol tuşları", (255, 30, 70)),
    ("space", "Boşluk", (255, 255, 255)),
    ("arrows", "Ok tuşları", (30, 230, 90)),
    ("numpad", "Numpad", (0, 220, 200)),
]
GROUP_DEFAULTS = {k: c for k, _, c in GROUPS}
_GROUP_KEYS = {
    "letters": [chr(c) for c in range(ord("A"), ord("Z") + 1)],
    "numbers": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "="],
    "punct": ["[", "]", "\\", ";", "'", ",", ".", "/"],
    "mods": ["ESC", "TAB", "CAPS", "LSHIFT", "RSHIFT", "LCTRL", "WIN", "LALT", "RALT", "FN", "RCTRL", "BKSP", "ENTER"],
    "space": ["SPACE"],
    "arrows": ["UP", "DOWN", "LEFT", "RIGHT"],
    "numpad": ["NUMLK", "KP+", "KP-", "KP0", "KP1", "KP2", "KP3", "KP4", "KP5", "KP6", "KP7", "KP8", "KP9", "KP."],
}


def _build_pos_group():
    from k78ctl import KEYMAP
    out = {}
    for g, names in _GROUP_KEYS.items():
        for n in names:
            out[KEYMAP[n]] = g
    return out


POS_GROUP = _build_pos_group()


EFFECTS = {}       # anahtar -> (Türkçe ad, fonksiyon, tepkili mi)


def effect(key, name, reactive=False):
    def deco(fn):
        EFFECTS[key] = (name, fn, reactive)
        return fn
    return deco


# ------------------------------------------------------------------ sürekli efektler
@effect("off", "Kapalı")
def fx_off(ctx, f):
    pass


@effect("static", "Statik")
def fx_static(ctx, f):
    for (r, c), (x, y) in KEYS:
        f[r][c] = tint(ctx, x / WIDTH * 0.85)


@effect("breath", "Nefes (Respire)")
def fx_breath(ctx, f):
    phase = ctx.t * ctx.speed
    k = 0.08 + 0.92 * (0.5 - 0.5 * math.cos(phase * 2 * math.pi))
    col = scale(tint(ctx, math.floor(phase) * 0.17), k)
    for (r, c), _ in KEYS:
        f[r][c] = col


@effect("spectrum", "Renk döngüsü (Rainbow)")
def fx_spectrum(ctx, f):
    col = hsv(ctx.t * ctx.speed * 0.25)
    for (r, c), _ in KEYS:
        f[r][c] = col


@effect("wave", "Gökkuşağı dalgası")
def fx_wave(ctx, f):
    for (r, c), (x, y) in KEYS:
        f[r][c] = hsv(x / WIDTH + y * 0.03 - ctx.t * ctx.speed)


@effect("wheel", "Gökkuşağı çarkı (Rainbow wheel)")
def fx_wheel(ctx, f):
    for (r, c), (x, y) in KEYS:
        a = math.atan2((y - CY) * 2.0, x - CX) / (2 * math.pi)
        f[r][c] = hsv(a - ctx.t * ctx.speed * 0.6)


@effect("neon", "Neon akış (Neon stream)")
def fx_neon(ctx, f):
    for (r, c), (x, y) in KEYS:
        h = x / WIDTH * 0.6 - y * 0.08 - ctx.t * ctx.speed * 0.5
        band = 0.55 + 0.45 * math.sin((x * 0.6 + y * 0.9 - ctx.t * ctx.speed * 9))
        f[r][c] = scale(hsv(h), band) if ctx.colorful else scale(ctx.color, band)


@effect("sine", "Sinüs dalgası (Sine wave)")
def fx_sine(ctx, f):
    for (r, c), (x, y) in KEYS:
        y0 = CY + 1.9 * math.sin(x * 0.45 - ctx.t * ctx.speed * 6)
        k = max(0.0, 1 - abs(y - y0) / 1.1)
        f[r][c] = mix(ctx.bg, tint(ctx, x / WIDTH - ctx.t * 0.05), k)


@effect("scan", "Tarayıcı (Retinue scanning)")
def fx_scan(ctx, f):
    period = 1.0 / max(0.05, ctx.speed * 0.8)
    ph = (ctx.t % period) / period
    pos = (ph * 2 if ph < 0.5 else 2 - ph * 2) * WIDTH
    going_right = ph < 0.5
    for (r, c), (x, y) in KEYS:
        d = x - pos
        behind = -d if going_right else d          # izin bıraktığı taraf
        k = 1 - abs(d) / 1.2 if abs(d) < 1.2 else (max(0.0, 1 - behind / 5.0) * 0.5 if behind > 0 else 0)
        f[r][c] = mix(ctx.bg, tint(ctx, pos / WIDTH), k)


@effect("windmill", "Yel değirmeni (Rotating windmill)")
def fx_windmill(ctx, f):
    for (r, c), (x, y) in KEYS:
        a = math.atan2((y - CY) * 2.0, x - CX)
        v = (0.5 + 0.5 * math.cos(4 * (a - ctx.t * ctx.speed * 3))) ** 3
        f[r][c] = mix(ctx.bg, tint(ctx, a / (2 * math.pi) + ctx.t * 0.05), v)


@effect("storm", "Dönen fırtına (Rotating storm)")
def fx_storm(ctx, f):
    for (r, c), (x, y) in KEYS:
        dx, dy = x - CX, (y - CY) * 2.0
        a, d = math.atan2(dy, dx), math.hypot(dx, dy)
        v = (0.5 + 0.5 * math.cos(2 * a + d * 0.9 - ctx.t * ctx.speed * 8)) ** 2
        f[r][c] = mix(ctx.bg, tint(ctx, d / 12.0 - ctx.t * ctx.speed * 0.3), v)


@effect("waterfall", "Renkli şelale (Colorful waterfall)")
def fx_waterfall(ctx, f):
    st = ctx.state
    if "phase" not in st:
        st["phase"] = {c: ctx.rng.random() * 6.28 for c in range(21)}
    for (r, c), (x, y) in KEYS:
        v = (0.5 + 0.5 * math.sin(st["phase"][c] - y * 1.3 + ctx.t * ctx.speed * 7)) ** 2
        f[r][c] = mix(ctx.bg, tint(ctx, x / WIDTH * 0.8 + ctx.t * 0.04), v)


@effect("raindrops", "Yağmur damlaları (Raindrops)")
def fx_raindrops(ctx, f):
    st = ctx.state
    drops = st.setdefault("drops", {})
    last = st.get("last", ctx.t)
    n = (ctx.t - last) * ctx.speed * 25 + st.get("acc", 0.0)
    while n >= 1:
        pos, _ = ctx.rng.choice(KEYS)
        drops[pos] = (ctx.t, ctx.rng.random())
        n -= 1
    st["acc"], st["last"] = n, ctx.t
    for pos, (t0, h) in list(drops.items()):
        age = ctx.t - t0
        if age > 1.0:
            del drops[pos]
            continue
        f[pos[0]][pos[1]] = mix(ctx.bg, tint(ctx, h), 1 - age)


@effect("stars", "Yıldızlar (Stars twinkle)")
def fx_stars(ctx, f):
    st = ctx.state
    stars = st.setdefault("stars", {})
    dim = scale(ctx.color, 0.08) if not ctx.colorful else (6, 6, 12)
    for (r, c), _ in KEYS:
        f[r][c] = dim
    last = st.get("last", ctx.t)
    n = (ctx.t - last) * ctx.speed * 18 + st.get("acc", 0.0)
    while n >= 1:
        pos, _ = ctx.rng.choice(KEYS)
        stars.setdefault(pos, (ctx.t, ctx.rng.random(), 0.8 + ctx.rng.random()))
        n -= 1
    st["acc"], st["last"] = n, ctx.t
    for pos, (t0, h, life) in list(stars.items()):
        age = (ctx.t - t0) / life
        if age > 1.0:
            del stars[pos]
            continue
        f[pos[0]][pos[1]] = mix(dim, tint(ctx, h), math.sin(age * math.pi))


@effect("bloom", "Çiçeklenme (Blossoming)")
def fx_bloom(ctx, f):
    st = ctx.state
    blooms = st.setdefault("blooms", [])
    if ctx.t >= st.get("next", 0):
        _, (x, y) = ctx.rng.choice(KEYS)
        blooms.append((x, y, ctx.t, ctx.rng.random()))
        st["next"] = ctx.t + 0.9 / max(0.05, ctx.speed * 2)
    for pos, t0 in ctx.presses:
        if t0 > st.get("seen", -1):
            x, y = CENTERS[pos]
            blooms.append((x, y, t0, ctx.rng.random()))
    st["seen"] = max([st.get("seen", -1)] + [t0 for _, t0 in ctx.presses])
    life = 1.6
    blooms[:] = [b for b in blooms if ctx.t - b[2] < life][-12:]
    for (r, c), (x, y) in KEYS:
        col = ctx.bg
        for bx, by, t0, h in blooms:
            age = (ctx.t - t0) / life
            rad = age * 7.0
            d = math.hypot(x - bx, (y - by) * 1.3)
            k = max(0.0, 1 - abs(d - rad) / 1.3) * (1 - age)
            if d < rad:
                k = max(k, 0.25 * (1 - age))
            if k > 0:
                col = mix(col, tint(ctx, h + age * 0.3), k)
        f[r][c] = col


@effect("snake", "Yılan (Retro snake)")
def fx_snake(ctx, f):
    n = len(SNAKE_PATH)
    head = ctx.t * ctx.speed * 18
    length = 9
    for i in range(length):
        idx = int(head - i) % n
        r, c = SNAKE_PATH[idx]
        k = 1 - i / length
        f[r][c] = mix(ctx.bg, tint(ctx, (head - i) / n), k)


@effect("groups", "Tuş grupları")
def fx_groups(ctx, f):
    custom = ctx.groups or {}
    for pos, _ in KEYS:
        g = POS_GROUP.get(pos)
        if g:
            f[pos[0]][pos[1]] = tuple(custom.get(g, GROUP_DEFAULTS[g]))


@effect("perfect", "Sabit gökkuşağı")
def fx_rainbow_static(ctx, f):
    for (r, c), (x, y) in KEYS:
        f[r][c] = hsv(x / WIDTH * 0.85 + y * 0.02)


# ------------------------------------------------------------------ tuşa tepki veren efektler
@effect("reaction", "Tepki (Reaction)", reactive=True)
def fx_reaction(ctx, f):
    for pos, t0 in ctx.presses:
        age = ctx.t - t0
        if 0 <= age < 1.0:
            f[pos[0]][pos[1]] = mix(f[pos[0]][pos[1]], tint(ctx, (t0 * 0.37) % 1), 1 - age)


@effect("flash", "Patlama (Flash away)", reactive=True)
def fx_flash(ctx, f):
    for pos, t0 in ctx.presses:
        age = ctx.t - t0
        if not 0 <= age < 0.7:
            continue
        px, py = CENTERS[pos]
        rad = 0.5 + age * 9
        for (r, c), (x, y) in KEYS:
            d = math.hypot(x - px, (y - py) * 1.3)
            if d <= rad:
                k = (1 - age / 0.7) * (1 - d / (rad + 0.01))
                f[r][c] = mix(f[r][c], tint(ctx, (t0 * 0.37) % 1), k)


@effect("ripples", "Dalgalanma (Ripples shining)", reactive=True)
def fx_ripples(ctx, f):
    for pos, t0 in ctx.presses:
        age = ctx.t - t0
        if not 0 <= age < 1.4:
            continue
        px, py = CENTERS[pos]
        rad = age * 10 * max(0.3, ctx.speed * 2)
        for (r, c), (x, y) in KEYS:
            d = math.hypot(x - px, (y - py) * 1.3)
            k = max(0.0, 1 - abs(d - rad) / 0.9) * (1 - age / 1.4)
            if k > 0:
                f[r][c] = mix(f[r][c], tint(ctx, (t0 * 0.37 + d * 0.04) % 1), k)


@effect("shadow", "Gölge (Shadow disappear)", reactive=True)
def fx_shadow(ctx, f):
    for (r, c), (x, y) in KEYS:
        f[r][c] = tint(ctx, x / WIDTH * 0.85)
    for pos, t0 in ctx.presses:
        age = ctx.t - t0
        if 0 <= age < 1.5:
            f[pos[0]][pos[1]] = scale(f[pos[0]][pos[1]], age / 1.5)


@effect("collision", "Çarpışma (Collision)", reactive=True)
def fx_collision(ctx, f):
    for pos, t0 in ctx.presses:
        age = ctx.t - t0
        if not 0 <= age < 1.1:
            continue
        r = pos[0]
        px = CENTERS[pos][0]
        row = POS_BY_ROW[r]
        left, right = min(x for _, x in row), max(x for _, x in row)
        travel = 0.6
        col = tint(ctx, (t0 * 0.37) % 1)
        if age < travel:                          # iki ışık kenarlardan tuşa doğru gelir
            a = left + (px - left) * age / travel
            b = right - (right - px) * age / travel
            for p, x in row:
                k = max(0.0, 1 - min(abs(x - a), abs(x - b)) / 0.9)
                if k > 0:
                    f[p[0]][p[1]] = mix(f[p[0]][p[1]], col, k)
        else:                                     # çarpışma: tuştan dışa doğru patlama
            e = (age - travel) / (1.1 - travel)
            for p2, (x, y) in KEYS:
                d = math.hypot(x - px, (y - (r - 0.5)) * 1.3)
                k = max(0.0, 1 - abs(d - e * 5) / 1.0) * (1 - e)
                if k > 0:
                    f[p2[0]][p2[1]] = mix(f[p2[0]][p2[1]], hsv((t0 * 0.37 + 0.5) % 1) if ctx.colorful else col, k)


ORDER = ["groups", "static", "breath", "spectrum", "wave", "wheel", "neon", "sine", "scan", "windmill", "storm",
         "waterfall", "raindrops", "stars", "bloom", "snake", "perfect",
         "reaction", "flash", "ripples", "shadow", "collision", "off"]
assert set(ORDER) == set(EFFECTS), set(ORDER) ^ set(EFFECTS)


def new_ctx():
    ctx = Ctx()
    ctx.state = {}
    ctx.rng = random.Random()
    ctx.presses = []
    ctx.groups = {}
    return ctx
