"""Render the tile the way the binary says — an independent check on the page.

Two placement rules, both read out of libcocos2dcpp.so.

Sprites (applier 0x33c1040 -> 0x33c360c):
    setContentSize(w, h) ; setPosition(x + w/2, y + h/2) ; setAnchorPoint(0.5, 0.5)
and the texture then resets the content size to its own, so a sprite is drawn at its
native size x scale, centred on the box's centre. The box's w/h only feeds nine-patch
stretching. Transparent padding inside a PNG is part of the placement: never trim it.

BMFont labels (applier 0x33c060c), for align/valign "center":
    position = (x + w/2, y + 3 + h/2)
    anchor.y = 0.5 + scale * (h - lineHeight) / (2 * lineHeight)
which lifts the glyphs out of the font's oversized line box and into the band."""
import argparse
import json
import os
import re

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(HERE, 'work', 'tile_fr')
LBL = os.path.join(HERE, 'work', 'labels_fr')
FNT = os.path.join(HERE, 'work', 'fonts', 'out', 'fr', 'custom', 'number')
LAY = json.load(open(os.path.join(HERE, 'work', 'chara_130_current.json'), encoding='utf-8'))
W, H = float(LAY['w']), float(LAY['h'])
N = LAY['nodes']


def font():
    g, common = {}, {}
    for line in open(f'{FNT}/number.fnt', encoding='utf-8', errors='replace'):
        kv = dict(re.findall(r'(\w+)=(-?\d+)', line))
        if line.startswith('common'):
            common = {k: int(v) for k, v in kv.items()}
        elif line.startswith('char '):
            g[int(kv['id'])] = {k: int(v) for k, v in kv.items()}
    return g, common


GLYPHS, COMMON = font()
ATLAS = Image.open(f'{FNT}/number.png').convert('RGBA')
PAD = 8                       # room so a glyph wider than its advance is never clipped


def label(s, kerning):
    """the string on its own line box, padded; returns (image, line width)"""
    lw = sum(GLYPHS[ord(c)]['xadvance'] + kerning for c in s if ord(c) in GLYPHS)
    im = Image.new('RGBA', (lw + 2 * PAD, COMMON['lineHeight'] + 2 * PAD), (0, 0, 0, 0))
    x = PAD
    for c in s:
        d = GLYPHS.get(ord(c))
        if not d:
            continue
        if d['width'] and d['height']:
            im.alpha_composite(ATLAS.crop((d['x'], d['y'], d['x'] + d['width'],
                                           d['y'] + d['height'])),
                               (x + d['xoffset'], PAD + d['yoffset']))
        x += d['xadvance'] + kerning
    return im, lw


def skew(im, baseline, deg=10):
    """The italic is a shader uniform, tan(10 deg) = 0.17612, and it leans the glyphs
    about the label's own origin — its baseline, not its middle. Skewing about the middle
    instead drags the whole word left, which is what pushed the level number into the
    label beside it."""
    import math
    k = math.tan(math.radians(deg))
    w, h = im.size
    grow = int(math.ceil(k * baseline))
    out = Image.new('RGBA', (w + grow, h), (0, 0, 0, 0))
    out.paste(im, (0, 0))
    return out.transform(out.size, Image.AFFINE, (1, k, -k * baseline, 0, 1, 0),
                         resample=Image.BICUBIC)


def put(canvas, art, left, bottom, dw, dh, Z):
    art = art.resize((max(1, int(round(dw * Z))), max(1, int(round(dh * Z)))), Image.LANCZOS)
    canvas.alpha_composite(art, (int(round(left * Z)), int(round((H - bottom - dh) * Z))))


def sprite(canvas, art, name, Z):
    n = N[name]
    s = n.get('scale', 1)
    dw, dh = art.width * s, art.height * s
    put(canvas, art, n['x'] + n['w'] / 2 - dw / 2, n['y'] + n['h'] / 2 - dh / 2, dw, dh, Z)


