"""
k78engine - K78 için canlı efekt motoru (report 8, yalnızca RAM; flash'a yazmaz).

Katmanlar (alttan üste):
  1. Arka plan : static | wave | breath | off
  2. CPU       : sayı sırasında (1..0) CPU yükü çubuğu
  3. Tepki     : basılan tuş ve çevresi parlayıp söner
  4. Kilitler  : Caps Lock / Num Lock açıkken o tuşlar beyaz
  Son olarak genel parlaklık uygulanır.

Tuş basışları GetAsyncKeyState ile yoklanır; hiçbir tuş vuruşu saklanmaz veya kaydedilmez.
"""
import ctypes
import ctypes.wintypes as W
import json
import math
import os
import sys
import threading
import time

import k78ctl
from k78ctl import COLS, ROWS, KEYMAP, LiveRGB
from k78effects import EFFECTS, ORDER, hsv, mix, new_ctx

user32 = ctypes.WinDLL("user32")
kernel32 = ctypes.WinDLL("kernel32")
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetKeyState.restype = ctypes.c_short

# Tuş adı -> Windows sanal tuş kodu (EN düzen). Fn donanımsal olduğu için yok.
VK = {
    "ESC": 0x1B, "-": 0xBD, "=": 0xBB, "BKSP": 0x08, "NUMLK": 0x90, "KP+": 0x6B, "KP-": 0x6D,
    "TAB": 0x09, "[": 0xDB, "]": 0xDD, "\\": 0xDC, "CAPS": 0x14, ";": 0xBA, "'": 0xDE, "ENTER": 0x0D,
    "LSHIFT": 0xA0, ",": 0xBC, ".": 0xBE, "/": 0xBF, "RSHIFT": 0xA1, "UP": 0x26,
    "LCTRL": 0xA2, "WIN": 0x5B, "LALT": 0xA4, "SPACE": 0x20, "RALT": 0xA5, "RCTRL": 0xA3,
    "LEFT": 0x25, "DOWN": 0x28, "RIGHT": 0x27, "KP0": 0x60, "KP.": 0x6E,
}
VK.update({str(d): 0x30 + d for d in range(10)})
VK.update({chr(c): c for c in range(ord("A"), ord("Z") + 1)})
VK.update({"KP%d" % d: 0x60 + d for d in range(1, 10)})
VK_KEYS = [(name, vk, KEYMAP[name]) for name, vk in VK.items() if name in KEYMAP]

CPU_KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]


class _FILETIME(ctypes.Structure):
    _fields_ = [("lo", W.DWORD), ("hi", W.DWORD)]


def _ft(f):
    return (f.hi << 32) | f.lo


class CpuMeter:
    def __init__(self):
        self.prev = self._times()
        self.value = 0.0

    @staticmethod
    def _times():
        i, k, u = _FILETIME(), _FILETIME(), _FILETIME()
        kernel32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u))
        return _ft(i), _ft(k), _ft(u)

    def sample(self):
        cur = self._times()
        di, dk, du = (c - p for c, p in zip(cur, self.prev))
        self.prev = cur
        total = dk + du
        if total > 0:
            load = max(0.0, min(1.0, (total - di) / total))
            self.value += (load - self.value) * 0.3      # yumuşatma
        return self.value


DEFAULT_SETTINGS = {
    "base": "wave",                 # k78effects.ORDER içindeki anahtarlardan biri
    "colorful": True,               # True: gökkuşağı renkleri, False: base_color
    "base_color": [0, 120, 255],
    "bg_color": [0, 0, 0],
    "static_keys": {},              # "W": [255,255,255] ...
    "group_colors": {},             # "letters": [r,g,b] ... (boşsa varsayılan grup renkleri)
    "speed": 0.3,                   # wave/breath hızı
    "brightness": 1.0,              # 0..1
    "reactive": True,
    "reactive_color": [255, 255, 255],
    "reactive_decay": 0.6,          # saniye
    "reactive_spread": 1.5,         # hücre
    "cpu": False,
    "locks": True,
    "fps": 30,
    "on_exit": "keep",              # keep | off | color  (uygulamadan çıkınca klavyede kalacak görüntü)
    "exit_color": [255, 255, 255],
}


