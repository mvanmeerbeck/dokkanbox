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
import csv, json, os, re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
GRD = os.path.join(HERE, 'work', 'grid')
CSV = os.path.join(HERE, 'work', 'cards', 'cards.csv')
ROUTES = os.path.join(HERE, 'work', 'cards', 'card_awakening_routes.csv')
CATS = os.path.join(HERE, 'work', 'cards', 'card_categories.csv')
CARD_CATS = os.path.join(HERE, 'work', 'cards', 'card_card_categories.csv')

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


# The awakening graph is directed: `card_id` awakens INTO `awaked_card_id`. Union-find only
# needs the pairs, but choosing the terminal form later needs the arrows — a Dokkan route
# can awaken a card into one with a SMALLER id (1007931 → 1006211), so the last form is the
# sink of this graph, not the highest id. Optimal rows are the EZA's own stages, self-loops
# on one id, and say nothing about succession, so they are left out here.
awakens = defaultdict(set)
for r in csv.DictReader(open(ROUTES, encoding='utf-8', errors='replace')):
    a, b = int(r['card_id']), int(r['awaked_card_id'])
    if a in rows and b in rows:
        join(a, b)
        if a != b and r['type'] != 'CardAwakeningRoute::Optimal':
            awakens[a].add(b)

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
        awakens[a].add(b)          # the Zet direction: base a awakens into a+1

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

# ---- the team categories, from the same public export as the rest ---------
# A card belongs to several (Fusion, Super Saiyan, Movie Bosses…); the game keys the link on
# every form's id, so a chain's categories are the union over its forms — the base and its
# awakenings do not always carry exactly the same list.
card_cats = defaultdict(set)
for r in csv.DictReader(open(CARD_CATS, encoding='utf-8', errors='replace')):
    card_cats[int(r['card_id'])].add(int(r['card_category_id']))

# ---- languages -----------------------------------------------------------
# One base = one language: its `name` column holds names in that language. The primary base
# (cards.csv / card_categories.csv) is the game's region we extracted — English here. A
# second language slots in as cards_<lang>.csv + card_categories_<lang>.csv, same tables from
# that region's base; only the name columns are read from it. So adding French later is a
# data drop, no code change — LANGS grows on its own and every name becomes a per-language map.
PRIMARY = 'en'
CARDS_DIR = os.path.dirname(CSV)
extra = sorted(m.group(1) for f in os.listdir(CARDS_DIR)
               if (m := re.match(r'cards_([a-z]{2})\.csv$', f)))
LANGS = [PRIMARY] + extra


def name_map(path, col='name'):
    return {int(r['id']): r[col]
            for r in csv.DictReader(open(path, encoding='utf-8', errors='replace'))}


card_name = {PRIMARY: {i: r['name'] for i, r in rows.items()}}
cat_name = {PRIMARY: name_map(CATS)}
for lang in extra:
    card_name[lang] = name_map(os.path.join(CARDS_DIR, f'cards_{lang}.csv'))
    cat_name[lang] = name_map(os.path.join(CARDS_DIR, f'card_categories_{lang}.csv'))


def loc_name(table, cid):
    """Name of `cid` in every language, primary as fallback where a language lacks it."""
    return {lang: table[lang].get(cid, table[PRIMARY].get(cid)) for lang in LANGS}

out, replis = [], 0
for key, bases in chains.items():
    family = members.get(key) or list(bases)
    # The terminal form is the sink of the family's awakening graph — the member no other
    # member awakens into a further form of. Following the highest id instead breaks
    # whenever a Dokkan route awakens into a smaller id (Gotenks 1007931 → 1006211): the
    # album then drew the pre-Dokkan illustration. Among sinks (normally one), and if the
    # graph is silent, the old rule stands.
    fam = set(family)
    sinks = [x for x in family if not (awakens.get(x, set()) & fam)] or family
    top = max(sinks, key=lambda x: (int(rows[x]['rarity']), int(rows[x]['lv_max'] or 0), x))
    # the artwork belongs to the base of the terminal form's own ladder — its id rounded
    # down to the ten. When that one has no thumbnail, fall back to the best base we do have.
    art = top - top % 10
    if art not in have:
        art = max(bases, key=lambda x: (int(rows[x]['rarity']), x))
        replis += 1
    t = rows[top]
    cats = sorted(set().union(*(card_cats.get(f, set()) for f in family)))
    out.append({'id': art, 'name': loc_name(card_name, top), 'rarity': int(t['rarity']),
                'element': int(t['element']), 'lv': int(t['lv_max'] or 0),
                'top': top, 'forms': sorted(family), 'cats': cats,
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
            c['cats'] = sorted(set(c['cats']) | set(best['cats']))
            c['eza'] = max(c['eza'], best['eza']); c['ev'] = max(c['ev'], best['ev'])
        fusion[k] = c
    else:
        best['forms'] = sorted(set(best['forms']) | set(c['forms']))
        best['cats'] = sorted(set(best['cats']) | set(c['cats']))
        best['eza'] = max(best['eza'], c['eza']); best['ev'] = max(best['ev'], c['ev'])
fusionnees = len(out) - len(fusion)
out = list(fusion.values())
out.sort(key=lambda c: c['id'])
json.dump(out, open(os.path.join(GRD, 'cards.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
# only the categories a shown card actually carries, id → {lang: name}, for the filter's menu
used = sorted(set().union(*(set(c['cats']) for c in out)))
json.dump({str(i): loc_name(cat_name, i) for i in used if i in cat_name[PRIMARY]},
          open(os.path.join(GRD, 'cats.json'), 'w', encoding='utf-8'), ensure_ascii=False)
# the languages this build carries, in order — the page reads it to know whether to show a
# switch at all and which flags to offer
json.dump(LANGS, open(os.path.join(GRD, 'langs.json'), 'w', encoding='utf-8'))
from collections import Counter
R = ['N', 'R', 'SR', 'SSR', 'UR', 'LR']
print(f'{len(have)} vignettes → {len(out)} entrées · {fusionnees} formes suprêmes fusionnées '
      f'· {replis} sans illustration du sommet')
print('par rareté terminale :',
      {R[k]: v for k, v in sorted(Counter(c['rarity'] for c in out).items())})
