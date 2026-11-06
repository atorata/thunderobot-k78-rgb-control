# Thunderobot K78 HID protokolü

Stok firmware'in (SH68F90, `258A:0049`) disassembly'sinden ve cihaz üzerinde yalnızca-okuma/RAM testlerinden çıkarılmıştır.
Adresler stok firmware'deki CODE / XRAM adresleridir.

## HID arayüzleri

Arayüz 1 (MI_01) altında vendor sayfası `0xFF00` olan üç feature raporu:

| Report ID | Uzunluk (ID dahil) | Windows koleksiyonu | Görev |
|---|---|---|---|
| 5 | 6 | COL05 | Komut kanalı |
| 6 | 1032 | COL06 | 8 bayt başlık + 1024 bayt veri |
| 8 | 382 | COL08 | Canlı per-key RGB (yalnızca RAM) |

USB istek işleyicileri: Keil generic pointer tablosu CODE `0x63AA` (21 × `FF hh ll`), dağıtım tablosu `0x63E9`
(`[bmRequestType, bRequest, indeks]`). GET_REPORT `0x26B5`, SET_REPORT setup `0x877E`, veri aşaması `0x0200`.

## Report 5 — komut

`SET_FEATURE [05, cmd, b2, b3, 00, 00]`

| cmd | Etki |
|---|---|
| `0x75` | **ISP bootloader'a atlar** (`EA=0; B=A5; A=5A; LJMP FF00`). Bu araçta engellidir. |
| `0xA5 xx` | Uygulama modu bayrağı açılır, `xx` → XRAM `0x08DE` |
| `0x5A` | Uygulama modu kapatılır |
| `0x83`–`0x89` | Sonraki `GET_FEATURE(6)` için okuma hazırlar (flash'a dokunmaz) |

`GET_FEATURE(5)` → `05 01 02 00 00 00` (CODE `0x639F…` sabitleri).

## Report 6 — veri bloğu

- `SET_FEATURE` komut `3..9`: başlıktaki `b2:b3` adresinde **flash sektörü silinir ve yazılır** (anahtar dizisi
  `IB_CON2..5 = E6/05/0A/09/06`). Komut 4–9 (`0x905B`) adres için aralık kontrolü yapmaz — yanlış adres kodu silebilir.
  Komut 3 (`0xA031`) profil sektörünü yazar ve `0xFE..0x1F9` aralığını fabrika tablolarından (`0xB4FE`, `0xB57C`) doldurur.
- `GET_FEATURE` (`05 83 B6 00` sonrası): başlık yankısı + aktif profilin RAM kopyası, `0xFE` bayt.

### Profil (`0xB600`, fabrika kopyası `0xB400`)

| Ofset | Anlam |
|---|---|
| `0x06..0x09` | Magic `5A A5 03 03` |
| `0x0D` | Açılışta yüklenen stok efekt (1..20) |
| `0x1C + 2·mod` | `[renk indeksi 0..7 (7 = gökkuşağı), hız<<4 | parlaklık]` — parlaklık Fn ile doğrulandı |

Firmware Fn ile yapılan değişiklikleri hemen kaydetmez; RAM kopyası flash'tan farklı olabilir.

## Report 8 — canlı per-key RGB (RAM)

`SET_FEATURE [08, x, x, x] + 378 bayt` → XRAM `0x01AC`. Setup aşaması aktif modu (`0x0192`) `0x15`'e çeker.

Render fonksiyonu (`0x8EB0`) tamponu şöyle okur:

```
adres = 0x01AC + sütun*18 + satır*3 + kanal     (21 sütun × 6 satır, kanal: R, G, B)
PWM   = 0x0567 + sütun*42 + satır*6
```

Mod `0x15` işleyicisi (`0x0E95`) yeni kare bayrağı (bit `54h`) set olunca çizer. Mod değişiminde efekt
yeniden başlatıldığı için ilk kare kaybolabilir; ikinci kareden itibaren görünür.

Aktif mod `0x0192` yalnızca açılışta (`main 0x8528 → 0x91C6`), Fn ile (`0x8DC7`) ve uyku modlarında (`0x20..0x26`)
değişir — host'tan stok efekte dönüş komutu bulunmadı.

## K78 LED haritası

Satır 0 ve sütun 17–20 kullanılmaz. `·` = LED yok.

```
     0      1    2    3    4    5     6   7   8    9   10    11  12     13    14    15   16
r1   Esc    1    2    3    4    5     6   7   8    9   0     -   =      Bksp  NumLk KP+  KP-
r2   Tab    Q    W    E    R    T     Y   U   I    O   P     [   ]      \     KP7   KP8  KP9
r3   Caps   A    S    D    F    G     H   J   K    L   ;     '   ·      Enter KP4   KP5  KP6
r4   LShift Z    X    C    V    B     N   M   ,    .   /     ·   RShift Up    KP1   KP2  KP3
r5   LCtrl  Win  LAlt ·    ·    Space ·   ·   RAlt Fn  RCtrl ·   Left   Down  Right KP0  KP.
```
