"""
k78ctl - Thunderobot K78 (SinoWealth 258A:0049) kontrol aracı.

FAZ 1: SADECE OKUMA. Bu dosyada flash'a yazan hiçbir fonksiyon yoktur.

Protokol (stok firmware disassembly'sinden, k78_full_1.bin):
  Report 5 (feature, 6 bayt)   : komut kanalı  [05, cmd, addrHi, addrLo, 0, 0]
      0x75        -> LJMP FF00 = ISP/bootloader moduna geçiş   (YASAK)
      0xA5 / 0x5A -> uygulama-kontrol modu aç / kapat           (henüz kullanılmıyor)
      0x83..0x89  -> sonraki GET_REPORT(6) için okuma hazırla   (GÜVENLİ, flash'a dokunmaz)
  Report 6 (feature, 1032 bayt): veri bloğu
      SET (cmd 3..9) -> başlıktaki adreste flash SEKTÖR SİLME + YAZMA (YASAK, bu fazda yok)
      GET            -> 0x83..0x89 ile hazırlanan veriyi döndürür
  Report 8 (feature, 382 bayt) : RAM'e canlı veri (muhtemelen tuş başına RGB) (henüz yok)

Bağımlılık yok: Windows hid.dll / setupapi.dll ctypes ile kullanılır.
"""
import argparse
import os
import ctypes
import ctypes.wintypes as W
import sys

VID, PID = 0x258A, 0x0049

# Report 5 için izin verilen komutlar: yalnızca okuma hazırlığı.
SAFE_READ_CMDS = set(range(0x83, 0x8A))
FORBIDDEN_CMDS = {0x75: "ISP moduna geçiş (LJMP FF00)"}

# Feature report uzunlukları (report ID baytı dahil) -> hangi koleksiyon
LEN_CMD, LEN_DATA, LEN_LIVE = 6, 1032, 382

# ---------------------------------------------------------------- Win32 / HID
setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class GUID(ctypes.Structure):
    _fields_ = [("Data1", W.DWORD), ("Data2", W.WORD), ("Data3", W.WORD), ("Data4", ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("InterfaceClassGuid", GUID), ("Flags", W.DWORD), ("Reserved", ctypes.c_void_p)]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Size", W.ULONG), ("VendorID", W.USHORT), ("ProductID", W.USHORT), ("VersionNumber", W.USHORT)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [("Usage", W.USHORT), ("UsagePage", W.USHORT),
                ("InputReportByteLength", W.USHORT), ("OutputReportByteLength", W.USHORT),
                ("FeatureReportByteLength", W.USHORT), ("Reserved", W.USHORT * 17),
                ("Counts", W.USHORT * 10)]


INVALID_HANDLE = ctypes.c_void_p(-1).value
GENERIC_READ, GENERIC_WRITE = 0x80000000, 0x40000000
FILE_SHARE_RW, OPEN_EXISTING = 0x3, 3
DIGCF_PRESENT_IFACE = 0x12

setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), W.LPCWSTR, W.HWND, W.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID), W.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD), ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
kernel32.CreateFileW.restype = ctypes.c_void_p
kernel32.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, ctypes.c_void_p, W.DWORD, W.DWORD, ctypes.c_void_p]
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
for fn in ("HidD_GetAttributes", "HidD_GetPreparsedData", "HidD_SetFeature", "HidD_GetFeature"):
    getattr(hid, fn).restype = W.BOOLEAN
hid.HidD_GetAttributes.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetPreparsedData.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidD_SetFeature.argtypes = [ctypes.c_void_p, ctypes.c_void_p, W.ULONG]
hid.HidD_GetFeature.argtypes = [ctypes.c_void_p, ctypes.c_void_p, W.ULONG]


def _open(path, rw=True):
    access = (GENERIC_READ | GENERIC_WRITE) if rw else 0
    h = kernel32.CreateFileW(path, access, FILE_SHARE_RW, None, OPEN_EXISTING, 0, None)
    return None if h in (None, INVALID_HANDLE) else h


