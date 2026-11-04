# Exporte les maillages du bras v7 (meme CAO que le STL Gazebo) en binaire, mm.
# Corps sans roues ni pieces mobiles ; un STL par articulation S1..S5.
import os
import FreeCAD as App
import Mesh
import MeshPart

SRC = "/home/maxadis/Documents/AGRIBOT/AGRIBOT_v7.FCStd"
OUT = "/home/maxadis/Documents/AGRIBOT/mon-agribot-webots/meshes"
os.makedirs(OUT, exist_ok=True)

WHEELS = {
    "P02_Jante_AvG", "P18_Bande_TPU_AvG",
    "P02_Jante_AvD", "P18_Bande_TPU_AvD",
    "P02_Jante_ArG", "P18_Bande_TPU_ArG",
    "P02_Jante_ArD", "P18_Bande_TPU_ArD",
}
# Pieces qui tournent. Le corps du servo reste sur le lien parent, le palonnier sur le lien mene.
LINKS = {
    "s1": [
        "S1_palonnier", "P04_Plateau_tournant", "P05_Chape_epaule", "S2_RDS5160_epaule",
    ],
    "s2": [
        "S2_palonnier", "A09_Bras_L1_plat_G", "A09_Bras_L1_plat_D", "P06_Berceau_coude",
        "S3_RDS5160_coude", "V01_Entretoise_pivot_epaule_5", "V02_Vis_M4x8_pivot_epaule",
    ],
    "s3": [
        "S3_palonnier", "P07_Chape_coude_L2", "A10_Bras_L2_tube", "P08_Bloc_poignet",
        "S4_DS3235_poignet", "V03_Entretoise_pivot_coude_15", "V04_Vis_M4x8_pivot_coude",
    ],
    "s4": [
        "S4_palonnier", "P09_Poutre_L3_pince", "E13_Camera_bras", "S5_DS3235_pince",
    ],
    "s5": [
        "S5_palonnier", "P16_Mors_mobile",
    ],
}

doc = App.openDocument(SRC)
by_name = {o.Name: o for o in doc.Objects}
moving = {n for names in LINKS.values() for n in names}
missing = [n for n in moving if n not in by_name]
if missing:
    raise SystemExit("missing " + ",".join(missing))


def export(names, path, deflection):
    mesh = Mesh.Mesh()
    for name in names:
        obj = by_name[name]
        part = MeshPart.meshFromShape(
            Shape=obj.Shape, LinearDeflection=deflection, AngularDeflection=0.45, Relative=False
        )
        mesh.addMesh(part)
    mesh.write(path)
    print("%s facets=%d bytes=%d" % (os.path.basename(path), mesh.CountFacets, os.path.getsize(path)), flush=True)


static = []
for obj in doc.Objects:
    if not hasattr(obj, "Shape") or obj.Shape.isNull():
        continue
    if obj.Name in WHEELS or obj.Name in moving:
        continue
    static.append(obj.Name)
print("static parts", len(static), flush=True)
export(static, os.path.join(OUT, "robot_static.stl"), 4.0)
for key, names in LINKS.items():
    export(names, os.path.join(OUT, "link_%s.stl" % key), 1.5)

for name in (
    "S1_DS3235_lacet", "S2_RDS5160_epaule", "S3_RDS5160_coude",
    "S4_DS3235_poignet", "S5_DS3235_pince", "P16_Mors_mobile", "P09_Poutre_L3_pince",
):
    bb = by_name[name].Shape.BoundBox
    print(
        "bbox", name,
        round(bb.XMin, 1), round(bb.YMin, 1), round(bb.ZMin, 1),
        round(bb.XMax, 1), round(bb.YMax, 1), round(bb.ZMax, 1),
        flush=True,
    )
App.closeDocument(doc.Name)
