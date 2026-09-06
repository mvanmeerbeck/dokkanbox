import json, sys, urllib.request
EPOCH = 1787989675
BASE = "https://dokkan-eclipse.com/api/file-browser"
CDN  = "https://cdn.dokkan-eclipse.com/uncompressed"

def get(path, epoch=EPOCH):
    u = f"{BASE}?path={urllib.parse.quote(path)}&epoch={epoch}"
    r = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(r))

def ls(path, epoch=EPOCH):
    d = get(path, epoch)
    if "items" not in d: return []
    return d["items"]

if __name__ == "__main__":
    for it in ls(sys.argv[1] if len(sys.argv) > 1 else ""):
        print(f"{it['type'][:3]:>3} {it.get('size') or '':>9}  {it['path']}")
