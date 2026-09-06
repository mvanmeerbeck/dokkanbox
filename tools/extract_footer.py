"""Extract the unit tile's maquette from any build of libcocos2dcpp.so, unaided.

Nothing here is tied to a version. The class is found through a string that occurs
exactly once in the binary; the functions that apply a node's geometry are recognised by
what they receive rather than by their address; and every node is read from the call that
hands its descriptor over, keyed by the z order, which the layout numbers from 1 upward.

  python extract_layout.py <libcocos2dcpp.so> [-o chara_130.json]
"""
import argparse
import json
import re
import struct
import sys

sys.path.insert(0, '/Users/maxime/perso/dokkan/tools')
from disas import Dis

# occurs once in the whole binary, inside the class we want
ANCHOR = 'common/foot/com_foo_base'
SPAN = 0x9000                 # how far either side of the anchor the class can reach
SCALE_OFFSETS = (0x30, 0x78)  # where an applier keeps the node's scale
SETNAME = 0x288               # vtable slot: the name written after the hand-over
GETCHILD = 0x1e8              # ... and the name looked up before it


def _f(raw):
    return None if raw is None else struct.unpack('<f', struct.pack('<I', raw))[0]


def _geometry(q):
    """does this 16-byte constant read as a node box rather than as text?"""
    w, h, x, y = q
    return (all(v == v and abs(v) < 4000 for v in q)
            and 0 < w <= 1200 and 0 < h <= 1200)


def _frame_sso(stack, base):
    """a short string sitting at `base` in a frame's stack"""
    cell = stack.get(base)
    if not cell:
        return None
    ln = cell[0][0] >> 1
    if not 0 < ln <= 22:
        return None
    buf = {}
    for at, (blob, w) in stack.items():
        if base < at <= base + 1 + ln:
            for i, b in enumerate(blob[:w]):
                buf[at + i - base - 1] = b
    out = ''.join(chr(buf[i]) for i in range(ln) if 32 <= buf.get(i, 0) < 127)
    return out if len(out) == ln else None


def _plausible(raw):
    v = _f(raw)
    return v if v is not None and 0.001 <= v <= 4 and v == v else None


