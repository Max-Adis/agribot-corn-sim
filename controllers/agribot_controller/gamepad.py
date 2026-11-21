"""Pilotage à la manette (roues + bras) pour agribot_controller.

GamepadControl ne dépend pas de Webots : il reçoit des axes logiques (-1..1) et des noms de
boutons, et rend des consignes. GamepadReader lit un appareil Joystick Webots (ou un faux
joystick de test avec la même interface) et traduit les numéros bruts via un profil."""
import json
import math
import sys

import gamepad_config as cfg


def apply_deadzone(value, deadzone):
    if abs(value) <= deadzone:
        return 0.0
    return math.copysign((abs(value) - deadzone) / (1.0 - deadzone), value)


def pick_profile(model, platform=None):
    if cfg.PROFILE != "auto":
        return cfg.PROFILE
    platform = platform or sys.platform
    name = (model or "").lower()
    if "xbox" in name or "xinput" in name or "x-box" in name:
        return "xbox_windows"
    if platform.startswith("linux"):
        return "ps4_linux"
    return "ps4_windows"


class GamepadReader:
    def __init__(self, joystick, profile=None, debug=None):
        self.joystick = joystick
        self.model = joystick.getModel() if joystick.isConnected() else ""
        self.profile_name = profile or getattr(joystick, 'profile_name', None) or pick_profile(self.model)
        self.profile = cfg.PROFILES[self.profile_name]
        self.debug = cfg.DEBUG if debug is None else debug
        self._by_index = {v: k for k, v in self.profile["buttons"].items()}
        self._last_raw = None

    def describe(self):
        if not self.joystick.isConnected():
            return "Aucune manette détectée (clavier seul)."
        return (f"Manette détectée : « {self.model} », {self.joystick.getNumberOfAxes()} axes, "
                f"profil {self.profile_name}{' (DEBUG)' if self.debug else ''}.")

    def read(self):
        """-> (axes logiques dict, boutons logiques set, boutons bruts list, axes bruts list)."""
        raw_buttons = []
        for _ in range(64):
            b = self.joystick.getPressedButton()
            if b < 0:
                break
            raw_buttons.append(b)
        n_axes = self.joystick.getNumberOfAxes()
        raw_axes = [self.joystick.getAxisValue(i) / 32768.0 for i in range(n_axes)]
        axes = {}
        for name, (index, inverted) in self.profile["axes"].items():
            value = raw_axes[index] if index < n_axes else 0.0
            value = max(-1.0, min(1.0, -value if inverted else value))
            axes[name] = apply_deadzone(value, cfg.DEADZONE)
        buttons = {self._by_index[b] for b in raw_buttons if b in self._by_index}
        if self.debug:
            snapshot = (tuple(sorted(raw_buttons)), tuple(round(a, 1) for a in raw_axes))
            if snapshot != self._last_raw:
                self._last_raw = snapshot
                axes_txt = " ".join(f"{i}:{a:+.2f}" for i, a in enumerate(raw_axes) if abs(a) > 0.15)
                print(f"[manette debug] boutons bruts {sorted(raw_buttons)} -> {sorted(buttons)} | "
                      f"axes bruts (|v|>0,15) {axes_txt or '-'}", flush=True)
        return axes, buttons, raw_buttons, raw_axes


class PadOutput:
    def __init__(self):
        self.drive = None          # (gauche, droite) en fraction de la vitesse max, ou None
        self.block_drive = False   # mode Bras / arrêt d'urgence : roues à 0, clavier compris
        self.block_arm = False     # arrêt d'urgence : servos figés, clavier compris
        self.joint_targets = {}    # nouvelles consignes d'articulations
        self.stop_auto = False
        self.estop_now = False
        self.events = []


