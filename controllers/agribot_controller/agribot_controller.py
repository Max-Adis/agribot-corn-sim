"""Contrôleur Agribot v7 : téléopération clavier et désherbage autonome."""
import math

from controller import Keyboard, Supervisor

# 4.8 rad/s * rayon 0.0825 m ≈ 0.4 m/s
MAX_WHEEL = 4.8
TURN = 3.6
WHEEL_ACCEL = 12.0
JOINT_SPEED = 2.0
CRUISE = 1.5
# Centre du robot → touffe, là où le bec atteint encore la base (plan du bras ~0,30 m).
STANDOFF = 0.29
# Arrêt où le poignet rabattu touche encore la touffe à moins de 5 cm.
GRASP_X0 = 0.22
GRASP_X1 = 0.26
GRASP_Z = 0.14
SHOULDER_X = 0.170
SHOULDER_Y = -0.021
SHOULDER_Z = 0.200
# Allée entre les rangs y=0 et y=0.85. y=0 est un rang, pas le passage.
LANE_Y = 0.425
ROW_END_X = 6.5

# Longueurs XZ des translations Agribot.proto : S2→S3, S3→S4, S4→S5.
L1 = math.hypot(0.063393, 0.135946)
L2 = math.hypot(0.226577, 0.105655)
L3 = math.hypot(0.013073, 0.149429)
# Bec fixe au-delà de l'axe S5, le long du même segment (60 mm).
TIP = 0.060
# Décalage Y du bec par rapport à l'origine S2 (translations S4 puis S5).
TIP_Y = -0.0275 - 0.0045
A1_0 = math.atan2(0.135946, 0.063393)
A2_0 = math.atan2(0.105655, -0.226577)
A3_0 = math.atan2(-0.149429, 0.013073)
LIMITS = ((-1.5708, 1.5708), (-2.2427, 2.2427), (-2.1206, 2.1206))

GRIP_OPEN = -0.70
GRIP_CLOSED = 0.90

# Articulations réelles du bras (pose 0 = conception). Touche + puis touche -.
ARM = (
    ('S1_lacet', 'Q', 'E'),
    ('S2_epaule', 'R', 'F'),
    ('S3_coude', 'T', 'G'),
    ('S4_poignet', 'Y', 'H'),
    ('S5_pince', 'U', 'J'),
)
ORDER = [name for name, _up, _down in ARM]


def clamp(value, low, high):
    return max(low, min(high, value))


def approach(current, target, max_step):
    if current < target:
        return min(current + max_step, target)
    return max(current - max_step, target)


def wrap(angle):
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle <= -math.pi:
        angle += 2.0 * math.pi
    return angle


def pressed_keys(keyboard):
    keys = set()
    key = keyboard.getKey()
    while key != -1:
        keys.add(key & Keyboard.KEY)
        key = keyboard.getKey()
    return keys


def chain(q2, q3, q4):
    """Points (u, z) du coude, du poignet et de la pointe du bec."""
    a1 = A1_0 - q2
    a2 = A2_0 - (q2 + q3)
    # S4 est en -Y : q4 positif se rabat avec l'épaule, le bec vers le bas.
    a3 = A3_0 - q2 - q3 + q4
    points = []
    along = 0.0
    height = 0.0
    for length, angle in ((L1, a1), (L2, a2), (L3 + TIP, a3)):
        along += length * math.cos(angle)
        height += length * math.sin(angle)
        points.append((along, SHOULDER_Z + height))
    return points


