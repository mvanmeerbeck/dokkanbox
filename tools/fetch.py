"""Download a CDN file by its real path: the browser API hands out the epoch-stamped URL."""
import os, sys, urllib.request
import browse

def cdn_url(path):
    d, n = path.rsplit('/', 1)
    for it in browse.ls(d):
        if it.get('name') == n:
            return it['cdnUrl']
    raise FileNotFoundError(path)

def get(path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, path.rsplit('/', 1)[-1])
    req = urllib.request.Request(cdn_url(path), headers={
        "User-Agent": "Mozilla/5.0", "Referer": "https://dokkan-eclipse.com/"})
    with urllib.request.urlopen(req) as r, open(out, 'wb') as f:
        f.write(r.read())
    return out

if __name__ == '__main__':
    for p in sys.argv[2:]:
        print(get(p, sys.argv[1]))
