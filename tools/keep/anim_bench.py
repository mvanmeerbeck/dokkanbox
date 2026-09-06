"""Why an animated grid stalls: compare three ways of playing the same sprite strip."""
import base64, json, os, re, subprocess, sys, tempfile, time

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PAGE = '/Users/maxime/perso/dokkan/design/grille.html'

def payload(name):
    s = open(PAGE, encoding='utf-8').read()
    m = re.search(rf'<script id="{name}" type="application/json">', s)
    return s[m.end():s.index('</script>', m.end())]

ANIM = json.loads(payload('gAnim'))
A = ANIM['seza']

CSS = {
 # the inner band is n times as wide as its window and slides: composited by the GPU,
 # but the layer it needs is the whole strip at display size
 'translation': '''
  .c{position:relative;overflow:hidden;width:var(--w);height:var(--w)}
  .c>u{display:block;width:calc(var(--n)*100%);height:100%;background-size:100% 100%;
    background-image:var(--sheet);mix-blend-mode:plus-lighter;
    animation:p calc(var(--n)/30*1s) steps(var(--n)) infinite}
  @keyframes p{to{transform:translateX(-100%)}}''',
 # the window stays one frame wide and the background scrolls: no oversized layer,
 # but background-position is not composited, so every frame repaints
 'fond': '''
  .c{position:relative;overflow:hidden;width:var(--w);height:var(--w);
    background-size:calc(var(--n)*100%) 100%;background-image:var(--sheet);
    mix-blend-mode:plus-lighter;
    animation:p calc(var(--n)/30*1s) steps(var(--n),jump-none) infinite}
  @keyframes p{to{background-position-x:100%}}''',
 # same as the first, without the additive blend, to price the blend on its own
 'translation sans fusion': '''
  .c{position:relative;overflow:hidden;width:var(--w);height:var(--w)}
  .c>u{display:block;width:calc(var(--n)*100%);height:100%;background-size:100% 100%;
    background-image:var(--sheet);
    animation:p calc(var(--n)/30*1s) steps(var(--n)) infinite}
  @keyframes p{to{transform:translateX(-100%)}}''',
}

HTML = """<style>body{margin:0;background:#111}
 %(shared)s
 #g{display:grid;grid-template-columns:repeat(8,1fr)}
 .cell{position:relative;aspect-ratio:1}
 %(css)s</style><div id="g"></div>
<script>
 const g=document.getElementById('g');
 for(let i=0;i<%(n)d;i++){
   const d=document.createElement('div');d.className='cell';
   const c=document.createElement('div');c.className='c';
   c.style.setProperty('--n',%(frames)d);
   c.style.setProperty('--w','100%%');
   %(setsheet)s
   %(inner)s
   d.appendChild(c);g.appendChild(d);
 }
</script>"""

def run(name, css, n, inner, sheet=None, shared=False):
    sh = sheet or A['img']
    html = HTML % dict(css=css, n=n, frames=A['n'], inner=inner,
                       shared=(':root{--sheet:url(%s)}' % sh) if shared else '',
                       setsheet='' if shared else "c.style.setProperty('--sheet','url(%s)');" % sh)
    tmp = tempfile.mkdtemp(); p = os.path.join(tmp, 'b.html')
    open(p, 'w', encoding='utf-8').write(html)
    out = os.path.join(tmp, 's.png')
    t0 = time.time()
    subprocess.run([CHROME, '--headless=new', '--hide-scrollbars',
                    '--virtual-time-budget=4000', '--window-size=1200,900',
                    f'--screenshot={out}', 'file://' + p], capture_output=True)
    return time.time() - t0

# une planche réduite, pour isoler le coût de la matière plutôt que de la technique
import io
from PIL import Image
_raw = base64.b64decode(A['img'].split(',', 1)[1])
_im = Image.open(io.BytesIO(_raw)).convert('RGBA')
SHEETS = {'planche pleine': A['img']}
for k, f in (('planche /2', 0.5), ('planche /4', 0.25)):
    _s = _im.resize((max(1, int(_im.width * f)), max(1, int(_im.height * f))), Image.LANCZOS)
    _b = io.BytesIO(); _s.save(_b, 'PNG', optimize=True)
    SHEETS[k] = 'data:image/png;base64,' + base64.b64encode(_b.getvalue()).decode()
    print(f'  {k}: {_s.size} · {len(_b.getvalue())/1024:.0f} Ko')
print(f'  planche pleine: {_im.size} · {len(_raw)/1024:.0f} Ko\n')

for n in (0, 64, 200):
    print(f'{n:>4} tuiles animées')
    for name, css in CSS.items():
        inner = "c.appendChild(document.createElement('u'));" if 'u{' in css else ""
        secs = min(run(name, css, n, inner) for _ in range(2))
        print(f'     {name:26s} {secs:5.2f} s')
print()
print('la planche posée une fois dans la feuille de style, au lieu d’une copie par tuile')
for n in (64, 200, 475):
    a = min(run('par tuile', CSS['translation'], n, "c.appendChild(document.createElement('u'));") for _ in range(2))
    b = min(run('partagée', CSS['translation'], n, "c.appendChild(document.createElement('u'));", shared=True) for _ in range(2))
    print(f'   {n:>4} tuiles · une copie par tuile {a:5.2f} s · une seule copie {b:5.2f} s')

print()
print('200 tuiles créées, une partie masquée (l’animation continue, en phase)')
HID = CSS['translation'] + '\n.cell:nth-child(n+31) .c{visibility:hidden}'
for lab, css in (('toutes visibles', CSS['translation']), ('30 visibles sur 200', HID)):
    secs = min(run(lab, css, 200, "c.appendChild(document.createElement('u'));")
               for _ in range(2))
    print(f'     {lab:26s} {secs:5.2f} s')
HID2 = CSS['translation'] + '\n.cell:nth-child(n+31) .c{display:none}'
secs = min(run('display none', HID2, 200, "c.appendChild(document.createElement('u'));")
           for _ in range(2))
print(f'     {"30 sur 200, display:none":26s} {secs:5.2f} s')

print()
print('même technique (translation), planches de tailles différentes, 200 tuiles')
for k, sh in SHEETS.items():
    secs = min(run(k, CSS['translation'], 200, "c.appendChild(document.createElement('u'));", sh)
               for _ in range(2))
    print(f'     {k:26s} {secs:5.2f} s')
