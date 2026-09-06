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
LANG = 'fr'
ARGS = [a for a in sys.argv[1:] if not a.startswith('-')]
LIMIT = int(ARGS[0]) if ARGS else 300

# Two ways out of the same build. Embedded, every asset is a data: URI and the page is one
# self-contained file you can double-click or share as a link — at the cost of a third
# more bytes, no caching, and a `loading="lazy"` that cannot fire because nothing is ever
# fetched. Served, the assets are files beside the page: real lazy loading, real caching,
# no size ceiling — and a local server, since file:// forbids the XHR the player needs.
WEB = '--web' in sys.argv
OUT = os.path.join(HERE, '..', ('web/index.html' if WEB else 'design/grille-lwf.html'))
ASSETS = os.path.join(HERE, '..', 'web', 'assets')
_written = {}
if WEB and os.path.isdir(ASSETS):
    import shutil as _sh          # rebuilt whole, so nothing stale survives a rename
    _sh.rmtree(ASSETS)


def uri(path, sub='img', name=None):
    if not WEB:
        return 'data:image/png;base64,' + base64.b64encode(open(path, 'rb').read()).decode()
    return blob(open(path, 'rb').read(), sub, name or os.path.basename(path))


def blob(data, sub, name):
    d = os.path.join(ASSETS, sub)
    os.makedirs(d, exist_ok=True)
    out = os.path.join(d, name)
    if _written.get(out, data) != data:
        raise SystemExit(f'deux contenus différents pour {sub}/{name}')
    _written[out] = data
    open(out, 'wb').write(data)
    return f'assets/{sub}/{name}'

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
# the outgame sky the game puts behind the character list: layout/image/common/com_bg.png,
# 852 x 1136, drawn 1:1 over the whole design area (box 852x1136 at 0,0, scale 1, z 1 —
# read from the binary, the layout's only other node being the anim_120000 overlay)
# the outgame sky is not a still: layout node z 1 is com_bg.png, z 2 is this timeline,
# centred on the design area — grid, starfield, drifting nebula, twinkles and the
# cyan ball that crosses. It ships inside the APK, not on the image server.
A120 = os.path.join(HERE, 'work', 'a120')
# Served, the animation is 2,4 Mo and arrives late. com_bg.png is the z 1 of the very same
# maquette — the same sky, still — and weighs 610 Ko: it holds the place underneath until
# the timeline starts drawing over it. Embedded there is nothing to stage, so it is skipped.
img['sky'] = uri(os.path.join(HERE, 'work', 'bg', 'com_bg.png')) if WEB else None
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
img['atlasMax'] = (blob(_buf.getvalue(), 'img', 'number_max.png') if WEB else
                   'data:image/png;base64,' + base64.b64encode(_buf.getvalue()).decode())

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

# ---- the player and its timelines, lifted from the tile page ------------
TILE = os.path.join(HERE, '..', 'design', 'vignette.html')
tile = open(TILE, encoding='utf-8').read()
m = re.search(r'<script id="tileAnims" type="application/json">', tile)
anim = json.loads(tile[m.end():tile.index('</script>', m.end())])
anim['anim_120000'] = {
    'lwf': base64.b64encode(open(f'{A120}/anim_120000.lwf', 'rb').read()).decode(),
    'img': {f'anim_120000-{i}.png':
            'data:image/png;base64,' + base64.b64encode(
                open(f'{A120}/anim_120000-{i}.png', 'rb').read()).decode() for i in (1, 2, 3, 4)}}

