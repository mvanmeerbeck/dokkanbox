"""Génère le menu du bas (FooterMenuLayer) fidèle au rendu du jeu.

Assets 100 % authentiques : le fond com_foo_base (852×320, extrait des CPK), les boutons =
timelines du vrai LWF globalnavi_btn (home→ef_001 … trade→ef_005 ; ef_006 = accueil sélectionné
animé), la police black.otf du jeu, et le style de libellé text_subtitle (styles.json : taille 24,
italique ~10°, contour noir 2px, ombre portée).

Placement : la maquette statique extraite du binaire (footer_current.json) est retransformée par
le jeu à l'exécution (les boutons y sont étalés ~×1.3 par rapport aux nœuds font_*), donc on ne
peut pas la copier telle quelle. On reproduit ce que le JEU AFFICHE, mesuré sur une capture du
jeu : 5 colonnes régulières sur toute la largeur, boutons à leur taille native, libellés dessous.
Ce sont les seules valeurs de cadrage ; tout le reste (dessins, police, style) vient du jeu.
"""
import base64, json, os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FOOT = os.path.join(HERE, 'work', 'footer')
WEB = os.path.join(HERE, '..', 'web')
OUT = os.path.join(WEB, 'menu-footer.html')


def env(name, default): return float(os.environ.get(name, default))

W = 852.0                                  # largeur du footer (= com_foo_base), en px de page
FH = env('FH', 144)                        # hauteur de la bande visible, en unités de page

# 5 colonnes régulières, mesurées sur le rendu du jeu (centres en fraction de largeur)
COLS = [0.092, 0.296, 0.500, 0.704, 0.908]

BTN_CY = env('BTN_CY', 65)                 # centre vertical des boutons (unités depuis le haut)
LBL_CY = env('LBL_CY', 114)                # centre vertical des libellés
FONT_SZ = env('FONT_SZ', 29)               # taille de police (unités)
LBL_W = env('LBL_W', 165)                  # largeur de boîte d'un libellé (unités)
LBL_H = env('LBL_H', 34)

CW = env('CW', 150)                        # boîte de canevas d'un bouton (unités)
CH = env('CH', 150)
BTN_SCALE = env('BTN_SCALE', 1.0)         # échelle des hexagones (1 = natif)
BG_TOP = env('BG_TOP', 72)                 # bord HAUT du fond com_foo_base (unités depuis le haut ;
                                           # mesuré dans le jeu : le vert commence à 115u au-dessus
                                           # du bas, soit 50u sous le haut de la bande)

BTN = [('ef_006', 'ACCUEIL'), ('ef_002', 'ÉQUIPE'), ('ef_003', 'INVOCATION'),
       ('ef_004', 'MAGASIN'), ('ef_005', 'ÉCHANGE')]


def px(u):   return u / W * 100                       # unité horizontale → %
def py(u):   return u / FH * 100                       # unité verticale → %


