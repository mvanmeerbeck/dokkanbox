"""Read enough of an ARM64 ELF to turn addresses into file offsets, find where the code
   builds a string's address, and read the relocation table."""
import struct
import numpy as np


class Elf:
    def __init__(self, path):
        self.d = d = open(path, 'rb').read()
        assert d[:4] == b'\x7fELF' and d[4] == 2, "pas un ELF 64 bits"
        e_shoff, = struct.unpack_from('<Q', d, 0x28)
        e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', d, 0x3A)
        self.secs = []
        for i in range(e_shnum):
            o = e_shoff + i * e_shentsize
            name, typ, flags = struct.unpack_from('<IIQ', d, o)
            addr, off, size = struct.unpack_from('<QQQ', d, o + 0x10)
            self.secs.append(dict(name=name, typ=typ, flags=flags, addr=addr, off=off, size=size))
        base = self.secs[e_shstrndx]['off']
        for s in self.secs:
            e = d.index(b'\0', base + s['name'])
            s['nm'] = d[base + s['name']:e].decode()

    def sec(self, nm):
        return next(s for s in self.secs if s['nm'] == nm)

    def va2off(self, va):
        for s in self.secs:
            if s['typ'] != 8 and s['addr'] and s['addr'] <= va < s['addr'] + s['size']:
                return s['off'] + (va - s['addr'])

    def off2va(self, off):
        for s in self.secs:
            if s['typ'] != 8 and s['addr'] and s['off'] <= off < s['off'] + s['size']:
                return s['addr'] + (off - s['off'])

    def cstr(self, va_or_off, is_off=False):
        o = va_or_off if is_off else self.va2off(va_or_off)
        if o is None or o >= len(self.d):
            return None
        e = self.d.index(b'\0', o)
        s = self.d[o:e]
        return s.decode('utf-8', 'replace') if len(s) < 400 else None

    # ---- code scanning -------------------------------------------------
    def text(self):
        t = self.sec('.text')
        return t['addr'], t['off'], t['size']

    def words(self):
        tva, toff, tsz = self.text()
        return tva, np.frombuffer(self.d[toff:toff + (tsz // 4) * 4], dtype='<u4')

    def adrp_table(self):
        """every ADRP: its index, the 4 KB page it points at, and its destination register"""
        tva, w = self.words()
        idx = np.nonzero((w & 0x9F000000) == 0x90000000)[0]
        v = w[idx].astype(np.int64)
        imm = (((v >> 5) & 0x7FFFF) << 2) | ((v >> 29) & 3)
        imm = np.where(imm & (1 << 20), imm - (1 << 21), imm) << 12
        page = ((tva + idx * 4) & ~0xFFF) + imm
        return idx, page, (v & 0x1F)

    def builders(self, target_va, idx=None, page=None, rd=None):
        """code addresses that compute exactly `target_va` with ADRP followed by ADD"""
        tva, w = self.words()
        if idx is None:
            idx, page, rd = self.adrp_table()
        sel = np.nonzero(page == (target_va & ~0xFFF))[0]
        out = []
        for k in sel:
            i = int(idx[k])
            for j in range(i + 1, min(i + 9, len(w))):
                x = int(w[j])
                if (x & 0xFF800000) == 0x91000000 and ((x >> 5) & 0x1F) == rd[k]:
                    if int(page[k]) + ((x >> 10) & 0xFFF) == target_va:
                        out.append(tva + i * 4)
                    break
                if (x & 0x9F000000) == 0x90000000 and (x & 0x1F) == rd[k]:
                    break
        return sorted(out)

    def strings_near(self, addr, span=0x500):
        """every string the code builds within `span` bytes either side of `addr`"""
        tva, w = self.words()
        idx, page, rd = self.adrp_table()
        m = ((idx * 4 + tva) >= addr - span) & ((idx * 4 + tva) <= addr + span)
        out = []
        for k in np.nonzero(m)[0]:
            i = int(idx[k])
            for j in range(i + 1, min(i + 9, len(w))):
                x = int(w[j])
                if (x & 0xFF800000) == 0x91000000 and ((x >> 5) & 0x1F) == rd[k]:
                    s = self.cstr(int(page[k]) + ((x >> 10) & 0xFFF))
                    if s and 2 < len(s) < 200 and s.isprintable():
                        out.append((tva + i * 4, s))
                    break
        return out

    def callers(self, target):
        """every BL that jumps to `target`"""
        tva, w = self.words()
        idx = np.nonzero((w & 0xFC000000) == 0x94000000)[0]
        imm = (w[idx] & 0x03FFFFFF).astype(np.int64)
        imm = np.where(imm & (1 << 25), imm - (1 << 26), imm)
        dst = tva + idx * 4 + imm * 4
        return (tva + idx[dst == target] * 4).tolist()

    # ---- relocations: how stripped C++ still tells you its class names ---
    def relocs(self):
        if getattr(self, '_rel', None) is None:
            parts = []
            for s in self.secs:
                if s['nm'].startswith('.rela'):
                    n = s['size'] // 24
                    a = np.frombuffer(self.d[s['off']:s['off'] + n * 24], dtype=np.uint64).reshape(n, 3)
                    parts.append(a[(a[:, 1] & 0xffffffff) == 1027][:, [0, 2]])   # R_AARCH64_RELATIVE
            self._rel = np.vstack(parts)
            self._by_add = self._rel[np.argsort(self._rel[:, 1])]
            self._by_off = self._rel[np.argsort(self._rel[:, 0])]
        return self._rel

    def pointers_to(self, va):
        self.relocs()
        i = np.searchsorted(self._by_add[:, 1], va)
        out = []
        while i < len(self._by_add) and self._by_add[i, 1] == va:
            out.append(int(self._by_add[i, 0])); i += 1
        return out

    def deref(self, va):
        self.relocs()
        i = np.searchsorted(self._by_off[:, 0], va)
        if i < len(self._by_off) and self._by_off[i, 0] == va:
            return int(self._by_off[i, 1])
        return None
