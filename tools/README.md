# Outils d'analyse du jeu

Le dossier de travail temporaire est purgé entre les sessions ; ces outils vivent donc ici.

- `elf.py` — lecture d'un ELF ARM64 : adresses ↔ offsets, recherche du code qui construit
  l'adresse d'une chaîne (ADRP+ADD), appelants d'une fonction (BL), et table de
  relocations, qui permet de retrouver les noms de classes C++ d'un binaire dépouillé.
- `disas.py` — désassemblage d'une plage, annoté avec les chaînes construites.
- `cpk.py` — archives CRIWARE (`@UTF`) et décompression CRILAYLA.
- `play.py` — rendu hors ligne d'une animation LWF par le lecteur officiel du jeu.

## Remonter au binaire

    cd work
    curl -sSL -A "Mozilla/5.0" "https://apkcombo.app/dragon-ball-z-dokkan-battle/com.bandainamcogames.dbzdokkanww/download/apk" -o ac.html
    # l'URL signée est dans un href="/r2?u=..." de cette page
    unzip -o dokkan.xapk config.arm64_v8a.apk
    unzip -o config.arm64_v8a.apk lib/arm64-v8a/libcocos2dcpp.so

Le lecteur LWF compilé se récupère depuis n'importe quelle page publiée qui l'embarque,
par exemple `design/animations-jouees.html`.

## Ce qui a été établi

L'étoile de potentiel de la vignette est `outgame/effect/icon_rare_20000`, séquences
`ef_002` (dorée) et `ef_003` (arc-en-ciel), 38 images à 30 i/s soit 1,27 s.

## La vignette d'une unité

- `browse.py` — arborescence du serveur d'images (dokkan-eclipse), par chemin.
- `build_vignette.py` — assemble `design/vignette.html` à partir de `vign_head.html`,
  `vign_body.html`, `vign_app.js` et des fichiers téléchargés dans `work/tile`.

Cadre **et** fond sont le même fichier, `character_thumb_bg/cha_base_%02d_%02d.png` ;
SSR, UR et LR partagent le leur. Le bandeau est `cha_base_bottom_%02d.png` (+ `_on`),
et son texte est écrit avec la police bitmap `custom/number/number.fnt` extraite de
`assets/fonts/fr.cpk`. Les coordonnées, elles, vivent dans `layout/json.cpk`, que le jeu
télécharge au premier lancement et qu'aucun miroir ne republie.