def main():
    bgn = Image.open(os.path.join(FOOT, 'com_foo_base.png')).size   # 852 × 320
    # fond dessiné à l'échelle native (852 de large = pleine largeur), ancré par son bord haut ;
    # il est plus haut que la bande visible, le surplus déborde sous l'écran comme dans le jeu
    els = [f'<img id="bg" src="footer/com_foo_base.png" alt="" '
           f'style="left:0;top:{py(BG_TOP):.4f}%;'
           f'width:100%;height:{py(bgn[1]):.4f}%">']

    btns = []
    for (ef, label), frac in zip(BTN, COLS):
        cx = frac * W
        btns.append({'ef': ef,
                     'left': round(px(cx - CW / 2), 4), 'top': round(py(BTN_CY - CH / 2), 4),
                     'wpc': round(px(CW), 4), 'hpc': round(py(CH), 4)})
        els.append(f'<div class="lbl" style="left:{px(cx - LBL_W / 2):.4f}%;'
                   f'top:{py(LBL_CY - LBL_H / 2):.4f}%;'
                   f'width:{px(LBL_W):.4f}%;height:{py(LBL_H):.4f}%">{label}</div>')

    # police du jeu : la source nomme black.otf pour ces libellés (poids Black condensé du
    # default.cpk). Contour 2 u = huit ombres portées ; ombre du style = une ombre vers le bas.
    font_b64 = base64.b64encode(open(os.path.join(FOOT, 'dokkan_ui_black.otf'), 'rb').read()).decode()
    dirs = [(dx, dy) for dx in (-2, 0, 2) for dy in (-2, 0, 2) if (dx, dy) != (0, 0)]
    outline = ','.join(f'calc(var(--u)*{dx}) calc(var(--u)*{dy}) 0 #000' for dx, dy in dirs)
    shadow = 'calc(var(--u)*0) calc(var(--u)*2) calc(var(--u)*1) #000'

    html = f"""<!doctype html><meta charset="utf-8"><title>Menu Dokkan</title>
<style>
  @font-face{{font-family:DokkanUI;src:url(data:font/otf;base64,{font_b64}) format("opentype")}}
  html,body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#05070c}}
  .footer{{position:relative;width:min({W:.0f}px,100vw);aspect-ratio:{W:.0f}/{FH:.0f};
    overflow:hidden;--u:calc(min(100vw,{W:.0f}px)/{W:.0f})}}   /* 1 unité en px */
  .footer>*{{position:absolute}}
  .lbl{{display:flex;align-items:center;justify-content:center;color:#fff;white-space:nowrap;
    font-family:DokkanUI,"Arial Narrow",sans-serif;font-size:calc(var(--u)*{FONT_SZ:.0f});line-height:1;
    transform:skewX(-10deg);   /* l'italique du jeu = cisaillement ~10° */
    z-index:50;   /* au-dessus des canevas de boutons, remis en dernier dans le DOM */
    text-shadow:{outline},{shadow}}}
</style>
<div class="footer" id="f">
{chr(10).join('  ' + e for e in els)}
</div>
<script src="footer/lwf.js"></script>
<script>
LWF.useCanvasRenderer();
const BTN={json.dumps(btns)};
const R=2, K={BTN_SCALE:.3f}, CWpx={CW:.0f}*R, CHpx={CH:.0f}*R, insts=[], f=document.getElementById('f');
for(const b of BTN){{
  const cv=document.createElement('canvas'); cv.width=CWpx; cv.height=CHpx;
  cv.style.cssText='position:absolute;left:'+b.left+'%;top:'+b.top+'%;width:'+b.wpc+'%;height:'+b.hpc+'%';
  f.appendChild(cv);
  LWF.ResourceCache.get().loadLWF({{lwf:'globalnavi_btn.lwf',prefix:'footer/',worker:false,stage:cv,
    onload:lwf=>{{ if(!lwf)return; lwf.rendererFactory.clearColor=null;
      lwf.rootMovie.moveTo(CWpx/2,CHpx/2); lwf.rootMovie.scaleTo(R*K,R*K);  /* échelle native */
      lwf.rootMovie.attachMovie(b.ef,'m'); lwf.exec(0); lwf.render(); insts.push(lwf); }}}});
}}
// les canevas sont ajoutés après les libellés : on remet les libellés en dernier pour qu'ils
// passent devant les hexagones (le skew crée son propre contexte d'empilement)
f.querySelectorAll('.lbl').forEach(l=>f.appendChild(l));
let prev=performance.now();
(function tick(now){{ let dt=(now-prev)/1000; prev=now; if(!(dt>0)||dt>0.1) dt=1/60;
  for(const l of insts){{ l.exec(dt); l.render(); }} requestAnimationFrame(tick); }})(prev);
</script>
"""
    open(OUT, 'w', encoding='utf-8').write(html)
    print(f'{os.path.relpath(OUT, HERE)} · {W:.0f}×{FH:.0f} u · colonnes {COLS} · '
          f'boutons y={BTN_CY:.0f} · libellés y={LBL_CY:.0f}')


if __name__ == '__main__':
    main()
