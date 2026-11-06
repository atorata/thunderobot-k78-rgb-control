"""
assets/k78.ico üretir: koyu yuvarlak zemin üzerinde gökkuşağı renkli tuşlar.
Yalnızca standart kütüphane (zlib ile PNG, PNG gömülü ICO). Kullanım: python tools/make_icon.py
"""
import colorsys
import os
import struct
import zlib

SIZES = [16, 24, 32, 48, 64, 128, 256]
SS = 3          # kenar yumuşatma için piksel başına SS x SS örnek


def rrect(px, py, x0, y0, x1, y1, r):
    """Yuvarlatılmış dikdörtgenin içinde mi?"""
    cx, cy = min(max(px, x0 + r), x1 - r), min(max(py, y0 + r), y1 - r)
    return (px - cx) ** 2 + (py - cy) ** 2 <= r * r and x0 <= px <= x1 and y0 <= py <= y1


def shapes():
    out = [((0.04, 0.04, 0.96, 0.96, 0.22), (21, 24, 32))]                  # zemin
    out.append(((0.10, 0.25, 0.90, 0.75, 0.08), (12, 14, 19)))              # klavye gövdesi
    rows, cols = 3, 4
    gx0, gy0, gx1, gy1, gap = 0.15, 0.30, 0.85, 0.70, 0.035
    kw = (gx1 - gx0 - gap * (cols - 1)) / cols
    kh = (gy1 - gy0 - gap * (rows - 1)) / rows
    for r in range(rows):
        for c in range(cols):
            h = (c / cols * 0.75 + r * 0.08) % 1.0
            rgb = tuple(int(v * 255) for v in colorsys.hsv_to_rgb(h, 0.85, 1.0))
            x0, y0 = gx0 + c * (kw + gap), gy0 + r * (kh + gap)
            out.append(((x0, y0, x0 + kw, y0 + kh, 0.03), rgb))
    return out


def render(n):
    sh = shapes()
    rows = []
    for y in range(n):
        row = bytearray([0])                                   # PNG satır filtresi: yok
        for x in range(n):
            acc = [0, 0, 0, 0]
            for sy in range(SS):
                for sx in range(SS):
                    px, py = (x + (sx + 0.5) / SS) / n, (y + (sy + 0.5) / SS) / n
                    col = None
                    for (x0, y0, x1, y1, r), rgb in sh:
                        if rrect(px, py, x0, y0, x1, y1, r):
                            col = rgb
                    if col:
                        acc[0] += col[0]; acc[1] += col[1]; acc[2] += col[2]; acc[3] += 255
            k = SS * SS
            a = acc[3] // k
            if a:
                row += bytes((acc[0] * 255 // acc[3], acc[1] * 255 // acc[3], acc[2] * 255 // acc[3], a))
            else:
                row += b"\0\0\0\0"
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "assets", "k78.ico")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    pngs = [render(n) for n in SIZES]
    header = struct.pack("<HHH", 0, 1, len(SIZES))
    offset = 6 + 16 * len(SIZES)
    entries, blobs = b"", b""
    for n, png in zip(SIZES, pngs):
        entries += struct.pack("<BBBBHHII", n % 256, n % 256, 0, 0, 1, 32, len(png), offset + len(blobs))
        blobs += png
    with open(out, "wb") as f:
        f.write(header + entries + blobs)
    with open(os.path.join(root, "assets", "k78_256.png"), "wb") as f:
        f.write(pngs[-1])
    print("yazıldı:", out, "(%d bayt)" % (6 + len(entries) + len(blobs)))


if __name__ == "__main__":
    main()
