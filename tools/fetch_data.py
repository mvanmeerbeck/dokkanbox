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
import os, re, shutil, subprocess, sys, tempfile

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


# Seules ces deux tables portent des noms traduits ; les autres (relations, éveils) sont les
# mêmes dans toutes les langues. Une langue secondaire n'en fournit donc que celles-là, sous
# cards_<lang>.csv / card_categories_<lang>.csv, que make_cards lit pour ses noms.
LOCALIZED = ['cards', 'card_categories']


def sqlcipher(db, sql):
    """Lance sqlcipher sur `db`, script SQL en entrée. Renvoie (code, sortie)."""
    fd, path = tempfile.mkstemp(suffix='.sql')
    with os.fdopen(fd, 'w') as f:
        f.write(f'PRAGMA key = "{PW}";\n{sql}\n')
    try:
        r = subprocess.run(['sqlcipher', db, '-init', path, '.quit'],
                           capture_output=True, text=True, timeout=120)
        return r.returncode, (r.stdout + r.stderr)
    finally:
        os.unlink(path)


def exporter(db, table, dest):
    """Exporte une table en CSV, de façon atomique."""
    fd, tmp = tempfile.mkstemp(dir=OUT, suffix='.csv'); os.close(fd)
    code, out = sqlcipher(db, f'.headers on\n.mode csv\n.output {tmp}\nSELECT * FROM {table};')
    if code != 0 or ',' not in open(tmp, encoding='utf-8').readline():
        os.unlink(tmp)
        raise SystemExit(f'  {os.path.basename(dest)} : export échoué — {out.strip()[:120]}')
    os.replace(tmp, dest)
    return sum(1 for _ in open(dest, encoding='utf-8')) - 1


def dechiffrable(db):
    code, out = sqlcipher(db, "SELECT 1 FROM sqlite_master LIMIT 1;")
    return code == 0 and 'not a database' not in out


def main():
    if not shutil.which('sqlcipher'):
        raise SystemExit('sqlcipher introuvable — `brew install sqlcipher`')
    if not os.path.exists(DB):
        raise SystemExit(f'base absente : {DB}\n(lancer extract_db.py au préalable)')
    os.makedirs(OUT, exist_ok=True)
    if not dechiffrable(DB):
        raise SystemExit('le mot de passe ne déchiffre pas cette base — '
                         'version du jeu ≠ mot de passe ? (voir DOKKAN_DB_PW)')

    # la base primaire : toutes les tables (structure + noms de sa langue)
    total = 0
    for nom, role in NEEDED.items():
        n = exporter(DB, nom, os.path.join(OUT, nom + '.csv'))
        total += n
        print(f'  {nom:26} {n:>7} lignes  · {role}')

    # les langues secondaires : leurs bases figées sur le disque, juste les tables traduites,
    # pour que la page offre le bouton de langue
    autres = 0
    for f in sorted(os.listdir(os.path.dirname(DB))):
        m = re.match(r'database_([a-z]{2})\.db$', f)
        if not m:
            continue
        lang, dbp = m.group(1), os.path.join(os.path.dirname(DB), f)
        if not dechiffrable(dbp):
            print(f'  [{lang}] ignorée : mot de passe différent'); continue
        for table in LOCALIZED:
            exporter(dbp, table, os.path.join(OUT, f'{table}_{lang}.csv'))
        autres += 1
        print(f'  [{lang}] noms traduits ajoutés (cards_{lang}, card_categories_{lang})')
    print(f'{len(NEEDED)} tables + {autres} langue(s) secondaire(s) → {os.path.relpath(OUT, HERE)}/')


if __name__ == '__main__':
    main()
