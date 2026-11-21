"""Test de sortie du dock (worlds/agribot_parcelle.wbt) : le robot quitte la place, descend la
rampe et entre de 2 m dans l'allée centrale (y = 0), bras au repos. Mettre controller
"parcelle_drive_test" sur l'Agribot pour le lancer. Affiche la progression, l'écart latéral,
roulis/tangage et tout contact hors de la bande de roulement (rails, buttes, châssis)."""
import math
from controller import Supervisor

SPEED = 3.0          # rad/s roue (~0,25 m/s)
X_STOP = -1.0        # 2 m après l'entrée des rangs (x = -3)
TIMEOUT = 40.0

robot = Supervisor()
dt_ms = int(robot.getBasicTimeStep())
node = robot.getSelf()
motors = {}
for name in ('fl_motor', 'fr_motor', 'rl_motor', 'rr_motor'):
    m = robot.getDevice(name); m.setPosition(float('inf')); m.setVelocity(0.0); motors[name] = m
for name in ('S1_lacet', 'S2_epaule', 'S3_coude', 'S4_poignet', 'S5_pince'):
    robot.getDevice(name).setPosition(0.0)

def local(p, t, r):
    d = [p[i] - t[i] for i in range(3)]
    return (r[0]*d[0] + r[3]*d[1] + r[6]*d[2], r[1]*d[0] + r[4]*d[1] + r[7]*d[2], r[2]*d[0] + r[5]*d[1] + r[8]*d[2])

start = node.getPosition()[:]
t = 0.0; last_print = -1.0
max_dy = max_roll = max_pitch = 0.0; bad = []; done = False
while robot.step(dt_ms) != -1:
    t += dt_ms / 1000.0
    p = node.getPosition(); r = node.getOrientation()
    heading = math.atan2(r[3], r[0])
    roll = math.degrees(math.atan2(r[7], r[8])); pitch = math.degrees(math.asin(max(-1, min(1, -r[6]))))
    steer = max(-1.0, min(1.0, 3.0 * (0.0 - p[1]) - 2.5 * heading)) if t > 0.5 else 0.0
    v = SPEED if t > 0.5 else 0.0
    for n_, m in motors.items():
        m.setVelocity(v - steer if n_[1] == 'l' else v + steer)
    if t > 0.5:
        max_dy = max(max_dy, abs(p[1])); max_roll = max(max_roll, abs(roll)); max_pitch = max(max_pitch, abs(pitch))
        for c in node.getContactPoints(True):
            lx, ly, lz = local(c.point, p, r)
            if lz > 0.02:   # contact au-dessus du bas des roues : rail, butte, rampe sur le châssis...
                bad.append((round(t, 2), round(c.point[0], 3), round(c.point[1], 3), round(c.point[2], 3), round(lx, 3), round(ly, 3), round(lz, 3)))
    if t - last_print >= 2.0:
        last_print = t
        print(f"t={t:5.1f}s x={p[0]:+.3f} y={p[1]:+.4f} z={p[2]:.3f} cap={math.degrees(heading):+.2f}° roulis={roll:+.2f}° tangage={pitch:+.2f}°", flush=True)
    if p[0] >= X_STOP or t > TIMEOUT:
        done = p[0] >= X_STOP
        break
for m in motors.values():
    m.setVelocity(0.0)
p = node.getPosition()
print(f"RESULTAT {'OK' if done and not bad else 'ECHEC'} : parcouru {p[0]-start[0]:.2f} m en {t:.1f} s, "
      f"écart latéral max {max_dy*100:.1f} cm, roulis max {max_roll:.1f}°, tangage max {max_pitch:.1f}°, "
      f"contacts hors roulement {len(bad)}", flush=True)
for b in bad[:10]:
    print("  contact", b, flush=True)
for _ in range(10):
    robot.step(dt_ms)   # laisse Webots vider la sortie console
robot.simulationQuit(0 if done and not bad else 1)
