"""Banc d'essai Agribot v9b (superviseur, sans clavier).

Apparition, pose repos, pose sol CAO pince ouverte, fermeture de la pince, retour au
repos, petit roulage. Écrit un rapport JSON et des captures si AGRIBOT_SHOTS est défini.
"""
import json
import math
import os
import time

from controller import Supervisor

SHOTS = os.environ.get("AGRIBOT_SHOTS", "")
REPORT = os.environ.get("AGRIBOT_REPORT", "")
ARM = ("S1_lacet", "S2_epaule", "S3_coude", "S4_poignet", "S5_pince")
REST = (0.0, 0.0, 0.0, 0.0, 0.0)
# Pose sol CAO 270 / 26.83 / -36.9 / -79.93 dans le repère des servos Webots.
GROUND = (math.radians(90.0), math.radians(26.83 - 115.0), math.radians(-36.9 + 90.0),
          math.radians(-120.0 + 79.93))
GRIP_OPEN = -0.70
# Bout des doigts attendu (CAO) : x 170 + 58, y -380, z 14 mm.
GROUND_TIP = (0.228, -0.380, 0.014)
REST_TIP = (0.025118, -0.058, 0.2324)

robot = Supervisor()
dt = int(robot.getBasicTimeStep())
motors = {n: robot.getDevice(n) for n in ARM}
sensors = {n: robot.getDevice(n + "_sensor") for n in ARM}
for s in sensors.values():
    s.enable(dt)
wheels = [robot.getDevice(n) for n in ("fl_motor", "fr_motor", "rl_motor", "rr_motor")]
for w in wheels:
    w.setPosition(float("inf"))
    w.setVelocity(0.0)
for m in motors.values():
    m.setVelocity(1.5)
self_node = robot.getSelf()
tip_node = self_node.getFromProtoDef("GRIP_TIP")
view = robot.getFromDef("VIEW")
results = {"steps": []}


def run(seconds):
    for _ in range(int(seconds * 1000 / dt)):
        if robot.step(dt) == -1:
            raise SystemExit


def local(p):
    t = self_node.getPosition()
    r = self_node.getOrientation()
    d = [p[i] - t[i] for i in range(3)]
    return [r[0] * d[0] + r[3] * d[1] + r[6] * d[2],
            r[1] * d[0] + r[4] * d[1] + r[7] * d[2],
            r[2] * d[0] + r[5] * d[1] + r[8] * d[2]]


def look(eye, target):
    """Viewpoint ENU : regard sur +X local, haut +Z local."""
    x = [target[i] - eye[i] for i in range(3)]
    n = math.sqrt(sum(c * c for c in x))
    x = [c / n for c in x]
    up = [0.0, 0.0, 1.0]
    y = [up[1] * x[2] - up[2] * x[1], up[2] * x[0] - up[0] * x[2], up[0] * x[1] - up[1] * x[0]]
    n = math.sqrt(sum(c * c for c in y))
    y = [c / n for c in y]
    z = [x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0]]
    m = [[x[0], y[0], z[0]], [x[1], y[1], z[1]], [x[2], y[2], z[2]]]
    angle = math.acos(max(-1.0, min(1.0, (m[0][0] + m[1][1] + m[2][2] - 1) / 2)))
    if abs(angle) < 1e-6:
        axis = [0, 0, 1]
    elif abs(angle - math.pi) < 1e-4:
        axis = [math.sqrt(max(0, (m[i][i] + 1) / 2)) for i in range(3)]
    else:
        s = 2 * math.sin(angle)
        axis = [(m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s]
    view.getField("position").setSFVec3f(list(eye))
    view.getField("orientation").setSFRotation(axis + [angle])


def shot(name, eye, target):
    if not SHOTS or view is None:
        return
    look(eye, target)
    run(0.2)
    path = os.path.join(SHOTS, name)
    robot.exportImage(path, 95)
    run(0.1)
    results.setdefault("shots", []).append(path)


def move(target, seconds):
    start = [sensors[n].getValue() for n in ARM]
    steps = int(seconds * 1000 / dt)
    for k in range(1, steps + 1):
        a = k / steps
        for i, n in enumerate(ARM):
            motors[n].setPosition(start[i] + (target[i] - start[i]) * a)
        robot.step(dt)
    run(1.0)


def record(name, expect_tip=None):
    q = [round(sensors[n].getValue(), 4) for n in ARM]
    tip = local(tip_node.getPosition())
    world_tip = tip_node.getPosition()
    r = self_node.getOrientation()
    entry = {"step": name, "q": q, "tip_robot": [round(c, 4) for c in tip],
             "tip_world_z": round(world_tip[2], 4),
             "robot_z": round(self_node.getPosition()[2], 4), "up_z": round(r[8], 4)}
    if expect_tip:
        entry["tip_error_mm"] = round(1000 * math.dist(tip, expect_tip), 1)
    results["steps"].append(entry)
    print(json.dumps(entry), flush=True)


run(1.5)
# Optionnel : attendre qu'un script externe ait agrandi la fenêtre avant les captures.
GO = os.environ.get("AGRIBOT_GO_FILE", "")
if GO:
    limit = time.time() + 60
    while not os.path.exists(GO) and time.time() < limit:
        time.sleep(0.2)
        robot.step(dt)
record("spawn", REST_TIP)
shot("v9b_rest_iso.png", (1.45, -1.25, 0.95), (0.0, 0.0, 0.22))
shot("v9b_rest_side.png", (0.0, -2.1, 0.35), (0.0, 0.0, 0.25))
move(REST[:4] + (GRIP_OPEN,), 1.0)
move(GROUND + (GRIP_OPEN,), 5.0)
record("ground_open", GROUND_TIP)
shot("v9b_ground_iso.png", (1.3, -1.5, 0.8), (0.1, -0.15, 0.15))
shot("v9b_ground_front.png", (1.6, -0.35, 0.30), (0.2, -0.3, 0.15))
# Zooms pince : axe du mors horizontal (le long de -Y), les doigts s'écartent en X.
weed = robot.getFromDef("WEED")
if weed is not None:
    weed.getField("translation").setSFVec3f([0.228, -0.380, -0.5])
shot("v9b_gripper_open_zoom.png", (0.228, -0.80, 0.07), (0.228, -0.38, 0.05))
move(GROUND + (0.0,), 1.5)
record("ground_closed", GROUND_TIP)
shot("v9b_gripper_closed_zoom.png", (0.228, -0.80, 0.07), (0.228, -0.38, 0.05))
if weed is not None:
    weed.getField("translation").setSFVec3f([0.228, -0.380, 0.0])
move(REST, 5.0)
record("back_to_rest", REST_TIP)
start = self_node.getPosition()
for w in wheels:
    w.setVelocity(3.0)
run(3.0)
for w in wheels:
    w.setVelocity(0.0)
run(1.0)
end = self_node.getPosition()
r = self_node.getOrientation()
results["drive"] = {"distance_m": round(math.dist(start[:2], end[:2]), 3),
                    "lateral_drift_m": round(end[1] - start[1], 3),
                    "heading_deg": round(math.degrees(math.atan2(r[3], r[0])), 2),
                    "up_z": round(r[8], 4)}
print(json.dumps(results["drive"]), flush=True)
if REPORT:
    with open(REPORT, "w") as fh:
        json.dump(results, fh, indent=1)
print("V9B_TEST_DONE", flush=True)
robot.simulationSetMode(Supervisor.SIMULATION_MODE_PAUSE)
robot.simulationQuit(0)
