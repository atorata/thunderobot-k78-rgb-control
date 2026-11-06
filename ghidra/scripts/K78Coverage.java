// K78: dolaylı erişilen kodu keşfet (LCALL/LJMP hedefleri + "LJMP xxxx" jump table'ları).
// Veri bölgeleri (tablolar, USB descriptor, ayar sektörleri, bootloader) hariç tutulur.
//@category K78

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSpace;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.Memory;

public class K78Coverage extends GhidraScript {

    // [başlangıç, bitiş) - kod olarak yorumlanmayacak bölgeler
    private static final long[][] DATA = {
        {0x1100, 0x1500}, {0x16A0, 0x1700}, {0x2E70, 0x2F00},
        {0x6100, 0x6400}, {0xB000, 0xC800}, {0xEB86, 0x10000}
    };

    private boolean isData(long a) {
        for (long[] r : DATA) if (a >= r[0] && a < r[1]) return true;
        return false;
    }

    private AddressSpace code;
    private Memory mem;
    private Listing lst;

    private int u8(long a) throws Exception { return mem.getByte(code.getAddress(a)) & 0xFF; }

    /** a adresindeki bayt, bir komutun başı mı ya da tanımsız mı (operand içi değil)? */
    private boolean startOrUndefined(long a) {
        Address ad = code.getAddress(a);
        Instruction i = lst.getInstructionContaining(ad);
        if (i != null) return i.getAddress().equals(ad);
        return lst.getDefinedDataContaining(ad) == null;
    }

    private boolean tryFunc(long t) {
        if (t >= 0xEB86 || isData(t)) return false;
        Address a = code.getAddress(t);
        if (lst.getInstructionAt(a) != null && getFunctionAt(a) != null) return false;
        if (lst.getInstructionContaining(a) != null && lst.getInstructionAt(a) == null) return false;
        disassemble(a);
        if (lst.getInstructionAt(a) == null) return false;
        if (getFunctionAt(a) == null && getFunctionContaining(a) == null) createFunction(a, null);
        return true;
    }

    @Override
    public void run() throws Exception {
        code = currentProgram.getAddressFactory().getAddressSpace("CODE");
        mem = currentProgram.getMemory();
        lst = currentProgram.getListing();
        int before = currentProgram.getFunctionManager().getFunctionCount();

        for (int round = 1; round <= 6; round++) {
            int added = 0;
            for (long p = 0; p < 0xEB86 - 2; p++) {
                if (isData(p) || !startOrUndefined(p)) continue;
                int op = u8(p);
                if (op == 0x12) {                         // LCALL hi lo
                    long t = (u8(p + 1) << 8) | u8(p + 2);
                    if (tryFunc(t)) added++;
                } else if (op == 0x73) {                  // JMP @A+DPTR -> ardından LJMP tablosu
                    long q = p + 1;
                    while (q < 0xEB86 - 2 && u8(q) == 0x02 && !isData(q)) {
                        long t = (u8(q + 1) << 8) | u8(q + 2);
                        if (t < 0xEB86 && !isData(t)) { disassemble(code.getAddress(q)); disassemble(code.getAddress(t)); added++; }
                        q += 3;
                    }
                }
            }
            analyzeChanges(currentProgram);
            println("tur " + round + ": +" + added);
            if (added == 0) break;
        }

        // Fonksiyonsuz kalan komut kümelerini fonksiyona bağla (ör. jump table hedefleri)
        int orphan = 0;
        for (Instruction i : lst.getInstructions(code.getAddress(0), true)) {
            if (i.getAddress().getOffset() >= 0xEB86) break;
            if (getFunctionContaining(i.getAddress()) == null && !isData(i.getAddress().getOffset())) {
                Instruction prev = i.getPrevious();
                boolean head = prev == null || !prev.getFlowType().isFallthrough() || getFunctionContaining(prev.getAddress()) != null;
                if (head && createFunction(i.getAddress(), null) != null) orphan++;
            }
        }

        long codeBytes = 0, total = 0;
        for (long a = 0; a < 0xEB86; a++) {
            if (isData(a)) continue;
            total++;
            if (lst.getInstructionContaining(code.getAddress(a)) != null) codeBytes++;
        }
        println(String.format("K78Coverage: fonksiyon %d -> %d (yetim %d), kod kapsamı %d/%d bayt (%%%.1f)",
            before, currentProgram.getFunctionManager().getFunctionCount(), orphan, codeBytes, total, 100.0 * codeBytes / total));
    }
}
