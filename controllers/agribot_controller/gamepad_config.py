"""Réglages de la manette pour agribot_controller (Webots, appareil Joystick).

Modifier ce fichier pour adapter les numéros de boutons/axes à votre manette et à votre système.
Les numéros bruts s'affichent avec DEBUG = True (ou la variable d'environnement
AGRIBOT_GAMEPAD_DEBUG=1) : appuyer sur chaque bouton / pousser chaque stick et lire la console Webots.

Correspondance convenue (17 oct., identique au robot réel ESP32 + Bluepad32) :
  L1            bascule mode Roues <-> mode Bras (en mode Bras le robot ne roule pas)
  R1 maintenu   homme mort : sans R1, ni roues ni servos ne bougent
  Mode Roues    (firmware etape_E/esp32/agribot_esp32/manette.cpp)
                stick gauche vertical = avance / recul, stick droit horizontal = rotation
                G = v + w, D = v - w, limité à 60 % (MOTEUR_MAX_POURMILLE 600)
                Triangle = Attente (arrêt), Options = retour au dock (non simulé), PS = mode Manuel
  Mode Bras     stick gauche X = S1 base, stick gauche Y = S2 épaule,
                stick droit Y = S3 coude, stick droit X = S4 poignet,
                Croix / Carré = ouvrir / fermer la pince (S5), Triangle = pose repos/transport
  Rond          ARRÊT D'URGENCE (verrouillé ; réarmement : bouton PS ou Share)
"""

# "auto" : choisi d'après le nom de la manette et le système ; sinon un nom de PROFILES.
PROFILE = "auto"
# Affiche les numéros bruts des boutons et des axes (pour remapper).
DEBUG = False

DEADZONE = 0.15            # fraction de la course du stick ignorée autour du centre
DRIVE_SCALE = 0.60         # 60 % de la vitesse max des roues, comme MOTEUR_MAX_POURMILLE = 600 / 1000

# Vitesse des servos stick à fond (rad/s) ; le servo garde sa position stick relâché.
ARM_RATES = {
    "S1_lacet": 0.8,
    "S2_epaule": 0.6,
    "S3_coude": 0.6,
    "S4_poignet": 0.8,
}
GRIPPER_RATE = 1.2         # rad/s pour ouvrir / fermer la pince
REST_RATE = 0.8            # rad/s max par articulation pour rejoindre la pose repos (Triangle)
# Sens : +1 ou -1 pour inverser une articulation si elle part dans le mauvais sens.
ARM_SIGNS = {
    "S1_lacet": -1.0,      # stick à droite = la base tourne vers la droite (lacet négatif)
    "S2_epaule": 1.0,
    "S3_coude": 1.0,
    "S4_poignet": 1.0,
}
# Stick (axe logique) -> articulation, en mode Bras.
ARM_AXES = {
    "S1_lacet": "lx",
    "S2_epaule": "ly",
    "S3_coude": "ry",
    "S4_poignet": "rx",
}
# Pose repos / transport (position 0 des servos = pose repos CAO v9b).
REST_POSE = {"S1_lacet": 0.0, "S2_epaule": 0.0, "S3_coude": 0.0, "S4_poignet": 0.0, "S5_pince": 0.0}
GRIP_OPEN = -0.70
GRIP_CLOSED = 0.0
REARM_BUTTONS = ("ps", "share")

# Profils : numéros bruts Webots (0..) des boutons, et axes {nom: (numéro, inversé)}.
# Après normalisation, stick vers le HAUT / vers la DROITE = +1.
PROFILES = {
    # DualShock 4 en DirectInput (Windows, câble USB ou Bluetooth sans DS4Windows).
    "ps4_windows": {
        "buttons": {"square": 0, "cross": 1, "circle": 2, "triangle": 3, "l1": 4, "r1": 5,
                    "l2": 6, "r2": 7, "share": 8, "options": 9, "l3": 10, "r3": 11, "ps": 12, "touchpad": 13},
        "axes": {"lx": (0, False), "ly": (1, True), "rx": (2, False), "ry": (5, True)},
    },
    # DualShock 4 sous Linux (pilote hid-sony / hid-playstation).
    "ps4_linux": {
        "buttons": {"cross": 0, "circle": 1, "triangle": 2, "square": 3, "l1": 4, "r1": 5,
                    "l2": 6, "r2": 7, "share": 8, "options": 9, "ps": 10, "l3": 11, "r3": 12},
        "axes": {"lx": (0, False), "ly": (1, True), "rx": (3, False), "ry": (4, True)},
    },
    # Manette Xbox / XInput (ou PS4 via DS4Windows qui émule une Xbox 360) sous Windows.
    # A = Croix, B = Rond, X = Carré, Y = Triangle, LB = L1, RB = R1, Back = Share, Start = Options.
    "xbox_windows": {
        "buttons": {"cross": 0, "circle": 1, "square": 2, "triangle": 3, "l1": 4, "r1": 5,
                    "share": 6, "options": 7, "l3": 8, "r3": 9, "ps": 10},
        "axes": {"ly": (0, True), "lx": (1, False), "ry": (2, True), "rx": (3, False)},
    },
}
