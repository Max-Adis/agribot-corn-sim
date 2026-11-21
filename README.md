# AGRI-BOT – simulation Webots R2025a

Mondes : `worlds/agribot_parcelle.wbt` (parcelle clôturée, dock, borne, benne) et `worlds/corn_field.wbt`.
Contrôleur du robot : `controllers/agribot_controller` (clavier, manette, désherbage auto touche P).

## Piloter avec une manette

### Installation et branchement
1. Brancher la manette **avant** d'ouvrir le monde dans Webots : une PS4 (DualShock 4) en USB,
   ou en Bluetooth appairée dans Windows. Une manette Xbox (ou une PS4 via DS4Windows) marche aussi.
2. Ouvrir `worlds/agribot_parcelle.wbt` (ou `corn_field.wbt`). Rien d'autre à installer.
3. La console Webots affiche : `Manette détectée : « … », N axes, profil …`.
   Sinon (`Aucune manette détectée`), rebrancher la manette puis recharger le monde (Ctrl+Maj+R).
4. Cliquer dans la vue 3D garde le clavier actif : clavier et manette marchent ensemble.

### Correspondance (identique au robot réel ESP32 + Bluepad32)
| Commande | Mode Roues | Mode Bras |
|---|---|---|
| **L1** | passer en mode Bras | passer en mode Roues |
| **R1 maintenu** | homme mort : sans R1 rien ne bouge | homme mort : sans R1 rien ne bouge |
| Stick gauche ↕ | avance / recul | S2 épaule |
| Stick gauche ↔ | – | S1 base (rotation) |
| Stick droit ↕ | – | S3 coude |
| Stick droit ↔ | rotation sur place / virage | S4 poignet |
| Croix / Carré | ouvrir / fermer la pince | ouvrir / fermer la pince (S5) |
| Triangle | Attente (arrêt, coupe le mode auto) | pose repos / transport |
| **Rond** | **ARRÊT D'URGENCE** | **ARRÊT D'URGENCE** |
| PS | mode manuel (coupe le mode auto), réarme l'arrêt d'urgence | idem |
| Share | réarme l'arrêt d'urgence | idem |
| Options | retour au dock (non simulé) | – |

- En mode Bras le robot ne roule pas, ni à la manette ni au clavier.
- Les servos bougent lentement tant que le stick est poussé et gardent leur position au relâché.
  Butées du proto respectées. Croix / Carré / Triangle s'exécutent tant que R1 est maintenu.
- Roues : gauche = v + w, droite = v − w, limité à 60 % comme le firmware (`DRIVE_SCALE`).
- Arrêt d'urgence : roues stoppées net, bras figé, clavier bloqué, mode auto coupé, jusqu'au réarmement.

### Mode debug (numéros bruts)
Mettre `DEBUG = True` dans `controllers/agribot_controller/gamepad_config.py` (ou lancer Webots avec la
variable d'environnement `AGRIBOT_GAMEPAD_DEBUG=1`), recharger le monde, puis appuyer sur chaque bouton
et pousser chaque stick. La console affiche par exemple :
`[manette debug] boutons bruts [5] -> ['r1'] | axes bruts (|v|>0,15) 1:-1.00`.

### Remapper
Dans `gamepad_config.py` :
- `PROFILE = "auto"` choisit `ps4_windows` (DirectInput), `xbox_windows` (XInput / DS4Windows) ou
  `ps4_linux` d'après le nom de la manette ; forcer un nom de profil si le choix est mauvais.
- Dans `PROFILES[...]["buttons"]`, mettre pour chaque bouton le numéro brut lu en mode debug ;
  dans `["axes"]`, `(numéro, inversé)` : inversé = True si le stick vers le haut donne une valeur négative.
- `ARM_SIGNS` inverse le sens d'une articulation, `ARM_RATES` / `GRIPPER_RATE` règlent les vitesses,
  `DEADZONE` (0,15) la zone morte, `DRIVE_SCALE` la vitesse des roues.

### Tests sans manette
`python3 -m unittest discover tests` (logique : homme mort, verrou de mode, butées, pince, pose repos,
arrêt d'urgence). Rejeu dans Webots : lancer Webots avec la variable d'environnement
`AGRIBOT_GAMEPAD_REPLAY=tests/gamepad_replay.json` (chemin absolu conseillé). Le contrôleur affiche
alors une ligne `MANETTE_ETAT` toutes les 0,5 s.