class Scan:
    """One pass over a range, tracking the little the extraction needs."""

    def __init__(self, dis):
        self.d = dis
        self.reg = {}      # register -> constant address it holds
        self.imm = {}      # register -> integer immediate
        self.mem = {}      # 8-byte blobs a register holds, loaded from rodata
        self.stack = {}    # sp offset -> (value, width)
        self.q = None      # last 16-byte constant stored, with its sp offset
        self.strings = []  # rodata strings the code built here
        self.x0 = None     # last `add x0, sp, #N`

    def reset_frame(self):
        self.imm, self.stack, self.q, self.strings, self.x0 = {}, {}, None, [], None

    def step(self, a, m, o, n):
        d = self.d
        if m == 'adrp':
            r = o.split(',')[0].strip()
            self.reg[r] = int(o.split('#')[1], 0)
            self.mem.pop(r, None)
        elif m == 'add':
            p = [x.strip() for x in o.split(',')]
            if len(p) >= 3 and p[1] in self.reg and p[2].startswith('#'):
                self.reg[p[0]] = self.reg[p[1]] + int(p[2][1:], 0)
                fo = d.e.va2off(self.reg[p[0]])
                if fo and fo > 0 and d.e.d[fo - 1] == 0:      # début réel de chaîne
                    s = d.e.cstr(self.reg[p[0]])
                    if s and 1 < len(s) < 200 and s.isprintable():
                        self.strings.append(s)
            if o.startswith('x0, sp, #'):
                self.x0 = int(o.split('#')[1], 0)
        elif m == 'mov' and re.match(r'^[wx]\d+, #-?(0x[0-9a-f]+|\d+)$', o):
            # a name of eight characters or fewer is materialised as an immediate,
            # 64 bits at a time, rather than kept as a string
            r, v = o.split(', #')
            self.imm[r] = int(v, 0) & (0xFFFFFFFF if r[0] == 'w' else (1 << 64) - 1)  # negatives wrap
            self.mem.pop(r, None)
        elif m == 'movk':
            p = [x.strip() for x in o.split(',')]
            if p[0] in self.imm:
                sh = 0
                mm = re.search(r'lsl #(\d+)', o)
                if mm:
                    sh = int(mm.group(1))
                self.imm[p[0]] |= int(p[1][1:], 0) << sh
        elif m in ('ldr', 'ldur'):
            mm = re.match(r'^(\w+), \[(\w+)(?:, #(-?\d+|0x[0-9a-f]+))?\]', o)
            if not mm:
                return
            dst, src, off = mm.group(1), mm.group(2), int(mm.group(3) or '0', 0)
            if dst.startswith('q') and src in self.reg:
                fo = d.e.va2off(self.reg[src] + off)
                if fo is not None:
                    # the same 16 bytes serve as a geometry constant or as name text
                    self.imm[dst] = struct.unpack_from('<4f', d.e.d, fo)
                    self.mem[dst] = d.e.d[fo:fo + 16]
            elif dst.startswith('d') and src in self.reg:
                fo = d.e.va2off(self.reg[src] + off)
                if fo is not None:
                    self.imm[dst] = struct.unpack_from('<I', d.e.d, fo)[0]
            elif dst.startswith('x') and src in self.reg:
                fo = d.e.va2off(self.reg[src] + off)
                if fo is not None:
                    self.mem[dst] = d.e.d[fo:fo + 8]
        elif m == 'stp':
            mm = re.match(r'^(\w+), (\w+), \[sp(?:, #(-?\d+|0x[0-9a-f]+))?\]', o)
            if mm:
                at = int(mm.group(3) or '0', 0)
                wide = 8 if mm.group(1)[0] == 'x' else 4
                for j, r in enumerate((mm.group(1), mm.group(2))):
                    v = 0 if r in ('wzr', 'xzr') else self.imm.get(r)
                    if isinstance(v, int):
                        self.stack[at + j * wide] = (v.to_bytes(8, 'little'), wide)
        elif m.startswith('st'):
            mm = re.match(r'^(\w+), \[sp(?:, #(-?\d+|0x[0-9a-f]+))?\]', o)
            if not mm:
                return
            r, at = mm.group(1), int(mm.group(2) or '0', 0)
            if r in self.mem:
                self.stack[at] = (self.mem[r], len(self.mem[r]))
            if r.startswith('q') and r in self.imm and _geometry(self.imm[r]):
                self.q = (at, self.imm[r])
            elif r in self.mem:
                pass
            elif r in ('wzr', 'xzr'):
                self.stack[at] = (b'\0' * 8, 8 if r == 'xzr' else 4)
            elif r in self.mem:
                self.stack[at] = (self.mem[r], 8)
            elif r in self.imm and isinstance(self.imm[r], int):
                w = {'strb': 1, 'sturb': 1, 'strh': 2, 'sturh': 2}.get(m, 8 if r[0] == 'x' else 4)
                self.stack[at] = (self.imm[r].to_bytes(8, 'little'), w)

    def sso(self, base):
        """the libc++ short string written at `base`: length byte, then the bytes"""
        cell = self.stack.get(base)
        if not cell:
            return None
        ln = cell[0][0] >> 1
        if not 0 < ln <= 22:
            return None
        buf = {}
        for at, (blob, w) in self.stack.items():
            if base < at <= base + 1 + ln:
                for i, b in enumerate(blob[:w]):
                    buf[at + i - base - 1] = b
        out = ''.join(chr(buf[i]) for i in range(ln) if 32 <= buf.get(i, 0) < 127)
        return out if len(out) == ln else None


def handovers(dis, lo, hi):
    """every descriptor handed to an applier in [lo, hi), with its name and strings

    One pass: the register state has to survive across nodes, because a long node name is
    loaded from rodata before the call and only written to the stack after it."""
    s = Scan(dis)
    out, slot, x1, ahead = [], None, None, None
    for a, m, o, n in dis.run(lo, hi):
        if m == 'bl' and s.q and s.x0 == s.q[0]:
            out.append(dict(at=a, applier=int(o.lstrip('#'), 0), base=s.q[0], box=s.q[1],
                            stack=dict(s.stack), strings=list(s.strings), name=ahead))
            s.reset_frame()
            slot, x1, ahead = None, None, None
            continue
        s.step(a, m, o, n)
        if m == 'add' and o.startswith('x1, sp, #'):
            x1 = int(o.split('#')[1], 0)
        elif m == 'ldr' and re.search(r', #(0x[0-9a-f]+)\]$', o):
            v = int(re.search(r', #(0x[0-9a-f]+)\]$', o).group(1), 0)
            slot = v if v in (SETNAME, GETCHILD) else slot
        elif m == 'blr':
            if slot and x1 is not None:
                nm = s.sso(x1)
                if nm:
                    if slot == SETNAME and out and out[-1]['name'] is None:
                        out[-1]['name'] = nm            # written after its own hand-over
                    elif slot == GETCHILD:
                        ahead = nm                      # looked up before it
            slot = None
        elif m == 'bl':
            slot = None
    return out


