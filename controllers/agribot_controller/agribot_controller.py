"""Contrôleur Agribot v7 pour Webots : téléopération clavier."""
from controller import Keyboard, Robot

# 4.8 rad/s * rayon 0.0825 m ≈ 0.4 m/s
MAX_WHEEL = 4.8
TURN = 3.6
WHEEL_ACCEL = 12.0
GRIPPER_SPEED = 0.8


def clamp(value, low, high):
    return max(low, min(high, value))


def approach(current, target, max_step):
    if current < target:
        return min(current + max_step, target)
    return max(current - max_step, target)


def pressed_keys(keyboard):
    keys = set()
    key = keyboard.getKey()
    while key != -1:
        keys.add(key & Keyboard.KEY)
        key = keyboard.getKey()
    return keys


def run_robot():
    robot = Robot()
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

    gripper = robot.getDevice('gripper_yaw')
    grip_target = 0.0
    grip_min = -1.25
    grip_max = 1.25
    if gripper is None:
        print("Moteur de pince introuvable.", flush=True)
    else:
        grip_min = gripper.getMinPosition()
        grip_max = gripper.getMaxPosition()
        gripper.setPosition(grip_target)
        gripper.setVelocity(GRIPPER_SPEED)

    # Seule caméra activée : front_camera. Aucune caméra de pince.
    camera = robot.getDevice('front_camera')
    if camera is None:
        print("front_camera introuvable.", flush=True)
    else:
        camera.enable(time_step * 2)

    lidar = robot.getDevice('rplidar')
    if lidar is not None:
        lidar.enable(time_step * 2)

    keyboard = robot.getKeyboard()
    keyboard.enable(time_step)

    print(
        "Touches : haut/W avant, bas/S arrière, gauche/A gauche, droite/D droite, "
        "espace arrêt, Q pince à gauche, E pince à droite.",
        flush=True,
    )

    left_speed = 0.0
    right_speed = 0.0
    max_step = WHEEL_ACCEL * dt

    while robot.step(time_step) != -1:
        keys = pressed_keys(keyboard)
        forward = 0.0
        turn = 0.0
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

        # Tourner à gauche : roues gauches plus lentes. Vitesse bornée.
        left_target = clamp(forward * MAX_WHEEL - turn * TURN, -MAX_WHEEL, MAX_WHEEL)
        right_target = clamp(forward * MAX_WHEEL + turn * TURN, -MAX_WHEEL, MAX_WHEEL)
        left_speed = approach(left_speed, left_target, max_step)
        right_speed = approach(right_speed, right_target, max_step)
        for motor in left_motors:
            motor.setVelocity(left_speed)
        for motor in right_motors:
            motor.setVelocity(right_speed)

        if gripper is not None and keys:
            if ord('Q') in keys or ord('q') in keys:
                grip_target += GRIPPER_SPEED * dt
            if ord('E') in keys or ord('e') in keys:
                grip_target -= GRIPPER_SPEED * dt
            grip_target = clamp(grip_target, grip_min, grip_max)
            gripper.setPosition(grip_target)


if __name__ == '__main__':
    run_robot()
