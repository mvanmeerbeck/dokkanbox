"""Génère web/template.html : notre guideline de composants Dokkan.

Le but : voir tous les éléments recomposés depuis le jeu, à LA MÊME ÉCHELLE (1 unité de
maquette = 1 px), pour se rendre compte de leurs tailles les uns par rapport aux autres,
et piocher dedans. Chaque composant vient d'une maquette JSON du jeu
(tools/work/layout_json/…) et d'assets authentiques (miroir public + CPK extraits).

- Onglets : maquette common/btn_tab_03.json ; images common/btn/com_btn_tab_03_*.png
  récupérées du miroir dokkaninfo (202×62).
- Footer : le menu du bas déjà recomposé (menu-footer.html, LWF globalnavi_btn + com_foo_base),
  intégré à sa taille réelle par une iframe.

Ajouter un composant = une entrée dans COMPONENTS (une maquette + ses images).
"""
import json, os, re, urllib.request
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
LAY = os.path.join(HERE, 'work', 'layout_json')
WEB = os.path.join(HERE, '..', 'web')
TPL_ASSETS = os.path.join(WEB, 'template')          # assets propres à la guideline
MIRROR = 'https://dokkaninfo.com/assets/global/en/layout/en/image'
UA = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://dokkaninfo.com/'}

# La vraie police bitmap des boutons du jeu (BMFont : atlas .png + descripteur .fnt).
# Les glyphes de l'atlas portent DÉJÀ le style (crème, contour, relief), donc on rend le
# texte en découpant l'atlas — c'est le texte du jeu, au pixel près.
_BMDIR = os.path.join(HERE, 'work', 'fonts', 'out', 'fr', 'custom', 'btn_normal')


def _load_bmfont():
    fnt = open(os.path.join(_BMDIR, 'btn_normal.fnt')).read()
    atlas = Image.open(os.path.join(_BMDIR, 'btn_normal.png')).convert('RGBA')
    common = dict(re.findall(r'(\w+)=(-?\d+)', re.search(r'common .*', fnt).group()))
    chars = {}
    for line in re.findall(r'char id=.*', fnt):
        d = {k: int(v) for k, v in re.findall(r'(\w+)=(-?\d+)', line)}
        chars[d['id']] = d
    kern = {}
    for line in re.findall(r'kerning .*', fnt):
        d = {k: int(v) for k, v in re.findall(r'(\w+)=(-?\d+)', line)}
        kern[(d['first'], d['second'])] = d['amount']
    return atlas, chars, kern, int(common['lineHeight'])


_BM = _load_bmfont()


def _bmlabel_native_width(text, letterspace):
    _, chars, kern, _ = _BM
    pen, prev = 0, None
    for ch in text:
        c = chars.get(ord(ch))
        if not c:
            prev = ord(ch); continue
        if prev is not None:
            pen += kern.get((prev, ord(ch)), 0)
        pen += c['xadvance'] + letterspace
        prev = ord(ch)
    return max(1, pen)


def render_bmlabel_png(text, scale, letterspace, dst):
    """rend `text` avec la BMFont du jeu et l'écrit en PNG ; renvoie (w, h) affichés."""
    atlas, chars, kern, lineH = _BM
    pen, prev, glyphs = 0, None, []
    for ch in text:
        c = chars.get(ord(ch))
        if not c:
            prev = ord(ch); continue
        if prev is not None:
            pen += kern.get((prev, ord(ch)), 0)
        glyphs.append((c, pen)); pen += c['xadvance'] + letterspace
        prev = ord(ch)
    W, H = max(1, pen), lineH
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for c, px in glyphs:
        if c['width'] == 0:
            continue
        gl = atlas.crop((c['x'], c['y'], c['x'] + c['width'], c['y'] + c['height']))
        img.alpha_composite(gl, (px + c['xoffset'], c['yoffset']))
    dw, dh = max(1, round(W * scale)), round(H * scale)
    img.resize((dw, dh)).save(dst)
    return dw, dh