def build(path):
    dis = Dis(path)
    e = dis.e
    hits = [m.start() for m in re.finditer(b'\0' + ANCHOR.encode() + b'\0', e.d)]
    vas = [e.off2va(h + 1) for h in hits]
    refs = sorted({a for v in vas if v for a in e.builders(v)})
    if len(refs) != 1:
        raise SystemExit(f'ancre « {ANCHOR} » : {len(refs)} références, il en faut une')
    anchor = refs[0]

    calls = handovers(dis, anchor - SPAN, anchor + SPAN)
    # The window sweeps other layout classes too. Ours is the run whose z numbers
    # 1, 2, 3 ... without a gap AND whose address range brackets the anchor.
    def zof(c):
        v = c['stack'].get(c['base'] + 0x10)
        return int.from_bytes(v[0][:4], 'little') if v else None

    runs, cur = [], []
    for c in calls:
        z = zof(c)
        if z == (zof(cur[-1]) + 1 if cur else 1):
            cur.append(c)
        else:
            if cur:
                runs.append(cur)
            cur = [c] if z == 1 else []
    if cur:
        runs.append(cur)
    run = next((r for r in runs if r[0]['at'] <= anchor <= r[-1]['at']), None)
    if run is None:
        raise SystemExit('aucune suite de z ne contient l’ancre')

    # each applier keeps the scale at its own offset; let the data say which
    off = {}
    for c in run:
        off.setdefault(c['applier'], []).append(c)
    for ap, grp in off.items():
        def score(k, grp=grp):
            n = 0
            for c in grp:
                cell = c['stack'].get(c['base'] + k)
                if cell and _plausible(int.from_bytes(cell[0][:4], 'little')) is not None:
                    n += 1
            return n
        off[ap] = max(SCALE_OFFSETS, key=score)

    nodes, last = {}, ''
    for i, c in enumerate(run):
        w, h, x, y = c['box']
        raw = c['stack'].get(c['base'] + off[c['applier']])
        sc = _plausible(int.from_bytes(raw[0][:4], 'little')) if raw else None
        files = [s for s in c['strings'] if '/' in s or s.endswith(('.png', '.lwf', '.fnt'))]
        node = {'x': x, 'y': y, 'w': w, 'h': h, 'z': i + 1, 'scale': round(sc or 1.0, 4)}
        if any(s.endswith('.otf') or s.endswith('.ttf') for s in c['strings']):
            node['type'] = 'label'
            node['font'] = next(s for s in c['strings'] if s.endswith(('.otf', '.ttf')))
        elif 'BMFont Label' in c['strings']:
            node['type'] = 'bmlabel'
            fnt = [s for s in files if s.endswith('.fnt')]
            if fnt:
                node['font'] = fnt[0]
            kern = c['stack'].get(c['base'] + 0x80)
            if kern:
                v = int.from_bytes(kern[0][:4], 'little', signed=False)
                node['kerning'] = v - (1 << 32) if v > (1 << 31) else v
            ital = c['stack'].get(c['base'] + 0x7c)
            node['italic'] = bool(ital and ital[0][0])
        elif any(s.endswith('.lwf') for s in files):
            node['type'] = 'flash'
            node['file'] = next(s for s in files if s.endswith('.lwf'))
            # the animation name is a short string built in the node's own frame
            for slot in sorted(c['stack']):
                t = _frame_sso(c['stack'], slot)
                if t and re.fullmatch(r'ef_\d{3}', t):
                    node['anime'] = t
                    break
        else:
            node['type'] = 'image'
            paths = [s for s in files if not s.endswith('.fnt')]
            if paths:
                node['file'] = paths[0]
        # a name longer than the stack can hold is allocated instead; it still shows up
        # as a rodata string in the node's own frame, and node names have a shape
        name = c.get('name')
        # a short name can read back as the previous node's, truncated: reject a strict
        # prefix of the name just assigned and fall back to the frame's own strings
        if name and nodes and name != last and last.startswith(name):
            name = None
        if not name:
            # the address of a short name is often built one frame earlier, so look there
            # too, and never reuse a name already taken
            pool = c['strings'] + (run[i - 1]['strings'] if i else [])
            cand = [t for t in pool
                    if re.fullmatch(r'(img|image|font|fla|btn|part)_[a-z0-9_]+', t)
                    and t not in nodes]
            name = cand[0] if cand else f'node_{i + 1:02d}'
        nodes[name] = node
        last = name
    return {'w': 130, 'h': 150, 'italic_deg': 10, 'anchor': hex(anchor), 'nodes': nodes}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('so')
    p.add_argument('-o', default=None)
    a = p.parse_args()
    out = build(a.so)
    txt = json.dumps(out, ensure_ascii=False, indent=1)
    if a.o:
        open(a.o, 'w', encoding='utf-8').write(txt)
        print(a.o, len(out['nodes']), 'nœuds · ancre', out['anchor'])
    else:
        print(txt)
