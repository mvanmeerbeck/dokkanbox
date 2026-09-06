"""Récupère les tables du jeu dont l'album a besoin, depuis l'export public de la base.

La base du jeu (`database.db`) est chiffrée en SQLCipher, avec une clé calculée à
l'exécution. Plutôt que de la re-dériver à chaque mise à jour, on tire les mêmes tables
d'un export public qui les republie en CSV : `Nicholas1006/dokkan-backend`. C'est la même
donnée, colonne pour colonne, que celle des CSV déjà présents.

Une seule liste à tenir, `NEEDED` : le fichier, et ce qu'il alimente. En ajouter un revient
à ajouter une ligne. Chaque téléchargement est vérifié (200, et un en-tête CSV) et écrit de
façon atomique, pour qu'un échec réseau ne laisse pas un fichier tronqué derrière lui.

    python tools/fetch_data.py            # depuis la branche par défaut (main)
    python tools/fetch_data.py master     # depuis une autre branche, au besoin
"""
import json, os, sys, tempfile, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'work', 'cards')
REPO = 'Nicholas1006/dokkan-backend'
BRANCH = sys.argv[1] if len(sys.argv) > 1 else 'main'
RAW = f'https://raw.githubusercontent.com/{REPO}/{BRANCH}/data/{{}}'
API = f'https://api.github.com/repos/{REPO}'

# fichier → ce qu'il alimente dans le pipeline
NEEDED = {
    'cards.csv':                 'la carte elle-même : nom, rareté, type, niveau',
    'card_awakening_routes.csv': "les chaînes d'éveil (Zet / Dokkan / EZA)",
    'card_categories.csv':       'le nom des catégories',
    'card_card_categories.csv':  'le lien carte → catégorie',
}


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {'User-Agent': 'dokkanbox'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def fraicheur():
    """La date du dernier push du dépôt : à quel point la donnée est récente."""
    try:
        return json.loads(get(API))['pushed_at']
    except Exception:
        return '?'


def main():
    os.makedirs(OUT, exist_ok=True)
    print(f'source {REPO}@{BRANCH} · export daté du {fraicheur()}')
    total = 0
    for nom, role in NEEDED.items():
        data = get(RAW.format(nom))
        tete = data[:200].lstrip()
        if not tete or b',' not in tete.split(b'\n', 1)[0]:
            raise SystemExit(f'  {nom} : réponse inattendue, pas un CSV — abandon')
        # écriture atomique : le fichier final n'apparaît qu'une fois complet
        fd, tmp = tempfile.mkstemp(dir=OUT)
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.replace(tmp, os.path.join(OUT, nom))
        lignes = data.count(b'\n')
        total += lignes
        print(f'  {nom:28} {lignes:>7} lignes  · {role}')
    print(f'{len(NEEDED)} tables, {total} lignes au total → {os.path.relpath(OUT, HERE)}/')


if __name__ == '__main__':
    main()