class Engine:
    def __init__(self, settings=None):
        self.settings = dict(DEFAULT_SETTINGS)
        if settings:
            self.settings.update(settings)
        self.lock = threading.Lock()
        self.frame = [[(0, 0, 0)] * COLS for _ in range(ROWS)]
        self.status = "durdu"
        self._stop = threading.Event()
        self._thread = None
        self._hits = {}            # (r,c) -> basılma zamanı (tepki katmanı)
        self._presses = []         # [(poz, zaman)] son basışlar (tepkili efektler)
        self._prev_down = set()
        self._cpu = CpuMeter()
        self._ctx = new_ctx()
        self._ctx_base = None
        self._t0 = time.perf_counter()

    # ---------------------------------------------------- ayarlar
    def update(self, **kw):
        with self.lock:
            self.settings.update(kw)

    def get(self, key):
        with self.lock:
            return self.settings[key]

    def save(self, path):
        with self.lock:
            data = dict(self.settings)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        with self.lock:
            self.settings = dict(DEFAULT_SETTINGS)
            self.settings.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})

    # ---------------------------------------------------- çizim
    def _render(self, t, s):
        bg = tuple(s["bg_color"])
        f = [[bg] * COLS for _ in range(ROWS)]
        base = s["base"] if s["base"] in EFFECTS else "wave"
        if base != self._ctx_base:                 # efekt değişince durumunu sıfırla
            self._ctx = new_ctx()
            self._ctx_base = base
        ctx = self._ctx
        ctx.t, ctx.speed = t, s["speed"]
        ctx.color, ctx.colorful, ctx.bg = tuple(s["base_color"]), bool(s["colorful"]), bg
        ctx.presses = [(p, pt - self._t0) for p, pt in self._presses]
        ctx.groups = s["group_colors"]
        EFFECTS[base][1](ctx, f)
        for name, rgb in s["static_keys"].items():
            pos = KEYMAP.get(name.upper())
            if pos:
                f[pos[0]][pos[1]] = tuple(rgb)

        if s["cpu"]:
            load = self._cpu.sample()
            lit = load * len(CPU_KEYS)
            for i, name in enumerate(CPU_KEYS):
                r, c = KEYMAP[name]
                level = max(0.0, min(1.0, lit - i))
                tint = hsv((1 - i / (len(CPU_KEYS) - 1)) * 0.33)     # yeşil -> kırmızı
                f[r][c] = mix((10, 10, 10), tint, level)

        if s["reactive"]:
            now = time.perf_counter()
            decay, spread = s["reactive_decay"], s["reactive_spread"]
            rc = tuple(s["reactive_color"])
            for (hr, hc), t0 in list(self._hits.items()):
                age = now - t0
                if age > decay:
                    del self._hits[(hr, hc)]
                    continue
                k_time = 1 - age / decay
                rad = spread * (0.4 + age / decay)
                for r in range(1, ROWS):
                    for c in range(17):
                        d = math.hypot(r - hr, c - hc)
                        if d <= rad:
                            k = k_time * (1 - d / (rad + 1e-6)) if d > 0 else k_time
                            f[r][c] = mix(f[r][c], rc, max(0.0, k))

        if s["locks"]:
            for name, vk in (("CAPS", 0x14), ("NUMLK", 0x90)):
                if user32.GetKeyState(vk) & 1:
                    r, c = KEYMAP[name]
                    f[r][c] = (255, 255, 255)

        br = max(0.0, min(1.0, s["brightness"]))
        if br < 1.0:
            f = [[tuple(int(x * br) for x in px) for px in row] for row in f]
        return f

    def _poll_keys(self):
        now = time.perf_counter()
        down = set()
        for name, vk, pos in VK_KEYS:
            if user32.GetAsyncKeyState(vk) & 0x8000:
                down.add(pos)
        for pos in down - self._prev_down:
            self._hits[pos] = now
            self._presses.append((pos, now))
        if self._presses:
            self._presses = [p for p in self._presses if now - p[1] < 3.0][-64:]
        for pos in down:                      # basılı tutulan tuş parlak kalsın
            self._hits[pos] = max(self._hits.get(pos, 0), now - 0.05)
        self._prev_down = down

    # ---------------------------------------------------- döngü
    def _run(self):
        live = None
        t0 = self._t0 = time.perf_counter()
        n = 0
        while not self._stop.is_set():
            with self.lock:
                s = dict(self.settings)
                s["static_keys"] = dict(self.settings["static_keys"])
                s["group_colors"] = dict(self.settings["group_colors"])
            if s["reactive"] or EFFECTS.get(s["base"], (0, 0, False))[2]:
                self._poll_keys()
            frame = self._render(time.perf_counter() - self._t0, s)
            with self.lock:
                self.frame = frame
            try:
                if live is None:
                    live = LiveRGB()
                live.send(frame)
                self.status = "çalışıyor"
            except SystemExit as e:              # k78ctl hataları SystemExit fırlatır
                self.status = "bağlantı yok: %s" % e
                if live:
                    try:
                        live.close()
                    except Exception:
                        pass
                live = None
                self._stop.wait(1.0)
                continue
            n += 1
            period = 1.0 / max(1, s["fps"])
            self._stop.wait(max(0.0, t0 + n * period - time.perf_counter()))
            if t0 + n * period < time.perf_counter() - 1:      # geride kaldıysa saati sıfırla
                t0, n = time.perf_counter(), 0
        if live:
            live.close()
        self.status = "durdu"

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="k78-engine", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def shutdown(self):
        """Motoru durdur ve 'on_exit' ayarına göre son görüntüyü bırak.
        Firmware'de host'tan stok efekte dönme komutu yok; stok efekte Fn ya da yeniden takma ile dönülür."""
        self.stop()
        mode = self.get("on_exit")
        if mode == "keep":
            return
        if mode == "off":
            col = (0, 0, 0)
        else:
            br = max(0.0, min(1.0, self.get("brightness")))
            col = tuple(int(x * br) for x in self.get("exit_color"))
        frame = [[col] * COLS for _ in range(ROWS)]
        try:
            live = LiveRGB()
            try:
                live.send(frame)
            finally:
                live.close()
        except SystemExit:
            pass                      # klavye takılı değilse sessizce geç

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive())


