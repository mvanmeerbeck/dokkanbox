"""Génère le menu du bas (FooterMenuLayer) à partir de la maquette EXTRAITE DU BINAIRE.

Rien n'est deviné : les positions viennent de tools/extract_footer.py (footer_current.json),
lu dans libcocos2dcpp.so courant. Le fond com_foo_base y est à y=-55 (décalé vers le bas), et
les boutons dépassent au-dessus — c'est ce que montre le jeu. Les 5 boutons sont des timelines
du vrai LWF globalnavi_btn (ef_001..005 statiques, ef_006 = onglet actif animé). Sortie servie :
web/menu-footer.html + assets sous web/footer/.
"""
import base64, json, os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
LAY = json.load(open(os.path.join(HERE, 'work', 'footer', 'footer_current.json')))
FOOT = os.path.join(HERE, 'work', 'footer')
WEB = os.path.join(HERE, '..', 'web')
OUT = os.path.join(WEB, 'menu-footer.html')

import os as _os
BG_Y = float(_os.environ.get('BG_Y','')) if _os.environ.get('BG_Y') else None
W, H = 852, 350                     # l'extracteur ne connaît pas la taille du canevas ; c'est celle du footer
NODES = LAY['nodes']                # dict nom → nœud
def N(name): return NODES[name]

# timeline du LWF par bouton ; l'onglet actif (accueil) prend la version animée ef_006
BTN = [('fla_btn_home', 'ef_006', 'font_home', 'ACCUEIL'),
       ('fla_btn_team', 'ef_002', 'font_team', 'ÉQUIPE'),
       ('fla_btn_gasha', 'ef_003', 'font_gasha', 'INVOCATION'),
       ('fla_btn_shop', 'ef_004', 'font_shop', 'MAGASIN'),
       ('fla_btn_trade', 'ef_005', 'font_trade', 'ÉCHANGE')]
SPAN = 150                          # taille du canevas d'un bouton, en unités de maquette


