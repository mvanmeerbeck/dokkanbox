"""Read each node's scale out of the binary, alongside its box.

The generated code fills a descriptor on the stack and hands it to an applier. The box is
a 16-byte constant stored at descriptor+0, the z order at +0x10, the scale at +0x30 or
+0x78 depending on the applier. Finding the `add x0, sp, #N` that precedes the call gives
N, and the stores follow from it."""
import re
import struct
import sys

sys.path.insert(0, '/Users/maxime/perso/dokkan/tools')
from disas import Dis
from layout_from_so import SO
# The generated code hands each descriptor to one of three appliers — image, flash,
# BMFont label — and each keeps the node's scale at a different offset inside it. Both the
# applier addresses and the offsets shift between builds, so nothing here is hard-coded:
# an applier is whatever `bl` receives a freshly built descriptor, and its scale offset is
# whichever candidate reads back a plausible float across every node that uses it.
SCALE_OFFSETS = (0x30, 0x78)


def _plausible(raw):
    if raw is None:
        return None
    v = struct.unpack('<f', struct.pack('<I', raw))[0]
    return v if 0 < v <= 4 and v == v else None


def node_geometry(dis, lo, hi, every=False):
    """(box, scale, z) for the last descriptor the code in [lo, hi) hands to the applier

    Stores land in any order, so record them all and resolve once the call appears."""
    imm, pages, wstore, qstore, out = {}, {}, {}, None, []
    x0_sp = None                 # the last `add x0, sp, #N`, which hands over a descriptor
    for a, m, o, n in dis.run(lo, hi):
        if m == 'add' and o.startswith('x0, sp, #'):
            x0_sp = int(o.split('#')[1], 0)
        elif m in ('add', 'mov', 'ldr', 'sub') and o.startswith('x0,'):
            x0_sp = None         # x0 was rebuilt from something else
        if m == 'adrp':
            pages[o.split(',')[0].strip()] = int(o.split('#')[1], 0)
        elif m == 'mov' and re.match(r'^w\d+, #(0x[0-9a-f]+|\d+)$', o):
            r, v = o.split(', #')
            imm[r] = int(v, 0)
        elif m == 'movk':
            p = [q.strip() for q in o.split(',')]
            if len(p) >= 2 and p[0] in imm:
                imm[p[0]] |= int(p[1][1:], 0) << 16
        elif m == 'fmov' and ', #' in o:
            r, v = o.split(', #')
            imm[r.replace('s', 'w', 1)] = struct.unpack('<I', struct.pack('<f', float(v)))[0]
        elif m == 'ldr' and o.startswith('d'):
            # flash nodes take their scale as a rodata pair, not an immediate
            mm = re.search(r'\[(\w+)(?:, #(0x[0-9a-f]+|\d+))?\]', o)
            if mm and mm.group(1) in pages:
                va = pages[mm.group(1)] + (int(mm.group(2), 0) if mm.group(2) else 0)
                off = dis.e.va2off(va)
                if off is not None:
                    imm[o.split(',')[0]] = struct.unpack_from('<I', dis.e.d, off)[0]
        elif m == 'ldr' and o.startswith('q'):
            mm = re.search(r'\[(\w+)(?:, #(0x[0-9a-f]+|\d+))?\]', o)
            if mm and mm.group(1) in pages:
                va = pages[mm.group(1)] + (int(mm.group(2), 0) if mm.group(2) else 0)
                off = dis.e.va2off(va)
                if off is not None:
                    imm['q0'] = struct.unpack_from('<4f', dis.e.d, off)
        elif m in ('str', 'stur'):
            mm = re.match(r'^(\w+), \[sp(?:, #(0x[0-9a-f]+|\d+))?\]', o)
            if not mm:
                continue
            reg, at = mm.group(1), int(mm.group(2), 0) if mm.group(2) else 0
            if reg.startswith('d') and reg in imm:
                wstore[at] = imm[reg]          # low half of the pair = the scale
            elif reg == 'q0' and 'q0' in imm:
                qstore = (at, imm['q0'])
            elif reg in imm:
                wstore[at] = imm[reg]
            elif reg == 'wzr':
                wstore[at] = 0
        elif m == 'bl' and qstore and x0_sp == qstore[0]:
            base, box = qstore
            out.append((a, box, int(o.lstrip('#'), 0), base, dict(wstore),
                        wstore.get(base + 0x10)))
            wstore, qstore = {}, None
    if every:
        return out
    return out[-1] if out else None


def read_nodes(dis, nodes):
    """(box, scale, z) per node.

    One pass over the whole class collects every descriptor hand-over; each name then
    takes the hand-over nearest its anchor, since an anchor sits within a few dozen bytes
    of its own call while neighbouring nodes are some 0x2d0 apart. That keeps nodes absent
    from `nodes` — the class has a few — from stealing their neighbour's geometry."""
    lo = min(a for _, a in nodes) - 0x400
    hi = max(a for _, a in nodes) + 0x400
    calls = node_geometry(dis, lo, hi, every=True)

    # an applier's scale offset is the one reading a plausible float for most of its nodes
    offset, by_applier = {}, {}
    for c in calls:
        by_applier.setdefault(c[2], []).append(c)
    for applier, group in by_applier.items():
        offset[applier] = max(SCALE_OFFSETS, key=lambda off: sum(
            1 for _, _, _, base, ws, _ in group if _plausible(ws.get(base + off)) is not None))

    # a hand-over belongs to one node: whichever anchor is nearest it. Names left over
    # are ones whose applier this pass does not recognise (the TTF labels), and they are
    # reported unread rather than handed a neighbour's box.
    claim = {}
    for name, anchor in nodes:
        near = min(calls, key=lambda c: abs(c[0] - anchor), default=None)
        if near is None or abs(near[0] - anchor) > 0x200:
            continue
        held = claim.get(near[0])
        if held is None or abs(near[0] - anchor) < abs(near[0] - dict(nodes)[held]):
            claim[near[0]] = name

    out = {name: (None, None, None) for name, _ in nodes}
    for c in calls:
        name = claim.get(c[0])
        if name is None:
            continue
        addr, box, applier, base, ws, z = c
        scale = _plausible(ws.get(base + offset[applier]))
        out[name] = (box, 1.0 if scale is None else scale, z)
    return out


if __name__ == '__main__':
    from layout_from_so import NODES
    table = read_nodes(Dis(SO), NODES)
    for name, _ in NODES:
        box, scale, z = table[name]
        if box is None:
            print(f'{name:24s} —')
            continue
        w, h, x, y = box
        print(f'{name:24s} x={x:7.1f} y={y:7.1f} w={w:7.1f} h={h:7.1f}  '
              f'échelle={scale:<6g} z={z}')