def enumerate_collections():
    guid = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(guid))
    hdev = setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, DIGCF_PRESENT_IFACE)
    out = []
    try:
        i = 0
        while True:
            ifd = SP_DEVICE_INTERFACE_DATA(); ifd.cbSize = ctypes.sizeof(ifd)
            if not setupapi.SetupDiEnumDeviceInterfaces(hdev, None, ctypes.byref(guid), i, ctypes.byref(ifd)):
                break
            i += 1
            need = W.DWORD()
            setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(ifd), None, 0, ctypes.byref(need), None)
            buf = ctypes.create_string_buffer(need.value)
            ctypes.cast(buf, ctypes.POINTER(W.DWORD))[0] = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(ifd), buf, need, None, None):
                continue
            path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
            if "vid_258a&pid_0049" not in path.lower():
                continue
            h = _open(path, rw=False)
            if not h:
                continue
            try:
                attr = HIDD_ATTRIBUTES(); attr.Size = ctypes.sizeof(attr)
                hid.HidD_GetAttributes(h, ctypes.byref(attr))
                pp = ctypes.c_void_p(); caps = HIDP_CAPS()
                if hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
                    hid.HidP_GetCaps(pp, ctypes.byref(caps))
                    hid.HidD_FreePreparsedData(pp)
                out.append(dict(path=path, vid=attr.VendorID, pid=attr.ProductID, ver=attr.VersionNumber,
                                usage_page=caps.UsagePage, usage=caps.Usage,
                                in_len=caps.InputReportByteLength, out_len=caps.OutputReportByteLength,
                                feat_len=caps.FeatureReportByteLength))
            finally:
                kernel32.CloseHandle(h)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return out


class K78:
    def __init__(self):
        cols = enumerate_collections()
        self.cmd_path = next((c["path"] for c in cols if c["usage_page"] == 0xFF00 and c["feat_len"] == LEN_CMD), None)
        self.data_path = next((c["path"] for c in cols if c["usage_page"] == 0xFF00 and c["feat_len"] == LEN_DATA), None)
        if not self.cmd_path or not self.data_path:
            raise SystemExit("HATA: report 5 (6 bayt) veya report 6 (1032 bayt) koleksiyonu bulunamadı. 'list' çıktısına bakın.")
        self.h_cmd = _open(self.cmd_path)
        self.h_data = _open(self.data_path)
        if not self.h_cmd or not self.h_data:
            raise SystemExit("HATA: koleksiyon açılamadı (WinError %d)" % ctypes.get_last_error())

    def close(self):
        for h in (self.h_cmd, self.h_data):
            if h:
                kernel32.CloseHandle(h)

    def _send_cmd(self, cmd, b2=0, b3=0):
        if cmd in FORBIDDEN_CMDS:
            raise SystemExit("ENGELLENDİ: komut 0x%02X = %s" % (cmd, FORBIDDEN_CMDS[cmd]))
        if cmd not in SAFE_READ_CMDS:
            raise SystemExit("ENGELLENDİ: komut 0x%02X faz 1 beyaz listesinde değil" % cmd)
        pkt = (ctypes.c_ubyte * LEN_CMD)(0x05, cmd, b2 & 0xFF, b3 & 0xFF, 0, 0)
        if not hid.HidD_SetFeature(self.h_cmd, pkt, LEN_CMD):
            raise SystemExit("HATA: SET_FEATURE(5) başarısız (WinError %d)" % ctypes.get_last_error())

    def _get_data(self):
        buf = (ctypes.c_ubyte * LEN_DATA)(); buf[0] = 0x06
        if not hid.HidD_GetFeature(self.h_data, buf, LEN_DATA):
            raise SystemExit("HATA: GET_FEATURE(6) başarısız (WinError %d)" % ctypes.get_last_error())
        return bytes(buf)

    def read_raw(self, cmd, addr):
        self._send_cmd(cmd, addr >> 8, addr & 0xFF)
        return self._get_data()

    def get_info(self):
        """GET_FEATURE(5): firmware 05 01 + CODE 0x639F.. sabitlerini döndürür. Hiçbir şey göndermez."""
        buf = (ctypes.c_ubyte * LEN_CMD)(); buf[0] = 0x05
        if not hid.HidD_GetFeature(self.h_cmd, buf, LEN_CMD):
            raise SystemExit("HATA: GET_FEATURE(5) başarısız (WinError %d)" % ctypes.get_last_error())
        return bytes(buf)