def solve_arm(along, z_abs):
    """Pointe du bec sur (along, z_abs). None si la touffe est hors portée."""
    height_rel = z_abs - SHOULDER_Z
    length = L3 + TIP
    best = None
    for degree in range(-150, -20):
        a3_aim = math.radians(degree)
        wrist_u = along - length * math.cos(a3_aim)
        wrist_z = height_rel - length * math.sin(a3_aim)
        distance = math.hypot(wrist_u, wrist_z)
        if distance > L1 + L2 - 1e-4 or distance < abs(L1 - L2) + 1e-4:
            continue
        cos_beta = (L1 * L1 + distance * distance - L2 * L2) / (2.0 * L1 * distance)
        cos_beta = max(-1.0, min(1.0, cos_beta))
        beta = math.acos(cos_beta)
        gamma = math.atan2(wrist_z, wrist_u)
        for sign in (1.0, -1.0):
            a1 = gamma + sign * beta
            elbow_u = L1 * math.cos(a1)
            elbow_z = L1 * math.sin(a1)
            a2 = math.atan2(wrist_z - elbow_z, wrist_u - elbow_u)
            q2 = clamp(wrap(A1_0 - a1), LIMITS[0][0], LIMITS[0][1])
            q3 = clamp(wrap(A2_0 - a2 - q2), LIMITS[1][0], LIMITS[1][1])
            q4 = clamp(wrap(a3_aim - A3_0 + q2 + q3), LIMITS[2][0], LIMITS[2][1])
            a1 = A1_0 - q2
            a2 = A2_0 - (q2 + q3)
            a3 = A3_0 - q2 - q3 + q4
            # Bec sous l'horizontale et vers la touffe, pas vers le haut ni l'arrière.
            if a3 > -0.25 or a3 < -1.75 or q2 < 0.0 or q4 < 0.0:
                continue
            height = 0.0
            lowest = 1e9
            for seg, ang in ((L1, a1), (L2, a2), (L3, a3), (TIP, a3)):
                height += seg * math.sin(ang)
                lowest = min(lowest, SHOULDER_Z + height)
            if lowest < 0.03:
                continue
            tip_u = L1 * math.cos(a1) + L2 * math.cos(a2) + length * math.cos(a3)
            tip_z = SHOULDER_Z + L1 * math.sin(a1) + L2 * math.sin(a2) + length * math.sin(a3)
            miss = math.hypot(tip_u - along, tip_z - z_abs)
            if miss > 0.05:
                continue
            cost = (miss, abs(a3 + 1.05), abs(q2) + abs(q3) + abs(q4))
            angles = (q2, q3, q4)
            if best is None or cost < best[0]:
                best = (cost, angles)
    # Butée S4 positive : le poignet accompagne l'épaule jusqu'au rang.
    q4_stop = LIMITS[2][1]
    q2 = LIMITS[0][0]
    while q2 <= LIMITS[0][1] + 1e-9:
        q3 = LIMITS[1][0]
        while q3 <= LIMITS[1][1] + 1e-9:
            if q2 >= 0.0 and q4_stop >= 0.0:
                a1 = A1_0 - q2
                a2 = A2_0 - (q2 + q3)
                a3 = A3_0 - q2 - q3 + q4_stop
                if -1.75 <= a3 <= -0.25:
                    height = 0.0
                    lowest = 1e9
                    for seg, ang in ((L1, a1), (L2, a2), (L3, a3), (TIP, a3)):
                        height += seg * math.sin(ang)
                        lowest = min(lowest, SHOULDER_Z + height)
                    if lowest >= 0.03:
                        tip_u = L1 * math.cos(a1) + L2 * math.cos(a2) + length * math.cos(a3)
                        tip_z = SHOULDER_Z + height
                        miss = math.hypot(tip_u - along, tip_z - z_abs)
                        if miss <= 0.05:
                            cost = (miss, abs(a3 + 1.05), abs(q2) + abs(q3) + abs(q4_stop))
                            angles = (q2, q3, q4_stop)
                            if best is None or cost < best[0]:
                                best = (cost, angles)
            q3 += 0.04
        q2 += 0.04
    if best is None:
        return None
    return best[1]


def robot_pose(robot):
    node = robot.getSelf()
    translation = node.getPosition()
    rotation = node.getOrientation()
    return translation, rotation


def world_to_robot(wx, wy, wz, translation, rotation):
    dx = wx - translation[0]
    dy = wy - translation[1]
    dz = wz - translation[2]
    lx = rotation[0] * dx + rotation[3] * dy + rotation[6] * dz
    ly = rotation[1] * dx + rotation[4] * dy + rotation[7] * dz
    lz = rotation[2] * dx + rotation[5] * dy + rotation[8] * dz
    return lx, ly, lz


