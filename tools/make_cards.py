"""Rebuild the grid's card list from the game's own dump, for whatever thumbnails are on disk.

Kept apart from the page builder on purpose: the list changes when the mirror gains cards,
the page changes when the rendering does, and neither should force the other.

One entry per EVOLUTION CHAIN, not per card. Awakening a card consumes it: a player who
turned their SSR into the LR no longer owns the SSR, so listing both would show them two
cards they do not have instead of the one they do. The chains come from the game's own
`card_awakening_routes` — Zet and Optimal climb a ladder keeping the same illustration,
Dokkan jumps to another card entirely.

An entry is therefore drawn with the artwork of its base card and the frame, name and level
of its terminal form. Nothing is invented: the terminal forms have ids ending in 1..9 and
the mirror serves no thumbnail for them, precisely because the game reuses the base one and
only swaps the frame.
"""
import csv, json, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
GRD = os.path.join(HERE, 'work', 'grid')
CSV = os.path.join(HERE, 'work', 'cards', 'cards.csv')
ROUTES = os.path.join(HERE, 'work', 'cards', 'card_awakening_routes.csv')

# Same range as the fetcher: only 10xxxxx is a card one can own. The 2000xxx are story
# enemies and 9999990 a tutorial placeholder — they came in with the first batch and would
# sort to the top of a newest-first list.
have = {int(f[:-4]) for f in os.listdir(GRD) if f.endswith('.png') and f[:-4].isdigit()
        and 1_000_000 <= int(f[:-4]) <= 1_099_999
        and os.path.getsize(os.path.join(GRD, f)) > 0}
rows = {int(r['id']): r for r in csv.DictReader(open(CSV, encoding='utf-8', errors='replace'))}

# ---- the chains, from the game's own awakening routes ---------------------
parent = {}


def root(x):
    parent.setdefault(x, x)
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def join(a, b):
    ra, rb = root(a), root(b)
    if ra != rb:
        parent[ra] = rb


for r in csv.DictReader(open(ROUTES, encoding='utf-8', errors='replace')):
    a, b = int(r['card_id']), int(r['awaked_card_id'])
    if a in rows and b in rows:
        join(a, b)

# The dump is missing most of the Zet edges: only 1502 of the 8648 consecutive pairs are
# there, so a card like 1034370 stayed alone while the chain holding its awakened form
# 1034371 became a separate entry — the same Cell Max shown twice, once UR and once LR.
# The relation itself is not in doubt: over all 8648 pairs the name is identical and the
# type — `element % 10`, since awakening only adds the Super or Extreme class — is too.
for b in list(rows):
    a = b - 1
    if b % 10 and a in rows and rows[a]['name'] == rows[b]['name'] \
            and int(rows[a]['element']) % 10 == int(rows[b]['element']) % 10:
        join(a, b)

OPTIMAL = {int(r['card_id']) for r in csv.DictReader(open(ROUTES, encoding='utf-8',
           errors='replace')) if r['type'] == 'CardAwakeningRoute::Optimal'}
# a chain reached by a Dokkan route has been awakened out of another card
ISSUES = {int(r['awaked_card_id']) for r in csv.DictReader(open(ROUTES, encoding='utf-8',
          errors='replace')) if r['type'] == 'CardAwakeningRoute::Dokkan'}
# The Extreme Z-Awakening comes in two grades, and the dump tells them apart with
# `optimal_awakening_type`: 1 for the ordinary one (665 cards), 2 for the SUPER one (35).
# It matters for the tile too — `fla_super_optimal_eff` is the *super* aura, and the
# maquette holds no other: an ordinary Extreme Z-Awakening lights nothing.
SUPER = {int(r['card_id']) for r in csv.DictReader(open(ROUTES, encoding='utf-8',
         errors='replace'))
         if r['type'] == 'CardAwakeningRoute::Optimal' and r['optimal_awakening_type'] == '2'}

members = defaultdict(list)
for cid in rows:
    if cid in parent:
        members[root(cid)].append(cid)

chains = defaultdict(list)
for cid in sorted(have):
    chains[root(cid)].append(cid)

out, replis = [], 0
for key, bases in chains.items():
    family = members.get(key) or list(bases)
    top = max(family, key=lambda x: (int(rows[x]['rarity']), x))
    # the artwork belongs to the base of the terminal form's own ladder — its id rounded
    # down to the ten. When that one has no thumbnail, fall back to the best base we do have.
    art = top - top % 10
    if art not in have:
        art = max(bases, key=lambda x: (int(rows[x]['rarity']), x))
        replis += 1
    t = rows[top]
    out.append({'id': art, 'name': t['name'], 'rarity': int(t['rarity']),
                'element': int(t['element']), 'lv': int(t['lv_max'] or 0),
                'top': top, 'forms': sorted(family),
                # what the tile has to show: the game reads awakening off the id — a form
                # whose id does not end in zero is awakened — and the Extreme Z aura belongs
                # to the cards that have an EZA route at all.
                'awk': 1 if top % 10 else 0,
                'eza': 1 if set(family) & SUPER else 0,
                # deepest awakening: 4 super Extreme Z, 3 Extreme Z, 2 Dokkan, 1 Z, 0 none
                'ev': (4 if set(family) & SUPER else
                       3 if set(family) & OPTIMAL else
                       2 if set(family) & ISSUES else
                       1 if top % 10 else 0)})
# The Extreme Z-Awakening is not a separate collectible: `1003761` is `1003760` after EZA —
# same name, same rarity, same illustration, only a higher level cap. The route file does not
# say so (its `Optimal` rows are self-loops describing the EZA's own stages), so the chains
# above keep them apart and the album showed every such card twice. Measured: 934 of the 2593
# chains. One entry per illustration, kept at its most awakened form.
fusion = {}
for c in out:
    k = c['id']
    best = fusion.get(k)
    if best is None or (c['rarity'], c['lv']) > (best['rarity'], best['lv']):
        if best:
            c['forms'] = sorted(set(c['forms']) | set(best['forms']))
            c['eza'] = max(c['eza'], best['eza']); c['ev'] = max(c['ev'], best['ev'])
        fusion[k] = c
    else:
        best['forms'] = sorted(set(best['forms']) | set(c['forms']))
        best['eza'] = max(best['eza'], c['eza']); best['ev'] = max(best['ev'], c['ev'])
fusionnees = len(out) - len(fusion)
out = list(fusion.values())
out.sort(key=lambda c: c['id'])
json.dump(out, open(os.path.join(GRD, 'cards.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
from collections import Counter
R = ['N', 'R', 'SR', 'SSR', 'UR', 'LR']
print(f'{len(have)} vignettes → {len(out)} entrées · {fusionnees} formes suprêmes fusionnées '
      f'· {replis} sans illustration du sommet')
print('par rareté terminale :',
      {R[k]: v for k, v in sorted(Counter(c['rarity'] for c in out).items())})
