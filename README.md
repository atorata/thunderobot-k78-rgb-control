# Thunderobot K78 RGB Control

**Türkçe** · [English](README.en.md)

Thunderobot K78 (kablolu, SinoWealth SH68F90, USB `258A:0049`) klavyesi için açık kaynak RGB kontrol uygulaması.
Üretici yazılımına gerek kalmadan, **flash'a yazmadan** tuş başına canlı RGB efektleri.

## Özellikler

- **23 efekt:** tuş grupları (harfler, rakamlar, kontrol tuşları, ok tuşları, numpad… ayrı renklerde), gökkuşağı dalgası, çark, neon, sinüs, tarayıcı, yel değirmeni, fırtına, şelale, yağmur, yıldızlar, çiçeklenme, yılan…
  ve tuşa basınca çalışanlar: tepki, patlama, dalgalanma, gölge, çarpışma. Her biri gökkuşağı ya da tek renk.
- **Tuş boyama:** önizlemede tuşlara tıklayıp/sürükleyip renk verin; boyamalar efektin üstünde kalır.
- **Katmanlar:** tuşa basınca parlama, CPU yükü göstergesi (1…0 sırası), Caps/Num Lock göstergesi.
- **Profiller**, sistem tepsisinde çalışma, Windows açılışında başlatma, çıkışta klavyenin ne göstereceği.
- **Komut satırı aracı** (`k78ctl.py`): renk/tuş/pixel komutları, protokol okumaları, korumalı kalıcı profil yazma.

## Flash'a yazmadan kullanın — flash aşınması hakkında

Bu uygulama efektleri **yalnızca klavyenin RAM'ine** gönderir (report 8). Klavyenin flash belleğine dokunmaz ve
bunun bilinçli bir nedeni var:

