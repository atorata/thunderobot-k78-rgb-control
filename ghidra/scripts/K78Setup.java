// K78 firmware: isimlendirme + decompile dışa aktarımı.
// Headless analizden sonra postScript olarak çalışır. Klavyeye hiçbir şey göndermez.
//@category K78

import java.io.File;
import java.io.PrintWriter;
import java.util.LinkedHashMap;
import java.util.Map;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSpace;
import ghidra.program.model.listing.CodeUnit;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.SourceType;

public class K78Setup extends GhidraScript {

    private AddressSpace code, ext, intm;

    private void label(AddressSpace sp, long off, String name, String comment) {
        try {
            Address a = sp.getAddress(off);
            currentProgram.getSymbolTable().createLabel(a, name, SourceType.USER_DEFINED);
            if (comment != null && sp == code) {
                currentProgram.getListing().setComment(a, CodeUnit.PLATE_COMMENT, comment);
            }
        } catch (Exception e) {
            println("label hatası " + name + ": " + e.getMessage());
        }
    }

    private Function func(long off, String name, String comment) {
        Address a = code.getAddress(off);
        try {
            disassemble(a);
            Function f = getFunctionAt(a);
            if (f == null) f = createFunction(a, name);
            if (f != null) f.setName(name, SourceType.USER_DEFINED);
            if (comment != null) currentProgram.getListing().setComment(a, CodeUnit.PLATE_COMMENT, comment);
            return f;
        } catch (Exception e) {
            println("fonksiyon hatası " + name + ": " + e.getMessage());
            return null;
        }
    }

