"""Put the page beside the reference across several states, and score each one."""
import subprocess, sys
from PIL import Image, ImageChops, ImageDraw
import render_ref

Z = 6
STATES = [
    ('base · SSR · 4 étoiles', "{rare:3,stars:4}",            dict(rare=3, stars=4)),
    ('éveillée · niveau max',  "{rare:3,stars:3,awakened:true,maxlv:true}",
                                dict(rare=3, stars=3, awakened=True, maxlevel=True)),
    ('taux d’apparition',      "{rare:3,stars:4,band:'rate'}", dict(rare=3, stars=4, band='rate')),
    ('LR · 5 étoiles',         "{rare:5,stars:5}",             dict(rare=5, stars=5)),
]
rows, scores = [], []
for i, (name, js, kw) in enumerate(STATES):
    out = f'/tmp/audit_{i}.png'
    subprocess.run([sys.executable, 'shot.py', '../design/vignette.html', out, str(Z), '0', js],
                   check=True, capture_output=True)
    mine = Image.open(out).convert('RGBA')
    ref = render_ref.render(Z=Z, **kw)
    ref = Image.alpha_composite(Image.new('RGBA', ref.size, (18, 20, 26, 255)), ref)
    diff = ImageChops.difference(mine.convert('RGB'), ref.convert('RGB')).convert('L')
    heat = Image.merge('RGB', (diff, Image.new('L', diff.size, 0), Image.new('L', diff.size, 0)))
    heat = Image.blend(ref.convert('RGB'), heat, 0.8)
    import numpy as np
    scores.append((name, float(np.array(diff).mean())))
    rows.append((name, [mine.convert('RGB'), ref.convert('RGB'), heat]))

pad, lab = 10, 18
w = rows[0][1][0].width
out = Image.new('RGB', (w * 3 + pad * 4, (rows[0][1][0].height + lab + pad) * len(rows) + pad),
                (18, 20, 26))
d = ImageDraw.Draw(out)
y = pad
for name, ims in rows:
    d.text((pad, y), name + '   —   ma page · référence · écart', fill=(235, 235, 235))
    for j, im in enumerate(ims):
        out.paste(im, (pad + j * (w + pad), y + lab))
    y += ims[0].height + lab + pad
out.save('/tmp/audit.png')
for n, sc in scores:
    print(f'  {n:26s} écart moyen {sc:5.2f}')
print('/tmp/audit.png', out.size)