def robot_to_world(lx, ly, lz, translation, rotation):
    wx = translation[0] + rotation[0] * lx + rotation[1] * ly + rotation[2] * lz
    wy = translation[1] + rotation[3] * lx + rotation[4] * ly + rotation[5] * lz
    wz = translation[2] + rotation[6] * lx + rotation[7] * ly + rotation[8] * lz
    return wx, wy, wz


def heading_of(rotation):
    return math.atan2(rotation[3], rotation[0])


def shoulder_yaw(x_rel, y_rel):
    # Axe S1 = (0, 0, 1) : angle positif (main droite) tourne +X vers +Y.
    # +Y est à gauche (ENU, nez vers +X). Une touffe à gauche garde ce signe.
    yaw = math.atan2(y_rel, x_rel - SHOULDER_X)
    for _ in range(5):
        sx = SHOULDER_X - SHOULDER_Y * math.sin(yaw)
        sy = SHOULDER_Y * math.cos(yaw)
        ax = x_rel - TIP_Y * (-math.sin(yaw))
        ay = y_rel - TIP_Y * math.cos(yaw)
        yaw = math.atan2(ay - sy, ax - sx)
    return clamp(yaw, -2.30, 2.30)


def reach_along(x_rel, y_rel, yaw):
    sx = SHOULDER_X - SHOULDER_Y * math.sin(yaw)
    sy = SHOULDER_Y * math.cos(yaw)
    dx = x_rel - sx
    dy = y_rel - sy
    return dx * math.cos(yaw) + dy * math.sin(yaw)


def gripper_local(yaw, q2, q3, q4):
    tip = chain(q2, q3, q4)[-1]
    sx = SHOULDER_X - SHOULDER_Y * math.sin(yaw)
    sy = SHOULDER_Y * math.cos(yaw)
    return (
        sx + tip[0] * math.cos(yaw) - TIP_Y * math.sin(yaw),
        sy + tip[0] * math.sin(yaw) + TIP_Y * math.cos(yaw),
        tip[1],
    )


# Boîte du proto : translation -0.018 0 0.255, size 0.84 0.43 0.29.
# Bas z=0.110, haut des roues z=0.165 (commentaire du proto).
CHASSIS_LO = (-0.438, -0.215, 0.110)
CHASSIS_HI = (0.402, 0.215, 0.400)
# Bac P14, arrière du maillage : x -0.46..0.11, rebord z≈0.37, fond z≈0.13.
BIN_LO = (-0.460, -0.215, 0.130)
BIN_HI = (0.110, 0.215, 0.370)
# Creux du bac, ouvert vers le haut. Le bec replié y reste ; les parois sont interdites.
BIN_OPEN_LO = (-0.425, -0.175, 0.165)
BIN_OPEN_HI = (0.070, 0.175, 0.500)
WHEEL_XY = ((0.30, 0.24), (0.30, -0.24), (-0.30, 0.24), (-0.30, -0.24))
WHEEL_R = 0.0825
WHEEL_HALF_W = 0.016
WHEEL_Z = 0.0825
# Mât avant (lidar 0.342, caméra 0.408) dans le devant de la boîte châssis.
MAST_X = 0.280
MAST_Y = 0.170
MAST_Z = 0.520
# Coude levé avant tout lacet : le bec passe au-dessus du châssis (z>0.40).
CLEAR_Q3 = 1.05
PATH_SAMPLES = 5
LINK_GAP = 0.02


def _lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(len(a)))


