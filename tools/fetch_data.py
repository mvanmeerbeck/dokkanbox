"""Extrait les tables du jeu depuis VOTRE base locale, sans dépendre d'un tiers.

La base maître du jeu (`work/db/database.db`, tirée du BlueStacks) est chiffrée en SQLCipher.
Son mot de passe n'est pas dans les fichiers du jeu : le serveur le fournit au téléchargement,
et il change à chaque version. On le donne ici (ou via la variable d'environnement
DOKKAN_DB_PW), et sqlcipher fait le reste — on exporte chaque table en CSV, comme le faisait
l'export public, mais depuis chez soi.

Vérifié contre cet export public : mêmes valeurs, colonne pour colonne, sur toutes les cartes
communes ; la base locale est même plus propre (des entiers, pas les flottants de pandas).

    python tools/fetch_data.py                 # mot de passe par défaut (v6.5.5)
    DOKKAN_DB_PW=<hex> python tools/fetch_data.py   # une autre version

Le mot de passe d'une version se trouve dans le `settings.json` du Dokkan Asset Downloader
(clé `GlbDbPassword`), ou se capture au vol sur un appareil qui télécharge la base.
"""
import os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'work', 'db', 'database.db')
OUT = os.path.join(HERE, 'work', 'cards')
# Mot de passe SQLCipher de la base Global, version 6.5.5. Propre à la version : à changer
# après une mise à jour du jeu (voir le docstring). C'est une passphrase, pas une clé brute.
PW = os.environ.get('DOKKAN_DB_PW',
                    '25bf95b8dcb8389da20e146e67620308457b1450e3d0f2abdf8bf390b305ad16')

# table → ce qu'elle alimente dans le pipeline
NEEDED = {
    'cards':                 'la carte elle-même : nom, rareté, type, niveau',
    'card_awakening_routes': "les chaînes d'éveil (Zet / Dokkan / EZA)",
    'card_categories':       'le nom des catégories',
    'card_card_categories':  'le lien carte → catégorie',
}


def sqlcipher(sql):
    """Lance sqlcipher sur la base, script SQL en entrée. Renvoie (code, sortie)."""
    fd, path = tempfile.mkstemp(suffix='.sql')
    with os.fdopen(fd, 'w') as f:
        f.write(f'PRAGMA key = "{PW}";\n{sql}\n')
    try:
        r = subprocess.run(['sqlcipher', DB, '-init', path, '.quit'],
                           capture_output=True, text=True, timeout=120)
        return r.returncode, (r.stdout + r.stderr)
    finally:
        os.unlink(path)


def main():
    if not shutil.which('sqlcipher'):
        raise SystemExit('sqlcipher introuvable — `brew install sqlcipher`')
    if not os.path.exists(DB):
        raise SystemExit(f'base absente : {DB}\n'
                         "(extraire database.db du BlueStacks au préalable)")
    os.makedirs(OUT, exist_ok=True)

    # une lecture témoin : le mot de passe ouvre-t-il bien la base ?
    code, out = sqlcipher("SELECT count(*) FROM sqlite_master WHERE type='table';")
    if 'not a database' in out or code != 0:
        raise SystemExit('le mot de passe ne déchiffre pas cette base — '
                         'version du jeu ≠ mot de passe ? (voir DOKKAN_DB_PW)')
    print(f'base déchiffrée · {out.strip().splitlines()[-1]} tables')

    total = 0
    for nom, role in NEEDED.items():
        dest = os.path.join(OUT, nom + '.csv')
        # export CSV atomique : on écrit dans un fichier temporaire que sqlcipher remplit,
        # puis on le bascule en place — une coupure ne laisse pas un CSV tronqué.
        fd, tmp = tempfile.mkstemp(dir=OUT, suffix='.csv'); os.close(fd)
        code, out = sqlcipher(f'.headers on\n.mode csv\n.output {tmp}\nSELECT * FROM {nom};')
        head = open(tmp, encoding='utf-8').readline()
        if code != 0 or ',' not in head:
            os.unlink(tmp)
            raise SystemExit(f'  {nom} : export échoué — {out.strip()[:120]}')
        os.replace(tmp, dest)
        lignes = sum(1 for _ in open(dest, encoding='utf-8')) - 1
        total += lignes
        print(f'  {nom:26} {lignes:>7} lignes  · {role}')
    print(f'{len(NEEDED)} tables, {total} lignes → {os.path.relpath(OUT, HERE)}/')


if __name__ == '__main__':
    main()