def render_action_buttons(cid):
    """Une rangée de boutons d'action de la box, en assets du jeu : base com_btn_01 (couleur
    par sémantique) + libellé rendu dans la police du jeu, auto-ajusté pour tenir dans la
    boîte du bouton (celle de btn_01.json : 224 × 54, centrée)."""
    actions = [('Exporter', 'green'), ('Importer', 'blue'), ('Tout décocher', 'red')]
    BW, BH, GAP = 262, 72, 24               # taille réelle de com_btn_01 + espace entre boutons
    BOX_W = 224                              # boîte du libellé (btn_01.json font_ok)
    W = len(actions) * BW + (len(actions) - 1) * GAP
    os.makedirs(os.path.join(TPL_ASSETS, 'labels'), exist_ok=True)
    els = []
    for i, (label, color) in enumerate(actions):
        fetch_image(f'common/btn/com_btn_01_{color}')
        bx = i * (BW + GAP)
        els.append(f'<img class="node" src="template/common/btn/com_btn_01_{color}.png" alt="" '
                   f'style="left:{bx}px;top:0;width:{BW}px;height:{BH}px">')
        # libellé : échelle qui le fait tenir dans la boîte (btn_normal est en taille 36)
        nat = _bmlabel_native_width(label, -1)
        scale = min(0.78, (BOX_W - 12) / nat)
        dst = os.path.join(TPL_ASSETS, 'labels', f'{cid}_{i}.png')
        lw, lh = render_bmlabel_png(label, scale, -1, dst)
        cx, cy = bx + BW / 2, BH / 2
        els.append(f'<img class="node" src="template/labels/{cid}_{i}.png" alt="{label}" '
                   f'style="left:{cx - lw / 2:.1f}px;top:{cy - lh / 2:.1f}px;'
                   f'width:{lw}px;height:{lh}px">')
    return W, BH, f'<div class="node-box" style="width:{W}px;height:{BH}px">{"".join(els)}</div>'


