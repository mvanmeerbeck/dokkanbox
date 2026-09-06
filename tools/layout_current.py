"""Write the tile's maquette as the installed binary holds it.

Boxes and scales come from libcocos2dcpp.so; the node kind, the file it draws and the
label properties come from the strings the same code builds. Nothing here is guessed,
and nothing is carried over from the 2020 JSON except node names."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from disas import Dis
from layout_from_so import NODES, SO
from scale_from_so import read_nodes

# what each node draws, read from the strings its own code builds
EXTRA = {
    'img_thumb_empty':         dict(type='image', file='character/cha_base_empty'),
    'img_bg':                  dict(type='image', file='character/character_thumb_bg/cha_base_00_05'),
    'fla_super_optimal_eff':   dict(type='flash', file='outgame/effect/super_optimal_eff/super_optimal_eff.lwf', anime='ef_001'),
    'fla_bg_effect':           dict(type='flash', file='outgame/effect/icon_rare_20000/icon_rare_20000.lwf', anime='ef_001'),
    'image_thumb':             dict(type='image', file='master/character/thumb/card_9999990_thumb'),
    'image_chara_bottom_base': dict(type='image', file='ui/character/cha_base_bottom_00'),
    'image_rare_ssr':          dict(type='image', file='character/cha_rare_sm_ssr'),
    'image_cha_icon_lock':     dict(type='image', file='character/cha_icon_lock.png'),
    'image_label_lv':          dict(type='image', file='common/label/com_label_lv'),
    'image_label_number':      dict(type='image', file='common/label/com_label_number'),
    'image_star_evo':          dict(type='image', file='character/cha_evo_star4'),
    'image_icon_type':         dict(type='image', file='character/cha_type_icon_02'),
    'image_new':               dict(type='image', file='character/cha_icon_new'),
    'image_leader':            dict(type='image', file='character/cha_icon_leader'),
    'image_icon_up':           dict(type='image', file='common/com_arrow_up01'),
}
# every band label: BMFont, number.fnt, italic 10 degrees, kerning -2, centred
BM = dict(type='bmlabel', font='number.fnt', kerning=-2, italic=True,
          align='center', valign='center')
for k in ('font_num', 'font_num02', 'font_num03', 'font_percent', 'font_text', 'font_text02'):
    EXTRA[k] = dict(BM)

if __name__ == '__main__':
    table = read_nodes(Dis(SO), NODES)
    out = {'w': 130, 'h': 150, 'italic_deg': 10, 'nodes': {}}
    for name, _ in NODES:
        box, scale, z = table[name]
        if box is None:
            print('non lu :', name)
            continue
        w, h, x, y = box
        n = {'x': x, 'y': y, 'w': w, 'h': h, 'z': z, 'scale': round(scale, 4)}
        n.update(EXTRA.get(name, {'type': 'image'}))
        out['nodes'][name] = n
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'work', 'chara_130_current.json')
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(dst, len(out['nodes']), 'nœuds')
