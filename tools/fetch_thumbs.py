"""Fetch every playable card's thumbnail from the public mirror.

Only the 10xxxxx range has artwork: the 9xxxxxx cards are enemies and the eight-digit ids
are items, and the mirror serves neither. Already-downloaded files are left alone, so this
can be re-run after a game update to pick up what is new.
"""
import csv, os, sys, threading, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'work', 'grid')
CSV = os.path.join(HERE, 'work', 'cards', 'cards.csv')
URL = ("https://dokkaninfo.com/assets/global/en/character/thumb/"
       "card_%07d_thumb/card_%07d_thumb.png")
LOW, HIGH = 1_000_000, 1_099_999

lock = threading.Lock()
done = {'ok': 0, 'absent': 0, 'erreur': 0, 'octets': 0}


def grab(cid):
    out = os.path.join(OUT, f'{cid}.png')
    if os.path.exists(out):
        return
    req = urllib.request.Request(URL % (cid, cid), headers={"User-Agent": "Mozilla/5.0"})
    for essai in range(2):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                blob = r.read()
            # the mirror answers 200 with an empty body for a handful of cards
            if not blob.startswith(b'\x89PNG'):
                with lock: done['absent'] += 1
                return
            tmp = out + '.part'                  # never leave a half file behind
            open(tmp, 'wb').write(blob)
            os.replace(tmp, out)
            with lock:
                done['ok'] += 1; done['octets'] += len(blob)
            return
        except urllib.error.HTTPError as e:
            if e.code == 404:
                with lock: done['absent'] += 1
                return
        except Exception:
            if essai:
                with lock: done['erreur'] += 1
    with lock:
        done['erreur'] += 1


def main():
    os.makedirs(OUT, exist_ok=True)
    ids = sorted({int(r['id']) for r in csv.DictReader(
        open(CSV, encoding='utf-8', errors='replace'))
        if int(r['id']) % 10 == 0 and LOW <= int(r['id']) <= HIGH})
    todo = [i for i in ids if not os.path.exists(os.path.join(OUT, f'{i}.png'))]
    print(f'{len(ids)} formes de base dans la tranche · {len(todo)} à récupérer', flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        for n, _ in enumerate(pool.map(grab, todo), 1):
            if n % 200 == 0:
                print(f'  {n}/{len(todo)} · {done["ok"]} pris · {done["absent"]} absents '
                      f'· {done["octets"]/1e6:.1f} Mo', flush=True)
    total = len([f for f in os.listdir(OUT) if f.endswith('.png')])
    print(f'terminé · {done["ok"]} pris, {done["absent"]} absents, {done["erreur"]} en erreur '
          f'· {done["octets"]/1e6:.1f} Mo · {total} vignettes en tout', flush=True)


if __name__ == '__main__':
    main()