def fetch_image(rel):
    """télécharge layout/en/image/<rel>.png du miroir vers web/template/<rel>.png"""
    dst = os.path.join(TPL_ASSETS, rel + '.png')
    if os.path.exists(dst):
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    req = urllib.request.Request(f'{MIRROR}/{rel}.png', headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    open(dst, 'wb').write(data)
    print(f'  ↓ {rel}.png ({len(data)} o)')


def render_layout(name, lay):
    """une maquette JSON → un bloc HTML à sa taille réelle (1 unité = 1 px).

    Règle d'application du jeu : une image est dessinée à sa TAILLE NATIVE, centrée sur le
    centre de sa boîte (le w/h du nœud n'est que la boîte). Ici les images d'onglet sont
    déjà à leur taille native (202×62 = la boîte), donc image = boîte."""
    w, h = lay['w'], lay['h']
    els = []
    for nid, n in lay.items():
        if not isinstance(n, dict) or 'x' not in n:
            continue
        x, y, nw, nh = n['x'], n['y'], n['w'], n['h']
        t = n.get('type')
        if t == 'button':
            # état « normal » par défaut ; le 1er onglet est montré sélectionné
            img = n['selected'] if nid == 'btn_tab_01' else n['normal']
            for st in (n.get('selected'), n.get('normal')):
                if st:
                    fetch_image(st)
            src = img.replace('common/', 'template/common/') + '.png'
            # correction : chemin servi = template/<rel>.png
            src = 'template/' + img + '.png'
            els.append(f'<img class="node" src="{src}" alt="" '
                       f'style="left:{x}px;top:{y}px;width:{nw}px;height:{nh}px">')
        elif t == 'bmlabel':
            # libellés réels de l'écran « Renforcer » (la maquette générique porte un texte
            # japonais de remplissage), rendus avec la vraie police bitmap btn_normal du jeu
            fr = {'font_text_01': 'Entraînement', 'font_text_02': 'Éveil',
                  'font_text_03': 'Apt. de lien'}.get(nid, n.get('text', ''))
            os.makedirs(os.path.join(TPL_ASSETS, 'labels'), exist_ok=True)
            dst = os.path.join(TPL_ASSETS, 'labels', f'{name}_{nid}.png')
            lw, lh = render_bmlabel_png(fr, n.get('scale', 1.0), n.get('kerning', 0), dst)
            # centré dans la boîte du nœud (align/valign center du style text_button)
            cx, cy = x + nw / 2, y + nh / 2
            els.append(f'<img class="node" src="template/labels/{name}_{nid}.png" alt="{fr}" '
                       f'style="left:{cx - lw / 2:.1f}px;top:{cy - lh / 2:.1f}px;'
                       f'width:{lw}px;height:{lh}px">')
    return w, h, '\n      '.join(els)


# Les composants de la guideline. footer est spécial (LWF) → iframe.
COMPONENTS = [
    {'id': 'onglets3', 'titre': 'Onglets (3) — btn_tab_03',
     'source': 'common/btn_tab_03.json · com_btn_tab_03_*.png · texte : police du jeu btn_normal.fnt',
     'layout': 'common/btn_tab_03.json'},
]


def main():
    blocks = []

    # Footer (menu du bas) — via iframe, à sa taille réelle (852 × 144)
    blocks.append(('Menu du bas — footer',
                   'menu-footer.html · com_foo_base + LWF globalnavi_btn + police du jeu',
                   852, 144,
                   '<iframe class="stage-frame" src="menu-footer.html" '
                   'style="width:852px;height:144px" scrolling="no"></iframe>'))

    # Composants issus d'une maquette
    for c in COMPONENTS:
        lay = json.load(open(os.path.join(LAY, c['layout'])))
        w, h, inner = render_layout(c['id'], lay)
        blocks.append((c['titre'], c['source'], w, h,
                       f'<div class="node-box" style="width:{w}px;height:{h}px">{inner}</div>'))

    # Boutons d'action de la box (Exporter / Importer / Tout décocher)
    w, h, html = render_action_buttons('actions')
    blocks.append(('Actions box — exporter / importer / tout décocher',
                   'common/btn_01.json · com_btn_01_{green,blue,red}.png · texte : btn_normal.fnt',
                   w, h, html))

    cards = []
    for titre, source, w, h, html in blocks:
        cards.append(f'''  <section class="card">
    <div class="meta"><h2>{titre}</h2><span class="dim">{w} × {h} u</span></div>
    <p class="src">{source}</p>
    <div class="hold">
      {html}
    </div>
  </section>''')

    page = f'''<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dokkan — Guideline</title>
<style>
  :root{{--bg:#0b0e14;--panel:#141925;--line:#26304a;--text:#e7ecf6;--muted:#8895b3;--accent:#4aa3ff}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--text);
    font:400 15px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}}
  header{{padding:28px 22px 8px;max-width:980px;margin:0 auto}}
  h1{{font-size:24px;margin:0 0 4px;letter-spacing:-.01em}}
  header p{{color:var(--muted);margin:0;font-size:13.5px}}
  .wrap{{max-width:980px;margin:0 auto;padding:12px 22px 80px;display:flex;flex-direction:column;gap:22px}}
  .card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}}
  .meta{{display:flex;align-items:baseline;justify-content:space-between;gap:12px;
    padding:14px 16px 2px}}
  .meta h2{{font-size:15px;margin:0;font-weight:600}}
  .dim{{font:500 12px/1 ui-monospace,monospace;color:var(--accent);white-space:nowrap}}
  .src{{margin:0;padding:0 16px 12px;color:var(--muted);
    font:12px/1.4 ui-monospace,monospace;word-break:break-all}}
  /* le décor : une réglette de 100 u, damier léger, pour juger les tailles à l'œil.
     Tous les composants partagent la MÊME échelle (1 u = 1 px) → tailles comparables. */
  .hold{{position:relative;overflow:auto;padding:20px;
    background:
      repeating-linear-gradient(90deg,transparent 0,transparent 99px,#ffffff14 99px,#ffffff14 100px),
      repeating-linear-gradient(0deg,transparent 0,transparent 99px,#ffffff14 99px,#ffffff14 100px),
      #0d1220}}
  .node-box{{position:relative}}
  .node-box .node{{position:absolute}}
  /* libellés d'onglet (police du jeu approximée : gras arrondi) */
  .bmlabel{{position:absolute;display:flex;align-items:center;justify-content:center;
    color:#dfe6f2;font:700 22px/1 "Arial Rounded MT Bold","Arial Black",system-ui;
    text-shadow:0 1px 0 #0007}}
  .bmlabel.on{{color:#fff;text-shadow:0 1px 2px #0009}}
  .stage-frame{{border:0;display:block;background:transparent}}
  /* échelle : le contenu déborde en largeur sur petit écran → il défile dans sa carte,
     ce qui préserve l'échelle réelle (1 u = 1 px) plutôt que de fausser les tailles */
</style>
<header>
  <h1>Dokkan — Guideline</h1>
  <p>Composants recomposés depuis le jeu, tous à la même échelle : <b>1 unité de maquette = 1 px</b>.
     La grille de fond a un pas de 100 u. On pioche ici.</p>
</header>
<div class="wrap">
{chr(10).join(cards)}
</div>
</html>
'''
    open(os.path.join(WEB, 'template.html'), 'w', encoding='utf-8').write(page)
    print(f'web/template.html · {len(blocks)} composants')


if __name__ == '__main__':
    main()