# ---------------------------------------------------------------- canlı RGB (report 8, yalnızca RAM)
# hid_set_report_setup (0x877E): report 8 verisi sabit olarak XRAM 0x01AC'ye kopyalanır,
# aktif mod RAM'de 0x15'e (per-key) çekilir. Flash'a yazılmaz; Fn ile mod değişince
# ya da klavye yeniden takılınca stok efektlere dönülür.
# Tampon düzeni render fonksiyonundan (0x8EB0) alındı: 21 sütun x 6 satır, sütun öncelikli,
# her LED 3 bayt yan yana:  0x01AC + sütun*18 + satır*3 + kanal  ->  PWM 0x0567 + sütun*42 + satır*6.
ROWS, COLS = 6, 21
# Kanal sırası henüz doğrulanmadı; varsayım R, G, B.
CH_ORDER = ("r", "g", "b")


class LiveRGB:
    def __init__(self):
        cols = enumerate_collections()
        self.path = next((c["path"] for c in cols if c["usage_page"] == 0xFF00 and c["feat_len"] == LEN_LIVE), None)
        if not self.path:
            raise SystemExit("HATA: report 8 (382 bayt) koleksiyonu bulunamadı.")
        self.h = _open(self.path)
        if not self.h:
            raise SystemExit("HATA: report 8 koleksiyonu açılamadı (WinError %d)" % ctypes.get_last_error())

    def close(self):
        kernel32.CloseHandle(self.h)

    def send(self, frame):
        """frame: ROWS x COLS listesi, her hücre (r, g, b)."""
        pkt = (ctypes.c_ubyte * LEN_LIVE)()
        pkt[0] = 0x08                               # bayt 1..3: firmware tarafından yok sayılıyor
        for row in range(ROWS):
            for col in range(COLS):
                r, g, b = frame[row][col]
                val = {"r": r, "g": g, "b": b}
                for k, ch in enumerate(CH_ORDER):
                    pkt[4 + col * ROWS * 3 + row * 3 + k] = val[ch] & 0xFF
        if not hid.HidD_SetFeature(self.h, pkt, LEN_LIVE):
            raise SystemExit("HATA: SET_FEATURE(8) başarısız (WinError %d)" % ctypes.get_last_error())


# ---------------------------------------------------------------- komutlar
def hexdump(b, base=0, rows=None):
    for i in range(0, len(b) if rows is None else min(len(b), rows * 16), 16):
        print("  %04X  %s" % (base + i, b[i:i + 16].hex(" ")))


def locate(resp, dump, addr):
    """Yanıtın hangi ofsetinden itibaren dökümdeki addr verisiyle eşleştiğini bul."""
    probe = dump[addr:addr + 32]
    if len(set(probe)) <= 1:
        return None
    off = resp.find(probe)
    return off if off >= 0 else None


def cmd_list(_):
    cols = enumerate_collections()
    if not cols:
        print("258A:0049 bulunamadı."); return
    for c in cols:
        role = {LEN_CMD: "report 5  komut", LEN_DATA: "report 6  veri", LEN_LIVE: "report 8  canlı"}.get(c["feat_len"], "") if c["usage_page"] == 0xFF00 else ""
        print("page=%04X usage=%04X in=%4d out=%4d feat=%4d  %-16s %s" % (
            c["usage_page"], c["usage"], c["in_len"], c["out_len"], c["feat_len"], role, c["path"]))


