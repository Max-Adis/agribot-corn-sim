"""Exporte les maillages Webots de l'Agribot v9b depuis les STL par pièce de la CAO.

Les STL de livraison (04_STL_impression) sont en mm, dans le repère de l'assemblage,
pose repos (lacet 180, épaule 115, coude -90, poignet -120). Repère robot : X avant,
Y gauche, Z haut, origine au sol au centre. Ce script n'a pas besoin de FreeCAD :
il regroupe les pièces, les ramène dans le repère de leur articulation (pose repos
= position 0 des moteurs Webots), réduit le nombre de facettes et calcule masse,
centre de masse et inertie de chaque lien.

    python3 tools/export_arm_links.py [dossier_STL] [dossier_meshes]

Dépendances : numpy, trimesh, fast-simplification (pip).
"""
import json
import math
import os
import sys

import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else "/workspace/agribot/livraison/AGRIBOT_v9b/04_STL_impression"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "meshes")
os.makedirs(OUT, exist_ok=True)

# ---- repères des articulations en pose repos (mm, repère robot) -----------------
# Cinématique de parts.arm() : B = (170,0,0)·Rz(lacet), épaule à z 200,
# L1 150, L2 250, L3 150 + bec 60, pince tournée de 90° autour de L3 (axe à y=58).
REST = (180.0, 115.0, -90.0, -120.0)
SHOULDER = np.array([170.0, 0.0, 200.0])


def _arm_points():
    yaw, t1, t2, t3 = [math.radians(a) for a in REST]
    xb = np.array([math.cos(yaw), math.sin(yaw), 0.0])
    yb = np.array([-math.sin(yaw), math.cos(yaw), 0.0])
    zb = np.array([0.0, 0.0, 1.0])

    def d(e):
        return math.cos(e) * xb + math.sin(e) * zb

    elbow = SHOULDER + 150.0 * d(t1)
    wrist = elbow + 250.0 * d(t1 + t2)
    e3 = t1 + t2 + t3
    x_w = d(e3)
    z_w = -math.sin(e3) * xb + math.cos(e3) * zb   # Z du repère poignet
    yc = 58.0                                       # axe de roulis de la pince (yb0+yb1)/2
    pivot = wrist + 150.0 * x_w + yc * yb           # axe S5 : ligne x=L3, y=yc, direction Z_w
    tip = wrist + 210.0 * x_w + yc * yb             # bout des doigts (L3 + GRIP)
    return elbow, wrist, pivot, tip, z_w


ELBOW, WRIST, PIVOT, TIP, S5_AXIS = _arm_points()
# Ancres des liens Webots (le Y de S4/S5 est mis au centre du servo / de la pince).
ANCHOR = {
    "s1": np.array([170.0, 0.0, 200.0]),
    "s2": SHOULDER.copy(),
    "s3": ELBOW.copy(),
    "s4": np.array([WRIST[0], -31.0, WRIST[2]]),
    "s5": PIVOT.copy(),
}
WHEELS = {
    "fl": ("AvG", np.array([300.0, 240.0, 82.5])),
    "fr": ("AvD", np.array([300.0, -240.0, 82.5])),
    "rl": ("ArG", np.array([-300.0, 240.0, 82.5])),
    "rr": ("ArD", np.array([-300.0, -240.0, 82.5])),
}

