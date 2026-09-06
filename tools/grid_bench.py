"""Two ways of animating the same grid, priced side by side.

Chrome is given a fixed budget of virtual time: the wall clock it needs to simulate that
budget is the rendering work. Same page content, same cards, same three timelines — the
only difference is who plays them, CSS on a strip per tile or one LWF instance copied
into a single overlay.
"""
import os, subprocess, sys, tempfile, time

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PAGES = [("planches (CSS)", "../design/grille.html"),
         ("lwf partagé",    "../design/grille-lwf.html")]
BUDGET = 6000


def prep(path, demo, scroll):
    s = open(path, encoding="utf-8").read()
    i = s.rindex("  sync();\n})();")
    s = (s[:i] + ("  Object.assign(state,{demo:%s});\n" % ("true" if demo else "false"))
         + s[i:])
    if scroll:
        s += "<script>scrollTo(0,%d)</script>" % scroll
    p = os.path.join(tempfile.mkdtemp(), "b.html")
    open(p, "w", encoding="utf-8").write(s)
    return p


def run(page, demo, scroll):
    p = prep(page, demo, scroll)
    out = p + ".png"
    t0 = time.time()
    subprocess.run([CHROME, "--headless=new", "--hide-scrollbars",
                    "--virtual-time-budget=%d" % BUDGET, "--window-size=1280,900",
                    "--screenshot=" + out, "file://" + p], capture_output=True)
    return time.time() - t0


here = os.path.dirname(os.path.abspath(__file__))
print("%d ms de temps virtuel simulés · 475 cartes · fenêtre 1280x900\n" % BUDGET)
for label, demo, scroll in (("haut de page, animations réelles", False, 0),
                            ("haut de page, tout animé", True, 0),
                            ("défilé à 6000 px, tout animé", True, 6000)):
    print(label)
    for name, rel in PAGES:
        path = os.path.join(here, rel)
        secs = min(run(path, demo, scroll) for _ in range(2))
        print("     %-16s %5.2f s" % (name, secs))
    print()