def cmd_read(a):
    dump = open(a.compare, "rb").read() if a.compare else None
    kb = K78()
    try:
        resp = kb.read_raw(a.cmd, a.addr)
    finally:
        kb.close()
    print("komut=0x%02X adres=0x%04X  yanıt %d bayt, başlık: %s" % (a.cmd, a.addr, len(resp), resp[:8].hex(" ")))
    hexdump(resp, rows=a.rows)
    if a.out:
        open(a.out, "wb").write(resp); print("kaydedildi:", a.out)
    if dump:
        off = locate(resp, dump, a.addr)
        if off is None:
            print("KARŞILAŞTIRMA: yanıt, dökümdeki 0x%04X verisini içermiyor." % a.addr)
        else:
            n = len(resp) - off
            same = sum(1 for i in range(n) if a.addr + i < len(dump) and resp[off + i] == dump[a.addr + i])
            print("KARŞILAŞTIRMA: döküm[0x%04X] yanıtın %d. baytından başlıyor; %d/%d bayt aynı." % (a.addr, off, same, n))


# ---------------------------------------------------------------- kalıcı profil (report 6, FLASH)
# Firmware A031 (cmd 3): sektör 0xB600'ü siler, tampondan 0x200 bayt yazar; 0xFE..0x1F9 aralığını
# fabrika tablolarından (0xB4FE, 0xB57C) doldurur. Yedekte bu tablolar 0xB6FE/0xB77C ile birebir aynı,
# yani tuş haritası değişmez. Komut ve adres SABİT; başka sektöre yazılamaz.
PROFILE_CMD, PROFILE_HI, PROFILE_LO = 0x03, 0xB6, 0x00
CFG_LEN = 0xFE
CFG_MAGIC = bytes([0x5A, 0xA5, 0x03, 0x03])     # ofset 6..9
OFF_MODE = 0x0D
MAX_MODE = 0x14                                 # 0x15 (per-key/host) kalıcı yapılmaz


def mode_pair_off(mode):
    return 0x1C + 2 * mode                      # [renk indeksi, hız<<4 | parlaklık]


def read_profile(kb):
    resp = kb.read_raw(0x83, (PROFILE_HI << 8) | PROFILE_LO)
    if resp[:4] != bytes([0x06, 0x83, PROFILE_HI, PROFILE_LO]):
        raise SystemExit("HATA: beklenmeyen okuma başlığı %s" % resp[:4].hex(" "))
    cfg = bytearray(resp[8:8 + CFG_LEN])
    if cfg[6:10] != CFG_MAGIC:
        raise SystemExit("HATA: profil magic değeri yok (%s); yazma iptal" % cfg[6:10].hex(" "))
    return cfg


def cmd_profile(_):
    kb = K78()
    try:
        cfg = read_profile(kb)
    finally:
        kb.close()
    print("aktif mod: %d" % cfg[OFF_MODE])
    for m in range(1, MAX_MODE + 1):
        o = mode_pair_off(m)
        print("  mod %2d: renk=%d hız=%d parlaklık=%d%s" % (m, cfg[o], cfg[o + 1] >> 4, cfg[o + 1] & 0x0F,
                                                        "   <- aktif" if m == cfg[OFF_MODE] else ""))


TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_REF = os.path.join(TOOL_DIR, "profile_ref_B600.bin")       # flash'taki profilin bilinen son hali
INITIAL_DUMP = os.path.join(os.path.expanduser("~"), "k78_backup", "k78_after_write.bin")