- **Flash belleğin ömrü sınırlıdır.** Her yazma, bir sektörün önce silinip sonra yeniden yazılması demektir
  (K78'de profil sektörü 512 bayt). Flash hücreleri belirli sayıda silme döngüsünden sonra yıpranır; bu sınır
  mikrodenetleyiciye göre değişir ve genelde on binler mertebesindedir. SH68F90 için kesin değeri doğrulamadık.
- **Animasyonu flash üzerinden sürmek klavyeyi hızla yıpratır.** Bazı araçlar "direct" modda her karede flash'a
  yazan bir komut kullanır (OpenRGB'nin devre dışı bırakılmış SinoWealth sürücüsü `06 09 BC…` gibi). Örneğin
  dayanıklılık 10.000 döngü olsaydı, saniyede 30 kare ile bu sınıra **yaklaşık 6 dakikada** ulaşılırdı.
- **Yıpranan sektör ayarları bozar.** Profil sektörü bozulursa klavye açılışta ayarlarını yükleyemez ya da
  tutarsız davranır. Bir sektörün yanlış adrese yazılması ise firmware'in kendisini silebilir.

Bu yüzden:

- Canlı efektler, tuş boyama ve katmanlar için hiçbir zaman flash'a yazılmaz; istediğiniz kadar kullanabilirsiniz.
- `k78ctl.py persist` yalnızca klavyenin **kendi** efekt ayarlarını kalıcı yapmak için vardır ve her çalıştırma
  bir sektör silme demektir. Gerçekten gerektiğinde, elle kullanın; script'lerde veya döngülerde **kullanmayın**.
- Klavyenin kendi Fn ayarlarını da firmware flash'a kaydeder; sık sık değiştirmeye gerek yoksa bırakın.

## Gereksinimler

- Windows 10/11
- Python 3.10+ (yalnızca standart kütüphane; tkinter dahil)
- Thunderobot K78, VID/PID `258A:0049`. Aynı VID/PID başka klavyelerde de kullanılıyor — aşağıdaki uyarıya bakın.

## Kurulum (Windows)

`K78RGB-Setup-1.0.0.exe` kurulum programı:

- Yönetici izni istemez; kullanıcının kendi `Programs` klasörüne kurulur. Python gerekmez.
- Başlat menüsü kısayolu; isteğe bağlı masaüstü kısayolu ve "Windows açılışında başlat".
- Ayarlar `%APPDATA%\K78RGB` altında tutulur ve kaldırırken silinmez.
- Program dijital imzalı değildir; Windows SmartScreen "tanınmayan uygulama" uyarısı gösterebilir
  (**Ek bilgi → Yine de çalıştır**).

Kurulum programını kendiniz derlemek için Python 3.10+ ve [Inno Setup](https://jrsoftware.org/isinfo.php) gerekir:

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1   # dist\K78RGB\ ve release\K78RGB-Setup-1.0.0.exe
```

## Kullanım

```powershell
python k78gui.py            # arayüz
python k78gui.py --tray     # tepside gizli başlat

python k78ctl.py list       # HID koleksiyonlarını listele (hiçbir şey göndermez)
python k78ctl.py fill ff0000
python k78ctl.py key --bg 000000 W ffffff A ffffff S ffffff D ffffff
python k78ctl.py wave --seconds 10
python k78ctl.py map        # tuş -> LED haritası
python k78engine.py --base ripples   # arayüzsüz efekt motoru
```

Uygulama kapatılınca klavye son karede kalır (ya da Ayarlar'da seçtiğiniz görüntüde). Klavyenin kendi
efektlerine **Fn** ile ya da kabloyu çıkarıp takarak dönersiniz — firmware'de bunu USB'den yapan bir komut yok.

## ⚠️ Güvenlik

- **Canlı efektler güvenlidir:** report 8 yalnızca klavyenin RAM'indeki renk tamponuna yazar; flash'a dokunmaz.
- **`k78ctl.py persist` flash'a yazar.** Varsayılan olarak yalnızca önizleme yapar; gerçek yazma için
  `--base flash|ram --write --confirm YAZ` gerekir. Komut ve adres kodda sabittir (yalnızca profil sektörü `0xB600`).
- Kodda **ISP komutu (`05 75`) engellidir** ve report 6 ile serbest flash yazma yoktur.
- **Başka bir klavyede denemeyin.** `258A:0049`, SinoWealth referans tasarımından gelen ortak bir ID'dir;
  OpenRGB bu ID için sürücüsünü, aynı ID'yi kullanan Redragon klavyeleri bozduğu için devre dışı bırakmıştır.
  Bu araç K78'in firmware'ine göre yazılmıştır.
- Değişiklik yapmadan önce firmware'inizin tam yedeğini alın (ör. [sinowisp](https://github.com/karstx/sinowisp)).
- Yazılım "olduğu gibi" sağlanır; donanımınızdaki sorumluluk size aittir.

## Dosyalar

| Dosya | Görev |
|---|---|
| `k78ctl.py` | HID katmanı (Windows `hid.dll`, ctypes), protokol, CLI, LED haritası |
| `k78engine.py` | 30 fps efekt motoru (katmanlar, tuş yoklama, CPU) |
| `k78effects.py` | Efekt kütüphanesi |
| `k78layout.py` | Fiziksel tuş yerleşimi |
| `k78gui.py` | tkinter arayüzü |
| `k78tray.py` | Bağımlılıksız sistem tepsisi simgesi |
| `ghidra/scripts/` | Firmware analizi için Ghidra script'leri (firmware dahil değildir) |
| `docs/PROTOCOL.md` | Tersine mühendislikle çıkarılan HID protokolü |

## Teşekkür

- [OpenRGB](https://gitlab.com/CalcProgrammer1/OpenRGB) — SinoWealth klavye protokolünün ilk belgelenmesi
- [sinowisp / sinowealth-kb-tool](https://github.com/karstx/sinowisp) ve [SMK](https://github.com/karstx/smk) — SinoWealth ISP ve platform bilgisi
- [Ghidra](https://github.com/NationalSecurityAgency/ghidra)

Thunderobot ile bağlantılı değildir. Thunderobot, sahibinin ticari markasıdır.

## Lisans

[MIT](LICENSE)
