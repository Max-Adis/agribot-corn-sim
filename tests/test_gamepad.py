"""Tests sans Webots ni manette de la logique manette (python3 -m unittest discover tests)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controllers", "agribot_controller"))
import gamepad  # noqa: E402
import gamepad_config as cfg  # noqa: E402
from gamepad import GamepadControl, GamepadReader, ReplayJoystick, apply_deadzone, pick_profile  # noqa: E402

# Butées du proto v9b (Agribot.proto).
LIMITS = {"S1_lacet": (-2.3562, 2.3562), "S2_epaule": (-2.7925, 1.9199), "S3_coude": (-0.7854, 3.9270),
          "S4_poignet": (-4.4506, 0.2618), "S5_pince": (-1.5708, 0.0)}
DT = 0.032


class FakeJoystick:
    """Même interface que controller.Joystick (Webots)."""
    def __init__(self, model="Wireless Controller", n_axes=6):
        self.model, self.axes, self.buttons, self._q = model, [0] * n_axes, [], None
    def isConnected(self): return True
    def getModel(self): return self.model
    def getNumberOfAxes(self): return len(self.axes)
    def getAxisValue(self, i): return self.axes[i]
    def getPressedButton(self):
        if self._q is None: self._q = list(self.buttons)
        if not self._q:
            self._q = None
            return -1
        return self._q.pop(0)


def targets0():
    return {k: 0.0 for k in LIMITS}


def run(ctrl, targets, seconds, axes=None, buttons=()):
    out = None
    for _ in range(int(round(seconds / DT))):
        out = ctrl.step(DT, dict(axes or {}), set(buttons), targets)
        targets.update(out.joint_targets)
    return out


def tap(ctrl, targets, button):
    out = ctrl.step(DT, {}, {button}, targets); targets.update(out.joint_targets)
    out2 = ctrl.step(DT, {}, set(), targets); targets.update(out2.joint_targets)
    return out


class TestDeadzoneAndReader(unittest.TestCase):
    def test_deadzone(self):
        self.assertEqual(apply_deadzone(0.14, 0.15), 0.0)
        self.assertAlmostEqual(apply_deadzone(1.0, 0.15), 1.0)
        self.assertAlmostEqual(apply_deadzone(-0.575, 0.15), -0.5)

    def test_profile_choice(self):
        self.assertEqual(pick_profile("Xbox 360 Controller", "win32"), "xbox_windows")
        self.assertEqual(pick_profile("Wireless Controller", "win32"), "ps4_windows")
        self.assertEqual(pick_profile("Sony Interactive Entertainment Wireless Controller", "linux"), "ps4_linux")

    def test_reader_ps4_windows(self):
        js = FakeJoystick()
        r = GamepadReader(js, profile="ps4_windows", debug=False)
        js.axes[1] = -32768          # stick gauche vers le haut (DirectInput : Y négatif)
        js.axes[2] = 32767           # stick droit vers la droite
        js.axes[0] = 3000            # dans la zone morte
        js.buttons = [5, 4]          # R1, L1
        axes, buttons, raw_b, _ = r.read()
        self.assertAlmostEqual(axes["ly"], 1.0, places=3)
        self.assertAlmostEqual(axes["rx"], 1.0, places=3)
        self.assertEqual(axes["lx"], 0.0)
        self.assertEqual(buttons, {"r1", "l1"})
        self.assertEqual(sorted(raw_b), [4, 5])

    def test_reader_xbox(self):
        js = FakeJoystick("Controller (XBOX 360 For Windows)")
        r = GamepadReader(js, debug=False)
        self.assertEqual(r.profile_name, "xbox_windows")
        js.buttons = [0, 1]
        _axes, buttons, _, _ = r.read()
        self.assertEqual(buttons, {"cross", "circle"})

    def test_replay_roundtrip(self):
        import json, tempfile
        sc = {"profile": "ps4_windows", "steps": [{"t": 0, "axes": {"ly": 0.8, "rx": -0.5}, "buttons": ["r1", "triangle"]}]}
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False); json.dump(sc, f); f.close()
        r = GamepadReader(ReplayJoystick(f.name, lambda: 0.0), profile="ps4_windows", debug=False)
        axes, buttons, _, _ = r.read()
        self.assertEqual(buttons, {"r1", "triangle"})
        self.assertAlmostEqual(axes["ly"], apply_deadzone(0.8, cfg.DEADZONE), places=3)
        self.assertAlmostEqual(axes["rx"], apply_deadzone(-0.5, cfg.DEADZONE), places=3)


class TestWheels(unittest.TestCase):
    def test_dead_man_and_mix(self):
        c, t = GamepadControl(LIMITS), targets0()
        self.assertIsNone(run(c, t, 0.2, {"ly": 1.0}).drive)          # sans R1 : rien (clavier libre)
        self.assertEqual(run(c, t, 0.2, {"ly": 1.0}, {"r1"}).drive, (0.6, 0.6))
        self.assertEqual(run(c, t, 0.2, {"ly": -0.5}, {"r1"}).drive, (-0.3, -0.3))
        left, right = run(c, t, 0.2, {"rx": 1.0}, {"r1"}).drive
        self.assertGreater(left, 0); self.assertLess(right, 0)        # stick droit à droite = tourne à droite
        self.assertEqual(t, targets0())                                # les sticks ne bougent pas le bras

    def test_triangle_is_attente_in_wheels(self):
        c, t = GamepadControl(LIMITS), targets0()
        out = c.step(DT, {"ly": 1.0}, {"r1", "triangle"}, t)
        self.assertEqual(out.drive, (0.0, 0.0)); self.assertTrue(out.stop_auto)


class TestArm(unittest.TestCase):
    def arm_mode(self):
        c, t = GamepadControl(LIMITS), targets0()
        tap(c, t, "l1")
        self.assertEqual(c.mode, "bras")
        return c, t

    def test_mode_lock(self):
        c, t = self.arm_mode()
        out = run(c, t, 0.5, {"ly": 1.0, "rx": 1.0}, {"r1"})
        self.assertEqual(out.drive, (0.0, 0.0)); self.assertTrue(out.block_drive)
        out = run(c, t, 0.2, {}, set())
        self.assertTrue(out.block_drive)                               # bloqué même sans R1
        tap(c, t, "l1"); self.assertEqual(c.mode, "roues")

    def test_rate_control_and_hold(self):
        c, t = self.arm_mode()
        run(c, t, 1.0, {"lx": 1.0}, {"r1"})
        self.assertAlmostEqual(t["S1_lacet"], -0.8, delta=0.03)       # 0,8 rad/s, stick à droite = lacet négatif
        held = dict(t)
        run(c, t, 1.0, {}, {"r1"}); self.assertEqual(t, held)         # stick relâché : position tenue
        run(c, t, 1.0, {"lx": 1.0, "ly": 1.0, "ry": 1.0, "rx": 1.0}, set())
        self.assertEqual(t, held)                                      # sans R1 : rien ne bouge
        run(c, t, 0.5, {"ly": 0.5}, {"r1"})
        self.assertGreater(t["S2_epaule"], 0.0)
        run(c, t, 0.5, {"ry": -1.0, "rx": 1.0}, {"r1"})
        self.assertLess(t["S3_coude"], 0.0); self.assertGreater(t["S4_poignet"], 0.0)

    def test_limits(self):
        c, t = self.arm_mode()
        run(c, t, 10.0, {"lx": -1.0, "ly": 1.0, "ry": 1.0, "rx": 1.0}, {"r1"})
        self.assertEqual(t["S1_lacet"], LIMITS["S1_lacet"][1])
        self.assertEqual(t["S2_epaule"], LIMITS["S2_epaule"][1])
        self.assertEqual(t["S3_coude"], LIMITS["S3_coude"][1])
        self.assertEqual(t["S4_poignet"], LIMITS["S4_poignet"][1])
        run(c, t, 20.0, {"lx": 1.0, "ly": -1.0, "ry": -1.0, "rx": -1.0}, {"r1"})
        for j in ("S1_lacet", "S2_epaule", "S3_coude", "S4_poignet"):
            self.assertEqual(t[j], LIMITS[j][0])

    def test_gripper(self):
        c, t = self.arm_mode()
        tap(c, t, "cross"); self.assertEqual(t["S5_pince"], 0.0)       # pas de R1 : rien
        run(c, t, 1.0, {}, {"r1"}); self.assertAlmostEqual(t["S5_pince"], cfg.GRIP_OPEN)
        tap(c, t, "square"); run(c, t, 1.0, {}, {"r1"}); self.assertEqual(t["S5_pince"], cfg.GRIP_CLOSED)

    def test_rest_pose(self):
        c, t = self.arm_mode()
        run(c, t, 1.5, {"lx": 1.0, "ly": 1.0, "ry": 1.0, "rx": -1.0}, {"r1"})
        self.assertNotEqual(t, targets0())
        tap(c, t, "triangle")
        run(c, t, 0.5, {}, set()); self.assertNotEqual(t, targets0())  # attend R1
        run(c, t, 4.0, {}, {"r1"}); self.assertEqual(t, targets0())

    def test_emergency_stop(self):
        c, t = self.arm_mode()
        run(c, t, 0.3, {"lx": 1.0}, {"r1"})
        frozen = dict(t)
        out = tap(c, t, "circle")
        self.assertTrue(out.estop_now and out.stop_auto and out.block_arm and out.block_drive)
        run(c, t, 1.0, {"lx": 1.0, "ly": 1.0}, {"r1"}); self.assertEqual(t, frozen)
        tap(c, t, "l1"); self.assertEqual(c.mode, "bras")             # L1 ignoré pendant l'arrêt
        tap(c, t, "triangle"); run(c, t, 1.0, {}, {"r1"}); self.assertEqual(t, frozen)
        tap(c, t, "ps"); self.assertFalse(c.estop)
        run(c, t, 0.3, {"lx": 1.0}, {"r1"}); self.assertLess(t["S1_lacet"], frozen["S1_lacet"])


if __name__ == "__main__":
    unittest.main()