def main():
    bg = N('img_footer_base')
    bgn = Image.open(os.path.join(FOOT, 'com_foo_base.png')).size    # 852 x 320, taille native
    # image dessinée à sa taille native, centrée sur le centre de sa boîte (règle des vignettes)
    _by = BG_Y if BG_Y is not None else bg['y']
    bcx, bcy = bg['x'] + bg['w'] / 2, _by + bg['h'] / 2
    bg_left = bcx - bgn[0] / 2
    bg_top = H - bcy - bgn[1] / 2                                     # repère bas-gauche → haut de page

    # bande visible : du haut des boutons jusque sous les libellés
    btn_top = min(H - (N(b)['y'] + N(b)['h'] / 2) - SPAN / 2 for b, *_ in BTN)
    lbl_bot = max(H - N(f)['y'] for *_, f, _ in [(0, 0, f, 0) for _, _, f, _ in BTN])
    STRIP = int(lbl_bot + 22)

    els = [f'<img id="bg" src="footer/com_foo_base.png" alt="" '
           f'style="left:{bg_left / W * 100:.4f}%;top:{bg_top / STRIP * 100:.4f}%;'
           f'width:{bgn[0] / W * 100:.4f}%;height:{bgn[1] / STRIP * 100:.4f}%">']

    btns = []
    for bname, ef, fname, label in BTN:
        b, fo = N(bname), N(fname)
        cx, cy = b['x'] + b['w'] / 2, b['y'] + b['h'] / 2            # centre du bouton
        left = (cx - SPAN / 2) / W * 100
        top = (H - cy - SPAN / 2) / STRIP * 100
        btns.append({'ef': ef, 'left': round(left, 4), 'top': round(top, 4),
                     'wpc': round(SPAN / W * 100, 4), 'hpc': round(SPAN / STRIP * 100, 4)})
        # libellé : à sa boîte
        lx, lw = fo['x'] / W * 100, fo['w'] / W * 100
        lt = (H - (fo['y'] + fo['h'])) / STRIP * 100
        lh = fo['h'] / STRIP * 100
        els.append(f'<div class="lbl" style="left:{lx:.4f}%;top:{lt:.4f}%;'
                   f'width:{lw:.4f}%;height:{lh:.4f}%">{label}</div>')

    # la vraie police du jeu (default.cpk de l'APK) : la version globale rend le style
    # FOT-NewRodinProN-EB en Helvetica Neue LT Condensed. On l'embarque et on applique le
    # style text_subtitle exact (styles.json) : taille 24, italique par cisaillement ~10°
    # (comme les chiffres), contour noir 2px, ombre noire.
    font_b64 = base64.b64encode(open(os.path.join(FOOT, 'dokkan_ui.otf'), 'rb').read()).decode()
    # contour de 2 unités : huit ombres portées autour du glyphe
    dirs = [(dx, dy) for dx in (-2, 0, 2) for dy in (-2, 0, 2) if (dx, dy) != (0, 0)]
    outline = ','.join(f'calc(var(--u)*{dx}) calc(var(--u)*{dy}) 0 #000' for dx, dy in dirs)
    html = f"""<!doctype html><meta charset="utf-8"><title>Menu Dokkan</title>
<style>
  @font-face{{font-family:DokkanUI;src:url(data:font/otf;base64,{font_b64}) format("opentype")}}
  html,body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#05070c}}
  .footer{{position:relative;width:min({W}px,100vw);aspect-ratio:{W}/{STRIP};overflow:hidden;
    --u:calc(min(100vw,{W}px)/{W})}}   /* 1 unité de maquette en px */
  .footer>*{{position:absolute}}
  .lbl{{display:flex;align-items:center;justify-content:center;color:#fff;white-space:nowrap;
    font-family:DokkanUI,"Arial Narrow",sans-serif;font-size:calc(var(--u)*24);
    transform:skewX(-10deg);   /* l'italique du jeu = cisaillement ~10°, pas une police oblique */
    z-index:50;   /* au-dessus des canevas de boutons, ajoutés après dans le DOM */
    text-shadow:{outline}}}
</style>
<div class="footer" id="f">
{chr(10).join('  ' + e for e in els)}
</div>
<script src="footer/lwf.js"></script>
<script>
LWF.useCanvasRenderer();
const BTN={json.dumps(btns)};
const R=2, insts=[], f=document.getElementById('f');
for(const b of BTN){{
  const cv=document.createElement('canvas'); cv.width=cv.height={SPAN}*R;
  cv.style.cssText='position:absolute;left:'+b.left+'%;top:'+b.top+'%;width:'+b.wpc+'%;height:'+b.hpc+'%';
  f.appendChild(cv);
  LWF.ResourceCache.get().loadLWF({{lwf:'globalnavi_btn.lwf',prefix:'footer/',worker:false,stage:cv,
    onload:lwf=>{{ if(!lwf)return; lwf.rendererFactory.clearColor=null;
      lwf.rootMovie.moveTo({SPAN}*R/2,{SPAN}*R/2); lwf.rootMovie.scaleTo(R,R);
      lwf.rootMovie.attachMovie(b.ef,'m'); lwf.exec(0); lwf.render(); insts.push(lwf); }}}});
}}
// les canevas sont ajoutés après les libellés : on remet les libellés en dernier pour
// qu'ils passent devant les hexagones (le z-index seul ne suffit pas, le skew des libellés
// crée son propre contexte d'empilement)
f.querySelectorAll('.lbl').forEach(l=>f.appendChild(l));
let prev=performance.now();
(function tick(now){{ let dt=(now-prev)/1000; prev=now; if(!(dt>0)||dt>0.1) dt=1/60;
  for(const l of insts){{ l.exec(dt); l.render(); }} requestAnimationFrame(tick); }})(prev);
</script>
"""
    open(OUT, 'w', encoding='utf-8').write(html)
    print(f'{os.path.relpath(OUT, HERE)} · bande {W}x{STRIP} · com_foo_base à y={bg["y"]} '
          f'(haut à {bg_top:.0f}px) · {len(BTN)} boutons')


if __name__ == '__main__':
    main()