if WEB:
    # Served, the player fetches its own files: each timeline gets a folder and the page
    # hands it the prefix instead of a base64 payload. The textures go out as lossless
    # WebP — the same pixels (measured: écart 0.000), about a tenth smaller. The game's
    # own PNGs are already quantised to 256 colours, so there is nothing else to gain:
    # re-encoding them as PNG makes them bigger, and lossy WebP above q90 too.
    import subprocess, shutil
    HAS_WEBP = shutil.which('cwebp') is not None
    if not HAS_WEBP:
        print('cwebp absent : les textures restent en PNG')
    for key, a in anim.items():
        blob(base64.b64decode(a['lwf']), f'anim/{key}', f'{key}.lwf')
        names = {}
        for nm, data in a['img'].items():
            raw = base64.b64decode(data.split(',', 1)[1])
            if HAS_WEBP:
                d = os.path.join(ASSETS, 'anim', key)
                os.makedirs(d, exist_ok=True)
                src = os.path.join(d, '.tmp.png')
                open(src, 'wb').write(raw)
                out = os.path.join(d, nm.rsplit('.', 1)[0] + '.webp')
                subprocess.run(['cwebp', '-quiet', '-lossless', '-z', '9', src, '-o', out],
                               check=True)
                os.remove(src)
                names[nm] = blob(open(out, 'rb').read(), f'anim/{key}',
                                 os.path.basename(out))
            else:
                names[nm] = blob(raw, f'anim/{key}', nm)
        anim[key] = {'dir': f'assets/anim/{key}/', 'img': names}
k = tile.index('if (typeof global === "undefined"')
lwfjs = tile[k:tile.index('</script>', k)]

# ---- the cards ------------------------------------------------------------
cards = json.load(open(f'{GRD}/cards.json', encoding='utf-8'))
cards = [c for c in cards if os.path.exists(f'{GRD}/{c["id"]}.png')]
# De la plus récente à la plus ancienne. L'identifiant sert de date : le jeu les attribue
# dans l'ordre des sorties, et la concordance avec le champ `open_at` est de 96 % sur les
# 2311 cartes qui en portent un exploitable. `open_at` lui-même ne peut pas servir de clé —
# c'est une date d'ouverture : 334 cartes portent celle du lancement et 43 une sentinelle
# fixée en 2038.
cards.sort(key=lambda c: -c['id'])
cards = cards[:LIMIT]
thumbs = {str(c['id']): uri(f'{GRD}/{c["id"]}.png', 'thumb') for c in cards}

head = open(f'{HERE}/grid_lwf_head.html', encoding='utf-8').read()
body = open(f'{HERE}/grid_lwf_body.html', encoding='utf-8').read()
app  = open(f'{HERE}/grid_lwf_app.js', encoding='utf-8').read()
# served, tell the browser what matters before it discovers it: the timelines are needed
# to draw anything at all, and would otherwise queue behind every card thumbnail
pre = ''
if WEB:
    links = []
    for key, a in anim.items():
        d = a['dir']
        # no `crossorigin`: same origin, and asking for CORS on a server that sends no
        # CORS header simply wastes the preload
        links.append(f'<link rel="preload" as="fetch" href="{d}{key}.lwf">')
        for nm in sorted(os.listdir(os.path.join(ASSETS, 'anim', key))):
            if nm.endswith(('.webp', '.png')):
                links.append(f'<link rel="preload" as="image" href="{d}{nm}">')
    pre = '\n'.join(links) + '\n'

parts = [head, pre, body,
         '<script id="gImg" type="application/json">', json.dumps(img), '</script>\n',
         '<script id="gFont" type="application/json">', json.dumps(font), '</script>\n',
         '<script id="gLay" type="application/json">', json.dumps(layout, ensure_ascii=False), '</script>\n',
         '<script id="gAnim" type="application/json">', json.dumps(anim), '</script>\n',
         '<script id="gCards" type="application/json">', json.dumps(cards, ensure_ascii=False), '</script>\n',
         '<script id="gThumbs" type="application/json">', json.dumps(thumbs), '</script>\n',
         '<script>', lwfjs, '</script>\n',
         '<script>', app, '</script>\n']
html = ''.join(parts)
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
open(OUT, 'w', encoding='utf-8').write(html)
if WEB:
    n = len(_written); w = sum(len(v) for v in _written.values())
    print(f'{OUT} · {len(cards)} cartes · page {len(html)/1e3:.0f} Ko '
          f'+ {n} fichiers ({w/1e6:.2f} Mo)')
else:
    print(f'{OUT} · {len(cards)} cartes · {len(html)/1e6:.2f} Mo')
