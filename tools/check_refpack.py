"""Replay the two-stage recognition on a real screenshot, to prove the pack is usable.

The broadcast extension cannot be run — Xcode is broken — so the pack is checked against
the same screen the phone would see, with the same maths the Swift does: a gradient
descriptor ranks every card at once, then a masked correlation verifies the shortlist.
"""
import struct, sys
import numpy as np
from PIL import Image

ART, SIDE, CELLS = 146, 88, 11
COLS = [0, 151, 302, 453, 604]
PERIOD = 176
INSET = (ART - SIDE) // 2


def load(path):
    raw = np.memmap(path, dtype=np.uint8, mode='r')
    magic, ver, n, dim, side = struct.unpack_from('<4sIIII', raw, 0)
    assert magic == b'DKPK' and side == SIDE, (magic, side)
    plane = side * side
    o = 20
    ids = np.frombuffer(raw[o:o + n * 4], '<u4'); o += n * 4
    desc = np.frombuffer(raw[o:o + n * dim * 4], '<f4').reshape(n, dim); o += n * dim * 4
    tpl = np.frombuffer(raw[o:o + n * plane], np.uint8).reshape(n, plane); o += n * plane
    msk = np.frombuffer(raw[o:o + n * plane], np.uint8).reshape(n, plane); o += n * plane
    st = np.frombuffer(raw[o:o + n * 12], '<f4').reshape(n, 3)
    return ids, desc, tpl.astype(np.float32), (msk >> 7).astype(np.float32), st


def descriptor(patch):
    t = patch.astype(np.int32)
    p = np.empty((SIDE + 2, SIDE + 2), np.int32); p[1:-1, 1:-1] = t
    p[0, 1:-1] = t[1]; p[-1, 1:-1] = t[SIDE - 2]
    p[1:-1, 0] = t[:, 1]; p[1:-1, -1] = t[:, SIDE - 2]
    p[0, 0] = t[1, 1]; p[0, -1] = t[1, SIDE - 2]
    p[-1, 0] = t[SIDE - 2, 1]; p[-1, -1] = t[SIDE - 2, SIDE - 2]
    tl, tc, tr = p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:]
    ml, mr = p[1:-1, :-2], p[1:-1, 2:]
    bl, bc, br = p[2:, :-2], p[2:, 1:-1], p[2:, 2:]
    gx = (tr - tl) + 2 * (mr - ml) + (br - bl)
    gy = (bl - tl) + 2 * (bc - tc) + (br - tr)
    c = SIDE // CELLS
    box = lambda g: g.reshape(CELLS, c, CELLS, c).sum(axis=(1, 3)) / (c * c)
    v = np.concatenate([box(gx).ravel(), box(gy).ravel()]).astype(np.float64)
    v -= v.mean(); n = np.sqrt((v ** 2).sum())
    return v / n if n else v


def correlate(patch, tpl, msk, st):
    """Pearson correlation over the pixels the artwork paints — the pack carries its sums."""
    p = patch.astype(np.float32).ravel()
    n, sT, sTT = st
    sI = float((msk * p).sum())
    sII = float((msk * p * p).sum())
    sIT = float((msk * p * tpl).sum())
    num = sIT - sI * sT / n
    vi = sII - sI * sI / n
    vt = sTT - sT * sT / n
    return num / np.sqrt(vi * vt) if vi > 0 and vt > 0 else -1.0


def main(shot, pack, shortlist=4, radius=1):
    ids, desc, tpl, msk, st = load(pack)
    im = Image.open(shot).convert('RGB')
    if im.width != 750:
        im = im.resize((750, round(im.height * 750 / im.width)), Image.BILINEAR)
    a = np.asarray(im).astype(np.float64)
    luma = a[:, :, 0] * 0.299 + a[:, :, 1] * 0.587 + a[:, :, 2] * 0.114
    luma = np.clip(np.rint(luma), 0, 255).astype(np.uint8)
    H, W = luma.shape
    print(f'capture {W}x{H} · pack {len(ids)} cartes')

    def patch(x, y):
        return luma[y + INSET:y + INSET + SIDE, x + INSET:x + INSET + SIDE]

    # find the row phase: the offset whose tiles rank best on the descriptor alone
    best = (-1, 0)
    for y0 in range(0, PERIOD, 2):
        rows = [y0 + k * PERIOD for k in range((H - y0 - ART) // PERIOD + 1)]
        if len(rows) < 3: continue
        s = 0.0
        for y in rows[:4]:
            for x in COLS[:3]:
                s += float(desc @ descriptor(patch(x, y))).__abs__() if False else float((desc @ descriptor(patch(x, y))).max())
        if s > best[0]: best = (s, y0)
    y0 = best[1]
    print(f'phase de lignes trouvée à y = {y0}')

    total = accept = 0
    lignes = []
    for k in range((H - y0 - ART) // PERIOD + 1):
        y = y0 + k * PERIOD
        ligne = []
        for x in COLS:
            q = descriptor(patch(x, y))
            scores = desc @ q
            cand = np.argpartition(-scores, shortlist)[:shortlist]
            note = []
            for c in cand:
                bestc = -1.0
                for dy in range(-radius, radius + 1):
                    for dx in range(-radius, radius + 1):
                        yy, xx = y + INSET + dy, x + INSET + dx
                        if yy < 0 or xx < 0 or yy + SIDE > H or xx + SIDE > W: continue
                        v = correlate(luma[yy:yy + SIDE, xx:xx + SIDE], tpl[c], msk[c], st[c])
                        bestc = max(bestc, v)
                note.append((bestc, int(ids[c])))
            note.sort(reverse=True)
            score, cid = note[0]
            marge = score - max(note[1][0], 0) if len(note) > 1 else score
            total += 1
            ok = score >= 0.55 and marge >= 0.08
            accept += ok
            ligne.append(f'{cid if ok else "?":>8} {score:4.2f}')
        lignes.append(' | '.join(ligne))
    for l in lignes: print('  ', l)
    print(f'{accept}/{total} tuiles acceptées ({100*accept/total:.0f} %)')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '/tmp/newpack.bin')
