"""Disassemble a range of ARM64 code, annotating the strings it builds."""
import sys
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
from elf import Elf


class Dis:
    def __init__(self, path):
        self.e = Elf(path)
        self.md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)

    def run(self, lo, hi):
        e = self.e
        code = e.d[e.va2off(lo):e.va2off(hi)]
        pages, out = {}, []
        for i in self.md.disasm(code, lo):
            note = ''
            if i.mnemonic == 'adrp':
                pages[i.op_str.split(',')[0].strip()] = int(i.op_str.split('#')[1], 0)
            elif i.mnemonic == 'add' and '#' in i.op_str:
                p = [x.strip() for x in i.op_str.split(',')]
                if len(p) >= 3 and p[1] in pages and p[2].startswith('#'):
                    va = pages[p[1]] + int(p[2][1:], 0)
                    s = e.cstr(va)
                    if s and 2 < len(s) < 200 and s.isprintable():
                        note = f'   ; "{s}"'
                    pages[p[0]] = va
            out.append((i.address, i.mnemonic, i.op_str, note))
        return out

    def show(self, lo, hi):
        for a, m, o, n in self.run(lo, hi):
            print(f"  {a:#010x}  {m:<9} {o}{n}")


if __name__ == '__main__':
    d = Dis(sys.argv[1])
    d.show(int(sys.argv[2], 0), int(sys.argv[3], 0))
