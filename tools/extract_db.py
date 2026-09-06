"""Sort les bases maîtresses du jeu du disque BlueStacks, sans root ni ADB.

C'était le maillon manquant du process de mise à jour : la base était tirée à la main.
BlueStacks range l'Android dans un qcow2 ; `qcow2.py` + `ext4.py` le lisent à la volée
(la partition /data est en ext4 à l'offset 0x100000). Le jeu télécharge une base par langue
sous `files/assets/sqlite/current/<lang>/database.db`, mais **ne tient à jour que la langue
courante** — les autres sont figées à leur dernier usage. On lit donc la langue courante dans
les préférences Cocos, on la pose comme base primaire (work/db/database.db), et on sort aussi
les autres langues présentes pour plus tard.

    python tools/extract_db.py

Le mot de passe pour ouvrir ces bases est propre à la version — voir tools/fetch_data.py.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qcow2 import Qcow2, Window
from ext4 import Ext4

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'work', 'db')
QCOW = ("/Users/Shared/Library/Application Support/BlueStacks/Engine/Tiramisu64/data.qcow2")
PART = 0x100000                       # partition ext4 (secteur 2048)
PKG = "data/com.bandainamcogames.dbzdokkanww"
SQLITE = PKG + "/files/assets/sqlite/current"


def langue_courante(fs):
    """La langue que le jeu tient à jour, lue dans les préférences Cocos."""
    try:
        xml = fs.cat(PKG + '/shared_prefs/Cocos2dxPrefsFile.xml').decode('utf-8', 'replace')
        m = re.search(r'name="CurrentUsingLanguage"[^>]*>([a-z]{2})<', xml)
        if m:
            return m.group(1)
    except Exception:
        pass
    return 'en'


def main():
    if not os.path.exists(QCOW):
        raise SystemExit(f'disque BlueStacks introuvable : {QCOW}')
    os.makedirs(OUT, exist_ok=True)
    fs = Ext4(Window(Qcow2(QCOW), PART))
    cur = langue_courante(fs)
    langs = sorted(fs.listdir(fs.resolve(SQLITE)))
    print(f'langue courante (à jour) : {cur} · langues présentes : {langs}')
    for lang in langs:
        data = fs.cat(f'{SQLITE}/{lang}/database.db')
        # la langue courante devient la base primaire ; les autres gardent leur suffixe
        dest = os.path.join(OUT, 'database.db' if lang == cur else f'database_{lang}.db')
        open(dest, 'wb').write(data)
        etat = 'à jour' if lang == cur else 'figée'
        print(f'  {lang} : {len(data)/1e6:.1f} Mo → {os.path.relpath(dest, HERE)} ({etat})')
    open(os.path.join(OUT, 'lang.txt'), 'w').write(cur)   # la langue de la base primaire
    print(f'primaire : {cur} (work/db/lang.txt)')


if __name__ == '__main__':
    main()
