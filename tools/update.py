"""La mise à jour de bout en bout, en une commande.

Après une sortie de cartes dans le jeu, tout se refait dans l'ordre :

    1. fetch_data     les tables du jeu (cartes, éveils, catégories)     → work/cards/
    2. fetch_thumbs    les vignettes manquantes, depuis le miroir         → work/grid/
    3. make_cards      les chaînes d'éveil, une entrée par illustration   → work/grid/cards.json
    4. build           la page servie et ses assets                       → web/

Chaque étape n'agit que sur ce qui a changé : fetch_thumbs ne tire que les vignettes
absentes, le build réécrit web/ en entier. Une étape qui échoue arrête la chaîne — inutile
de bâtir la page sur des données à moitié récupérées.

    python tools/update.py            # tout, jusqu'à la page servie
    python tools/update.py --data     # seulement les données (étapes 1 à 3)
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable                       # le même interprète, donc le même venv

ETAPES = [
    ('récupérer les tables du jeu', ['fetch_data.py']),
    ('récupérer les vignettes',      ['fetch_thumbs.py']),
    ('reconstruire les chaînes',     ['make_cards.py']),
]
BUILD = ('reconstruire la page servie', ['build_grid_lwf.py', '5000', '--web'])


def run(titre, cmd):
    print(f'\n\033[1m▸ {titre}\033[0m  ({" ".join(cmd)})', flush=True)
    r = subprocess.run([PY, os.path.join(HERE, cmd[0]), *cmd[1:]], cwd=HERE)
    if r.returncode:
        raise SystemExit(f'\n✗ échec à « {titre} » — chaîne arrêtée')


def main():
    etapes = list(ETAPES)
    if '--data' not in sys.argv:
        etapes.append(BUILD)
    for titre, cmd in etapes:
        run(titre, cmd)
    print('\n\033[32m✓ à jour\033[0m')


if __name__ == '__main__':
    main()