def arm_points(yaw, q2, q3, q4):
    """Épaule, coude, poignet, bec dans le repère du robot."""
    a1 = A1_0 - q2
    a2 = A2_0 - (q2 + q3)
    a3 = A3_0 - q2 - q3 + q4
    sx = SHOULDER_X - SHOULDER_Y * math.sin(yaw)
    sy = SHOULDER_Y * math.cos(yaw)
    shoulder = (sx, sy, SHOULDER_Z)
    points = [shoulder]
    along = 0.0
    height = 0.0
    for length, angle, y_off in ((L1, a1, 0.0), (L2, a2, -0.0275), (L3 + TIP, a3, TIP_Y)):
        along += length * math.cos(angle)
        height += length * math.sin(angle)
        points.append((
            sx + along * math.cos(yaw) - y_off * math.sin(yaw),
            sy + along * math.sin(yaw) + y_off * math.cos(yaw),
            SHOULDER_Z + height,
        ))
    return points


def _in_aabb(point, low, high):
    return all(low[i] <= point[i] <= high[i] for i in range(3))


def _in_wheel(point):
    x, y, z = point
    for cx, cy in WHEEL_XY:
        if abs(y - cy) <= WHEEL_HALF_W and math.hypot(x - cx, z - WHEEL_Z) <= WHEEL_R:
            return True
        if math.hypot(x - cx, y - cy) < WHEEL_R + 0.015 and z < WHEEL_Z + WHEEL_R:
            return True
    return False


def _in_bin_wall(point):
    if not _in_aabb(point, BIN_LO, BIN_HI):
        return False
    return not _in_aabb(point, BIN_OPEN_LO, BIN_OPEN_HI)


def _in_chassis_solid(point):
    """Dalle et mât avant de la boîte châssis. Le vide autour de l'épaule n'est pas un mur."""
    x, y, z = point
    if not (CHASSIS_LO[0] <= x <= CHASSIS_HI[0] and abs(y) <= CHASSIS_HI[1]):
        return False
    if CHASSIS_LO[2] <= z <= WHEEL_Z + WHEEL_R:
        return True
    if x >= MAST_X and abs(y) <= MAST_Y and WHEEL_Z + WHEEL_R <= z <= MAST_Z:
        return True
    return False


def _links_cross(points):
    shoulder, elbow, wrist, beak = points
    for i in range(6):
        t = i / 5.0
        p = _lerp(shoulder, elbow, t)
        for j in range(6):
            s = j / 5.0
            if math.dist(p, _lerp(wrist, beak, s)) < LINK_GAP:
                return True
    return False


def pose_hits(yaw, q2, q3, q4):
    """Un segment (épaule, coude, poignet, bec) dans le châssis, une roue ou le bac."""
    points = arm_points(yaw, q2, q3, q4)
    shoulder = points[0]
    if _links_cross(points):
        return True
    for index in range(3):
        for step in range(PATH_SAMPLES):
            t = step / (PATH_SAMPLES - 1)
            point = _lerp(points[index], points[index + 1], t)
            if math.dist(point, shoulder) < 0.06:
                continue
            if _in_wheel(point) or _in_bin_wall(point) or _in_chassis_solid(point):
                return True
    return False


def _yaw_too_low(yaw, q2, q3, q4):
    points = arm_points(yaw, q2, q3, q4)
    return points[1][2] < 0.30 or points[3][2] <= CHASSIS_HI[2]


def move_hits(start, end):
    """Échantillons le long du mouvement d'articulations. Jamais de lacet bras bas."""
    yaw_moves = abs(start[0] - end[0]) > 0.12
    for step in range(PATH_SAMPLES):
        pose = _lerp(start, end, step / (PATH_SAMPLES - 1))
        if pose_hits(*pose):
            return True
        if yaw_moves and _yaw_too_low(*pose):
            return True
    return False


