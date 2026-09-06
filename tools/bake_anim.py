"""Bake a looping LWF timeline into a sprite strip, so a grid can play it with CSS only.

Running one LWF instance per tile means redrawing a canvas per tile per frame. The
timelines loop, so each is rendered once here, frame by frame, into a strip that a page
then steps through with `animation-timing-function: steps()` — no player, no canvas."""
import base64
import io
import json
import os
import subprocess
import sys
import tempfile

from PIL import Image

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PAGE = '/Users/maxime/perso/dokkan/design/vignette.html'

SHIM = """
<script>
window.__frames = [];
(function () {
  var done = false;
  function grab() {
    var c = Array.prototype.find.call(document.querySelectorAll('#tile canvas'),
              function (x) { return x.style.zIndex === '%(z)s'; });
    if (!c || !window.__lwf) { setTimeout(grab, 60); return; }
    // the root's own frame count is meaningless here: these timelines animate through
    // nested movies, so render a generous run and let the loop be found by content
    var n = %(fallback)d;
    for (var i = 0; i < n; i++) {
      window.__lwf.exec(1 / 30);
      window.__lwf.render();
      window.__frames.push(c.toDataURL('image/png'));
    }
    var o = document.createElement('div'); o.id = 'baked';
    o.textContent = JSON.stringify({ n: n, w: c.width, h: c.height, f: window.__frames });
    document.body.appendChild(o);
  }
  setTimeout(grab, 2500);
})();
</script>"""


def bake(z, fallback=240):
    html = open(PAGE, encoding='utf-8').read()
    # freeze the page's own driver and keep a handle on the instance we want
    html = html.replace('lwf.exec((now - prev) / 1000); lwf.render(); prev = now;', '')
    html = html.replace('requestAnimationFrame(step);', '')
    html = html.replace('        done(lwf);',
                        '        if (canvas.style.zIndex === "%s") window.__lwf = lwf;\n        done(lwf);' % z)
    html += SHIM % dict(z=z, fallback=fallback)
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, 'b.html')
    open(p, 'w', encoding='utf-8').write(html)
    r = subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--virtual-time-budget=30000',
                        '--dump-dom', 'file://' + p], capture_output=True, text=True)
    i = r.stdout.find('<div id="baked">')
    if i < 0:
        raise SystemExit(f'z={z} : rien cuit')
    seg = r.stdout[i + len('<div id="baked">'):]
    data = json.loads(seg[:seg.index('</div>')])
    frames = []
    for u in data['f']:
        frames.append(Image.open(io.BytesIO(base64.b64decode(u.split(',', 1)[1]))).convert('RGBA'))
    return loop(frames)


def loop(frames, settle=110, cap=48):
    """One turn of the steady loop, or a representative run when there is no loop.

    These timelines open with an entrance — the LR aura flares, the awaken star grows in —
    and only then settle. Baking from frame zero captures the entrance and makes the sprite
    pop when it wraps. So let the run settle, then find the period by matching the tail
    against itself. The awaken star loops exactly in 38 frames, the super awakening ring in
    48; the LR lightning has no period at all — it is close to random — so it simply takes
    a run of `cap` frames, where a wrap hides in the chaos."""
    import numpy as np
    small = [np.asarray(f.convert('L').resize((40, 40)), dtype=np.int16) for f in frames]
    s = min(settle, max(0, len(small) - 2 * cap - 4))
    best, bp = None, None
    for p in range(4, min(cap + 12, (len(small) - s) // 2)):
        d = float(np.mean([np.abs(small[s + i] - small[s + i + p]).mean() for i in range(p)]))
        if best is None or d < best:
            best, bp = d, p
    if bp and best <= 3.0:
        return frames[s:s + bp]
    # no period: choose the window whose two ends match best, so the wrap is least visible
    lo, hi = 60, max(61, len(small) - cap - 1)
    st = min(range(lo, hi), key=lambda k: float(np.abs(small[k] - small[k + cap]).mean()))
    return frames[st:st + cap]


def unpremultiply(im):
    """Turn an additive sprite into a straight-alpha one.

    These effects are drawn on opaque black and meant to be added to what is behind them.
    Baked as-is they carry a black square that only a blend mode can hide, and blend modes
    are at the mercy of whatever stacking context the page happens to build. Deriving the
    alpha from the intensity instead gives a sprite that composites correctly anywhere."""
    import numpy as np
    a = np.asarray(im.convert('RGBA'), dtype=np.float32)
    inten = a[:, :, :3].max(axis=2)
    alpha = np.clip(inten, 0, 255)
    with np.errstate(divide='ignore', invalid='ignore'):
        rgb = np.where(alpha[:, :, None] > 0, a[:, :, :3] * 255.0 / alpha[:, :, None], 0)
    out = np.dstack([np.clip(rgb, 0, 255), alpha]).astype('uint8')
    return Image.fromarray(out, 'RGBA')


def strip(frames, out, scale=0.5, additive=True):
    """one row of frames, cropped to the ink they share, optionally halved"""
    if additive:
        frames = [unpremultiply(f) for f in frames]
    box = None
    for f in frames:
        bb = f.getchannel('A').getbbox()
        if bb:
            box = bb if box is None else (min(box[0], bb[0]), min(box[1], bb[1]),
                                          max(box[2], bb[2]), max(box[3], bb[3]))
    if box is None:
        raise SystemExit('images vides')
    w, h = box[2] - box[0], box[3] - box[1]
    tw, th = max(1, int(w * scale)), max(1, int(h * scale))
    sheet = Image.new('RGBA', (tw * len(frames), th), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.paste(f.crop(box).resize((tw, th), Image.LANCZOS), (i * tw, 0))
    sheet.save(out, optimize=True)
    return dict(file=os.path.basename(out), frames=len(frames), w=tw, h=th,
                crop=box, src=(frames[0].width, frames[0].height), bytes=os.path.getsize(out))


if __name__ == '__main__':
    os.makedirs('work/baked', exist_ok=True)
    meta = {}
    for name, z in (('lr_aura', '4'), ('seza', '3'), ('pulse', '100')):
        fr = bake(z)
        meta[name] = strip(fr, f'work/baked/{name}.png')
        m = meta[name]
        print(f"  {name:10s} {m['frames']:>3} images · planche {m['w']}×{m['h']} "
              f"· {m['bytes']/1024:>6.0f} Ko · recadrage {m['crop']} de {m['src']}")
    json.dump(meta, open('work/baked/meta.json', 'w'), indent=1)
