"""Build the recognition pack the broadcast extension memory-maps.

The script that made the first one is gone; this rebuilds it from the card thumbnails, and
every constant below was recovered by comparing against that first pack rather than guessed:
the artwork is drawn in a 146 px box on a 750 px wide screen, the template is its central
88 px, resampled BILINEAR (measured: mean error 0.25 against the reference, where bicubic
gives 5.8 and Lanczos 8.8), luma is Rec.601 at full range, and the mask keeps alpha > 127.

    python make_refpack.py [-o spike-ios/refpack.bin]

Format, as `Recognizer.swift` reads it:
    "DKPK" u32 · version u32 = 1 · count u32 · dim u32 · side u32
    ids count×u32 · desc count×dim×f32 · tpl count×side²×u8 · mask count×side²×u8
    stats count×3×f32  (kept pixels, sum T, sum T²)
"""
import argparse, json, os, struct, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GRD = os.path.join(HERE, 'work', 'grid')
ART = 146          # the artwork box on a 750 px wide screen
SIDE = 88          # the template, centred in it
CELLS = 11         # descriptor grid per gradient plane; SIDE must divide by it
DIM = CELLS * CELLS * 2


def template(path):
    """One card's greyscale template and its mask, exactly as the runtime sees the screen."""
    im = Image.open(path).convert('RGBA').resize((ART, ART), Image.BILINEAR)
    a = np.asarray(im).astype(np.float64)
    i = (ART - SIDE) // 2
    crop = a[i:i + SIDE, i:i + SIDE]
    luma = crop[:, :, 0] * 0.299 + crop[:, :, 1] * 0.587 + crop[:, :, 2] * 0.114
    keep = crop[:, :, 3] > 127
    # Under a transparent pixel a PNG usually keeps black, and the descriptor — which is
    # computed unmasked — then reads a hard silhouette edge the screen does not have, since
    # the screen shows the type-coloured frame there. Flattening those pixels to the mean of
    # the artwork removes the phantom edge: measured on a real screenshot, the right card
    # goes to rank 1 on all 25 tiles, against a worst rank of 47 when left as it comes.
    luma = np.where(keep, luma, luma[keep].mean() if keep.any() else 0)
    tpl = np.clip(np.rint(luma), 0, 255).astype(np.uint8)
    mask = np.where(keep, 255, 0).astype(np.uint8)
    return tpl, mask


def descriptor(tpl):
    """Sobel responses averaged over an 11x11 grid per axis, centred and unit length.

    Edges are mirrored the way the player does it — index -1 reads 1, index side reads
    side-2 — so exporter and runtime stay bit-comparable."""
    t = tpl.astype(np.int32)
    p = np.empty((SIDE + 2, SIDE + 2), np.int32)
    p[1:-1, 1:-1] = t
    p[0, 1:-1] = t[1]; p[-1, 1:-1] = t[SIDE - 2]
    p[1:-1, 0] = t[:, 1]; p[1:-1, -1] = t[:, SIDE - 2]
    p[0, 0] = t[1, 1]; p[0, -1] = t[1, SIDE - 2]
    p[-1, 0] = t[SIDE - 2, 1]; p[-1, -1] = t[SIDE - 2, SIDE - 2]

    tl, tc, tr = p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:]
    ml, mr = p[1:-1, :-2], p[1:-1, 2:]
    bl, bc, br = p[2:, :-2], p[2:, 1:-1], p[2:, 2:]
    gx = (tr - tl) + 2 * (mr - ml) + (br - bl)
    gy = (bl - tl) + 2 * (bc - tc) + (br - tr)

    cell = SIDE // CELLS
    box = lambda g: g.reshape(CELLS, cell, CELLS, cell).sum(axis=(1, 3)) / (cell * cell)
    v = np.concatenate([box(gx).ravel(), box(gy).ravel()]).astype(np.float32)
    v -= v.mean()
    n = np.sqrt((v.astype(np.float64) ** 2).sum())
    return (v / n if n > 0 else v).astype(np.float32)


def build(cards, out):
    n = len(cards)
    ids = np.array([c['id'] for c in cards], dtype='<u4')
    desc = np.empty((n, DIM), '<f4')
    tpls = np.empty((n, SIDE * SIDE), np.uint8)
    masks = np.empty((n, SIDE * SIDE), np.uint8)
    stats = np.empty((n, 3), '<f4')
    for k, c in enumerate(cards):
        t, m = template(os.path.join(GRD, f'{c["id"]}.png'))
        keep = (m >> 7).astype(np.float64)
        tf = t.astype(np.float64)
        tpls[k] = t.ravel(); masks[k] = m.ravel()
        stats[k] = (keep.sum(), (keep * tf).sum(), (keep * tf * tf).sum())
        desc[k] = descriptor(t)
        if (k + 1) % 500 == 0:
            print(f'  {k + 1}/{n}', flush=True)
    with open(out, 'wb') as f:
        f.write(struct.pack('<4sIIII', b'DKPK', 1, n, DIM, SIDE))
        for block in (ids, desc, tpls, masks, stats):
            f.write(block.tobytes())
    print(f'{out} · {n} cartes · {os.path.getsize(out) / 1e6:.2f} Mo')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', default=os.path.join(HERE, '..', 'spike-ios', 'refpack.bin'))
    a = ap.parse_args()
    cards = json.load(open(os.path.join(GRD, 'cards.json'), encoding='utf-8'))
    cards = [c for c in cards if os.path.exists(os.path.join(GRD, f'{c["id"]}.png'))]
    cards.sort(key=lambda c: c['id'])
    build(cards, a.o)
