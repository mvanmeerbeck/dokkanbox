"""Put the page's tile beside the reference render, and show where they disagree."""
import subprocess, sys
from PIL import Image, ImageChops, ImageDraw
import render_ref

Z = 6
subprocess.run([sys.executable, 'shot.py', '../design/vignette.html', '/tmp/mine.png', str(Z)], check=True)
mine = Image.open('/tmp/mine.png').convert('RGBA')
ref = render_ref.render(Z=Z, **eval(sys.argv[1]) if len(sys.argv) > 1 else {})
bg = Image.new('RGBA', ref.size, (18, 20, 26, 255))
ref_flat = Image.alpha_composite(bg, ref)
mine = mine.resize(ref.size, Image.LANCZOS)

diff = ImageChops.difference(mine.convert('RGB'), ref_flat.convert('RGB')).convert('L')
heat = Image.merge('RGB', (diff, Image.new('L', diff.size, 0), Image.new('L', diff.size, 0)))
heat = Image.blend(ref_flat.convert('RGB'), heat, 0.75)

pad, lab = 12, 22
W = ref.width * 3 + pad * 4
out = Image.new('RGB', (W, ref.height + pad * 2 + lab), (18, 20, 26))
d = ImageDraw.Draw(out)
for i, (t, im) in enumerate([('ma page', mine.convert('RGB')),
                             ('référence (binaire)', ref_flat.convert('RGB')),
                             ('écart', heat)]):
    x = pad + i * (ref.width + pad)
    out.paste(im, (x, pad + lab))
    d.text((x, 6), t, fill=(235, 235, 235))
out.save('/tmp/compare.png')
print('/tmp/compare.png', out.size, '· écart moyen', round(sum(diff.getdata()) / (diff.width * diff.height), 2))