class GamepadControl:
    """Logique de la correspondance convenue. limits = {articulation: (min, max)}."""

    def __init__(self, limits):
        self.limits = limits
        self.mode = "roues"
        self.estop = False
        self.grip_goal = None
        self.rest_active = False
        self._prev = set()

    def _clamp(self, name, value):
        low, high = self.limits.get(name, (-math.inf, math.inf))
        return max(low, min(high, value))

    def step(self, dt, axes, buttons, targets):
        out = PadOutput()
        pressed = buttons - self._prev
        self._prev = set(buttons)

        if "circle" in pressed and not self.estop:
            self.estop = True
            self.rest_active = False
            self.grip_goal = None
            out.estop_now = True
            out.stop_auto = True
            out.events.append("ARRÊT D'URGENCE (Rond) : roues et bras figés. Réarmer : PS ou Share.")
        elif self.estop and pressed & set(cfg.REARM_BUTTONS):
            self.estop = False
            out.events.append("Arrêt d'urgence réarmé.")
        if self.estop:
            out.block_drive = True
            out.block_arm = True
            out.drive = (0.0, 0.0)
            return out

        if "l1" in pressed:
            self.mode = "bras" if self.mode == "roues" else "roues"
            self.rest_active = False
            out.events.append("Mode BRAS (le robot ne roule pas)." if self.mode == "bras" else "Mode ROUES.")
        if "ps" in pressed:
            out.stop_auto = True
            out.events.append("Mode manuel (PS).")
        dead_man = "r1" in buttons

        # Pince (Croix / Carré) et pose repos (Triangle en mode Bras) : consignes mémorisées,
        # exécutées seulement R1 maintenu.
        if "cross" in pressed:
            self.grip_goal = cfg.GRIP_OPEN
        if "square" in pressed:
            self.grip_goal = cfg.GRIP_CLOSED
        if "triangle" in pressed:
            if self.mode == "bras":
                self.rest_active = True
                out.events.append("Pose repos / transport (Triangle) : maintenir R1.")
            else:
                out.stop_auto = True
                out.drive = (0.0, 0.0)
                out.events.append("Attente (Triangle) : arrêt.")
        if "options" in pressed:
            out.events.append("Retour au dock (Options) : non simulé, utiliser le site / étape E.")

        if self.mode == "bras":
            out.block_drive = True
            out.drive = (0.0, 0.0)
            if dead_man:
                moving = False
                for joint, axis in cfg.ARM_AXES.items():
                    value = axes.get(axis, 0.0)
                    if value != 0.0 and joint in targets:
                        moving = True
                        new = targets[joint] + cfg.ARM_SIGNS.get(joint, 1.0) * value * cfg.ARM_RATES[joint] * dt
                        out.joint_targets[joint] = self._clamp(joint, new)
                if moving:
                    self.rest_active = False
                if self.rest_active:
                    done = True
                    for joint, goal in cfg.REST_POSE.items():
                        if joint not in targets:
                            continue
                        cur = targets[joint]
                        stepv = cfg.REST_RATE * dt
                        new = goal if abs(goal - cur) <= stepv + 1e-9 else cur + math.copysign(stepv, goal - cur)
                        out.joint_targets[joint] = self._clamp(joint, new)
                        done = done and abs(new - goal) < 1e-6
                    if done:
                        self.rest_active = False
                        self.grip_goal = None
                        out.events.append("Pose repos atteinte.")
        else:
            if dead_man and out.drive is None:
                v = axes.get("ly", 0.0)
                w = axes.get("rx", 0.0)
                s = cfg.DRIVE_SCALE
                out.drive = (max(-s, min(s, (v + w) * s)), max(-s, min(s, (v - w) * s)))

        if dead_man and self.grip_goal is not None and "S5_pince" in targets and not self.rest_active:
            cur = out.joint_targets.get("S5_pince", targets["S5_pince"])
            stepv = cfg.GRIPPER_RATE * dt
            goal = self._clamp("S5_pince", self.grip_goal)
            new = goal if abs(goal - cur) <= stepv + 1e-9 else cur + math.copysign(stepv, goal - cur)
            out.joint_targets["S5_pince"] = new
            if new == goal:
                self.grip_goal = None
        return out


class ReplayJoystick:
    """Faux Joystick Webots qui rejoue un scénario JSON (tests sans manette physique).
    Scénario : {"profile": "ps4_windows", "steps": [{"t": 0.0, "axes": {"lx": 0.5}, "buttons": ["r1"]}, ...]}
    Chaque étape vaut jusqu'à la suivante. Les noms logiques sont traduits en numéros bruts du profil."""

    def __init__(self, path, clock):
        data = json.load(open(path))
        self.profile_name = data.get("profile", "ps4_windows")
        self.profile = cfg.PROFILES[self.profile_name]
        self.steps = sorted(data["steps"], key=lambda s: s["t"])
        self.clock = clock
        self._queue = None

    def _current(self):
        t = self.clock()
        cur = self.steps[0]
        for s in self.steps:
            if s["t"] <= t:
                cur = s
        return cur

    def isConnected(self):
        return True

    def getModel(self):
        return f"Rejeu {self.profile_name}"

    def getNumberOfAxes(self):
        return 1 + max(i for i, _ in self.profile["axes"].values())

    def getAxisValue(self, index):
        for name, (i, inverted) in self.profile["axes"].items():
            if i == index:
                v = self._current().get("axes", {}).get(name, 0.0)
                return int(max(-32768, min(32767, (-v if inverted else v) * 32767)))
        return 0

    def getPressedButton(self):
        if self._queue is None:
            self._queue = [self.profile["buttons"][b] for b in self._current().get("buttons", [])]
        if not self._queue:
            self._queue = None
            return -1
        return self._queue.pop(0)