def text(canvas, s, name, Z, colour=None):
    n = N[name]
    sc, lh = n.get('scale', 1), COMMON['lineHeight']
    im, lw = label(s, n.get('kerning', 0))
    if colour:
        tint = Image.new('RGBA', im.size, tuple(colour) + (255,))
        tint.putalpha(im.getchannel('A'))
        im = Image.composite(tint, im, im.convert('L').point(lambda v: 255 if v > 200 else 0))
    if n.get('italic'):
        im = skew(im, im.height - PAD)          # the baseline sits PAD above the bottom
    ay = 0.5 + sc * (n['h'] - lh) / (2.0 * lh)
    left = (n['x'] + n['w'] / 2) - lw * sc / 2 - PAD * sc
    bottom = (n['y'] + 3 + n['h'] / 2) - lh * ay * sc - PAD * sc
    put(canvas, im, left, bottom, im.width * sc, im.height * sc, Z)


def render(Z=6, typ=1, rare=3, cls=1, stars=4, lock=True, band='lv', on=False,
           awakened=False, maxlevel=False):
    """rare is the game's own index: 0 N, 1 R, 2 SR, 3 SSR, 4 UR, 5 LR"""
    sm = ['n', 'r', 'sr', 'ssr', 'ur', 'lr'][rare]
    canvas = Image.new('RGBA', (int(W * Z), int(H * Z)), (0, 0, 0, 0))
    op = Image.open
    layers = [
        ('img_bg', op(f'{T}/bg/cha_base_0{typ}_0{min(rare, 3)}.png')),
        ('image_thumb', op(f'{T}/thumb_1024540.png')),
        ('image_chara_bottom_base', op(f'{T}/cha_base_bottom_0{typ}{"_on" if on else ""}.png')),
        ('image_rare_ssr', op(f'{T}/cha_rare_sm_{sm}.png')),
    ]
    # an awakened card (its id does not end in 0) shifts the row into image_star_evo_dokkan
    # and adds the big star; a base card keeps the plain row
    # the row's files are star1..star4; star5 is the single big star, and it belongs to
    # image_star_evo_big, the only node cut for an 80 x 60 texture
    if stars:
        layers.append(('image_star_evo_dokkan' if awakened else 'image_star_evo',
                       op(f'{T}/cha_evo_star{min(stars, 4)}.png')))
    if awakened:
        layers.append(('image_star_evo_big', op(f'{T}/cha_evo_star5.png')))
    if lock:
        layers.append(('image_cha_icon_lock', op(f'{T}/cha_icon_lock.png')))
    if band == 'lv':
        layers.append(('image_label_lv', op(f'{LBL}/com_label_lv.png')))
    layers.append(('image_icon_type', op(f'{T}/cha_type_icon_{cls}{typ}.png')))

    for name, art in sorted(layers, key=lambda p: N[p[0]]['z']):
        sprite(canvas, art.convert('RGBA'), name, Z)
    # the LR sparkle (fla_bg_effect, ef_001) is a timeline: the page plays it, this marks it
    if band == 'lv':
        # white, or yellow once the level has reached its cap
        text(canvas, '120', 'font_num', Z, (255, 255, 0) if maxlevel else None)
    else:
        text(canvas, '55 %', 'font_text', Z)
    return canvas


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('-o', default='/tmp/ref.png')
    p.add_argument('-z', type=int, default=6)
    p.add_argument('--band', default='lv')
    p.add_argument('--rare', type=int, default=3)
    p.add_argument('--stars', type=int, default=4)
    p.add_argument('--awakened', action='store_true')
    p.add_argument('--maxlevel', action='store_true')
    a = p.parse_args()
    im = render(Z=a.z, band=a.band, rare=a.rare, stars=a.stars,
                awakened=a.awakened, maxlevel=a.maxlevel)
    im.save(a.o)
    print(a.o, im.size)
