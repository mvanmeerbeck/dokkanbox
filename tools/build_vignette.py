"""Assemble design/vignette.html: the unit tile put back together from the game's own
   files — frame and background, the bottom band, and the text the band carries."""
import base64, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
# The shared tree (frames, bands, stars, rarity plates) is identical across locales; only
# the fifteen type badges and the level label are translated, and those come per language
# from work/loc/<lang>/.
T = os.path.join(HERE, 'work', 'tile_fr')
LOC = os.path.join(HERE, 'work', 'loc')
LANGS = ('fr', 'en', 'de', 'es')
LBL = os.path.join(HERE, 'work', 'labels_fr')
FNT = os.path.join(HERE, 'work', 'fonts', 'out', 'fr', 'custom', 'number')
OUT = os.path.join(HERE, '..', 'design', 'vignette.html')
RECAP = os.path.join(HERE, '..', 'design', 'recap.html')


def uri(path):
    return 'data:image/png;base64,' + base64.b64encode(open(path, 'rb').read()).decode()


# ---- the still images ----------------------------------------------------
# Each node draws its file at the file's native size times the node's scale, centred on
# the node's box — so the page needs those native sizes, and no margin may be trimmed.
from PIL import Image as _Image


def native(path):
    with _Image.open(path) as im:
        return list(im.size)


img = {'bg': {}, 'band': {}, 'type': {}, 'rare': {}, 'star': {}, 'langs': list(LANGS)}
for t in range(5):
    for r in range(4):          # SSR, UR and LR share the SSR file, byte for byte
        img['bg'][f'{t}_{r}'] = uri(f'{T}/bg/cha_base_0{t}_0{r}.png')
    img['band'][str(t)] = uri(f'{T}/cha_base_bottom_0{t}.png')
    img['band'][f'{t}_on'] = uri(f'{T}/cha_base_bottom_0{t}_on.png')
for lang in LANGS:
    img['type'][lang] = {str(cls * 10 + t): uri(f'{LOC}/{lang}/cha_type_icon_{cls}{t}.png')
                         for cls in range(3) for t in range(5)}
for k in ('n', 'r', 'sr', 'ssr', 'ur', 'lr'):
    img['rare'][k] = uri(f'{T}/cha_rare_sm_{k}.png')
for n in range(1, 6):
    img['star'][str(n)] = uri(f'{T}/cha_evo_star{n}.png')
img['lock'] = uri(f'{T}/cha_icon_lock.png')
img['label'] = {lang: uri(f'{LOC}/{lang}/com_label_lv.png') for lang in LANGS}
img['art'] = uri(f'{T}/thumb_1024540.png')
img['atlas'] = uri(f'{FNT}/number.png')
img['native'] = {
    'bg': native(f'{T}/bg/cha_base_01_03.png'),
    'band': native(f'{T}/cha_base_bottom_01.png'),
    'type': native(f'{LOC}/fr/cha_type_icon_11.png'),
    'rare': native(f'{T}/cha_rare_sm_ssr.png'),
    'lock': native(f'{T}/cha_icon_lock.png'),
    'label': native(f'{LOC}/fr/com_label_lv.png'),   # same in every locale, verified
    'art': native(f'{T}/thumb_1024540.png'),
    'star': {str(n): native(f'{T}/cha_evo_star{n}.png') for n in range(1, 6)},
}

# ---- the bitmap font -----------------------------------------------------
common, glyphs = {}, {}
for line in open(f'{FNT}/number.fnt', encoding='utf-8', errors='replace'):
    kv = dict(re.findall(r'(\w+)=(-?\d+)', line))
    if line.startswith('common'):
        common = kv
    elif line.startswith('char '):
        glyphs[int(kv['id'])] = kv

WANTED = '0123456789% '
font = {
    'lineHeight': int(common['lineHeight']),
    'base': int(common['base']),
    'atlas': img['atlas'],
    'glyphs': {},
    # The band's rate goes into font_text: it is the only node that is both full size
    # (0.58, like the digits beside it) and centred on the band itself (x 65) — "55 %"
    # lands at exactly 65.0. font_num02 sits at 51.5 and font_percent draws its sign at
    # 0.4, two thirds the height of a digit; that pair belongs to some other display.
    'samples': {'lv': '120', 'rate': '55 %'},
}
for ch in set(WANTED):
    g = glyphs.get(ord(ch))
    if not g:
        print('glyphe absent :', repr(ch)); continue
    font['glyphs'][ord(ch)] = [int(g['x']), int(g['y']), int(g['width']), int(g['height']),
                               int(g['xoffset']), int(g['yoffset']), int(g['xadvance'])]
missing = [c for v in font['samples'].values() for c in v if ord(c) not in font['glyphs']]
if missing:
    print('exemple de taux impossible :', missing); sys.exit(1)

# ---- the super Z awakening aura: its own LWF, straight off the image server ----
SOE = os.path.join(HERE, 'work', 'soe')
soe = {'lwf': base64.b64encode(open(f'{SOE}/super_optimal_eff.lwf', 'rb').read()).decode(),
       'img': {f'super_optimal_eff-{i}.png': uri(f'{SOE}/super_optimal_eff-{i}.png')
               for i in (1, 2)}}

# ---- the two timelines, lifted from the page that already carries them ----
recap = open(RECAP, encoding='utf-8').read()
m = re.search(r'<script id="anims" type="application/json">', recap)
anims_all = json.loads(recap[m.end():recap.index('</script>', m.end())])
anims = {k: {'lwf': v['lwf'], 'img': v['img']}
         for k, v in anims_all.items() if k == 'icon_rare_20000'}
anims['super_optimal_eff'] = soe

# ---- the maquette: the game's own layout file, kept as the page's source of truth
layout = json.load(open(os.path.join(HERE, 'work', 'chara_130_current.json')))

# the compiled player sits between the two <script> tags that follow the payload
i = recap.index('if (typeof global === "undefined"')
lwfjs = recap[i:recap.index('</script>', i)]

head = open(f'{HERE}/vign_head.html', encoding='utf-8').read()
body = open(f'{HERE}/vign_body.html', encoding='utf-8').read()
app = open(f'{HERE}/vign_app.js', encoding='utf-8').read()

parts = [
    head, body,
    '<script id="tileImages" type="application/json">', json.dumps(img), '</script>\n',
    '<script id="tileFont" type="application/json">', json.dumps(font), '</script>\n',
    '<script id="tileAnims" type="application/json">', json.dumps(anims), '</script>\n',
    '<script id="tileLayout" type="application/json">', json.dumps(layout, ensure_ascii=False), '</script>\n',
    '<script>', lwfjs, '</script>\n',
    '<script>', app, '</script>\n',
]
html = ''.join(parts)
open(OUT, 'w', encoding='utf-8').write(html)
print(f'{OUT} · {len(html)/1e6:.2f} Mo')