def gesture_hits(current, yaw, solved):
    """Levée du coude, lacet en haut, descente, retour au bac, repli."""
    raised_here = (current[0], 0.0, CLEAR_Q3, 0.0)
    raised_side = (yaw, 0.0, CLEAR_Q3, 0.0)
    grasp = (yaw, solved[0], solved[1], solved[2])
    raised_bin = (0.0, 0.0, CLEAR_Q3, 0.0)
    home = (0.0, 0.0, 0.0, 0.0)
    # La prise elle-même doit laisser le bec hors de la boîte. Sinon la touffe
    # n'est atteignable qu'en traversant le robot.
    if _in_aabb(arm_points(*grasp)[3], CHASSIS_LO, CHASSIS_HI):
        return True
    waypoints = (current, raised_here, raised_side, grasp, raised_side, raised_bin, home)
    for pose in waypoints[1:]:
        if pose_hits(*pose):
            return True
    for start, end in zip(waypoints, waypoints[1:]):
        if move_hits(start, end):
            return True
    return False


def is_weed(node):
    if node.getTypeName() == 'WeedClump':
        return True
    field = node.getField('name')
    if field is None:
        return False
    return field.getSFString().startswith('weed')


def collect_weeds(robot):
    weeds = []
    children = robot.getRoot().getField('children')
    for index in range(children.getCount()):
        node = children.getMFNode(index)
        if is_weed(node):
            weeds.append({'node': node, 'seen': False, 'skip': False})
    return weeds


def pixel_green(camera, image, px, py):
    width = camera.getWidth()
    height = camera.getHeight()
    if px < 0 or py < 0 or px >= width or py >= height:
        return False
    red = camera.imageGetRed(image, width, px, py)
    green = camera.imageGetGreen(image, width, px, py)
    blue = camera.imageGetBlue(image, width, px, py)
    return green > 40 and green > red and green > blue


