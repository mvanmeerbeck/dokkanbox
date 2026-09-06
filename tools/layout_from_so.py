"""Read the tile's layout out of the current binary.

The 2020 build shipped the maquettes as JSON; this one compiles them in. Each node's
getter loads a 16-byte constant — (w, h, x, y) as four floats — from .rodata, so the
geometry is recoverable by disassembling the getter and following the load."""
import re
import struct
import sys

sys.path.insert(0, '/Users/maxime/perso/dokkan/tools')
from disas import Dis

# 6.5.5, the newest build available; 6.5.0 (the copy installed in the emulator) yields
# an identical chara_130 — every node, scale and z order compared.
SO = '/Users/maxime/perso/dokkan/tools/work/lib655/lib/arm64-v8a/libcocos2dcpp.so'


def quads(dis, lo, hi):
    """every 16-byte constant the code in [lo, hi) loads into a vector register"""
    pages, out = {}, []
    for a, m, o, _ in dis.run(lo, hi):
        if m == 'adrp':
            pages[o.split(',')[0].strip()] = int(o.split('#')[1], 0)
        elif m == 'ldr' and o.startswith('q'):
            mm = re.search(r'\[(\w+)(?:, #(0x[0-9a-f]+|\d+))?\]', o)
            if not mm or mm.group(1) not in pages:
                continue
            va = pages[mm.group(1)] + (int(mm.group(2), 0) if mm.group(2) else 0)
            off = dis.e.va2off(va)
            if off is None:
                continue
            out.append((a, va, struct.unpack_from('<4f', dis.e.d, off)))
    return out


def plausible(f):
    w, h, x, y = f
    return (all(v == v and abs(v) < 4000 for v in f)
            and 0 < w <= 1200 and 0 < h <= 1200
            and abs(x) <= 1200 and abs(y) <= 1200)


NODES = [
    ('img_thumb_empty', 0x2098004), ('img_bg', 0x20982d4),
    ('fla_super_optimal_eff', 0x2098454), ('fla_bg_effect', 0x20986a4),
    ('image_thumb', 0x20988ec), ('image_chara_bottom_base', 0x2098b24),
    ('image_rare_ssr', 0x2098d74), ('font_num03', 0x2098f9c),
    ('font_num02', 0x2099270), ('font_percent', 0x209954c),
    ('image_icon_up', 0x2099828), ('font_num', 0x2099a50),
    ('font_text02', 0x2099d1c),
    ('font_text', 0x209a000), ('image_cha_icon_lock', 0x209a2d0),
    ('image_label_lv', 0x209a514), ('image_label_number', 0x209a73c),
    ('image_label_efchange', 0x209a96c), ('image_star_evo', 0x209aba4),
    ('image_star_evo_dokkan', 0x209adcc), ('image_star_evo_big', 0x209affc),
    ('img_reward_icon', 0x209b238), ('img_cost_over', 0x209b460),
    ('fla_button', 0x209b888), ('img_in_use', 0x209baf4),
    ('image_leader', 0x209bd20), ('image_icon_type', 0x209bf54),
    ('img_cha_base_clear', 0x209c17c), ('img_level_max', 0x209c3ac),
    ('img_com_label_sp_lv', 0x209c5d0),
    # font_sp_num_100 and font_sp_100_2 are TTF labels, not BMFont ones: they go through a
    # fourth applier this pass does not recognise, so they are left out rather than handed
    # a neighbour's box. They belong to the special-attack display, not to the tile.
    ('image_new', 0x209cefc),
    ('img_select_number', 0x209d11c),
]

if __name__ == '__main__':
    dis = Dis(SO)
    for name, addr in NODES:
        got = [q for q in quads(dis, addr, addr + 0x190) if plausible(q[2])]
        if got:
            w, h, x, y = got[-1][2]
            print(f'{name:24s} x={x:7.1f} y={y:7.1f} w={w:7.1f} h={h:7.1f}   @{got[-1][1]:#x}')
        else:
            print(f'{name:24s} —')