# ---- pièces par lien (le corps d'un servo reste sur le parent, le palonnier va sur le lien mené)
LINKS = {
    "s1": {"print": ["P04_Plateau_tournant", "P05_Chape_epaule"],
           "dark": ["S1_palonnier", "S2_RDS5160_epaule"]},
    "s2": {"alu": ["A09_Bras_L1_plat_G", "A09_Bras_L1_plat_D"],
           "print": ["P06_Berceau_coude"],
           "dark": ["S2_palonnier", "S3_RDS5160_coude", "V01_Entretoise_pivot_epaule_5",
                    "V02_Vis_M4x8_pivot_epaule"]},
    "s3": {"alu": ["A10_Bras_L2_tube"],
           "print": ["P07_Chape_coude_L2", "P08_Bloc_poignet"],
           "dark": ["S3_palonnier", "S4_DS3235_poignet", "V03_Entretoise_pivot_coude_15",
                    "V04_Vis_M4x8_pivot_coude"]},
    # P09 porte le bec fixe (roulis 90° intégré) et le corps du servo pince.
    "s4": {"print": ["P09_Poutre_L3_pince"],
           "dark": ["S4_palonnier", "E13_Camera_bras", "S5_DS3235_pince"]},
    # Mors mobile : tourne autour de l'axe S5, se ferme latéralement contre le bec.
    "s5": {"jaw": ["P16_Mors_mobile"], "dark": ["S5_palonnier"]},
}
BODY = {
    "alu": ("A01", "A02", "A03", "A06", "A08", "A11", "A13"),
    "white": ("A04", "A05", "A07", "A14", "P10", "P11", "P19"),
    "print": ("P01", "P03", "P12", "P13"),
    "bin": ("P14", "P17"),
    "dark": ("E", "M_", "S1_DS3235", "B01", "V05", "V06", "V07"),
}

# ---- masses (g). P.. : nomenclature v9b (PETG). Alu : volume CAO × 2,70 g/cm³.
# Achats : ESTIMATIONS (fiches fabricant typiques), à remplacer par une pesée.
PRINTED_G = {
    "P01": 28.8, "P02": 198.6, "P03": 98.5, "P04": 61.9, "P05": 120.0, "P06": 83.5,
    "P07": 87.5, "P08": 65.7, "P09": 57.0, "P10": 76.1, "P11": 14.4, "P12": 82.6,
    "P13": 30.4, "P14_Bac_moitie_1": 1982.9, "P14_Bac_moitie_2": 2063.3, "P16": 13.4,
    "P17": 0.3, "P18": 43.8, "P19": 3.9,
}
BOUGHT_EST_G = {
    "E01": 750.0, "E02": 66.0, "E03": 30.0, "E04": 10.0, "E05": 30.0, "E06": 30.0,
    "E07": 10.0, "E08": 60.0, "E09": 80.0, "E10": 50.0, "E11": 170.0, "E12": 80.0,
    "E13": 15.0, "M_": 205.0, "C_": 20.0, "B01": 50.0, "S1_DS3235": 60.0,
    "S4_DS3235": 60.0, "S5_DS3235": 60.0, "S2_RDS5160": 155.0, "S3_RDS5160": 155.0,
    "palonnier": 8.0, "A11": 10.0, "V0": 4.0,
}
ALU_DENSITY = 2.70e-3  # g/mm³


def part_mass(name, mesh):
    for key, grams in PRINTED_G.items():
        if name.startswith(key):
            return grams, "nomenclature"
    for key, grams in BOUGHT_EST_G.items():
        if key in name if key == "palonnier" else name.startswith(key):
            return grams, "estimation"
    if name.startswith("A"):
        return abs(mesh.volume) * ALU_DENSITY, "volume alu"
    return abs(mesh.volume) * ALU_DENSITY, "volume alu"


_cache = {}


def load(name):
    if name not in _cache:
        path = os.path.join(SRC, name + ".stl")
        if not os.path.exists(path):
            raise SystemExit("pièce manquante : " + path)
        _cache[name] = trimesh.load(path, force="mesh")
    return _cache[name]


def all_parts():
    return sorted(f[:-4] for f in os.listdir(SRC) if f.endswith(".stl"))


def decimate(mesh, max_faces):
    if len(mesh.faces) <= max_faces:
        return mesh
    try:
        import fast_simplification
        pts, fcs = fast_simplification.simplify(
            mesh.vertices.astype(np.float32), mesh.faces.astype(np.int32),
            target_reduction=1.0 - max_faces / float(len(mesh.faces)))
        return trimesh.Trimesh(pts, fcs, process=True)
    except ImportError:
        print("fast-simplification absent : maillage non réduit", flush=True)
        return mesh


def write(names, origin, path, max_faces):
    meshes = [load(n).copy() for n in names]
    mesh = trimesh.util.concatenate(meshes)
    mesh.apply_translation(-origin)
    mesh = decimate(mesh, max_faces)
    mesh.export(path)
    print("%-28s pièces=%2d facettes=%6d octets=%d" % (
        os.path.basename(path), len(names), len(mesh.faces), os.path.getsize(path)), flush=True)


