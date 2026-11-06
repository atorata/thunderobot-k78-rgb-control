"""
k78gui - Thunderobot K78 ışık kontrolü (tkinter, ek bağımlılık yok).

Canlı efektler report 8 ile yalnızca RAM'e gider; flash'a yazılmaz.
Pencere kapatılınca tepside çalışmaya devam eder; tamamen kapatmak için Ayarlar > Çıkış veya tepsi menüsü.
"""
import json
import os
import random
import sys
import time
import tkinter as tk
import winreg
from tkinter import colorchooser, messagebox, simpledialog

from k78effects import EFFECTS, GROUP_DEFAULTS, GROUPS, ORDER, new_ctx
from k78engine import PROFILE_DIR, Engine
from k78layout import RECTS, WIDTH
from k78tray import TrayIcon

LAST_PROFILE = os.path.join(PROFILE_DIR, "_son.json")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "K78Isik"

# ------------------------------------------------------------------ tema
C = dict(bg="#0d0f14", panel="#141720", card="#1a1e28", card_hi="#232937", line="#2c3344",
         text="#e9ecf2", muted="#8890a4", faint="#5b6378", accent="#7c5cff", accent_hi="#9077ff",
         ok="#22c55e", warn="#f59e0b", err="#ef4444", key_off="#20242f")


def F(size, weight="normal"):
    return ("Segoe UI", size, weight)


def hexcol(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(x))) for x in rgb)


def luminance(rgb):
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def round_rect(cv, x0, y0, x1, y1, r, **kw):
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
           x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return cv.create_polygon(pts, smooth=True, **kw)


DESC = {
    "groups": "Harfler, rakamlar, noktalama, kontrol tuşları, boşluk, ok tuşları ve numpad farklı renklerde. "
              "Her grubun rengini aşağıdan seçebilirsiniz.",
    "static": "Tek renk ya da soldan sağa sabit gökkuşağı geçişi.",
    "breath": "Işık yavaşça yanıp söner. Renkli modda her nefeste renk değişir.",
    "spectrum": "Tüm klavye birlikte renkten renge geçer.",
    "wave": "Gökkuşağı soldan sağa akar.",
    "wheel": "Renkler klavyenin merkezi etrafında döner.",
    "neon": "Çapraz neon bantlar akar.",
    "sine": "Sinüs biçiminde bir ışık bandı dalgalanır.",
    "scan": "Bir ışık huzmesi iz bırakarak sağa sola tarar.",
    "windmill": "Merkezde dört kanatlı bir pervane döner.",
    "storm": "Dönen bir spiral.",
    "waterfall": "Işık sütunlar halinde yukarıdan aşağı dökülür.",
    "raindrops": "Rastgele tuşlar damla gibi yanıp söner.",
    "stars": "Loş zemin üzerinde yıldızlar parıldar.",
    "bloom": "Rastgele noktalardan halkalar açılır; tuşa basınca da açılır.",
    "snake": "Bir ışık yılanı satırlar boyunca kıvrılır.",
    "perfect": "Hareketsiz gökkuşağı.",
    "reaction": "Bastığınız tuş yanar ve söner.",
    "flash": "Bastığınız tuştan ışık patlar ve dağılır.",
    "ripples": "Bastığınız tuştan halka halka dalga yayılır.",
    "shadow": "Klavye yanar; bastığınız tuş kararır ve yavaşça geri gelir.",
    "collision": "İki ışık satır boyunca gelir, tuşta çarpışır ve patlar.",
    "off": "Tüm ışıklar kapalı (katmanlar ve boyamalar görünür).",
}
PALETTE = [(255, 255, 255), (255, 40, 40), (255, 130, 0), (255, 220, 0), (40, 230, 80),
           (0, 220, 220), (30, 110, 255), (130, 60, 255), (255, 60, 200), (0, 0, 0)]


# ------------------------------------------------------------------ otomatik başlatma
def autostart_command():
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pyw):
        exe = pyw
    return '"%s" "%s" --tray' % (exe, os.path.abspath(__file__))


def autostart_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_NAME)
            return True
    except OSError:
        return False


def set_autostart(on):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass


# ------------------------------------------------------------------ küçük bileşenler
def button(parent, text, cmd, kind="ghost", bg=None):
    styles = {"primary": (C["accent"], C["accent_hi"], "white"),
              "ghost": (C["card_hi"], C["line"], C["text"]),
              "danger": ("#3a1d24", "#4d2430", "#ff9a9a")}
    b0, b1, fg = styles[kind]
    lb = tk.Label(parent, text=text, bg=b0, fg=fg, font=F(10, "bold" if kind == "primary" else "normal"),
                  padx=14, pady=6, cursor="hand2")
    lb.bind("<Enter>", lambda e: lb.configure(bg=b1))
    lb.bind("<Leave>", lambda e: lb.configure(bg=b0))
    lb.bind("<Button-1>", lambda e: cmd())
    return lb


def card(parent, title=None, sub=None):
    f = tk.Frame(parent, bg=C["card"], padx=16, pady=14)
    if title:
        tk.Label(f, text=title, bg=C["card"], fg=C["text"], font=F(11, "bold")).pack(anchor="w")
    if sub:
        tk.Label(f, text=sub, bg=C["card"], fg=C["muted"], font=F(9), wraplength=420,
                 justify="left").pack(anchor="w", pady=(2, 8))
    return f