def load_flash_ref():
    """Flash'taki profilin bilinen son hali: önce referans dosyası, yoksa son tam döküm."""
    if os.path.exists(PROFILE_REF):
        data = open(PROFILE_REF, "rb").read()
        src = PROFILE_REF
    elif os.path.exists(INITIAL_DUMP):
        data = open(INITIAL_DUMP, "rb").read()[0xB600:0xB600 + CFG_LEN]
        src = INITIAL_DUMP + " [0xB600]"
    else:
        raise SystemExit("HATA: flash referansı yok (%s / %s)" % (PROFILE_REF, INITIAL_DUMP))
    if len(data) != CFG_LEN or data[6:10] != CFG_MAGIC:
        raise SystemExit("HATA: flash referansı geçersiz: %s" % src)
    return bytearray(data), src


def cmd_persist(a):
    kb = K78()
    try:
        ram = read_profile(kb)
        flash, ref_src = load_flash_ref()
        pending = [i for i in range(CFG_LEN) if ram[i] != flash[i]]
        print("flash referansı: %s" % ref_src)
        if pending:
            print("UYARI: RAM'de flash'a kaydedilmemiş %d bayt var (Fn ile yapılan değişiklikler):" % len(pending))
            for i in pending:
                print("  +0x%02X  flash=%02X  RAM=%02X" % (i, flash[i], ram[i]))
            if a.base is None:
                print("Hangi temelden yazılacağını seçin:\n"
                      "  --base flash : yalnızca istediğiniz değişiklik yazılır, yukarıdaki RAM farkları kaydedilmez\n"
                      "  --base ram   : yukarıdaki RAM farkları da kalıcı olur")
        base = a.base or ("ram" if not pending else None)
        old = flash                       # karşılaştırma her zaman flash'taki duruma göre
        new = bytearray(ram if base == "ram" else flash)
        mode = a.mode if a.mode is not None else old[OFF_MODE]
        if not 1 <= mode <= MAX_MODE:
            raise SystemExit("mod 1..%d olmalı" % MAX_MODE)
        new[OFF_MODE] = mode
        o = mode_pair_off(mode)
        if a.color is not None:
            if not 0 <= a.color <= 7:
                raise SystemExit("renk indeksi 0..7 olmalı")
            new[o] = a.color
        sp, br = new[o + 1] >> 4, new[o + 1] & 0x0F
        if a.speed is not None:
            if not 0 <= a.speed <= 4:
                raise SystemExit("hız 0..4 olmalı")
            sp = a.speed
        if a.brightness is not None:
            if not 0 <= a.brightness <= 4:
                raise SystemExit("parlaklık 0..4 olmalı")
            br = a.brightness
        new[o + 1] = (sp << 4) | br

        diffs = [(i, old[i], new[i]) for i in range(CFG_LEN) if old[i] != new[i]]
        print("temel: %s   mod %d  ofset 0x%02X: renk=%d hız=%d parlaklık=%d" % (
            base or "SEÇİLMEDİ", mode, o, new[o], new[o + 1] >> 4, new[o + 1] & 0x0F))
        if not diffs:
            print("Flash'a göre değişiklik yok; yazılmadı.")
            return
        print("FLASH'TA DEĞİŞECEK BAYTLAR (flash -> yeni):")
        intended = set()
        if a.mode is not None:
            intended.add(OFF_MODE)
        if a.color is not None:
            intended.add(o)
        if a.speed is not None or a.brightness is not None:
            intended.add(o + 1)
        for i, x, y in diffs:
            tag = "   (istenen)" if i in intended else ("   (RAM'deki kaydedilmemiş değişiklik)" if i in pending else "")
            print("  +0x%02X: %02X -> %02X%s" % (i, x, y, tag))
        if base is None:
            print("YAZILMADI: önce --base flash veya --base ram seçin.")
            return
        if not (a.write and a.confirm == "YAZ"):
            print("ÖNİZLEME: flash'a yazılmadı. Yazmak için: --write --confirm YAZ")
            return

        # Yedek
        import datetime
        bdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profile_backups")
        os.makedirs(bdir, exist_ok=True)
        bpath = os.path.join(bdir, "B600_%s.bin" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        open(bpath, "wb").write(bytes(old))
        open(bpath.replace(".bin", "_ram.bin"), "wb").write(bytes(ram))
        print("eski profil yedeği (flash + RAM):", bpath)

        pkt = (ctypes.c_ubyte * LEN_DATA)()
        pkt[0], pkt[1], pkt[2], pkt[3] = 0x06, PROFILE_CMD, PROFILE_HI, PROFILE_LO
        assert (pkt[1], pkt[2], pkt[3]) == (0x03, 0xB6, 0x00)
        for i, v in enumerate(new):
            pkt[8 + i] = v
        if not hid.HidD_SetFeature(kb.h_data, pkt, LEN_DATA):
            raise SystemExit("HATA: SET_FEATURE(6) başarısız (WinError %d)" % ctypes.get_last_error())
        print("YAZILDI (sektör 0xB600).")
        open(PROFILE_REF, "wb").write(bytes(new))
        print("flash referansı güncellendi:", PROFILE_REF)
        import time
        time.sleep(0.5)
        back = read_profile(kb)
        bad = [i for i in range(CFG_LEN) if back[i] != new[i]]
        print("geri okuma (RAM): %s" % ("yazılanla aynı" if not bad else "%d bayt farklı: %s" % (
            len(bad), " ".join("+0x%02X" % i for i in bad[:10]))))
        print("Flash'ı doğrulamak için klavyeyi çıkarıp takın ve 'profile' komutunu çalıştırın.")
    finally:
        kb.close()


def cmd_info(_):
    kb = K78()
    try:
        b = kb.get_info()
    finally:
        kb.close()
    print("GET_FEATURE(5): %s" % b.hex(" "))


def _color(s):
    s = s.lstrip("#")
    if len(s) != 6:
        raise argparse.ArgumentTypeError("renk RRGGBB biçiminde olmalı, ör. ff0000")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def cmd_fill(a):
    live = LiveRGB()
    try:
        live.send([[a.color] * COLS for _ in range(ROWS)])
    finally:
        live.close()
    print("canlı RGB (RAM): tüm tuşlar #%02x%02x%02x" % a.color)


def cmd_pixel(a):
    if not (0 <= a.row < ROWS and 0 <= a.col < COLS):
        raise SystemExit("satır 0..%d, sütun 0..%d olmalı" % (ROWS - 1, COLS - 1))
    frame = [[a.bg] * COLS for _ in range(ROWS)]
    frame[a.row][a.col] = a.color
    live = LiveRGB()
    try:
        live.send(frame)
    finally:
        live.close()
    print("canlı RGB (RAM): [%d,%d] = #%02x%02x%02x" % ((a.row, a.col) + a.color))


ROW_COLORS = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
ROW_COLOR_NAMES = ["kırmızı", "yeşil", "mavi", "sarı", "mor", "turkuaz"]


def cmd_rows(_):
    """Her firmware satırını ayrı renkte yak: satır -> fiziksel sıra eşlemesi için."""
    frame = [[ROW_COLORS[r]] * COLS for r in range(ROWS)]
    live = LiveRGB()
    try:
        live.send(frame)
    finally:
        live.close()
    for r in range(ROWS):
        print("satır %d = %s" % (r, ROW_COLOR_NAMES[r]))


# K78 LED haritası (ışık testleriyle doğrulandı, 2026-11-05): tuş -> (satır, sütun).
# Satır 0 ve sütun 17..20 kullanılmıyor; boş hücreler: (3,12), (4,11), (5,3), (5,4), (5,6), (5,7), (5,11).
_K78_ROWS = {
    1: ["Esc", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "Bksp", "NumLk", "KP+", "KP-"],
    2: ["Tab", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "[", "]", "\\", "KP7", "KP8", "KP9"],
    3: ["Caps", "A", "S", "D", "F", "G", "H", "J", "K", "L", ";", "'", None, "Enter", "KP4", "KP5", "KP6"],
    4: ["LShift", "Z", "X", "C", "V", "B", "N", "M", ",", ".", "/", None, "RShift", "Up", "KP1", "KP2", "KP3"],
    5: ["LCtrl", "Win", "LAlt", None, None, "Space", None, None, "RAlt", "Fn", "RCtrl", None,
        "Left", "Down", "Right", "KP0", "KP."],
}
KEYMAP = {name.upper(): (r, c) for r, names in _K78_ROWS.items() for c, name in enumerate(names) if name}
assert len(KEYMAP) == 78


def cmd_map(_):
    print("     " + " ".join("%-6d" % c for c in range(17)))
    for r in range(1, 6):
        print("r%d   " % r + " ".join("%-6s" % (n or ".") for n in _K78_ROWS[r]))
    print("toplam %d tuş" % len(KEYMAP))


def cmd_key(a):
    """key [--bg RRGGBB] TUŞ RENK [TUŞ RENK ...]"""
    if len(a.pairs) % 2:
        raise SystemExit("tuş/renk çiftleri halinde verin: ör. Esc ff0000 W 00ff00")
    frame = [[a.bg] * COLS for _ in range(ROWS)]
    for name, col in zip(a.pairs[::2], a.pairs[1::2]):
        pos = KEYMAP.get(name.upper())
        if not pos:
            raise SystemExit("bilinmeyen tuş: %s  (liste için: map)" % name)
        frame[pos[0]][pos[1]] = _color(col)
    live = LiveRGB()
    try:
        live.send(frame)
    finally:
        live.close()
    print("canlı RGB (RAM): %d tuş ayarlandı" % (len(a.pairs) // 2))


def _hsv(h):
    i, f = int(h * 6) % 6, (h * 6) % 1
    q, t = int(255 * (1 - f)), int(255 * f)
    return [(255, t, 0), (q, 255, 0), (0, 255, t), (0, q, 255), (t, 0, 255), (255, 0, q)][i]


def cmd_wave(a):
    """Soldan sağa akan gökkuşağı; Ctrl+C ile durur. Yalnızca RAM'e yazar."""
    import time
    live = LiveRGB()
    period = 1.0 / a.fps
    t0 = time.perf_counter()
    try:
        n = 0
        while a.seconds <= 0 or time.perf_counter() - t0 < a.seconds:
            phase = (time.perf_counter() - t0) * a.speed
            frame = [[_hsv((c / 17.0 + r * 0.03 - phase) % 1.0) for c in range(COLS)] for r in range(ROWS)]
            live.send(frame)
            n += 1
            time.sleep(max(0.0, t0 + n * period - time.perf_counter()))
    except KeyboardInterrupt:
        pass
    finally:
        live.close()
    print("wave bitti: %d kare" % n)


PALETTE = [((255, 0, 0), "kırmızı"), ((0, 255, 0), "yeşil"), ((0, 0, 255), "mavi"),
           ((255, 255, 0), "sarı"), ((255, 0, 255), "mor"), ((0, 255, 255), "turkuaz"),
           ((255, 255, 255), "beyaz")]


def cmd_cols(a):
    """Seçilen sütunları (tüm satırlarda) farklı renklerle yak; diğerleri sönük."""
    if len(a.cols) > len(PALETTE):
        raise SystemExit("en fazla %d sütun" % len(PALETTE))
    frame = [[(0, 0, 0)] * COLS for _ in range(ROWS)]
    for i, c in enumerate(a.cols):
        if not 0 <= c < COLS:
            raise SystemExit("sütun 0..%d olmalı" % (COLS - 1))
        for r in range(ROWS):
            frame[r][c] = PALETTE[i][0]
    live = LiveRGB()
    try:
        live.send(frame)
    finally:
        live.close()
    for i, c in enumerate(a.cols):
        print("sütun %2d = %s" % (c, PALETTE[i][1]))


def main():
    p = argparse.ArgumentParser(description="Thunderobot K78 kontrol aracı (flash'a yazmaz)")
    sp = p.add_subparsers(dest="sub", required=True)
    sp.add_parser("list", help="258A:0049 HID koleksiyonlarını listele").set_defaults(fn=cmd_list)
    sp.add_parser("info", help="GET_FEATURE(5) cihaz bilgisi (hiçbir şey göndermez)").set_defaults(fn=cmd_info)
    f = sp.add_parser("fill", help="report 8: tüm tuşları tek renge boya (yalnızca RAM)")
    f.add_argument("color", type=_color)
    f.set_defaults(fn=cmd_fill)
    px = sp.add_parser("pixel", help="report 8: tek LED yak (yalnızca RAM)")
    px.add_argument("row", type=int); px.add_argument("col", type=int); px.add_argument("color", type=_color)
    px.add_argument("--bg", type=_color, default=(0, 0, 0))
    px.set_defaults(fn=cmd_pixel)
    sp.add_parser("rows", help="report 8: her satırı ayrı renkte yak (eşleme testi)").set_defaults(fn=cmd_rows)
    cl = sp.add_parser("cols", help="report 8: seçilen sütunları farklı renklerle yak (eşleme testi)")
    cl.add_argument("cols", type=int, nargs="+")
    cl.set_defaults(fn=cmd_cols)
    sp.add_parser("map", help="K78 tuş -> LED haritasını göster").set_defaults(fn=cmd_map)
    sp.add_parser("profile", help="kalıcı profili oku ve çöz (yalnızca okuma)").set_defaults(fn=cmd_profile)
    ps = sp.add_parser("persist", help="profili FLASH'a yaz (varsayılan: sadece önizleme)")
    ps.add_argument("--mode", type=int, help="stok efekt 1..20")
    ps.add_argument("--color", type=int, help="renk indeksi 0..7 (7 = gökkuşağı)")
    ps.add_argument("--speed", type=int, help="0..4")
    ps.add_argument("--brightness", type=int, help="0..4")
    ps.add_argument("--base", choices=["flash", "ram"],
                    help="RAM'de kaydedilmemiş değişiklik varsa zorunlu: flash = sadece istenen değişiklik, ram = RAM farkları da kalıcı")
    ps.add_argument("--write", action="store_true", help="gerçekten yaz")
    ps.add_argument("--confirm", default="", help="yazmak için 'YAZ'")
    ps.set_defaults(fn=cmd_persist)
    k = sp.add_parser("key", help="report 8: tuş adlarıyla renk ver, ör. key Esc ff0000 W 00ff00")
    k.add_argument("pairs", nargs="+")
    k.add_argument("--bg", type=_color, default=(0, 0, 0))
    k.set_defaults(fn=cmd_key)
    w = sp.add_parser("wave", help="report 8: canlı gökkuşağı animasyonu (yalnızca RAM)")
    w.add_argument("--fps", type=float, default=30)
    w.add_argument("--speed", type=float, default=0.3, help="tur/saniye")
    w.add_argument("--seconds", type=float, default=0, help="0 = Ctrl+C'ye kadar")
    w.set_defaults(fn=cmd_wave)
    r = sp.add_parser("read", help="report 5 okuma komutu + report 6 GET (flash'a dokunmaz)")
    r.add_argument("addr", type=lambda s: int(s, 0))
    r.add_argument("--cmd", type=lambda s: int(s, 0), default=0x83, help="okuma komutu 0x83..0x89 (varsayılan 0x83)")
    r.add_argument("--compare", help="karşılaştırılacak .bin döküm")
    r.add_argument("--out", help="ham yanıtı dosyaya kaydet")
    r.add_argument("--rows", type=int, default=8, help="gösterilecek hexdump satırı")
    r.set_defaults(fn=cmd_read)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
