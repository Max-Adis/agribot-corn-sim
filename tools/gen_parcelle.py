"""Génère la parcelle clôturée AGRI-BOT (monde validé « preview_v2 ») :
textures procédurales (protos/textures/), PROTOs réutilisables (protos/) et
worlds/agribot_parcelle.wbt. Chemins relatifs uniquement. Usage : python3 tools/gen_parcelle.py
Dépendances : numpy, Pillow."""
import math, os, random
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "protos"); T = os.path.join(P, "textures"); W = os.path.join(ROOT, "worlds")
os.makedirs(T, exist_ok=True)
rng = np.random.default_rng(11); random.seed(11)
HDR = "#VRML_SIM R2025a utf8\n"

# ---------------------------------------------------------------- textures
def noise(n, scales):
    out = np.zeros((n, n))
    for s, a in scales:
        small = rng.random((n // s, n // s))
        out += a * np.array(Image.fromarray((small * 255).astype(np.uint8)).resize((n, n), Image.BICUBIC)) / 255.0
    return out / sum(a for _, a in scales)
def save(arr, name, blur=0.6, q=92):
    Image.fromarray((arr.clip(0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur)).save(os.path.join(T, name), quality=q)
v = noise(1024, [(64, 0.3), (16, 0.3), (4, 0.2), (1, 0.2)])
a, b = np.array([0.26, 0.52, 0.14]), np.array([0.40, 0.68, 0.22])
save(a * (1 - v[..., None]) + b * v[..., None], "gazon.jpg", 0.4)
v = noise(1024, [(128, 0.3), (32, 0.3), (8, 0.2), (2, 0.2)])
fur = 0.5 + 0.5 * np.sin(np.arange(1024) / 1024 * 2 * math.pi * 24)[:, None] * np.ones((1, 1024))
v = 0.85 * v + 0.15 * fur
a, b = np.array([0.50, 0.36, 0.23]), np.array([0.66, 0.50, 0.34])
save(a * (1 - v[..., None]) + b * v[..., None], "terre.jpg")
v = noise(256, [(64, 0.5), (8, 0.5)])
grain = 0.5 + 0.5 * np.sin(np.linspace(0, 40, 256)[:, None] + 3 * v)
a, b = np.array([0.40, 0.26, 0.14]), np.array([0.60, 0.42, 0.25])
save(a * (1 - grain[..., None]) + b * grain[..., None], "bois.jpg", 0.5)
im = Image.new("RGB", (256, 128), (12, 30, 50)); d = ImageDraw.Draw(im)
d.rectangle([40, 40, 190, 88], outline=(220, 240, 255), width=5); d.rectangle([190, 54, 202, 74], fill=(220, 240, 255))
d.rectangle([50, 50, 150, 78], fill=(70, 220, 110)); d.text((60, 98), "AGRI-BOT  80 %", fill=(220, 240, 255))
im.save(os.path.join(T, "ecran.png"))
# béton : même tirage que l'aperçu v1 (graine 7, après les textures de latérite et d'abords)
r7 = np.random.default_rng(7)
for n_, scales in ((1024, (128, 32, 8, 2)), (None, None), (1024, (128, 32, 8, 2)), (1024, (128, 32))):
    if n_ is None:
        r7.random((1024, 1024)); continue
    for s_ in scales:
        r7.random((n_ // s_, n_ // s_))
rng_saved, rng = rng, r7
c = noise(512, [(64, 0.4), (16, 0.35), (4, 0.25)]); g = 0.62 + 0.16 * (c - 0.5)
rng = rng_saved
Image.fromarray((np.dstack([g, g, g * 0.97]).clip(0, 1) * 255).astype(np.uint8)).save(os.path.join(T, "beton.jpg"), quality=92)

# ---------------------------------------------------------------- helpers
def shape(geom, color, rough=0.7, metal=0.0, extra=""):
    return f"Shape {{ appearance PBRAppearance {{ baseColor {color} roughness {rough} metalness {metal} {extra}}} geometry {geom} }}"
def pose(t, r, child):
    return f"Pose {{ translation {t} rotation {r} children [ {child} ] }}"
def tex(name, ts=None):
    s = f'baseColorMap ImageTexture {{ url [ "textures/{name}" ] }}'
    return s + (f" textureTransform TextureTransform {{ scale {ts} }}" if ts else "")
def bshape(t, size, color, rough=0.6, metal=0.0, extra="", rot="0 0 1 0"):
    return pose(t, rot, f"Shape {{ appearance PBRAppearance {{ baseColor {color} roughness {rough} metalness {metal} {extra} }} geometry Box {{ size {size} }} }}")
def bbox(t, size, rot="0 0 1 0"):
    return pose(t, rot, f"Box {{ size {size} }}")
def write_proto(fname, text):
    open(os.path.join(P, fname), "w").write(text)

# ---------------------------------------------------------------- CornPlantV8
leaves = []
for k in range(10):
    z = 0.07 + 0.065 * k; az = (k * 2.4) % (2 * math.pi)
    L1 = 0.075 - 0.002 * k; L2 = 0.11 - 0.004 * k; up = 0.95 - 0.02 * k
    app = "DEF LEAF PBRAppearance { baseColor IS leafColor roughness 0.55 metalness 0 }" if k == 0 else "USE LEAF"
    seg1 = pose(f"{L1/2:.3f} 0 0", "0 0 1 0", f"Shape {{ appearance {app} geometry Box {{ size {L1:.3f} 0.032 0.003 }} }}")
    seg2 = pose(f"{L1:.3f} 0 0", "0 1 0 1.25", pose(f"{L2/2:.3f} 0 0", "0 0 1 0", f"Shape {{ appearance USE LEAF geometry Box {{ size {L2:.3f} 0.024 0.003 }} }}"))
    leaves.append(pose(f"0 0 {z:.3f}", f"0 0 1 {az:.3f}", f"Pose {{ rotation 0 1 0 {-up:.3f} children [ {seg1} {seg2} ] }}"))
write_proto("CornPlantV8.proto", HDR + """# Maïs jeune stade ~V8 : ~0,85 m de haut, emprise ~25 cm, feuilles arquées.
# Collision légère : cylindre de la tige seulement (statique, pas de Physics).
PROTO CornPlantV8 [
  field SFVec3f    translation 0 0 0
  field SFRotation rotation    0 0 1 0
  field SFString   name        "corn"
  field SFColor    leafColor   0.20 0.58 0.15
  field SFColor    stalkColor  0.30 0.52 0.18
]
{
  Solid {
    translation IS translation
    rotation IS rotation
    name IS name
    children [
""" + "\n".join(leaves + [
    pose("0 0 0.375", "0 0 1 0", "Shape { appearance PBRAppearance { baseColor IS stalkColor roughness 0.7 metalness 0 } geometry Cylinder { height 0.75 radius 0.013 subdivision 8 } }"),
    pose("0 0 0.765", "0 0 1 0", "Shape { appearance USE LEAF geometry Cone { bottomRadius 0.010 height 0.06 subdivision 6 } }")]) + """
    ]
    boundingObject Pose { translation 0 0 0.375 children [ Cylinder { height 0.75 radius 0.013 } ] }
  }
}
""")

# ---------------------------------------------------------------- adventices
def rosette(nleaf, length, width, color, tilt, z=0.005, rot0=0.0):
    return [pose(f"0 0 {z}", f"0 0 1 {rot0 + 2*math.pi*k/nleaf:.3f}", pose(f"{length/2*math.cos(tilt):.3f} 0 {length/2*math.sin(tilt):.3f}", f"0 1 0 {-tilt:.3f}",
            shape(f"Box {{ size {length:.3f} {width:.3f} 0.003 }}", color, 0.6))) for k in range(nleaf)]
SPECIES = {
    "Gomphrena": ("Gomphrena celosioides : rosette prostrée vert moyen (~16 cm, h ~3 cm).",
                  rosette(9, 0.08, 0.022, "0.36 0.62 0.24", 0.15) + rosette(5, 0.05, 0.018, "0.44 0.70 0.30", 0.5, 0.01, 0.3), 0.05, 0.03),
    "Acalypha": ("Acalypha indica : touffe dressée basse, feuilles larges vert clair (h ~7 cm).",
                 rosette(6, 0.07, 0.04, "0.48 0.76 0.30", 0.55) + rosette(4, 0.05, 0.035, "0.54 0.80 0.34", 0.9, 0.02, 0.4), 0.04, 0.07),
    "Euphorbia": ("Euphorbia prostrata : tapis ras de fines tiges (h ~1 cm).",
                  rosette(12, 0.09, 0.012, "0.30 0.52 0.22", 0.05) + rosette(8, 0.06, 0.010, "0.36 0.56 0.24", 0.10, 0.008, 0.2), 0.05, 0.015),
    "Croton": ("Croton hirtus : touffe gris-vert (h ~8 cm).",
               rosette(7, 0.07, 0.03, "0.46 0.58 0.40", 0.7) + rosette(5, 0.05, 0.028, "0.52 0.64 0.46", 1.0, 0.02, 0.5), 0.04, 0.08),
    "Commelina": ("Commelina : rosette lancéolée vert foncé (h ~5 cm).",
                  rosette(7, 0.10, 0.02, "0.16 0.48 0.18", 0.30, 0.005, 0.2) + rosette(4, 0.07, 0.018, "0.20 0.54 0.20", 0.6, 0.015), 0.05, 0.05),
}
for sp, (comment, body, r, h) in SPECIES.items():
    write_proto(f"Weed{sp}.proto", HDR + f"""# {comment}
# Adventice préhensible : nom « weed… » (reconnu par agribot_controller), petit cylindre de
# collision (r {r} m, h {h} m) désactivable via « collision », Physics optionnelle (NULL = statique,
# déplacée par le superviseur lors de la saisie).
PROTO Weed{sp} [
  field SFVec3f    translation 0 0 0
  field SFRotation rotation    0 0 1 0
  field SFString   name        "weed_{sp.lower()}"
  field SFBool     collision   TRUE
  field SFNode     physics     NULL
]
{{
  Solid {{
    translation IS translation
    rotation IS rotation
    name IS name
    children [
{chr(10).join(body)}
    ]
    %< if (fields.collision.value) {{ >%
    boundingObject Pose {{ translation 0 0 {h/2:.4f} children [ Cylinder {{ height {h} radius {r} }} ] }}
    %< }} >%
    physics IS physics
  }}
}}
""")

# ---------------------------------------------------------------- butte
write_proto("CornRidge.proto", HDR + """# Butte de culture : dessus 25 cm, pied 29 cm, hauteur 8 cm (au-dessus du sol), longueur réglable.
PROTO CornRidge [
  field SFVec3f    translation 0 0 0
  field SFRotation rotation    0 0 1 0
  field SFString   name        "ridge"
  field SFFloat    length      6.4
]
{
  %< const L = fields.length.value; >%
  Solid {
    translation IS translation
    rotation IS rotation
    name IS name
    children [
      Pose { translation 0 0 0.02 children [ Shape { appearance PBRAppearance { baseColor 0.97 0.95 0.93 baseColorMap ImageTexture { url [ "textures/terre.jpg" ] } roughness 1 metalness 0 textureTransform TextureTransform { scale %<= (3 * L / 6.4).toFixed(2) >% 0.15 } } geometry Box { size %<= (L + 0.04).toFixed(3) >% 0.29 0.04 } } ] }
      Pose { translation 0 0 0.04 children [ Shape { appearance PBRAppearance { baseColor 1 1 1 baseColorMap ImageTexture { url [ "textures/terre.jpg" ] } roughness 1 metalness 0 textureTransform TextureTransform { scale %<= (3 * L / 6.4).toFixed(2) >% 0.12 } } geometry Box { size %<= L.toFixed(3) >% 0.25 0.08 } } ] }
    ]
    boundingObject Group { children [
      Pose { translation 0 0 0.02 children [ Box { size %<= (L + 0.04).toFixed(3) >% 0.29 0.04 } ] }
      Pose { translation 0 0 0.04 children [ Box { size %<= L.toFixed(3) >% 0.25 0.08 } ] }
    ] }
  }
}
""")

# ---------------------------------------------------------------- clôture
write_proto("WoodFence3Rail.proto", HDR + """# Côté de clôture bois : poteaux 10x10 cm h 1,10 m, 3 lisses (0,30 / 0,62 / 0,94 m), le long de +X.
PROTO WoodFence3Rail [
  field SFVec3f    translation 0 0 0
  field SFRotation rotation    0 0 1 0
  field SFString   name        "fence"
  field SFFloat    length      9.6
  field SFInt32    segments    5
]
{
  %< const L = fields.length.value; const n = fields.segments.value; const H = 1.1; const R = [0.30, 0.62, 0.94]; >%
  Solid {
    translation IS translation
    rotation IS rotation
    name IS name
    children [
      DEF WOOD_POST Shape { appearance PBRAppearance { baseColor 1 1 1 baseColorMap ImageTexture { url [ "textures/bois.jpg" ] } roughness 0.9 metalness 0 textureTransform TextureTransform { scale 0.3 1 } } geometry Box { size 0.10 0.10 1.1 } }
      %< for (let i = 0; i <= n; ++i) { >%
      Pose { translation %<= (L * i / n).toFixed(4) >% 0 %<= H / 2 >% children [ USE WOOD_POST ] }
      %< } >%
      %< for (const h of R) { >%
      Pose { translation %<= (L / 2).toFixed(4) >% 0 %<= h >% children [ Shape { appearance PBRAppearance { baseColor 1 1 1 baseColorMap ImageTexture { url [ "textures/bois.jpg" ] } roughness 0.9 metalness 0 textureTransform TextureTransform { scale %<= (L / 1.5).toFixed(1) >% 0.2 } } geometry Box { size %<= (L + 0.10).toFixed(3) >% 0.035 0.09 } } ] }
      %< } >%
    ]
    boundingObject Group { children [
      %< for (let i = 0; i <= n; ++i) { >%
      Pose { translation %<= (L * i / n).toFixed(4) >% 0 %<= H / 2 >% children [ Box { size 0.10 0.10 1.1 } ] }
      %< } >%
      %< for (const h of R) { >%
      Pose { translation %<= (L / 2).toFixed(4) >% 0 %<= h >% children [ Box { size %<= (L + 0.10).toFixed(3) >% 0.035 0.09 } ] }
      %< } >%
    ] }
  }
}
""")

# ---------------------------------------------------------------- dock (origine = centre de la place, au niveau du sol)
SH = 0.10   # dalle
Y = "0.95 0.78 0.10"
dock = [bshape(f"0 -0.2 {SH/2}", f"1.6 3.6 {SH}", "1 1 1", 0.9, 0, tex("beton.jpg", "2 4"))]
for (t, s) in (("0 0.35", "1.10 0.04 0.003"), ("0 -0.35", "1.10 0.04 0.003"), ("-0.55 0", "0.04 0.74 0.003"), ("0.55 0", "0.04 0.74 0.003")):
    dock.append(bshape(f"{t} {SH+0.0015:.4f}", s, Y, 0.8))
for s in (1, -1):
    dock.append(bshape(f"-0.1 {s*0.30:.2f} {SH+0.025:.3f}", "0.80 0.03 0.05", "0.55 0.57 0.60", 0.4, 0.8))
dock.append(bshape(f"-0.56 0 {SH+0.06:.3f}", "0.06 0.50 0.12", "0.15 0.15 0.15", 0.8))
# rampe béton côté rangs (pente 0,10 m sur 0,50 m) pour sortir / remonter sur la dalle
RL, RT = 0.50, 0.04; ang = math.atan2(SH, RL); Ls = math.hypot(SH, RL)
rc = (0.8 + RL / 2 - RT / 2 * math.sin(ang), SH / 2 - RT / 2 * math.cos(ang))
ramp_rot = f"0 1 0 {ang:.4f}"
dock.append(bshape(f"{rc[0]:.4f} 0 {rc[1]:.4f}", f"{Ls+0.01:.3f} 0.70 {RT}", "0.95 0.95 0.95", 0.9, 0, tex("beton.jpg", "0.5 0.8"), rot=ramp_rot))
dock_bo = [bbox(f"0 -0.2 {SH/2}", f"1.6 3.6 {SH}"), bbox(f"-0.1 0.30 {SH+0.025:.3f}", "0.80 0.03 0.05"), bbox(f"-0.1 -0.30 {SH+0.025:.3f}", "0.80 0.03 0.05"),
           bbox(f"-0.56 0 {SH+0.06:.3f}", "0.06 0.50 0.12"), bbox(f"{rc[0]:.4f} 0 {rc[1]:.4f}", f"{Ls+0.01:.3f} 0.70 {RT}", ramp_rot)]
write_proto("AgribotDock.proto", HDR + """# Dock AGRI-BOT (départ / arrivée) : dalle béton 1,6 x 3,6 m (h 0,10 m), place de parc jaune
# 1,10 x 0,70 m, 2 rails de guidage bas (y ±0,30 m), butée arrière, rampe d'accès 0,5 m côté +X.
# Origine = centre de la place au niveau du sol ; le robot s'y gare à z = +0,10 m, face à +X.
PROTO AgribotDock [
  field SFVec3f    translation 0 0 0
  field SFRotation rotation    0 0 1 0
  field SFString   name        "dock"
]
{
  Solid {
    translation IS translation
    rotation IS rotation
    name IS name
    children [
""" + "\n".join(dock) + """
    ]
    boundingObject Group { children [
""" + "\n".join(dock_bo) + """
    ] }
  }
}
""")

# ---------------------------------------------------------------- borne de recharge (origine = base, sur la dalle)
st = [bshape("0 0 0.03", "0.36 0.30 0.06", "0.25 0.25 0.27", 0.6, 0.3), bshape("0 0 0.56", "0.26 0.20 1.00", "0.92 0.93 0.94", 0.4, 0.1),
      bshape("0 0 0.91", "0.27 0.21 0.06", "0.20 0.62 0.25", 0.4), bshape("0 0 1.08", "0.32 0.26 0.04", "0.25 0.25 0.27", 0.5, 0.3),
      pose("0.131 0 0.78", "0.57735 0.57735 0.57735 2.0944", 'Shape { appearance PBRAppearance { baseColorMap ImageTexture { url [ "textures/ecran.png" ] } emissiveColorMap ImageTexture { url [ "textures/ecran.png" ] } emissiveIntensity 0.8 roughness 0.2 metalness 0 } geometry Plane { size 0.16 0.08 } }')]
def cable(p0, p1, sag, n=12, zmin=0.015):
    pts = []
    for i in range(n + 1):
        f = i / n; p = p0 + f * (p1 - p0); p[2] -= sag * math.sin(math.pi * f); p[2] = max(p[2], zmin); pts.append(p)
    out = []
    for i in range(n):
        a_, b_ = pts[i], pts[i + 1]; m = (a_ + b_) / 2; d_ = b_ - a_; Ls = np.linalg.norm(d_); d_ /= Ls
        ax = np.cross([0, 0, 1], d_); s = np.linalg.norm(ax); an = math.atan2(s, d_[2]); ax = ax / s if s > 1e-9 else np.array([1, 0, 0])
        app = "DEF CABLE PBRAppearance { baseColor 0.05 0.05 0.05 roughness 0.6 metalness 0 }" if i == 0 else "USE CABLE"
        out.append(pose(f"{m[0]:.4f} {m[1]:.4f} {m[2]:.4f}", f"{ax[0]:.4f} {ax[1]:.4f} {ax[2]:.4f} {an:.4f}", f"Shape {{ appearance {app} geometry Cylinder {{ height {Ls+0.01:.4f} radius 0.012 subdivision 8 }} }}"))
    return out
P0 = np.array([0.0, -0.10, 0.55])
PLUG = np.array([-0.15, -0.588, 0.28])      # prise sur le flanc gauche du robot garé (robot = borne + (-0,05, -0,85))
conn = cable(P0.copy(), PLUG.copy(), 0.30) + [bshape(f"{PLUG[0]:.3f} {PLUG[1]+0.012:.3f} {PLUG[2]:.3f}", "0.07 0.03 0.06", "0.20 0.62 0.25", 0.5)]
HOOK = np.array([0.0, -0.13, 0.40])
free = cable(P0.copy(), np.array([0.06, -0.12, 0.42]), 0.22, 8) + [bshape("0.06 -0.115 0.42", "0.07 0.03 0.06", "0.20 0.62 0.25", 0.5)]
write_proto("ChargingStation.proto", HDR + """# Borne de recharge : socle, fût 0,26 x 0,20 x 1,0 m, bandeau vert, écran (face +X), câble.
# cableConnected TRUE : câble branché sur la prise du robot garé au dock (borne à (+0,05 ; +0,85) m
# du centre de la place, soit à GAUCHE du robot). FALSE : connecteur rangé sur la borne.
PROTO ChargingStation [
  field SFVec3f    translation    0 0 0
  field SFRotation rotation       0 0 1 0
  field SFString   name           "charging_station"
  field SFBool     cableConnected TRUE
]
{
  Solid {
    translation IS translation
    rotation IS rotation
    name IS name
    children [
""" + "\n".join(st) + """
      %< if (fields.cableConnected.value) { >%
""" + "\n".join(conn) + """
      %< } else { >%
""" + "\n".join(free) + """
      %< } >%
    ]
    boundingObject Group { children [
      Pose { translation 0 0 0.03 children [ Box { size 0.36 0.30 0.06 } ] }
      Pose { translation 0 0 0.56 children [ Box { size 0.26 0.20 1.00 } ] }
    ] }
  }
}
""")

# ---------------------------------------------------------------- géométrie parcelle (identique à preview_v2)
NR, PITCH, RIDGE_W, RIDGE_H, SOIL = 6, 0.85, 0.25, 0.08, 0.01
ROW_Y = [-(NR - 1) * PITCH / 2 + PITCH * i for i in range(NR)]
ALLEY_Y = [(ROW_Y[i] + ROW_Y[i + 1]) / 2 for i in range(NR - 1)]
RX0, RX1, STEP = -3.0, 3.0, 0.5
FRONT, REAR, LAT = 5.0, 3.5, 2.55
FX0, FX1 = RX0 - FRONT, RX1 + REAR
FY = ROW_Y[-1] + RIDGE_W / 2 + LAT
ZT = SOIL + RIDGE_H
RBX, RBY = -7.0, 0.0
SZ = SOIL + SH

def look_at(eye, tgt):
    x = np.array(tgt, float) - eye; x /= np.linalg.norm(x)
    y = np.array([-x[1], x[0], 0.0]); y /= np.linalg.norm(y); z = np.cross(x, y)
    m = np.column_stack([x, y, z]); an = math.acos(max(-1, min(1, (np.trace(m) - 1) / 2))); s2 = 2 * math.sin(an)
    ax = [(m[2, 1] - m[1, 2]) / s2, (m[0, 2] - m[2, 0]) / s2, (m[1, 0] - m[0, 1]) / s2]
    return f"{ax[0]:.4f} {ax[1]:.4f} {ax[2]:.4f} {an:.4f}"
VP_ORI = look_at(np.array([-14.5, -12.5, 11.5]), (-0.9, 0.0, 0.0))
w = [HDR + f"""# Parcelle AGRI-BOT clôturée (validée, « preview_v2 ») : {FX1-FX0:.1f} x {2*FY:.1f} m, 6 rangs de maïs de 6 m sur buttes,
# allées de 60 cm, plants tous les 50 cm, 32 adventices sur les buttes entre les plants,
# zone avant {FRONT} m (dock, borne, benne), zone arrière {REAR} m, dégagements latéraux {LAT} m.
# Généré par tools/gen_parcelle.py. Repère ENU, Z vers le haut, rangs selon +X.
EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/objects/backgrounds/protos/TexturedBackground.proto"
EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/objects/backgrounds/protos/TexturedBackgroundLight.proto"
EXTERNPROTO "../protos/Agribot.proto"
EXTERNPROTO "../protos/CornPlantV8.proto"
EXTERNPROTO "../protos/CornRidge.proto"
EXTERNPROTO "../protos/WoodFence3Rail.proto"
EXTERNPROTO "../protos/AgribotDock.proto"
EXTERNPROTO "../protos/ChargingStation.proto"
EXTERNPROTO "../protos/WeedDisposalBin.proto\""""]
for sp in SPECIES:
    w.append(f'EXTERNPROTO "../protos/Weed{sp}.proto"')
w.append(f"""
WorldInfo {{
  info [
    "Parcelle AGRI-BOT : 6 rangs x 13 plants (pas 0,50 m), allées 0,60 m (rangs à 0,85 m), allée centrale y = 0."
    "Dock à x = {RBX}, y = {RBY} (robot face aux rangs). Borne à gauche, benne à droite."
  ]
  title "AGRI-BOT parcelle"
  basicTimeStep 32
  coordinateSystem "ENU"
  contactProperties [
    ContactProperties {{ material1 "tire" material2 "soil" coulombFriction 1.2 bounce 0 bounceVelocity 0.01 softCFM 0.0001 bumpSound "" rollSound "" slideSound "" }}
  ]
}}
Viewpoint {{
  fieldOfView 0.8
  orientation {VP_ORI}
  position -14.5 -12.5 11.5
  description "Vue générale"
  near 0.05
  far 120
}}
TexturedBackground {{ texture "noon_park_empty" }}
TexturedBackgroundLight {{ texture "noon_park_empty" luminosity 0.8 }}
DirectionalLight {{ direction 0.35 0.55 -1 intensity 1.25 ambientIntensity 0.3 castShadows TRUE }}
# gazon
Solid {{ name "gazon" children [ Shape {{ appearance PBRAppearance {{ baseColorMap ImageTexture {{ url [ "../protos/textures/gazon.jpg" ] }} roughness 1 metalness 0 textureTransform TextureTransform {{ scale 30 30 }} }} geometry Plane {{ size 80 80 }} }} ] boundingObject Plane {{ size 80 80 }} contactMaterial "soil" }}
# parcelle de terre nue {FX1-FX0:.1f} x {2*FY:.1f} m
Solid {{ name "parcelle" translation {(FX0+FX1)/2:.3f} 0 {SOIL/2:.3f} children [ Shape {{ appearance PBRAppearance {{ baseColorMap ImageTexture {{ url [ "../protos/textures/terre.jpg" ] }} roughness 1 metalness 0 textureTransform TextureTransform {{ scale {(FX1-FX0)/2.5:.2f} {2*FY/2.5:.2f} }} }} geometry Box {{ size {FX1-FX0:.3f} {2*FY:.3f} {SOIL} }} }} ] boundingObject Box {{ size {FX1-FX0:.3f} {2*FY:.3f} {SOIL} }} contactMaterial "soil" }}""")
L = RX1 - RX0 + 0.4
for i, y in enumerate(ROW_Y):
    w.append(f'CornRidge {{ translation {(RX0+RX1)/2:.3f} {y:.3f} {SOIL} name "ridge_{i}" length {L:.2f} }}')
k = 0
for i, y in enumerate(ROW_Y):
    for j in range(round((RX1 - RX0) / STEP) + 1):
        x = RX0 + STEP * j
        w.append(f'CornPlantV8 {{ translation {x:.3f} {y + random.uniform(-0.01, 0.01):.3f} {ZT:.3f} rotation 0 0 1 {random.uniform(0, 6.28):.2f} name "corn_{i}_{j}" leafColor {0.20+random.uniform(-0.03,0.04):.2f} {0.58+random.uniform(-0.05,0.05):.2f} {0.15+random.uniform(-0.03,0.03):.2f} }}')
        k += 1
SP = list(SPECIES)
weeds = []
slots = [(i, j) for i in range(NR) for j in range(12)]
wr = random.Random(5); pick = sorted(wr.sample(slots, 32))
for n_, (i, j) in enumerate(pick):
    weeds.append((SP[n_ % 5], RX0 + STEP * j + 0.25 + wr.uniform(-0.05, 0.05), ROW_Y[i] + wr.uniform(-0.04, 0.04), ZT))
w.append("# adventices : uniquement sur les buttes, à mi-distance entre deux plants (32 des 72 intervalles)")
for n_, (s, x, y, z) in enumerate(weeds):
    w.append(f'Weed{s} {{ translation {x:.3f} {y:.3f} {z:.3f} rotation 0 0 1 {random.uniform(0,6.28):.2f} name "weed_{n_}_{s.lower()}" }}')
# clôture
for tag, (x0, y0), (x1, y1), n in (("front", (FX0, -FY), (FX0, FY), 5), ("rear", (FX1, -FY), (FX1, FY), 5),
                                    ("right", (FX0, -FY), (FX1, -FY), 8), ("left", (FX0, FY), (FX1, FY), 8)):
    Ls = math.hypot(x1 - x0, y1 - y0); an = math.atan2(y1 - y0, x1 - x0)
    w.append(f'WoodFence3Rail {{ translation {x0:.3f} {y0:.3f} 0 rotation 0 0 1 {an:.4f} name "fence_{tag}" length {Ls:.3f} segments {n} }}')
# quadrillage discret (marquage au sol, sans collision)
GL = "0.60 0.48 0.34"; g = []
for gx in np.arange(FX0 + 2, RX0 - 0.4, 1.0):
    g.append(bshape(f"{gx:.3f} 0 {SOIL+0.001:.4f}", f"0.03 {2*FY-0.4:.2f} 0.002", GL, 1))
for gy in np.arange(-math.floor(FY), FY - 0.1, 1.0):
    g.append(bshape(f"{(FX0+1.8+RX0-0.4)/2:.3f} {gy:.3f} {SOIL+0.001:.4f}", f"{RX0-0.4-(FX0+1.8):.2f} 0.03 0.002", GL, 1))
w.append("# marquage au sol : quadrillage 1 m de la zone avant\nGroup { children [\n" + "\n".join(g) + "\n] }")
w.append(f'AgribotDock {{ translation {RBX} {RBY} {SOIL} name "dock" }}')
w.append(f'ChargingStation {{ translation {RBX+0.05:.3f} {RBY+0.85:.3f} {SZ:.3f} name "charging_station" }}')
# ---- benne (même tirage aléatoire que l'aperçu)
KL, KW, KH, th = 1.10, 0.75, 0.55, 0.04
KC = "0.62 0.74 0.14"
bn = [bshape(f"0 0 0.06", f"{KL:.2f} {KW:.2f} {th}", KC, 0.5, 0.3)]
for s in (1, -1):
    bn.append(bshape(f"0 {s*(KW/2-th/2):.3f} {0.04+KH/2:.3f}", f"{KL:.2f} {th} {KH}", KC, 0.5, 0.3))
    bn.append(bshape(f"{s*(KL/2-th/2):.3f} 0 {0.04+KH/2:.3f}", f"{th} {KW-2*th:.2f} {KH}", KC, 0.5, 0.3))
    bn.append(bshape(f"0 {s*(KW/2):.3f} {0.04+KH:.3f}", f"{KL+0.04:.2f} 0.06 0.03", "0.50 0.60 0.10", 0.5, 0.3))
    for t in (-1, 1):
        bn.append(bshape(f"{t*0.42:.3f} {s*0.26:.3f} 0.02", "0.10 0.10 0.04", "0.2 0.2 0.2", 0.7))
for n_ in range(7):
    an = n_ * 0.9; r = 0.0 if n_ == 0 else 0.22
    sxs, sys_, szs = random.uniform(0.18, 0.26), random.uniform(0.14, 0.20), random.uniform(0.08, 0.12)
    col = random.choice(["0.30 0.40 0.16", "0.36 0.44 0.20", "0.40 0.36 0.20"])
    bn.append(pose(f"{r*1.5*math.cos(an):.3f} {r*math.sin(an):.3f} {0.36 + (0.05 if n_==0 else 0):.3f}", "0 0 1 0",
                   f"Transform {{ scale {sxs:.2f} {sys_:.2f} {szs:.2f} children [ {shape('Sphere { radius 1 subdivision 2 }', col, 0.95)} ] }}"))
for n_ in range(14):
    s_ = SP[n_ % 5]; an = n_ * 0.9; rr = 0.1 + 0.25 * ((n_ * 7) % 4) / 3
    bn.append(f'Weed{s_} {{ translation {0.36*rr/0.35*math.cos(an)*0.9:.3f} {0.22*rr/0.35*math.sin(an)*0.9:.3f} {0.42+0.03*((n_+1)%3):.3f} rotation {random.uniform(-1,1):.2f} {random.uniform(-1,1):.2f} 1 {random.uniform(0.3,1.2):.2f} name "waste_{n_}" collision FALSE }}')
bin_bo = [bbox("0 0 0.06", f"{KL:.2f} {KW:.2f} {th}")] + [bbox(f"0 {s*(KW/2-th/2):.3f} {0.04+KH/2:.3f}", f"{KL:.2f} {th} {KH}") for s in (1, -1)] + \
         [bbox(f"{s*(KL/2-th/2):.3f} 0 {0.04+KH/2:.3f}", f"{th} {KW-2*th:.2f} {KH}") for s in (1, -1)]
write_proto("WeedDisposalBin.proto", HDR + f"""# Benne ouverte à adventices (jaune-vert) 1,10 x 0,75 x 0,55 m sur pieds, avec un tas d'herbes arrachées.
# Placée à DROITE du robot garé (centre à (+0,05 ; -1,35) m de la place). Les herbes du tas s'appellent
# « waste_… » (ignorées par agribot_controller) et n'ont pas de collision.
""" + "".join(f'EXTERNPROTO "Weed{sp}.proto"\n' for sp in SPECIES) + """PROTO WeedDisposalBin [
  field SFVec3f    translation 0 0 0
  field SFRotation rotation    0 0 1 0
  field SFString   name        "weed_disposal_bin"
]
{
  Solid {
    translation IS translation
    rotation IS rotation
    name IS name
    children [
""" + "\n".join(bn) + """
    ]
    boundingObject Group { children [
""" + "\n".join(bin_bo) + """
    ] }
  }
}
""")
w.append(f'WeedDisposalBin {{ translation {RBX+0.05:.3f} {RBY-1.35:.3f} {SZ:.3f} name "weed_disposal_bin" }}')
w.append(f'''DEF AGRIBOT Agribot {{
  translation {RBX:.3f} {RBY:.3f} {SZ+0.004:.3f}
  customData "lane_y=0.0 row_end_x={RX1}"
}}''')
open(os.path.join(W, "agribot_parcelle.wbt"), "w").write("\n".join(w) + "\n")
print(dict(fence_m=(FX1 - FX0, 2 * FY), rows=NR, plants=k, weeds=len(weeds), alleys=[round(a, 3) for a in ALLEY_Y]))
