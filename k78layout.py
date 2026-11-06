"""
k78layout - K78 tuşlarının fiziksel yerleşimi (birim = 1 standart tuş genişliği).

Arayüz (çizim) ve efekt motoru (geometrik efektler) aynı koordinatları kullanır.
"""
from k78ctl import _K78_ROWS

# Görsel genişlikler (birim); konum soldan kümülatif hesaplanır
WIDE = {"BKSP": 1.6, "TAB": 1.4, "\\": 1.2, "CAPS": 1.7, "ENTER": 2.0, "LSHIFT": 2.1, "RSHIFT": 1.4,
        "LCTRL": 1.3, "WIN": 1.2, "LALT": 1.3, "SPACE": 5.6, "RALT": 1.1, "FN": 1.1, "RCTRL": 1.1}
GAP_BEFORE = {"NUMLK": 0.4, "KP7": 0.4, "KP4": 0.4, "KP1": 0.25, "KP0": 0.25, "UP": 0.25, "LEFT": 0.25}


def key_rects():
    """[(ad, satır, sütun, x, genişlik)]  — y = satır - 1"""
    out = []
    for r in range(1, 6):
        x = 0.0
        for c, name in enumerate(_K78_ROWS[r]):
            if not name:
                continue
            key = name.upper()
            x += GAP_BEFORE.get(key, 0)
            w = WIDE.get(key, 1.0)
            out.append((key, r, c, x, w))
            x += w
    return out


RECTS = key_rects()
# (satır, sütun) -> (x merkez, y merkez)
CENTERS = {(r, c): (x + w / 2.0, (r - 1) + 0.5) for _, r, c, x, w in RECTS}
WIDTH = max(x + w for _, _, _, x, w in RECTS)
HEIGHT = 5.0
CX, CY = WIDTH / 2.0, HEIGHT / 2.0
# Yılan efekti için yılan yolu: satırlar sırayla, bir soldan sağa bir sağdan sola
SNAKE_PATH = []
for _r in range(1, 6):
    _row = sorted([(x, (r, c)) for _, r, c, x, _ in RECTS if r == _r])
    if _r % 2 == 0:
        _row.reverse()
    SNAKE_PATH.extend(p for _, p in _row)