def inertia(names, origin):
    """Masse (kg), centre de masse et inertie au CdM (kg·m²) dans le repère du lien (m)."""
    total = 0.0
    first = np.zeros(3)
    parts = []
    sources = {}
    for n in names:
        m = load(n)
        grams, src = part_mass(n, m)
        sources[n] = (round(grams, 1), src)
        kg = grams / 1000.0
        if m.is_watertight and abs(m.volume) > 1e-6:
            com = (m.center_mass - origin) / 1000.0
            unit = m.moment_inertia / abs(m.volume) / 1e6   # par unité de masse, m²
        else:
            com = (m.bounds.mean(axis=0) - origin) / 1000.0
            ext = (m.bounds[1] - m.bounds[0]) / 1000.0
            unit = np.diag([(ext[1]**2 + ext[2]**2), (ext[0]**2 + ext[2]**2), (ext[0]**2 + ext[1]**2)]) / 12.0
        parts.append((kg, com, unit * kg))
        total += kg
        first += kg * com
    com_all = first / total
    tensor = np.zeros((3, 3))
    for kg, com, inert in parts:
        r = com - com_all
        tensor += inert + kg * (np.dot(r, r) * np.eye(3) - np.outer(r, r))
    return total, com_all, tensor, sources


def main():
    names = all_parts()
    moving = {n for g in LINKS.values() for lst in g.values() for n in lst}
    wheel_parts = {n for n in names if n.startswith(("P02_Jante_", "P18_Bande_TPU_", "C_"))}
    static = [n for n in names if n not in moving and n not in wheel_parts]
    report = {"rest_pose_deg": REST, "anchors_mm": {k: v.round(3).tolist() for k, v in ANCHOR.items()},
              "s5_axis": S5_AXIS.round(6).tolist(), "tip_mm": TIP.round(3).tolist(), "links": {}}

    zero = np.zeros(3)
    used = set()
    for group, prefixes in BODY.items():
        lst = [n for n in static if n.startswith(prefixes) and n not in used]
        used.update(lst)
        write(lst, zero, os.path.join(OUT, "body_%s.stl" % group), 12000)
    left = [n for n in static if n not in used]
    if left:
        raise SystemExit("pièces sans groupe : " + ",".join(left))
    m, c, i, s = inertia(static, zero)
    report["links"]["body"] = dict(mass=m, com=c.tolist(), inertia=i.tolist(), parts=s)

    for key, (suffix, center) in WHEELS.items():
        rim = ["P02_Jante_" + suffix, "C_%s_Accouplement_6mm" % suffix]
        tire = ["P18_Bande_TPU_" + suffix]
        write(rim, center, os.path.join(OUT, "wheel_%s_rim.stl" % key), 3000)
        write(tire, center, os.path.join(OUT, "wheel_%s_tire.stl" % key), 3000)
        m, c, i, s = inertia(rim + tire, center)
        report["links"]["wheel_" + key] = dict(mass=m, com=c.tolist(), inertia=i.tolist(), parts=s)

    for key, groups in LINKS.items():
        allp = []
        for group, lst in groups.items():
            write(lst, ANCHOR[key], os.path.join(OUT, "link_%s_%s.stl" % (key, group)), 6000)
            allp += lst
        m, c, i, s = inertia(allp, ANCHOR[key])
        report["links"][key] = dict(mass=m, com=c.tolist(), inertia=i.tolist(), parts=s)

    path = os.path.join(OUT, "..", "tools", "v9b_mass_report.json")
    with open(path, "w") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)
    for k, v in report["links"].items():
        i = v["inertia"]
        print("%-9s m=%.3f kg com=%s I=[%.2e %.2e %.2e %.2e %.2e %.2e]" % (
            k, v["mass"], np.round(v["com"], 4).tolist(),
            i[0][0], i[1][1], i[2][2], i[0][1], i[0][2], i[1][2]))
    print("ancres", report["anchors_mm"], "axe S5", report["s5_axis"], "bout", report["tip_mm"])


if __name__ == "__main__":
    main()