def camera_sees_side(camera, image, on_left):
    """Vert dans le bas de l'image, du côté du rang (la caméra regarde +X)."""
    if image is None:
        return False
    width = camera.getWidth()
    height = camera.getHeight()
    # +Z est le haut de l'image, la droite de l'image est −Y.
    if on_left:
        x0, x1 = 4, width // 2
    else:
        x0, x1 = width // 2, width - 4
    step_x = max(8, (x1 - x0) // 5)
    step_y = max(8, height // 10)
    hits = 0
    for px in range(x0, x1, step_x):
        for py in range(int(height * 0.45), height - 2, step_y):
            if pixel_green(camera, image, px, py):
                hits += 1
                if hits >= 3:
                    return True
    return False


def project_weed(camera, x_rel, y_rel, z_rel):
    dx = x_rel - 0.408
    dy = y_rel
    dz = z_rel - 0.420
    if dx < 0.15:
        return None
    half_h = camera.getFov() * 0.5
    half_v = math.atan(math.tan(half_h) * camera.getHeight() / camera.getWidth())
    px = camera.getWidth() * 0.5 * (1.0 + math.atan2(-dy, dx) / half_h)
    py = camera.getHeight() * 0.5 * (1.0 - math.atan2(dz, dx) / half_v)
    return int(px), int(py)


def camera_sees_weed(camera, image, x_rel, y_rel):
    if image is None:
        return False
    if camera_sees_side(camera, image, y_rel > 0.0):
        return True
    projected = project_weed(camera, x_rel, y_rel, GRASP_Z)
    if projected is None:
        return False
    px, py = projected
    for dx in (-20, -8, 0, 8, 20):
        for dy in (-12, 0, 12, 24):
            if pixel_green(camera, image, px + dx, py + dy):
                return True
    return False


def place_node(node, local, pose):
    wx, wy, wz = robot_to_world(local[0], local[1], local[2], pose[0], pose[1])
    node.getField('translation').setSFVec3f([wx, wy, wz])


def bin_local(slot):
    # Tas dans le bac P14, sous la pince repliée (rebord z ≈ 0,37, fond z ≈ 0,13).
    column = slot % 3
    row = (slot // 3) % 3
    return (-0.02 + column * 0.04, -0.04 + row * 0.04, 0.17)


def run_robot():
    robot = Supervisor()
    time_step = int(robot.getBasicTimeStep())
    dt = time_step / 1000.0

    left_motors = []
    right_motors = []
    for name, side in (
        ('fl_motor', left_motors),
        ('fr_motor', right_motors),
        ('rl_motor', left_motors),
        ('rr_motor', right_motors),
    ):
        motor = robot.getDevice(name)
        if motor is None:
            print("Moteur de roue introuvable : %s" % name, flush=True)
            continue
        motor.setPosition(float('inf'))
        motor.setVelocity(0.0)
        side.append(motor)

    joints = {}
    joint_list = []
    for name, up, down in ARM:
        motor = robot.getDevice(name)
        if motor is None:
            print("Moteur de bras introuvable : %s" % name, flush=True)
            continue
        motor.setPosition(0.0)
        motor.setVelocity(JOINT_SPEED)
        joint = {
            'name': name,
            'motor': motor,
            'target': 0.0,
            'goal': 0.0,
            'min': motor.getMinPosition(),
            'max': motor.getMaxPosition(),
            'up': (ord(up), ord(up.lower())),
            'down': (ord(down), ord(down.lower())),
        }
        joints[name] = joint
        joint_list.append(joint)

    camera = robot.getDevice('front_camera')
    if camera is None:
        print("front_camera introuvable.", flush=True)
    else:
        camera.enable(64)

    lidar = robot.getDevice('rplidar')
    if lidar is not None:
        lidar.enable(128)

    keyboard = robot.getKeyboard()
    keyboard.enable(time_step)

    print(
        "Touches : haut/W avant, bas/S arrière, gauche/A gauche, droite/D droite, "
        "espace arrêt, Q/E S1 lacet, R/F S2 épaule, T/G S3 coude, Y/H S4 poignet, "
        "U/J S5 pince, P désherbage auto.",
        flush=True,
    )

    weeds = collect_weeds(robot)
    if not weeds:
        print("Aucune adventice trouvée.", flush=True)

    left_speed = 0.0
    right_speed = 0.0
    max_step = WHEEL_ACCEL * dt
    joint_step = JOINT_SPEED * dt
    auto = False
    p_was = False
    state = 'stow'
    target = None
    carried = None
    grasp = None
    parked = []
    hold = 0
    announced_end = False

    def set_goal(s1, s2, s3, s4, s5):
        values = {
            'S1_lacet': s1,
            'S2_epaule': s2,
            'S3_coude': s3,
            'S4_poignet': s4,
            'S5_pince': s5,
        }
        for name, value in values.items():
            joint = joints.get(name)
            if joint is None:
                continue
            joint['goal'] = clamp(value, joint['min'], joint['max'])

    def arrived():
        for joint in joint_list:
            if abs(joint['target'] - joint['goal']) > 0.04:
                return False
        return True

    def track_carried(pose):
        if carried is None:
            return
        yaw = joints['S1_lacet']['target']
        local = gripper_local(
            yaw,
            joints['S2_epaule']['target'],
            joints['S3_coude']['target'],
            joints['S4_poignet']['target'],
        )
        place_node(carried['node'], (local[0], local[1], local[2] - 0.02), pose)

    def park(weed, pose):
        place_node(weed['node'], bin_local(len(parked)), pose)
        parked.append(weed)

    def choose_target(pose, image):
        translation, rotation = pose
        best = None
        best_x = 1e9
        left_green = camera_sees_side(camera, image, True)
        right_green = camera_sees_side(camera, image, False)
        for weed in weeds:
            if weed['skip'] or weed in parked or weed is carried:
                continue
            position = weed['node'].getPosition()
            x_rel, y_rel, _z_rel = world_to_robot(
                position[0], position[1], position[2], translation, rotation
            )
            if x_rel < -0.05 or x_rel > 3.0 or abs(y_rel) < 0.2 or abs(y_rel) > 0.85:
                continue
            on_left = y_rel > 0.0
            if not weed['seen'] and (left_green if on_left else right_green):
                weed['seen'] = True
            if not weed['seen'] and camera_sees_weed(camera, image, x_rel, y_rel):
                weed['seen'] = True
            # Brins trop fins : près du robot, la position de la touffe sur le rang suffit.
            if not weed['seen'] and x_rel < 1.6:
                weed['seen'] = True
            if not weed['seen']:
                continue
            if x_rel < best_x:
                best_x = x_rel
                best = weed
        return best

    while robot.step(time_step) != -1:
        keys = pressed_keys(keyboard)
        p_down = (ord('P') in keys) or (ord('p') in keys)
        if p_down and not p_was:
            auto = not auto
            if auto:
                state = 'stow'
                target = None
                grasp = None
                hold = 0
                announced_end = False
                set_goal(0.0, 0.0, 0.0, 0.0, 0.0)
                print("Désherbage auto activé.", flush=True)
            else:
                print("Désherbage auto arrêté.", flush=True)
                if carried is not None:
                    park(carried, robot_pose(robot))
                    carried = None
        p_was = p_down

        pose = robot_pose(robot)
        image = None
        if camera is not None and camera.getImage() is not None:
            image = camera.getImage()

        for weed in parked:
            place_node(weed['node'], bin_local(parked.index(weed)), pose)

        forward = 0.0
        turn = 0.0
        if not auto:
            stopped = (not keys) or (32 in keys)
            if not stopped:
                if Keyboard.UP in keys or ord('W') in keys or ord('w') in keys:
                    forward += 1.0
                if Keyboard.DOWN in keys or ord('S') in keys or ord('s') in keys:
                    forward -= 1.0
                if Keyboard.LEFT in keys or ord('A') in keys or ord('a') in keys:
                    turn += 1.0
                if Keyboard.RIGHT in keys or ord('D') in keys or ord('d') in keys:
                    turn -= 1.0
            left_target = clamp(forward * MAX_WHEEL - turn * TURN, -MAX_WHEEL, MAX_WHEEL)
            right_target = clamp(forward * MAX_WHEEL + turn * TURN, -MAX_WHEEL, MAX_WHEEL)
            if keys:
                for joint in joint_list:
                    if joint['up'][0] in keys or joint['up'][1] in keys:
                        joint['target'] += joint_step
                    if joint['down'][0] in keys or joint['down'][1] in keys:
                        joint['target'] -= joint_step
                    joint['target'] = clamp(joint['target'], joint['min'], joint['max'])
                    joint['goal'] = joint['target']
        else:
            track_carried(pose)
            translation, rotation = pose
            heading = heading_of(rotation)
            lane = LANE_Y
            speed = 0.0
            steer = 0.0

            if state == 'cruise':
                if translation[0] > ROW_END_X:
                    if not announced_end:
                        print("Fin du rang.", flush=True)
                        announced_end = True
                else:
                    if target is None or target['skip'] or target in parked:
                        target = choose_target(pose, image)
                    if target is not None:
                        position = target['node'].getPosition()
                        x_rel, y_rel, _z_rel = world_to_robot(
                            position[0], position[1], position[2], translation, rotation
                        )
                        in_window = GRASP_X0 <= x_rel <= GRASP_X1
                        in_alley = abs(translation[1] - LANE_Y) < 0.1
                        if in_window and in_alley:
                            speed = 0.0
                            state = 'brake'
                            hold = 0
                        elif x_rel < GRASP_X0:
                            target['skip'] = True
                            target = None
                            speed = CRUISE
                        else:
                            speed = 0.45 if x_rel < 0.7 else CRUISE
                    else:
                        speed = CRUISE
            elif state == 'brake':
                speed = 0.0
                hold += 1
                if target is None:
                    state = 'cruise'
                elif (abs(left_speed) < 0.2 and abs(right_speed) < 0.2) or hold > 20:
                    position = target['node'].getPosition()
                    x_rel, y_rel, z_rel = world_to_robot(
                        position[0], position[1], position[2], translation, rotation
                    )
                    # Cible = base de la touffe, quelques cm au-dessus du sol, dans le plan du bras.
                    # Le bec dépasse S5 de TIP : la pointe doit tomber sur ce point, pas au-delà.
                    z_aim = z_rel + GRASP_Z
                    yaw = shoulder_yaw(x_rel, y_rel)
                    along = reach_along(x_rel, y_rel, yaw)
                    solved = solve_arm(along, z_aim)
                    if solved is not None:
                        tip_local = gripper_local(yaw, solved[0], solved[1], solved[2])
                        miss = math.sqrt((tip_local[0] - x_rel)**2 + (tip_local[1] - y_rel)**2 + (tip_local[2] - z_aim)**2)
                        if miss > 0.05:
                            solved = None
                            
                    blocked = False
                    if solved is not None:
                        current = (
                            joints['S1_lacet']['target'],
                            joints['S2_epaule']['target'],
                            joints['S3_coude']['target'],
                            joints['S4_poignet']['target'],
                        )
                        if gesture_hits(current, yaw, solved):
                            solved = None
                            blocked = True
                    if solved is None:
                        target['skip'] = True
                        target = None
                        state = 'cruise'
                        if blocked:
                            print("Trajectoire dans le robot, adventice ignorée.", flush=True)
                    else:
                        side_name = "gauche" if y_rel > 0.0 else "droite"
                        print(
                            "Arrachage %s, distance %.2f m." % (side_name, abs(along)),
                            flush=True,
                        )
                        grasp = (yaw, solved[0], solved[1], solved[2])
                        # Coude levé avant le lacet : pas de bras bas qui balaie le châssis.
                        set_goal(joints['S1_lacet']['target'], 0.0, CLEAR_Q3, 0.0, GRIP_OPEN)
                        state = 'raise'
                        hold = 0
            elif state in ('raise', 'slew', 'reach', 'grip', 'lift', 'transfer', 'open', 'stow'):
                speed = 0.0
                if arrived():
                    hold += 1
                else:
                    hold = 0
                if hold > 12:
                    hold = 0
                    if state == 'raise':
                        set_goal(grasp[0], 0.0, CLEAR_Q3, 0.0, GRIP_OPEN)
                        state = 'slew'
                    elif state == 'slew':
                        set_goal(grasp[0], grasp[1], grasp[2], grasp[3], GRIP_OPEN)
                        state = 'reach'
                    elif state == 'reach':
                        set_goal(
                            joints['S1_lacet']['goal'],
                            joints['S2_epaule']['goal'],
                            joints['S3_coude']['goal'],
                            joints['S4_poignet']['goal'],
                            GRIP_CLOSED,
                        )
                        state = 'grip'
                    elif state == 'grip':
                        carried = target
                        set_goal(grasp[0], 0.0, CLEAR_Q3, 0.0, GRIP_CLOSED)
                        state = 'lift'
                    elif state == 'lift':
                        set_goal(0.0, 0.0, CLEAR_Q3, 0.0, GRIP_CLOSED)
                        state = 'transfer'
                    elif state == 'transfer':
                        set_goal(0.0, 0.0, CLEAR_Q3, 0.0, GRIP_OPEN)
                        state = 'open'
                    elif state == 'open':
                        if carried is not None:
                            park(carried, pose)
                            carried = None
                        target = None
                        grasp = None
                        set_goal(0.0, 0.0, 0.0, 0.0, 0.0)
                        state = 'stow'
                    elif state == 'stow':
                        state = 'cruise'

            y_error = lane - translation[1]
            steer = clamp(3.2 * y_error - 2.0 * heading, -1.2, 1.2)
            if state != 'cruise' or speed == 0.0:
                steer = 0.0
            left_target = clamp(speed - steer, -MAX_WHEEL, MAX_WHEEL)
            right_target = clamp(speed + steer, -MAX_WHEEL, MAX_WHEEL)
            for joint in joint_list:
                joint['target'] = approach(joint['target'], joint['goal'], joint_step)

        left_speed = approach(left_speed, left_target, max_step)
        right_speed = approach(right_speed, right_target, max_step)
        for motor in left_motors:
            motor.setVelocity(left_speed)
        for motor in right_motors:
            motor.setVelocity(right_speed)
        for joint in joint_list:
            joint['motor'].setPosition(joint['target'])


if __name__ == '__main__':
    run_robot()
