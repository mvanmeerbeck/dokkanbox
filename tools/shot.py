"""Screenshot just the tile, pinned to the corner at a known size, so it lines up
pixel for pixel with the reference render."""
import os, subprocess, sys, tempfile

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PAGE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else '../design/vignette.html')
OUT = sys.argv[2] if len(sys.argv) > 2 else '/tmp/mine.png'
Z = int(sys.argv[3]) if len(sys.argv) > 3 else 6
# headless advances rAF timestamps but not LWF's clock, so a throwaway copy gets a
# fixed-step driver instead; FRAMES says how many frames to run before the shot
FRAMES = int(sys.argv[4]) if len(sys.argv) > 4 else 0
STATE = sys.argv[5] if len(sys.argv) > 5 else ''  
W, HH = 130 * Z, 150 * Z

shim = f"""<style>
html,body{{margin:0;padding:0;background:#12141a!important;overflow:hidden}}
.page{{margin:0!important;padding:0!important;max-width:none!important}}
.page>*{{display:none!important}}
.page .stage{{display:block!important;margin:0!important;padding:0!important;gap:0!important}}
.stage .side,.stage .caption{{display:none!important}}
.stage>div{{margin:0!important;padding:0!important}}
.tile{{position:fixed!important;left:0;top:0;width:{W}px!important;height:{HH}px!important;margin:0!important}}
</style>"""
html = open(PAGE, encoding='utf-8').read().replace('</style>', '</style>' + shim, 1)
if FRAMES:
    html = html.replace('lwf.exec((now - prev) / 1000); lwf.render(); prev = now;',
                        'if (window.__n-- > 0) { lwf.exec(1 / 30); lwf.render(); }')
    html = html.replace('requestAnimationFrame(step);', 'setTimeout(step, 4);')
    html = html.replace('<script id="tileImages"',
                        '<script>window.__n = %d;</script>\n<script id="tileImages"' % FRAMES)
if STATE:
    html = html.replace('  sync();\n})();',
                        '  Object.assign(state, %s); sync();\n})();' % STATE)
tmp = tempfile.mkdtemp()
p = os.path.join(tmp, 'iso.html')
open(p, 'w', encoding='utf-8').write(html)
subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars',
                '--virtual-time-budget=6000', f'--window-size={W},{HH}',
                f'--screenshot={OUT}', 'file://' + p], check=True, capture_output=True)
print(OUT)