class Toggle(tk.Canvas):
    def __init__(self, parent, value, command, bg=C["card"]):
        super().__init__(parent, width=44, height=24, bg=bg, highlightthickness=0, cursor="hand2")
        self.value, self.command = bool(value), command
        self.bind("<Button-1>", self._click)
        self._draw()

    def _draw(self):
        self.delete("all")
        round_rect(self, 1, 1, 43, 23, 11, fill=C["accent"] if self.value else C["line"], outline="")
        x = 31 if self.value else 13
        self.create_oval(x - 8, 4, x + 8, 20, fill="white", outline="")

    def _click(self, _):
        self.value = not self.value
        self._draw()
        self.command(self.value)

    def set(self, v):
        self.value = bool(v)
        self._draw()


class Slider(tk.Canvas):
    def __init__(self, parent, lo, hi, value, command, fmt=lambda v: "%.0f%%" % (v * 100), width=240, bg=C["card"]):
        super().__init__(parent, width=width, height=30, bg=bg, highlightthickness=0, cursor="hand2")
        self.lo, self.hi, self.value, self.command, self.fmt, self.w = lo, hi, value, command, fmt, width
        self.bind("<Button-1>", self._set)
        self.bind("<B1-Motion>", self._set)
        self._draw()

    def _span(self):
        return 10, self.w - 58

    def _draw(self):
        self.delete("all")
        x0, x1 = self._span()
        y = 15
        t = (self.value - self.lo) / (self.hi - self.lo)
        x = x0 + max(0.0, min(1.0, t)) * (x1 - x0)
        self.create_line(x0, y, x1, y, fill=C["line"], width=5, capstyle="round")
        self.create_line(x0, y, x, y, fill=C["accent"], width=5, capstyle="round")
        self.create_oval(x - 8, y - 8, x + 8, y + 8, fill=C["text"], outline=C["accent"], width=2)
        self.create_text(self.w - 2, y, text=self.fmt(self.value), anchor="e", fill=C["muted"], font=F(9))

    def _set(self, e):
        x0, x1 = self._span()
        t = max(0.0, min(1.0, (e.x - x0) / (x1 - x0)))
        self.value = self.lo + t * (self.hi - self.lo)
        self._draw()
        self.command(self.value)

    def set(self, v):
        self.value = v
        self._draw()


class Swatch(tk.Canvas):
    def __init__(self, parent, color, command, size=28, bg=C["card"], selected=False, plus=False):
        super().__init__(parent, width=size + 6, height=size + 6, bg=bg, highlightthickness=0, cursor="hand2")
        self.size, self.color, self.selected, self.plus = size, tuple(color), selected, plus
        self.bind("<Button-1>", lambda e: command())
        self._draw()

    def _draw(self):
        self.delete("all")
        s = self.size
        if self.selected:
            self.create_oval(1, 1, s + 5, s + 5, outline=C["text"], width=2)
        fill = hexcol(self.color)
        outline = C["line"] if luminance(self.color) < 40 else ""
        self.create_oval(4, 4, s + 2, s + 2, fill=fill, outline=outline, width=1)
        if self.plus:
            self.create_text(s / 2 + 3, s / 2 + 3, text="+", fill="white" if luminance(self.color) < 140 else "black",
                             font=F(12, "bold"))

    def set(self, color=None, selected=None):
        if color is not None:
            self.color = tuple(color)
        if selected is not None:
            self.selected = selected
        self._draw()


class Segmented(tk.Frame):
    def __init__(self, parent, options, value, command):
        super().__init__(parent, bg=C["line"])
        self.value, self.command, self.labels = value, command, {}
        for i, (v, t) in enumerate(options):
            lb = tk.Label(self, text=t, font=F(9), padx=12, pady=5, cursor="hand2")
            lb.grid(row=0, column=i, padx=(1, 1), pady=1)
            lb.bind("<Button-1>", lambda e, v=v: self._pick(v))
            self.labels[v] = lb
        self._paint()

    def _paint(self):
        for v, lb in self.labels.items():
            on = v == self.value
            lb.configure(bg=C["accent"] if on else C["card"], fg="white" if on else C["muted"])

    def _pick(self, v):
        self.value = v
        self._paint()
        self.command(v)

    def set(self, v):
        self.value = v
        self._paint()


