"""Assemble design/grille.html: a collection grid of real cards.

Two things differ from the single-tile page, and both are what make a grid viable.
The band text is built from DOM glyphs rather than a canvas — a canvas per tile is waste
when the text never changes. And the timelines are pre-baked sprite strips played by CSS
`steps()`, instead of one LWF instance per tile redrawing 300 000 pixels every frame."""
import base64, io, json, os, re, sys
from PIL import Image as _I

HERE = os.path.dirname(os.path.abspath(__file__))
T   = os.path.join(HERE, 'work', 'tile_fr')
LOC = os.path.join(HERE, 'work', 'loc')
FNT = os.path.join(HERE, 'work', 'fonts', 'out', 'fr', 'custom', 'number')
BAK = os.path.join(HERE, 'work', 'baked')
GRD = os.path.join(HERE, 'work', 'grid')
OUT = os.path.join(HERE, '..', 'design', 'grille.html')
LANG = 'fr'
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 300

uri = lambda p: 'data:image/png;base64,' + base64.b64encode(open(p, 'rb').read()).decode()

layout = json.load(open(os.path.join(HERE, 'work', 'chara_130_current.json'), encoding='utf-8'))
N = layout['nodes']

# ---- the shared chrome: one copy, however many cards ---------------------
img = {'bg': {}, 'band': {}, 'type': {}, 'rare': {}, 'star': {}}
for t in range(5):
    for r in range(4):
        img['bg'][f'{t}_{r}'] = uri(f'{T}/bg/cha_base_0{t}_0{r}.png')
    img['band'][str(t)] = uri(f'{T}/cha_base_bottom_0{t}.png')
for cls in range(3):
    for t in range(5):
        img['type'][str(cls * 10 + t)] = uri(f'{LOC}/{LANG}/cha_type_icon_{cls}{t}.png')
for k in ('n', 'r', 'sr', 'ssr', 'ur', 'lr'):
    img['rare'][k] = uri(f'{T}/cha_rare_sm_{k}.png')
for n in range(1, 6):
    img['star'][str(n)] = uri(f'{T}/cha_evo_star{n}.png')
img['lock'] = uri(f'{T}/cha_icon_lock.png')
img['label'] = uri(f'{LOC}/{LANG}/com_label_lv.png')
img['atlas'] = uri(f'{FNT}/number.png')
# the controller recolours the level to yellow at max; the glyphs are white with a black
# outline, so a recoloured copy of the atlas does the same job without a canvas
_a = _I.open(f'{FNT}/number.png').convert('RGBA')
_px = _a.load()
for _y in range(_a.height):
    for _x in range(_a.width):
        r, g, b, al = _px[_x, _y]
        if al > 8 and r > 150 and g > 150 and b > 150:
            _px[_x, _y] = (255, 255, 0, al)
_buf = io.BytesIO(); _a.save(_buf, 'PNG', optimize=True)
img['atlasMax'] = 'data:image/png;base64,' + base64.b64encode(_buf.getvalue()).decode()

nat = lambda p: list(_I.open(p).size)
img['native'] = {
    'bg': nat(f'{T}/bg/cha_base_01_03.png'), 'band': nat(f'{T}/cha_base_bottom_01.png'),
    'type': nat(f'{LOC}/{LANG}/cha_type_icon_11.png'), 'rare': nat(f'{T}/cha_rare_sm_ssr.png'),
    'lock': nat(f'{T}/cha_icon_lock.png'), 'label': nat(f'{LOC}/{LANG}/com_label_lv.png'),
    'star': {str(n): nat(f'{T}/cha_evo_star{n}.png') for n in range(1, 6)},
}

# ---- the glyph atlas, as metrics the page turns into spans ---------------
common, glyphs = {}, {}
for line in open(f'{FNT}/number.fnt', encoding='utf-8', errors='replace'):
    kv = dict(re.findall(r'(\w+)=(-?\d+)', line))
    if line.startswith('common'):
        common = kv
    elif line.startswith('char '):
        glyphs[int(kv['id'])] = kv
font = {'lineHeight': int(common['lineHeight']), 'atlasW': int(common['scaleW']),
        'atlasH': int(common['scaleH']), 'glyphs': {}}
for ch in '0123456789% ':
    g = glyphs.get(ord(ch))
    if g:
        font['glyphs'][ord(ch)] = [int(g['x']), int(g['y']), int(g['width']), int(g['height']),
                                   int(g['xoffset']), int(g['yoffset']), int(g['xadvance'])]

# ---- the baked timelines, placed where their node puts them -------------
meta = json.load(open(f'{BAK}/meta.json'))
big = N['image_star_evo_big']
PLACE = {  # (origin x, origin y, canvas span in layout units, oversampling)
    'lr_aura': (N['fla_bg_effect']['x'], N['fla_bg_effect']['y'], 144, 2),
    'seza':    (N['fla_super_optimal_eff']['x'], N['fla_super_optimal_eff']['y'], 200, 2),
    'pulse':   (big['x'] + big['w'] / 2 + 15, big['y'] + big['h'] / 2, 120, 2),
}
anim = {}
for k, m in meta.items():
    ox, oy, span, R = PLACE[k]
    x0, y0, x1, y1 = m['crop']
    anim[k] = {'img': uri(f'{BAK}/{m["file"]}'), 'n': m['frames'],
               'z': {'lr_aura': N['fla_bg_effect']['z'],
                     'seza': N['fla_super_optimal_eff']['z'], 'pulse': 100}[k],
               # the strip was cropped out of a canvas centred on the node's origin
               'x': ox - span / 2 + x0 / R, 'y': oy - span / 2 + (m['src'][1] - y1) / R,
               'w': (x1 - x0) / R, 'h': (y1 - y0) / R}

# ---- the cards ------------------------------------------------------------
cards = json.load(open(f'{GRD}/cards.json', encoding='utf-8'))
cards = [c for c in cards if os.path.exists(f'{GRD}/{c["id"]}.png')]
cards.sort(key=lambda c: (-c['rarity'], -c['lv'], c['id']))   # comme le tri par défaut du jeu
cards = cards[:LIMIT]
thumbs = {str(c['id']): uri(f'{GRD}/{c["id"]}.png') for c in cards}

head = open(f'{HERE}/grid_head.html', encoding='utf-8').read()
body = open(f'{HERE}/grid_body.html', encoding='utf-8').read()
app  = open(f'{HERE}/grid_app.js', encoding='utf-8').read()
parts = [head, body,
         '<script id="gImg" type="application/json">', json.dumps(img), '</script>\n',
         '<script id="gFont" type="application/json">', json.dumps(font), '</script>\n',
         '<script id="gLay" type="application/json">', json.dumps(layout, ensure_ascii=False), '</script>\n',
         '<script id="gAnim" type="application/json">', json.dumps(anim), '</script>\n',
         '<script id="gCards" type="application/json">', json.dumps(cards, ensure_ascii=False), '</script>\n',
         '<script id="gThumbs" type="application/json">', json.dumps(thumbs), '</script>\n',
         '<script>', app, '</script>\n']
html = ''.join(parts)
open(OUT, 'w', encoding='utf-8').write(html)
print(f'{OUT} · {len(cards)} cartes · {len(html)/1e6:.2f} Mo')