    @Override
    public void run() throws Exception {
        code = currentProgram.getAddressFactory().getAddressSpace("CODE");
        ext = currentProgram.getAddressFactory().getAddressSpace("EXTMEM");
        intm = currentProgram.getAddressFactory().getAddressSpace("INTMEM");
        println("adres alanları: CODE=" + code + " EXTMEM=" + ext + " INTMEM=" + intm);

        Memory mem = currentProgram.getMemory();
        if (ext != null && !mem.contains(ext.getAddress(0x0000))) {
            try {
                mem.createUninitializedBlock("XRAM", ext.getAddress(0x0000), 0x1000, false);
            } catch (Exception e) {
                println("XRAM bloğu oluşturulamadı: " + e.getMessage());
            }
        }

        // 8051 kesme vektörleri: LJMP içerenleri giriş noktası yap
        for (int v = 0x03; v <= 0x83; v += 8) {
            if ((mem.getByte(code.getAddress(v)) & 0xFF) == 0x02) {
                disassemble(code.getAddress(v));
                addEntryPoint(code.getAddress(v));
                label(code, v, String.format("ivec_%02X", v), null);
            }
        }

        // ---- Fonksiyonlar (analizde doğrulananlar)
        func(0xADE9, "enter_isp_DANGER", "05 75 komutu: EA=0, B=A5, A=5A, LJMP FF00 -> ISP bootloader");
        func(0xAA67, "flash_erase_sector", "IB_CON2..5 = E6/05/0A/09/06 anahtar dizisi: sektör silme");
        func(0x9C54, "flash_write_block", "XRAM tamponunu flash'a yazar (0F1C = uzunluk)");
        func(0xA031, "cfg_cmd3_write_profile", "report 6 cmd 3: profil sektörünü sil+yaz, B4FE/B57C tablolarını koru");
        func(0x905B, "cfg_write_1k", "report 6 cmd 4..9: başlıktaki adreste 2 sektör sil+yaz, ARALIK KONTROLÜ YOK");
        func(0xA83A, "usb_ep_reset_buf", null);
        func(0x70EB, "usb_ep0_next_chunk", null);

        // USB istek tablosu: 0x63AA'da Keil generic pointer (FF hh ll) dizisi,
        // 0x63E9'da [bmRequestType, bRequest, indeks] dağıtım tablosu.
        label(code, 0x63AA, "usb_req_handler_ptrs", "21 x generic pointer (FF hh ll)");
        label(code, 0x63E9, "usb_req_dispatch_tbl", "[bmRequestType, bRequest, handler index]");
        func(0x0056, "usb_req_stall", "tablo girdisi [0]: desteklenmeyen istek");
        func(0xAD28, "usb_clear_feature_dev", null);
        func(0xA7CF, "usb_clear_feature_ep", null);
        func(0xAD3A, "usb_set_feature_dev", null);
        func(0xA86B, "usb_set_feature_ep", null);
        func(0xADB1, "usb_set_address", null);
        func(0xA952, "usb_set_configuration", null);
        func(0xA8FC, "usb_set_interface", null);
        func(0x003E, "usb_set_descriptor", null);
        func(0xA308, "usb_get_status_dev", null);
        func(0xA3F5, "usb_get_status_if", null);
        func(0x96AC, "usb_get_status_ep", null);
        func(0x469E, "usb_get_descriptor", null);
        func(0xA97C, "usb_get_configuration", null);
        func(0xAA1E, "usb_get_interface", null);
        func(0x26B5, "hid_get_report", "A1 01: GET_REPORT; feature 6 için cmd 0x83..0x89 okuma yolları (0x2817)");
        func(0x877E, "hid_set_report_setup", "21 09: SET_REPORT setup aşaması; veri aşaması set_report_dispatch (0x0200)");
        func(0xAD03, "hid_set_idle", null);
        func(0xA9F8, "hid_get_idle", null);
        func(0xAA43, "hid_set_protocol", null);
        func(0xA516, "hid_get_protocol", null);

        // İçinde bulunduğumuz ama başı bilinmeyen kod noktaları
        label(code, 0x0200, "set_report_dispatch", "USB SET_REPORT (bRequest 09) işleyicisi; wLength'e göre report 5/6/8");
        label(code, 0x025E, "rep5_check_isp", "05 75 -> enter_isp_DANGER");
        label(code, 0x027D, "rep5_app_mode_on", "05 A5 xx -> bit 4D=1, 08DE=xx");
        label(code, 0x02A7, "rep5_app_mode_off", "05 5A -> bit 4D=0");
        label(code, 0x02BD, "rep5_generic", "diğer 05 komutları: 8 bayt IRAM 08..0F'a");
        label(code, 0x0360, "rep8_live_receive", "report 8 (382 bayt): XRAM'e (0F20 pointer) kopya, flash yok");
        label(code, 0x0471, "rep6_receive", "report 6 (1032 bayt): XRAM 0A04'e topla, sonra cmd 3..9 dağıtımı");
        label(code, 0x04EE, "rep6_cmd_dispatch", null);
        label(code, 0x2817, "get_report6_dispatch", "GET_REPORT(6): cmd 0x83..0x89 okuma yolları");
        label(code, 0xA2E1, "cfg_load_header", "aktif profil başlığı -> XRAM 0E2C, 5A A5 yoksa B400 fabrika");

        // ---- Veri
        label(code, 0x1108, "tbl_hid_usage_1", null);
        label(code, 0x1293, "tbl_breath_up", null);
        label(code, 0x12D4, "tbl_breath_down", null);
        label(code, 0x61B4, "usb_strings", null);
        label(code, 0x61E2, "hid_rd_keyboard", null);
        label(code, 0x6320, "usb_device_descriptor", null);
        label(code, 0xB400, "cfg_factory_profile", "fabrika profili (sektör 0xB400)");
        label(code, 0xB4FE, "keymap_factory_a", null);
        label(code, 0xB57C, "keymap_factory_b", null);
        label(code, 0xB600, "cfg_active_profile", "aktif profil (OpenRGB 06 03 B6 bunu siler!)");
        label(code, 0xB800, "cfg_sector_B800", "OpenRGB 'static' (06 08 B8)");
        label(code, 0xBC00, "cfg_sector_BC00", "OpenRGB 'direct' (06 09 BC)");
        label(code, 0xC000, "cfg_sector_C000", null);
        label(code, 0xEB86, "free_space", "~1.1 KB boş alan (0xEB86-0xEFFA)");
        label(code, 0xF000, "bootloader", "ISP bootloader - DOKUNMA");
        label(code, 0xFF00, "isp_entry", null);

        if (ext != null) {
            Map<Long, String> x = new LinkedHashMap<>();
            x.put(0x0A04L, "x_rep6_rxbuf"); x.put(0x0E2CL, "x_cfg_active"); x.put(0x08DEL, "x_app_mode_param");
            x.put(0x0F12L, "x_loop_i"); x.put(0x0F20L, "x_rep8_dst_ptr"); x.put(0x0F36L, "x_read_len");
            x.put(0x0F39L, "x_rx_count"); x.put(0x0F3FL, "x_wLength"); x.put(0x0F41L, "x_read_addr");
            x.put(0x0F45L, "x_ep0_state"); x.put(0x0F46L, "x_ep0_bufptr"); x.put(0x1100L, "x_ep0_buf");
            for (Map.Entry<Long, String> e : x.entrySet()) label(ext, e.getKey(), e.getValue(), null);
        }
        if (intm != null) label(intm, 0x08, "i_cmd_hdr", null);

        // Analizi yeni giriş noktalarıyla tamamla
        analyzeAll(currentProgram);

        // ---- Decompile dışa aktarımı
        File outDir = new File(getScriptArgs().length > 0 ? getScriptArgs()[0] : "decomp");
        outDir.mkdirs();
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        int n = 0, fail = 0;
        try (PrintWriter all = new PrintWriter(new File(outDir, "all_functions.c"), "UTF-8");
             PrintWriter idx = new PrintWriter(new File(outDir, "functions.txt"), "UTF-8")) {
            for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
                if (monitor.isCancelled()) break;
                idx.printf("%s  %-32s  %d bayt%n", f.getEntryPoint(), f.getName(), f.getBody().getNumAddresses());
                DecompileResults r = ifc.decompileFunction(f, 60, monitor);
                all.println("// ===== " + f.getName() + " @ " + f.getEntryPoint());
                if (r != null && r.decompileCompleted()) {
                    all.println(r.getDecompiledFunction().getC());
                    n++;
                } else {
                    all.println("// decompile başarısız: " + (r == null ? "?" : r.getErrorMessage()));
                    fail++;
                }
            }
        }
        // Önemli noktaları içeren fonksiyonlar ayrı dosyalara
        long[] keys = {0x0200, 0x0360, 0x0471, 0x2817, 0xA2E1, 0xA031, 0x905B, 0xAA67, 0x9C54, 0xADE9};
        for (long k : keys) {
            Function f = getFunctionContaining(code.getAddress(k));
            if (f == null) { println(String.format("0x%04X: fonksiyon bulunamadı", k)); continue; }
            DecompileResults r = ifc.decompileFunction(f, 120, monitor);
            try (PrintWriter w = new PrintWriter(new File(outDir, String.format("%04X_%s.c", k, f.getName())), "UTF-8")) {
                w.println(String.format("// 0x%04X adresini içeren fonksiyon: %s @ %s", k, f.getName(), f.getEntryPoint()));
                w.println(r != null && r.decompileCompleted() ? r.getDecompiledFunction().getC() : "// başarısız");
            }
        }
        ifc.dispose();
        println("K78: " + currentProgram.getFunctionManager().getFunctionCount() + " fonksiyon, decompile ok=" + n + " hata=" + fail + " -> " + outDir.getAbsolutePath());
    }
}