class ScrollFrame(tk.Frame):
    """İçerik + ince özel kaydırma çubuğu; fare tekerleği imleç üzerindeyken çalışır."""

    def __init__(self, parent, bg, on_resize=None):
        super().__init__(parent, bg=bg)
        self.on_resize = on_resize
        self.cv = tk.Canvas(self, bg=bg, highlightthickness=0, yscrollincrement=20)
        self.inner = tk.Frame(self.cv, bg=bg)
        self.win = self.cv.create_window(0, 0, window=self.inner, anchor="nw")
        self.bar = tk.Canvas(self, width=8, bg=bg, highlightthickness=0, cursor="hand2")
        self.cv.pack(side="left", fill="both", expand=True)
        self.bar.pack(side="right", fill="y", padx=(4, 0))
        self.cv.configure(yscrollcommand=self._bar_draw)
        self.inner.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.cv.bind("<Configure>", self._resize)
        self.bar.bind("<Button-1>", self._bar_drag)
        self.bar.bind("<B1-Motion>", self._bar_drag)
        self.cv.bind_all("<MouseWheel>", self._wheel, add="+")

    def _resize(self, e):
        self.cv.itemconfigure(self.win, width=e.width)
        if self.on_resize:
            self.on_resize(e.width)

    def _bar_draw(self, lo, hi):
        lo, hi = float(lo), float(hi)
        self.bar.delete("all")
        if hi - lo >= 0.999:
            return
        h = self.bar.winfo_height()
        round_rect(self.bar, 1, 0, 7, h, 3, fill=C["panel"], outline="")
        round_rect(self.bar, 1, lo * h, 7, max(lo * h + 24, hi * h), 3, fill=C["line"], outline="")

    def _bar_drag(self, e):
        lo, hi = self.cv.yview()
        h = max(1, self.bar.winfo_height())
        self.cv.yview_moveto(max(0.0, e.y / h - (hi - lo) / 2))

    def _wheel(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        while w is not None:
            if w is self.cv or w is self.bar:
                self.cv.yview_scroll(int(-e.delta / 40), "units")
                return
            w = w.master


class KeyboardView(tk.Canvas):
    """Ana klavye önizlemesi: canlı renkler, tıklama/sürükleme ile boyama."""

    def __init__(self, parent, unit=44, on_paint=None, on_hover=None):
        w = int(WIDTH * unit) + 24
        super().__init__(parent, width=w, height=5 * unit + 24, bg=C["panel"], highlightthickness=0)
        self.unit, self.on_paint, self.on_hover = unit, on_paint, on_hover
        self.items = []      # (ad, (r, c), poligon, metin)
        self._cache = {}
        round_rect(self, 2, 2, w - 2, 5 * unit + 22, 14, fill="#0a0c10", outline=C["line"])
        for name, r, c, x, kw in RECTS:
            x0, y0 = 12 + x * unit, 12 + (r - 1) * unit
            poly = round_rect(self, x0 + 2, y0 + 2, x0 + kw * unit - 2, y0 + unit - 2, 8,
                              fill=C["key_off"], outline="")
            label = {"BKSP": "⌫", "LSHIFT": "Shift", "RSHIFT": "Shift", "LCTRL": "Ctrl", "RCTRL": "Ctrl",
                     "LALT": "Alt", "RALT": "Alt", "UP": "↑", "DOWN": "↓", "LEFT": "←", "RIGHT": "→",
                     "NUMLK": "Num", "SPACE": "", "KP+": "+", "KP-": "−", "KP.": ".", "CAPS": "Caps",
                     "ENTER": "Enter", "TAB": "Tab", "WIN": "Win", "ESC": "Esc", "FN": "Fn"}.get(name, name.replace("KP", ""))
            txt = self.create_text(x0 + kw * unit / 2, y0 + unit / 2, text=label, fill=C["muted"], font=F(9, "bold"))
            self.items.append((name, (r, c), poly, txt))
        self.bind("<Button-1>", lambda e: self._paint(e, False))
        self.bind("<B1-Motion>", lambda e: self._paint(e, False))
        self.bind("<Button-3>", lambda e: self._paint(e, True))
        self.bind("<B3-Motion>", lambda e: self._paint(e, True))
        self.bind("<Motion>", self._hover)
        self.bind("<Leave>", lambda e: self.on_hover and self.on_hover(None))

    def key_at(self, x, y):
        for item in self.find_overlapping(x, y, x, y):
            for name, _, poly, txt in self.items:
                if item in (poly, txt):
                    return name
        return None

    def _paint(self, e, erase):
        name = self.key_at(e.x, e.y)
        if name and self.on_paint:
            self.on_paint(name, erase)

    def _hover(self, e):
        if self.on_hover:
            self.on_hover(self.key_at(e.x, e.y))

    def show(self, frame):
        for name, (r, c), poly, txt in self.items:
            rgb = frame[r][c]
            if self._cache.get(name) == rgb:
                continue
            self._cache[name] = rgb
            off = luminance(rgb) < 8
            self.itemconfigure(poly, fill=C["key_off"] if off else hexcol(rgb))
            self.itemconfigure(txt, fill=C["faint"] if off else ("#111111" if luminance(rgb) > 150 else "#f4f4f4"))


class EffectCard(tk.Frame):
    S = 8   # mini önizleme ölçeği (piksel / birim)

    def __init__(self, parent, key, on_select):
        super().__init__(parent, bg=C["card"], highlightthickness=2, highlightbackground=C["card"],
                         padx=8, pady=8, cursor="hand2")
        self.key = key
        s = self.S
        self.cv = tk.Canvas(self, width=int(WIDTH * s) + 8, height=5 * s + 8, bg="#0a0c10", highlightthickness=0)
        self.cv.pack()
        self.cells = []
        for _, r, c, x, kw in RECTS:
            it = self.cv.create_rectangle(4 + x * s + 1, 4 + (r - 1) * s + 1, 4 + (x + kw) * s - 1, 4 + r * s - 1,
                                          fill=C["key_off"], outline="")
            self.cells.append((it, (r, c)))
        name, _, reactive = EFFECTS[key]
        row = tk.Frame(self, bg=C["card"])
        row.pack(fill="x", pady=(6, 0))
        self.title = tk.Label(row, text=name, bg=C["card"], fg=C["text"], font=F(9, "bold"), anchor="w",
                              justify="left", wraplength=int(WIDTH * s) - 14)
        self.title.pack(side="left")
        if reactive:
            tk.Label(row, text="⌨", bg=C["card"], fg=C["accent_hi"], font=F(10)).pack(side="right")
        self._cache = {}
        for w in (self, self.cv, row, self.title):
            w.bind("<Button-1>", lambda e: on_select(key))

    def select(self, on):
        self.configure(highlightbackground=C["accent"] if on else C["card"])

    def show(self, frame):
        for it, (r, c) in self.cells:
            rgb = frame[r][c]
            if self._cache.get(it) != rgb:
                self._cache[it] = rgb
                self.cv.itemconfigure(it, fill=C["key_off"] if luminance(rgb) < 8 else hexcol(rgb))


# ------------------------------------------------------------------ uygulama
class App(tk.Tk):
    PAGES = [("effects", "Efektler"), ("paint", "Tuş boyama"), ("layers", "Katmanlar"),
             ("profiles", "Profiller"), ("settings", "Ayarlar")]

    def __init__(self, start_hidden=False):
        super().__init__()
        self.title("K78 Işık Kontrolü")
        self.configure(bg=C["bg"])
        self.minsize(1180, 800)
        self.engine = Engine()
        if os.path.exists(LAST_PROFILE):
            try:
                self.engine.load(LAST_PROFILE)
            except Exception:
                pass
        self._saved_json = self._settings_json()
        self._hint_shown = False
        self.brush = [255, 255, 255]
        self.tool = "brush"
        self.page = None
        self._thumb_ctx = {k: new_ctx() for k in ORDER}
        self._thumb_t0 = time.perf_counter()
        self._synth = []
        self._synth_next = 0.0
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._hide)
        self.tray = TrayIcon("K78 Işık Kontrolü")
        self.tray.start()
        self.engine.start()
        self._goto("effects")
        if start_hidden:
            self.withdraw()
        self.after(60, self._tick)
        self.after(160, self._thumb_tick)
        self.after(2000, self._autosave)

    # ---------------------------------------------------------- iskelet
    def _build(self):
        # Üst çubuk
        top = tk.Frame(self, bg=C["bg"], padx=20, pady=14)
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        top.columnconfigure(1, weight=1)
        tk.Label(top, text="K78", bg=C["bg"], fg=C["text"], font=F(20, "bold")).grid(row=0, column=0, rowspan=2, padx=(0, 12))
        tk.Label(top, text="Thunderobot · 78 tuş · canlı RGB (flash'a yazmaz)", bg=C["bg"], fg=C["muted"],
                 font=F(9)).grid(row=1, column=1, sticky="w")
        self.status = tk.Label(top, text="", bg=C["bg"], font=F(10, "bold"))
        self.status.grid(row=0, column=1, sticky="w")
        tk.Label(top, text="Parlaklık", bg=C["bg"], fg=C["muted"], font=F(9)).grid(row=0, column=2, rowspan=2, padx=(0, 6))
        self.s_bright = Slider(top, 0.05, 1.0, self.engine.get("brightness"),
                               lambda v: self.engine.update(brightness=v), bg=C["bg"], width=220)
        self.s_bright.grid(row=0, column=3, rowspan=2)
        self.btn_run = button(top, "❚❚  Duraklat", self._toggle_run)
        self.btn_run.grid(row=0, column=4, rowspan=2, padx=(16, 0))

        # Klavye önizlemesi
        kb_wrap = tk.Frame(self, bg=C["panel"], padx=16, pady=12)
        kb_wrap.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20)
        self.kb = KeyboardView(kb_wrap, on_paint=self._paint_key, on_hover=self._hover_key)
        self.kb.pack()
        self.hint = tk.Label(kb_wrap, text="", bg=C["panel"], fg=C["muted"], font=F(9))
        self.hint.pack(anchor="w", pady=(6, 0))

        # Kenar menü + sayfalar
        side = tk.Frame(self, bg=C["bg"], padx=12, pady=16)
        side.grid(row=2, column=0, sticky="ns")
        self.nav = {}
        for key, text in self.PAGES:
            item = tk.Frame(side, bg=C["bg"], cursor="hand2")
            item.pack(fill="x", pady=2)
            bar = tk.Frame(item, bg=C["bg"], width=3)
            bar.pack(side="left", fill="y")
            lb = tk.Label(item, text=text, bg=C["bg"], fg=C["muted"], font=F(10), anchor="w",
                          padx=16, pady=9, width=15, cursor="hand2")
            lb.pack(side="left", fill="x")
            for w in (item, lb, bar):
                w.bind("<Button-1>", lambda e, k=key: self._goto(k))
                w.bind("<Enter>", lambda e, k=key: self._nav_hover(k, True))
                w.bind("<Leave>", lambda e, k=key: self._nav_hover(k, False))
            self.nav[key] = (item, bar, lb)

        host = tk.Frame(self, bg=C["bg"], padx=8, pady=16)
        host.grid(row=2, column=1, sticky="nsew", padx=(0, 20))
        self.rowconfigure(2, weight=1)
        self.columnconfigure(1, weight=1)
        host.rowconfigure(0, weight=1)
        host.columnconfigure(0, weight=1)
        self.pages = {}
        for key, _ in self.PAGES:
            f = tk.Frame(host, bg=C["bg"])
            f.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = f
        self._page_effects(self.pages["effects"])
        self._page_paint(self.pages["paint"])
        self._page_layers(self.pages["layers"])
        self._page_profiles(self.pages["profiles"])
        self._page_settings(self.pages["settings"])

    def _nav_hover(self, key, on):
        if key != self.page:
            item, bar, lb = self.nav[key]
            bg = C["card"] if on else C["bg"]
            for w in (item, bar, lb):
                w.configure(bg=bg)

    def _goto(self, key):
        self.page = key
        self.pages[key].tkraise()
        for k, (item, bar, lb) in self.nav.items():
            sel = k == key
            bg = C["card_hi"] if sel else C["bg"]
            item.configure(bg=bg)
            bar.configure(bg=C["accent"] if sel else bg)
            lb.configure(bg=bg, fg=C["text"] if sel else C["muted"], font=F(10, "bold" if sel else "normal"))
        self.kb.configure(cursor="pencil" if key == "paint" else "")
        if key == "profiles":
            self._refresh_profiles()
        self._update_hint(None)

    # ---------------------------------------------------------- Efektler
    def _page_effects(self, p):
        p.columnconfigure(0, weight=1)
        p.rowconfigure(0, weight=1)
        sf = ScrollFrame(p, C["bg"], on_resize=self._reflow_cards)
        sf.grid(row=0, column=0, sticky="nsew")
        self.cards = {}
        self._card_cols = 0
        for key in ORDER:
            self.cards[key] = EffectCard(sf.inner, key, self._select_effect)
        self._reflow_cards(600)

        opt = card(p)
        opt.grid(row=0, column=1, sticky="ns", padx=(12, 0))
        self.e_title = tk.Label(opt, text="", bg=C["card"], fg=C["text"], font=F(13, "bold"), wraplength=260, justify="left")
        self.e_title.pack(anchor="w")
        self.e_desc = tk.Label(opt, text="", bg=C["card"], fg=C["muted"], font=F(9), wraplength=260, justify="left")
        self.e_desc.pack(anchor="w", pady=(4, 2))
        self.e_tag = tk.Label(opt, text="", bg=C["card"], fg=C["accent_hi"], font=F(9, "bold"))
        self.e_tag.pack(anchor="w", pady=(0, 10))

        self.dyn = tk.Frame(opt, bg=C["card"])
        self.dyn.pack(fill="x")
        # Standart efekt ayarları
        self.std_box = tk.Frame(self.dyn, bg=C["card"])
        std = self.std_box
        tk.Label(std, text="Renkler", bg=C["card"], fg=C["text"], font=F(10, "bold")).pack(anchor="w")
        self.seg_color = Segmented(std, [("rainbow", "Gökkuşağı"), ("mono", "Tek renk")],
                                   "rainbow" if self.engine.get("colorful") else "mono", self._set_color_mode)
        self.seg_color.pack(anchor="w", pady=(4, 8))
        row = tk.Frame(std, bg=C["card"])
        row.pack(anchor="w", pady=(0, 10))
        tk.Label(row, text="Efekt rengi", bg=C["card"], fg=C["muted"], font=F(9)).pack(side="left", padx=(0, 8))
        self.sw_base = Swatch(row, self.engine.get("base_color"), lambda: self._pick("base_color", self.sw_base))
        self.sw_base.pack(side="left")
        tk.Label(row, text="   Zemin", bg=C["card"], fg=C["muted"], font=F(9)).pack(side="left", padx=(0, 8))
        self.sw_bg = Swatch(row, self.engine.get("bg_color"), lambda: self._pick("bg_color", self.sw_bg))
        self.sw_bg.pack(side="left")

        tk.Label(std, text="Hız", bg=C["card"], fg=C["text"], font=F(10, "bold")).pack(anchor="w")
        self.s_speed = Slider(std, 0.05, 2.0, self.engine.get("speed"), lambda v: self.engine.update(speed=v),
                              fmt=lambda v: "%.2f×" % (v / 0.3), width=260)
        self.s_speed.pack(anchor="w", pady=(2, 10))

        # Tuş grupları ayarları
        self.group_box = tk.Frame(self.dyn, bg=C["card"])
        tk.Label(self.group_box, text="Grup renkleri", bg=C["card"], fg=C["text"], font=F(10, "bold")).pack(anchor="w")
        tk.Label(self.group_box, text="Renge tıklayıp değiştirin.", bg=C["card"], fg=C["muted"],
                 font=F(9)).pack(anchor="w", pady=(0, 6))
        self.group_sw = {}
        for gkey, gname, _ in GROUPS:
            r = tk.Frame(self.group_box, bg=C["card"])
            r.pack(fill="x", pady=1)
            sw = Swatch(r, self._group_color(gkey), lambda k=gkey: self._pick_group(k), size=22)
            sw.pack(side="left")
            tk.Label(r, text=gname, bg=C["card"], fg=C["text"], font=F(9)).pack(side="left", padx=(8, 0))
            self.group_sw[gkey] = sw
        button(self.group_box, "Varsayılan renklere dön", self._reset_groups).pack(anchor="w", pady=(10, 0))
        tk.Label(opt, text="İpucu: kartın üzerindeki önizleme\nefektin klavyede nasıl görüneceğini gösterir.",
                 bg=C["card"], fg=C["faint"], font=F(8), justify="left").pack(anchor="w", side="bottom")
        self._select_effect(self.engine.get("base") if self.engine.get("base") in EFFECTS else "wave", apply=False)

    def _reflow_cards(self, width):
        card_w = int(WIDTH * EffectCard.S) + 8 + 16 + 4 + 12      # önizleme + iç boşluk + çerçeve + aralık
        cols = max(1, width // card_w)
        if cols == self._card_cols:
            return
        self._card_cols = cols
        inner = self.cards[ORDER[0]].master
        for c in range(8):
            inner.columnconfigure(c, weight=1 if c < cols else 0, uniform="cards" if c < cols else "")
        for i, key in enumerate(ORDER):
            self.cards[key].grid(row=i // cols, column=i % cols, padx=6, pady=6, sticky="nsew")

    def _select_effect(self, key, apply=True):
        if apply:
            self.engine.update(base=key)
        for k, cd in self.cards.items():
            cd.select(k == key)
        name, _, reactive = EFFECTS[key]
        self.e_title.configure(text=name)
        self.e_desc.configure(text=DESC.get(key, ""))
        self.e_tag.configure(text="⌨  Tuşlara basınca çalışır" if reactive else "")
        show, hide = (self.group_box, self.std_box) if key == "groups" else (self.std_box, self.group_box)
        hide.pack_forget()
        show.pack(fill="x")

    def _group_color(self, gkey):
        return self.engine.get("group_colors").get(gkey, GROUP_DEFAULTS[gkey])

    def _pick_group(self, gkey):
        rgb, _ = colorchooser.askcolor(color=hexcol(self._group_color(gkey)), parent=self)
        if rgb:
            gc = dict(self.engine.get("group_colors"))
            gc[gkey] = [int(x) for x in rgb]
            self.engine.update(group_colors=gc)
            self.group_sw[gkey].set(gc[gkey])

    def _reset_groups(self):
        self.engine.update(group_colors={})
        for gkey, sw in self.group_sw.items():
            sw.set(GROUP_DEFAULTS[gkey])

    def _set_color_mode(self, v):
        self.engine.update(colorful=(v == "rainbow"))

    def _pick(self, setting, swatch):
        rgb, _ = colorchooser.askcolor(color=hexcol(self.engine.get(setting)), parent=self)
        if rgb:
            c = [int(x) for x in rgb]
            self.engine.update(**{setting: c})
            swatch.set(c)

    def _thumb_tick(self):
        if self.page == "effects" and self.state() != "withdrawn":
            now = time.perf_counter()
            t = now - self._thumb_t0
            if t >= self._synth_next:                  # önizleme için sahte tuş basışları
                pos = random.choice(RECTS)
                self._synth.append(((pos[1], pos[2]), t))
                self._synth = [s for s in self._synth if t - s[1] < 3.0]
                self._synth_next = t + 0.45
            s = self.engine.settings
            for key, cd in self.cards.items():
                ctx = self._thumb_ctx[key]
                ctx.t, ctx.speed = t, s["speed"]
                ctx.color, ctx.colorful, ctx.bg = tuple(s["base_color"]), bool(s["colorful"]), tuple(s["bg_color"])
                ctx.presses = self._synth
                ctx.groups = s["group_colors"]
                f = [[ctx.bg] * 21 for _ in range(6)]
                EFFECTS[key][1](ctx, f)
                cd.show(f)
        self.after(160, self._thumb_tick)

    # ---------------------------------------------------------- Tuş boyama
    def _page_paint(self, p):
        cd = card(p, "Tuş boyama", "Önizlemedeki tuşlara tıklayın ya da sürükleyin. Sağ tık siler. "
                                   "Boyanan tuşlar seçili efektin üstünde sabit renkte kalır.")
        cd.pack(fill="x")
        tk.Label(cd, text="Fırça rengi", bg=C["card"], fg=C["text"], font=F(10, "bold")).pack(anchor="w", pady=(4, 4))
        pal = tk.Frame(cd, bg=C["card"])
        pal.pack(anchor="w")
        self.pal_sw = []
        for col in PALETTE:
            sw = Swatch(pal, col, lambda c=col: self._set_brush(list(c)))
            sw.pack(side="left", padx=2)
            self.pal_sw.append(sw)
        self.sw_custom = Swatch(pal, (60, 60, 70), self._custom_brush, plus=True)
        self.sw_custom.pack(side="left", padx=(10, 2))

        row = tk.Frame(cd, bg=C["card"])
        row.pack(anchor="w", pady=(14, 0))
        self.seg_tool = Segmented(row, [("brush", "✎  Fırça"), ("eraser", "⌫  Silgi")], "brush",
                                  lambda v: setattr(self, "tool", v))
        self.seg_tool.pack(side="left")
        button(row, "Tümünü boya", self._paint_all).pack(side="left", padx=(16, 6))
        button(row, "Boyamaları temizle", self._clear_paint, kind="danger").pack(side="left")
        self.paint_count = tk.Label(cd, text="", bg=C["card"], fg=C["muted"], font=F(9))
        self.paint_count.pack(anchor="w", pady=(10, 0))
        self._set_brush(self.brush)

    def _set_brush(self, c):
        self.brush = list(c)
        for sw in self.pal_sw:
            sw.set(selected=list(sw.color) == self.brush)
        self.sw_custom.set(selected=all(list(sw.color) != self.brush for sw in self.pal_sw))
        self.seg_tool.set("brush")
        self.tool = "brush"

    def _custom_brush(self):
        rgb, _ = colorchooser.askcolor(color=hexcol(self.brush), parent=self)
        if rgb:
            c = [int(x) for x in rgb]
            self.sw_custom.set(color=c)
            self._set_brush(c)

    def _paint_key(self, name, erase):
        if self.page != "paint":
            self.hint.configure(text="Tuşları boyamak için soldan  ✎ Tuş boyama  sayfasını açın.", fg=C["warn"])
            return
        sk = dict(self.engine.get("static_keys"))
        if erase or self.tool == "eraser":
            if name not in sk:
                return
            sk.pop(name, None)
        else:
            if sk.get(name) == self.brush:
                return
            sk[name] = list(self.brush)
        self.engine.update(static_keys=sk)
        self._update_paint_count()

    def _paint_all(self):
        self.engine.update(static_keys={name: list(self.brush) for name, *_ in RECTS})
        self._update_paint_count()

    def _clear_paint(self):
        self.engine.update(static_keys={})
        self._update_paint_count()

    def _update_paint_count(self):
        n = len(self.engine.get("static_keys"))
        self.paint_count.configure(text="%d tuş boyalı" % n if n else "Boyalı tuş yok")

    # ---------------------------------------------------------- Katmanlar
    def _page_layers(self, p):
        def layer(title, sub, key):
            cd = card(p)
            cd.pack(fill="x", pady=(0, 10))
            head = tk.Frame(cd, bg=C["card"])
            head.pack(fill="x")
            txt = tk.Frame(head, bg=C["card"])
            txt.pack(side="left", fill="x", expand=True)
            tk.Label(txt, text=title, bg=C["card"], fg=C["text"], font=F(11, "bold")).pack(anchor="w")
            tk.Label(txt, text=sub, bg=C["card"], fg=C["muted"], font=F(9)).pack(anchor="w")
            tg = Toggle(head, self.engine.get(key), lambda v: self.engine.update(**{key: v}))
            tg.pack(side="right")
            return cd, tg

        cd, self.t_react = layer("Tuşa basınca parla", "Seçili efektin üstünde, bastığınız tuş ve çevresi parlar.", "reactive")
        row = tk.Frame(cd, bg=C["card"])
        row.pack(anchor="w", pady=(10, 0))
        tk.Label(row, text="Renk", bg=C["card"], fg=C["muted"], font=F(9)).grid(row=0, column=0, sticky="w")
        self.sw_react = Swatch(row, self.engine.get("reactive_color"), lambda: self._pick("reactive_color", self.sw_react))
        self.sw_react.grid(row=0, column=1, padx=(8, 24))
        tk.Label(row, text="Süre", bg=C["card"], fg=C["muted"], font=F(9)).grid(row=0, column=2)
        self.s_decay = Slider(row, 0.1, 2.0, self.engine.get("reactive_decay"),
                              lambda v: self.engine.update(reactive_decay=v), fmt=lambda v: "%.1f s" % v, width=200)
        self.s_decay.grid(row=0, column=3, padx=(8, 24))
        tk.Label(row, text="Yayılım", bg=C["card"], fg=C["muted"], font=F(9)).grid(row=0, column=4)
        self.s_spread = Slider(row, 0.0, 4.0, self.engine.get("reactive_spread"),
                               lambda v: self.engine.update(reactive_spread=v), fmt=lambda v: "%.1f tuş" % v, width=200)
        self.s_spread.grid(row=0, column=5, padx=(8, 0))

        _, self.t_cpu = layer("CPU yükü göstergesi", "1…0 sırası, işlemci yüküne göre yeşilden kırmızıya dolar.", "cpu")
        _, self.t_locks = layer("Caps / Num Lock göstergesi", "Açıkken Caps ve Num tuşları beyaz yanar.", "locks")

    # ---------------------------------------------------------- Profiller
    def _page_profiles(self, p):
        cd = card(p, "Profiller", "Efekt, renkler, boyamalar ve katmanlar birlikte kaydedilir. "
                                  "Son ayarlarınız ayrıca otomatik olarak saklanır.")
        cd.pack(fill="both", expand=True)
        body = tk.Frame(cd, bg=C["card"])
        body.pack(fill="both", expand=True)
        self.lst = tk.Listbox(body, bg=C["panel"], fg=C["text"], selectbackground=C["accent"], selectforeground="white",
                              highlightthickness=0, borderwidth=0, font=F(10), activestyle="none", height=8)
        self.lst.pack(side="left", fill="both", expand=True)
        self.lst.bind("<Double-Button-1>", lambda e: self._load_profile())
        btns = tk.Frame(body, bg=C["card"], padx=14)
        btns.pack(side="left", fill="y")
        button(btns, "Yükle", self._load_profile, kind="primary").pack(fill="x", pady=(0, 6))
        button(btns, "Yeni profil olarak kaydet", self._save_profile).pack(fill="x", pady=(0, 6))
        button(btns, "Seçiliyi güncelle", self._overwrite_profile).pack(fill="x", pady=(0, 6))
        button(btns, "Sil", self._delete_profile, kind="danger").pack(fill="x")

    def _profile_files(self):
        os.makedirs(PROFILE_DIR, exist_ok=True)
        return sorted(f[:-5] for f in os.listdir(PROFILE_DIR) if f.endswith(".json") and not f.startswith("_"))

    def _refresh_profiles(self):
        self.lst.delete(0, "end")
        for n in self._profile_files():
            self.lst.insert("end", "  " + n)
        if not self.lst.size():
            self.lst.insert("end", "  (henüz kayıtlı profil yok)")

    def _selected_profile(self):
        sel = self.lst.curselection()
        if not sel:
            return None
        name = self.lst.get(sel[0]).strip()
        return name if name in self._profile_files() else None

    def _save_profile(self):
        name = simpledialog.askstring("Profil", "Profil adı:", parent=self)
        if not name:
            return
        name = "".join(ch for ch in name if ch not in '\\/:*?"<>|').strip()
        if name:
            self.engine.save(os.path.join(PROFILE_DIR, name + ".json"))
            self._refresh_profiles()

    def _overwrite_profile(self):
        n = self._selected_profile()
        if n:
            self.engine.save(os.path.join(PROFILE_DIR, n + ".json"))

    def _load_profile(self):
        n = self._selected_profile()
        if not n:
            return
        try:
            self.engine.load(os.path.join(PROFILE_DIR, n + ".json"))
        except Exception as e:
            messagebox.showerror("Profil", str(e), parent=self)
            return
        self._sync_all()

    def _delete_profile(self):
        n = self._selected_profile()
        if n and messagebox.askyesno("Profil", "'%s' silinsin mi?" % n, parent=self):
            os.remove(os.path.join(PROFILE_DIR, n + ".json"))
            self._refresh_profiles()

    # ---------------------------------------------------------- Ayarlar
    def _page_settings(self, p):
        cd = card(p)
        cd.pack(fill="x", pady=(0, 10))
        head = tk.Frame(cd, bg=C["card"])
        head.pack(fill="x")
        tk.Label(head, text="Windows açılışında başlat", bg=C["card"], fg=C["text"], font=F(11, "bold")).pack(side="left")
        self.t_auto = Toggle(head, autostart_enabled(), self._toggle_autostart)
        self.t_auto.pack(side="right")
        tk.Label(cd, text="Oturum açılınca tepside, pencere açmadan başlar ve son ayarlarınızla devam eder.",
                 bg=C["card"], fg=C["muted"], font=F(9)).pack(anchor="w")

        cd = card(p, "Çıkışta klavye", "Uygulamadan tamamen çıkınca klavyede kalacak görüntü. "
                                       "Klavyenin kendi efektlerine Fn ile ya da kabloyu çıkarıp takarak dönersiniz.")
        cd.pack(fill="x", pady=(0, 10))
        row = tk.Frame(cd, bg=C["card"])
        row.pack(anchor="w")
        self.seg_exit = Segmented(row, [("keep", "Son karede kalsın"), ("off", "Sönsün"), ("color", "Sabit renk")],
                                  self.engine.get("on_exit"), lambda v: self.engine.update(on_exit=v))
        self.seg_exit.pack(side="left")
        self.sw_exit = Swatch(row, self.engine.get("exit_color"), lambda: self._pick("exit_color", self.sw_exit))
        self.sw_exit.pack(side="left", padx=12)

        cd = card(p, "Performans", "Saniyedeki kare sayısı. Yüksek değer daha akıcıdır, USB trafiği biraz artar.")
        cd.pack(fill="x", pady=(0, 10))
        self.s_fps = Slider(cd, 10, 60, self.engine.get("fps"), lambda v: self.engine.update(fps=int(round(v))),
                            fmt=lambda v: "%d fps" % round(v), width=320)
        self.s_fps.pack(anchor="w")

        bottom = tk.Frame(p, bg=C["bg"])
        bottom.pack(fill="x", pady=(4, 0))
        tk.Label(bottom, text="258A:0049 · SH68F90 · canlı efektler report 8 ile yalnızca RAM'e gönderilir",
                 bg=C["bg"], fg=C["faint"], font=F(8)).pack(side="left")
        button(bottom, "Uygulamadan çık", self._quit, kind="danger").pack(side="right")

    def _toggle_autostart(self, v):
        try:
            set_autostart(v)
        except OSError as e:
            messagebox.showerror("Otomatik başlatma", str(e), parent=self)
            self.t_auto.set(autostart_enabled())

    # ---------------------------------------------------------- senkron / döngüler
    def _sync_all(self):
        g = self.engine.get
        self._select_effect(g("base") if g("base") in EFFECTS else "wave", apply=False)
        self.seg_color.set("rainbow" if g("colorful") else "mono")
        self.sw_base.set(g("base_color"))
        self.sw_bg.set(g("bg_color"))
        self.s_speed.set(g("speed"))
        self.s_bright.set(g("brightness"))
        self.t_react.set(g("reactive"))
        self.sw_react.set(g("reactive_color"))
        self.s_decay.set(g("reactive_decay"))
        self.s_spread.set(g("reactive_spread"))
        self.t_cpu.set(g("cpu"))
        self.t_locks.set(g("locks"))
        self.seg_exit.set(g("on_exit"))
        self.sw_exit.set(g("exit_color"))
        self.s_fps.set(g("fps"))
        for gkey, sw in self.group_sw.items():
            sw.set(self._group_color(gkey))
        self._update_paint_count()

    def _hover_key(self, name):
        self._update_hint(name)

    def _update_hint(self, name):
        if self.page == "paint":
            txt = "✎  %s — sol tık boya, sağ tık sil" % name if name else "✎  Tuşlara tıklayın veya sürükleyin · sağ tık siler"
        else:
            txt = "Tuş: %s" % name if name else "Canlı önizleme · klavyede gördüğünüzün aynısı"
        self.hint.configure(text=txt, fg=C["muted"])

    def _toggle_run(self):
        if self.engine.running:
            self.engine.stop()
        else:
            self.engine.start()

    def _settings_json(self):
        with self.engine.lock:
            return json.dumps(self.engine.settings, sort_keys=True)

    def _autosave(self, force=False):
        cur = self._settings_json()
        if force or cur != self._saved_json:
            try:
                os.makedirs(PROFILE_DIR, exist_ok=True)
                self.engine.save(LAST_PROFILE)
                self._saved_json = cur
            except OSError:
                pass
        if not force:
            self.after(2000, self._autosave)

    def _tick(self):
        while not self.tray.events.empty():
            ev = self.tray.events.get_nowait()
            if ev == "show":
                self.deiconify()
                self.lift()
                self.focus_force()
            elif ev == "quit":
                self._quit()
                return
        if self.state() != "withdrawn":
            with self.engine.lock:
                frame = self.engine.frame
            self.kb.show(frame)
            st = self.engine.status
            if not self.engine.running:
                self.status.configure(text="❚❚  Duraklatıldı", fg=C["warn"])
                self.btn_run.configure(text="▶  Devam et")
            elif st.startswith("bağlantı yok"):
                self.status.configure(text="●  Klavye bulunamadı — takılı mı?", fg=C["err"])
                self.btn_run.configure(text="❚❚  Duraklat")
            else:
                self.status.configure(text="●  Bağlı", fg=C["ok"])
                self.btn_run.configure(text="❚❚  Duraklat")
        self.after(50, self._tick)

    def _hide(self):
        self.withdraw()
        if not self._hint_shown:
            self.tray.balloon("K78 arka planda çalışıyor",
                              "Efektler devam ediyor. Simgeye çift tıklayınca pencere açılır; sağ tık > Çıkış.")
            self._hint_shown = True

    def _quit(self):
        self._autosave(force=True)
        self.engine.shutdown()
        self.tray.stop()
        self.destroy()


if __name__ == "__main__":
    App(start_hidden="--tray" in sys.argv).mainloop()