def data_dir():
    """Kurulu .exe'de kullanıcı verisi %APPDATA%\\K78RGB'de; kaynaktan çalışırken script klasöründe."""
    if getattr(sys, "frozen", False):
        return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "K78RGB")
    return os.path.dirname(os.path.abspath(__file__))


PROFILE_DIR = os.path.join(data_dir(), "profiles")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="K78 canlı efekt motoru (Ctrl+C ile durur)")
    p.add_argument("--base", choices=ORDER, default="wave")
    p.add_argument("--mono", action="store_true", help="tek renk (base_color)")
    p.add_argument("--no-reactive", action="store_true")
    p.add_argument("--cpu", action="store_true")
    p.add_argument("--seconds", type=float, default=0)
    p.add_argument("--profile", help="profiles/ altındaki JSON profil")
    a = p.parse_args()
    eng = Engine()
    if a.profile:
        eng.load(a.profile if os.path.isabs(a.profile) else os.path.join(PROFILE_DIR, a.profile))
    else:
        eng.update(base=a.base, reactive=not a.no_reactive, cpu=a.cpu, colorful=not a.mono)
    eng.start()
    try:
        t_end = time.time() + a.seconds if a.seconds > 0 else None
        while t_end is None or time.time() < t_end:
            time.sleep(0.5)
            if not eng.running:
                break
    except KeyboardInterrupt:
        pass
    eng.stop()
    print("motor durdu:", eng.status)
