"""Contrôleur Agribot v7 pour Webots."""
from controller import Robot


def run_robot():
    robot = Robot()
    time_step = int(robot.getBasicTimeStep())

    motors = [
        robot.getDevice('fl_motor'),
        robot.getDevice('fr_motor'),
        robot.getDevice('rl_motor'),
        robot.getDevice('rr_motor'),
    ]
    for motor in motors:
        motor.setPosition(float('inf'))
        motor.setVelocity(0.0)

    camera = robot.getDevice('front_camera')
    camera.enable(time_step * 2)

    lidar = robot.getDevice('rplidar')
    lidar.enable(time_step * 2)

    print("Agribot démarré dans le champ de maïs !", flush=True)

    # 4.8 rad/s * rayon 0.0825 m ≈ 0.4 m/s
    speed = 4.8

    while robot.step(time_step) != -1:
        for motor in motors:
            motor.setVelocity(speed)


if __name__ == '__main__':
    run_robot()
