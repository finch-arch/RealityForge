#!/usr/bin/env python3
"""Drive a Unitree G1 with WASD, and move a generated world along with it.

    ./venv/bin/python drive_g1.py --no-world          # G1 only, full speed, free
    ./venv/bin/python drive_g1.py                     # + LingBot World 2 at 0.25x

Controls (toggle, not hold — `key_callback` has no key-up event, and both the
robot command and the world-model axes are persistent state anyway):

    W / S   walk forward / back        A / D   strafe left / right
    Q / E   turn left / right          SPACE   stop everything
    R       reset world-model context (drift escape hatch)
    1-4     swap the world's scene prompt

Speed: the world model generates at 0.25x realtime (measured; `attn_window`
does not change it). So the sim is slowed to match, keeping robot and world in
step. The viewer shows slow motion; recorded video plays back normally.
"""

import argparse
import asyncio
import os
import pathlib
import select
import subprocess
import sys
import threading
import time

import mujoco
import mujoco.viewer
import numpy as np
import torch
from PIL import Image
import yaml

ROOT = pathlib.Path(__file__).parent
G1 = ROOT / "unitree_rl_gym"
MODEL = "reactor/lingbot-world-2"

# Safe to import: deploy_mujoco.py guards its sim behind `if __name__ == "__main__"`,
# so only the helpers come across.
sys.path.insert(0, str(G1))
sys.path.insert(0, str(G1 / "deploy" / "deploy_mujoco"))
from deploy_mujoco import get_gravity_orientation, pd_control  # noqa: E402

# Passed as the background to Compositor.frame() to mean "no compositing —
# write the MuJoCo render as-is". Distinct from None, which means "world frame
# not ready yet, skip".
RAW = object()

# GLFW keycodes: letters are uppercase ASCII.
K_W, K_A, K_S, K_D, K_Q, K_E, K_R, K_SPACE = 87, 65, 83, 68, 81, 69, 82, 32

# Visual refresh rate, independent of the 500 Hz physics. Kept low because this
# machine software-renders (no working NVIDIA driver).
SYNC_HZ = 20
# Cap physics steps per frame so a slow render can never make the loop unresponsive;
# the sim falls behind instead of freezing.
MAX_STEPS_PER_FRAME = 200

# Well inside Unitree's own real-robot limits (max_cmd: [0.8, 0.5, 1.57]).
V_FWD, V_LAT, V_YAW = 0.5, 0.3, 0.8

PROMPTS = [
    "A sunlit gravel path winding through an open grassy meadow, tall wheat on both "
    "sides, scattered oak trees, distant rolling hills. Photorealistic, warm light.",
    "A wide concrete warehouse floor, steel racking on both sides, roller shutter "
    "doors, cool overhead strip lighting, painted floor markings. Photorealistic.",
    "A forest trail of packed earth between tall pines, dappled sunlight through the "
    "canopy, ferns and moss along the edges. Photorealistic, soft morning light.",
    "A dusty red Martian plain strewn with rocks, distant eroded cliffs, pale pink "
    "sky, long shadows. Photorealistic, harsh directional sunlight.",
]


class Shared:
    """Latest-value-wins state between the sim thread and the Reactor thread.

    Deliberately not a queue: stale commands are worthless and a queue would
    build unbounded lag behind the world model's ~2 Hz command rate.
    """

    def __init__(self) -> None:
        self.cmd = np.zeros(3, dtype=np.float32)     # vx, vy, yaw-rate
        self.axes = {"long": "idle", "lat": "idle", "look": "idle"}
        self.prompt_idx = 0
        self.prompt_dirty = False
        self.reset_cache = False
        self.quit = False
        self.status = "connecting"
        # Newest world-model frame, overwritten in place. One frame is 4.8 MB;
        # keeping a history is what killed an earlier run.
        self.frame = None

    def stop(self) -> None:
        self.cmd[:] = 0.0
        self.axes.update(long="idle", lat="idle", look="idle")


def show(sh: Shared) -> None:
    print(f"\r  cmd=[{sh.cmd[0]:+.2f} {sh.cmd[1]:+.2f} {sh.cmd[2]:+.2f}]  "
          f"world={sh.axes['long']}/{sh.axes['lat']}/{sh.axes['look']}"
          f"  [{sh.status}]        ", end="", flush=True)


def apply_key(sh: Shared, ch: str) -> bool:
    """Apply one keystroke. `ch` is a lowercase character. True if it did something."""
    # `"" in "1234"` is True in Python, so an empty ch used to fall into the digit
    # branch and raise int(""). Any non-printable viewer key produced one.
    if len(ch) != 1:
        return False
    if ch == "w":
        sh.cmd[0] = V_FWD; sh.axes["long"] = "forward"
    elif ch == "s":
        sh.cmd[0] = -V_FWD; sh.axes["long"] = "back"
    elif ch == "a":
        sh.cmd[1] = V_LAT; sh.axes["lat"] = "strafe_left"
    elif ch == "d":
        sh.cmd[1] = -V_LAT; sh.axes["lat"] = "strafe_right"
    elif ch == "q":
        sh.cmd[2] = V_YAW; sh.axes["look"] = "left"
    elif ch == "e":
        sh.cmd[2] = -V_YAW; sh.axes["look"] = "right"
    elif ch == " ":
        sh.stop()
    elif ch == "r":
        sh.reset_cache = True
    elif ch.isdigit() and ch in "1234":
        sh.prompt_idx = int(ch) - 1
        sh.prompt_dirty = True
    else:
        return False
    show(sh)
    return True


def make_key_callback(sh: Shared):
    """For the MuJoCo viewer window (GLFW keycodes, uppercase ASCII)."""
    def on_key(code: int) -> None:
        try:
            apply_key(sh, chr(code).lower() if 32 < code < 127 else
                      (" " if code == K_SPACE else ""))
        except Exception as exc:                     # never kill the render thread
            print(f"\n  key {code} ignored: {exc}")
    return on_key


def stdin_reader(sh: Shared) -> None:
    """Read keys from the terminal, so control does not depend on window focus.

    The MuJoCo viewer only receives keys when its window is focused, which is
    easy to lose — keystrokes then land in the shell instead. Reading stdin as
    well means you can watch the viewer and drive from the terminal.
    """
    import termios
    import tty

    fd = sys.stdin.fileno()
    try:
        saved = termios.tcgetattr(fd)
    except termios.error:
        # stdin is a pipe, not a terminal — the GUI drives us this way. Read it
        # plainly instead of bailing out; no termios setup is needed or possible.
        saved = None

    try:
        if saved is not None:
            tty.setcbreak(fd)                   # char-at-a-time, Ctrl-C still works
            new = termios.tcgetattr(fd)
            new[3] &= ~termios.ECHO             # don't echo driving keys
            termios.tcsetattr(fd, termios.TCSANOW, new)
        while not sh.quit:
            r, _, _ = select.select([fd], [], [], 0.2)
            if not r:
                continue
            data = sys.stdin.read(1)
            if not data:                        # pipe closed: the GUI is done
                if saved is None:
                    return
                continue
            for ch in data:
                apply_key(sh, ch.lower())
    except Exception:
        pass
    finally:
        if saved is not None:
            termios.tcsetattr(fd, termios.TCSADRAIN, saved)



# ----------------------------------------------------------------------- composite


class Compositor:
    """Cut G1 out of a MuJoCo render and paste it over the world-model frame.

    This is what "replacing the MuJoCo environment" means in practice: the sim
    keeps a bare floor so the robot has something to stand on, but every visible
    pixel of scenery comes from the world model.

    Measured on this (software-rendering) machine: 100 ms/frame at 1664x960 and
    41 ms at 832x480, against a ~4 fps requirement — comfortable either way.
    """

    def __init__(self, model_xml: pathlib.Path, w: int, h: int, fps: int,
                 out_path: pathlib.Path, fovy: float, dist: float, elev: float,
                 preview: bool = False):
        import re
        # G1's scene.xml declares no offscreen framebuffer, so it defaults to
        # 640x480 and any larger Renderer raises. Inject one, writing beside the
        # original so its <include> still resolves.
        xml = re.sub(r"(<mujoco[^>]*>)",
                     rf'\1\n  <visual><global offwidth="{w}" offheight="{h}"/></visual>',
                     model_xml.read_text(), count=1)
        self._tmp = model_xml.parent / "_scene_composite.xml"
        self._tmp.write_text(xml)
        self.model = mujoco.MjModel.from_xml_path(str(self._tmp))
        self.renderer = mujoco.Renderer(self.model, height=h, width=w)
        self.w, self.h = w, h

        self.cam = mujoco.MjvCamera()
        self.cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
        self.cam.trackbodyid = mujoco.mj_name2id(
            self.model, mujoco.mjtObj.mjOBJ_BODY, "pelvis")
        self.cam.distance = dist
        self.cam.elevation = elev
        self.model.vis.global_.fovy = fovy

        self.ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
             "-r", str(fps), "-i", "-",
             "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
             str(out_path)],
            stdin=subprocess.PIPE)
        self.n = 0
        # The MuJoCo viewer shows the raw sim, never the composite — without this
        # you are driving blind and only see the result after the run.
        self.preview = preview
        self._cv2 = None
        if preview:
            try:
                import cv2
                cv2.namedWindow("composite", cv2.WINDOW_NORMAL)
                cv2.resizeWindow("composite", min(w, 960), int(min(w, 960) * h / w))
                self._cv2 = cv2
            except Exception as exc:
                # opencv-python-headless has imshow but no GUI backend; do not
                # let a missing window abort the whole run.
                print(f"  preview unavailable ({type(exc).__name__}); "
                      f"recording continues to {out_path}")

    def _show(self, rgb) -> None:
        if self._cv2 is not None:
            self._cv2.imshow("composite", rgb[:, :, ::-1])   # RGB -> BGR
            self._cv2.waitKey(1)

    def frame(self, data, world_frame) -> None:
        """Render the robot at the sim's current state and composite one frame."""
        # Keep the camera behind the robot's heading, so turning the robot turns
        # the view the same way the world model's look axis does.
        qw, qx, qy, qz = data.qpos[3:7]
        yaw = np.arctan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))
        self.cam.azimuth = np.degrees(yaw) + 180.0
        self.cam.lookat[:] = data.qpos[0:3]

        self.renderer.update_scene(data, camera=self.cam)
        rgb = self.renderer.render()

        self.renderer.enable_segmentation_rendering()
        self.renderer.update_scene(data, camera=self.cam)
        seg = self.renderer.render()
        self.renderer.disable_segmentation_rendering()

        # seg[..., 0] is the geom id; -1 is empty space. The floor is the only
        # non-robot geom in the scene, so excluding it leaves exactly the robot.
        geom = seg[:, :, 0]
        floor = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
        mask = (geom >= 0) & (geom != floor)

        if world_frame is RAW:        # plain chase-cam recording
            self.ff.stdin.write(rgb.astype(np.uint8).tobytes())
            self._show(rgb)
            self.n += 1
            return
        if world_frame is None:
            return                    # no world yet: skip rather than emit sim scenery

        bg = np.asarray(world_frame)
        if bg.shape[:2] != (self.h, self.w):
            bg = np.asarray(Image.fromarray(bg).resize((self.w, self.h)))
        bg = self._contact_shadow(bg, mask)
        out = np.where(mask[:, :, None], rgb, bg)

        out = out.astype(np.uint8)
        self.ff.stdin.write(out.tobytes())
        self._show(out)
        self.n += 1

    def _contact_shadow(self, bg, mask):
        """Darken a soft ellipse under the robot's feet.

        The world model gives no depth, so the cutout is always drawn in front of
        everything and reads as floating. A fake contact shadow is the standard
        compositing fix and does most of the work of grounding the figure.
        """
        ys, xs = np.nonzero(mask)
        if ys.size == 0:
            return bg
        cx = int(xs.mean())
        foot_y = int(ys.max())
        rx = max(8, int((xs.max() - xs.min()) * 0.75))
        ry = max(3, rx // 4)
        y0, y1 = max(0, foot_y - ry), min(self.h, foot_y + ry)
        x0, x1 = max(0, cx - rx), min(self.w, cx + rx)
        if y1 <= y0 or x1 <= x0:
            return bg

        yy, xx = np.mgrid[y0:y1, x0:x1]
        r2 = ((xx - cx) / rx) ** 2 + ((yy - foot_y) / ry) ** 2
        fall = np.clip(1.0 - r2, 0.0, 1.0) ** 1.5          # soft edge
        bg = bg.copy()
        patch = bg[y0:y1, x0:x1].astype(np.float32)
        bg[y0:y1, x0:x1] = (patch * (1.0 - 0.55 * fall[:, :, None])).astype(np.uint8)
        return bg

    def close(self) -> None:
        try:
            self.ff.stdin.close(); self.ff.wait(timeout=30)
        except Exception:
            pass
        try:
            self.renderer.close()
        except Exception:
            pass
        if self._cv2 is not None:
            try:
                self._cv2.destroyAllWindows()
            except Exception:
                pass
        self._tmp.unlink(missing_ok=True)


# --------------------------------------------------------------------------- world


async def world_loop(sh: Shared, args) -> None:
    """Mirror the key state onto the world model. Runs on its own thread."""
    from reactor_sdk import Reactor, ReactorStatus

    key = (ROOT / "api.js").read_text().strip()
    reactor = Reactor(model_name=MODEL, api_key=key)
    ready, cond = asyncio.Event(), asyncio.Event()

    @reactor.on_status(ReactorStatus.READY)
    async def on_ready(status):
        ready.set()

    @reactor.on_message
    def on_message(msg):
        t = msg.get("type")
        if t == "conditions_ready":
            cond.set()
        elif t == "command_error":
            print(f"\n  [command_error] {msg.get('data')}")

    sent = {"long": None, "lat": None, "look": None}
    t_gen = time.monotonic()

    try:
        sh.status = "connecting"
        await reactor.connect()
        await asyncio.wait_for(ready.wait(), timeout=60)
        sh.status = "uploading"

        if args.composite:
            @reactor.track("main_video").on_frame
            def on_frame(frame):
                sh.frame = frame          # reference only; never appended

        ref = await reactor.upload_file(str(args.image))
        await reactor.send_command("set_seed", {"seed": args.seed})
        await reactor.send_command("set_image", {"image": ref})
        await reactor.send_command("set_prompt", {"prompt": PROMPTS[0]})
        await reactor.send_command("set_kv_cache_reset", {"mode": "auto"})
        sh.status = "waiting for model"
        await asyncio.wait_for(cond.wait(), timeout=120)
        await reactor.send_command("start", {})
        sh.status = "live"

        cmd_for = {
            "long": ("set_move_longitudinal", "move_longitudinal"),
            "lat":  ("set_move_lateral", "move_lateral"),
            "look": ("set_look_horizontal", "look_horizontal"),
        }

        while not sh.quit:
            # Persistent axes: only emit on a real change, at most at chunk rate.
            for axis, (command, field) in cmd_for.items():
                want = sh.axes[axis]
                if want != sent[axis]:
                    await reactor.send_command(command, {field: want})
                    sent[axis] = want

            if sh.prompt_dirty:
                sh.prompt_dirty = False
                await reactor.send_command(
                    "set_prompt", {"prompt": PROMPTS[sh.prompt_idx]})
            if sh.reset_cache:
                sh.reset_cache = False
                await reactor.send_command("trigger_kv_cache_reset", {})

            await asyncio.sleep(0.3)          # just under the ~0.456 s chunk cadence

        if args.out:
            secs = (time.monotonic() - t_gen) * 0.25   # measured media rate
            secs = max(3.0, min(secs, 60.0))
            print(f"\n\ndownloading ~{secs:.0f}s clip ...")
            await reactor.download_clip(secs, args.out, ready_timeout=45)
            print(f"saved {args.out}")
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        print(f"\n  !! world model unavailable: {type(exc).__name__}: {exc}")
        print("     the sim keeps running; re-run with --no-world to skip it entirely")
        sh.status = "WORLD DOWN"
    finally:
        try:
            await reactor.send_command("reset", {})
        except Exception:
            pass
        await reactor.disconnect()


# ----------------------------------------------------------------------------- sim


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-world", action="store_true",
                    help="G1 only at full speed; no Reactor session, costs nothing")
    ap.add_argument("--speed", type=float, default=None,
                    help="sim speed vs wall clock (default 0.25 with world, 1.0 without)")
    ap.add_argument("--image", type=pathlib.Path, default=ROOT / "out" / "seed.png")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=pathlib.Path, default=None,
                    help="download a clip of the drive on exit (.ts)")
    ap.add_argument("--duration", type=float, default=300.0)
    ap.add_argument("--describe", default=None, metavar="TEXT",
                    help='build a scene from a description and drive it, e.g. '
                         '--describe "a scene in banaras". Generates, validates '
                         'and walk-tests it first. Implies --dressed.')
    ap.add_argument("--preset", default=None,
                    help="an existing scene by name — the six built-ins "
                         "(meadow|warehouse|forest|street|courtyard|medieval) or "
                         "anything --describe saved earlier. `--preset list` shows "
                         "all of them with their matching LingBot prompts.")
    ap.add_argument("--dressed", action="store_true",
                    help="teleop in the dressed physics scene — grass, sky, and "
                         "props you can actually walk into — instead of the stock "
                         "black-void checkerboard")
    ap.add_argument("--record", type=pathlib.Path, default=None,
                    help="record the third-person chase view to mp4; works with "
                         "--no-world, no world model needed")
    ap.add_argument("--composite", type=pathlib.Path, default=None,
                    help="render G1 over the generated world into this .mp4")
    ap.add_argument("--comp-size", default="832x480",
                    help="composite resolution (832x480 is ~2.5x faster than 1664x960)")
    ap.add_argument("--comp-fps", type=int, default=10)
    ap.add_argument("--preview", action="store_true",
                    help="show the composited frames live in a window; the MuJoCo "
                         "viewer only ever shows the raw sim")
    ap.add_argument("--script", default=None,
                    help="scripted keys for reproducible runs / headless testing, "
                         "e.g. \"0:w,8:q,14: ,18:w\" (seconds:key)")
    ap.add_argument("--cam-dist", type=float, default=3.0,
                    help="camera distance behind the robot")
    ap.add_argument("--cam-elev", type=float, default=-10.0,
                    help="camera elevation in degrees (negative looks down)")
    ap.add_argument("--cam-fovy", type=float, default=60.0,
                    help="vertical field of view; tune so horizons line up")
    args = ap.parse_args()

    if args.describe:
        # One command: describe -> generate -> validate -> walk-test -> drive.
        import hashlib
        import scene_describe
        name = "d_" + hashlib.sha1(args.describe.encode()).hexdigest()[:8]
        try:
            import custom_presets
            known = name in custom_presets.CUSTOM
        except Exception:
            known = False
        if known:
            print(f"scene for that description already built ({name})")
        else:
            print(f"building a scene for: {args.describe}")
            r = subprocess.run(
                [sys.executable, "scene_describe.py", args.describe, "--save", name],
                cwd=str(ROOT))
            if r.returncode != 0:
                sys.exit("could not build a walkable scene from that description")
        # The subprocess wrote custom_presets.py after we imported scene_builder.
        import scene_builder as _sb
        _sb.refresh()
        args.preset = name

    if args.preset == "list":
        import scene_builder
        for name in sorted(scene_builder.PRESETS):
            print(f"\n{name}\n  {scene_builder.preset_prompt(name)}")
        return
    if args.preset:
        args.dressed = True

    if args.speed is None:
        # 0.25 keeps the world model, which generates at 0.25x realtime, in step.
        args.speed = 1.0 if args.no_world else 0.25

    cfg = yaml.safe_load(
        (G1 / "deploy" / "deploy_mujoco" / "configs" / "g1.yaml").read_text())
    root = str(G1)
    policy = torch.jit.load(cfg["policy_path"].replace("{LEGGED_GYM_ROOT_DIR}", root))
    if args.dressed:
        import scene_builder
        cw0, ch0 = ((int(v) for v in args.comp_size.lower().split("x"))
                    if (args.composite or args.record) else (1280, 704))
        scene_path = scene_builder.build(cw0, ch0, props=True,
                                         preset=args.preset or "meadow")
        print(f"scene: {args.preset or 'meadow'}")
    else:
        scene_path = pathlib.Path(cfg["xml_path"].replace("{LEGGED_GYM_ROOT_DIR}", root))
    m = mujoco.MjModel.from_xml_path(str(scene_path))
    d = mujoco.MjData(m)
    m.opt.timestep = cfg["simulation_dt"]

    kps = np.array(cfg["kps"], dtype=np.float32)
    kds = np.array(cfg["kds"], dtype=np.float32)
    default = np.array(cfg["default_angles"], dtype=np.float32)
    n = cfg["num_actions"]
    target = default.copy()
    action = np.zeros(n, dtype=np.float32)
    obs = np.zeros(cfg["num_obs"], dtype=np.float32)

    sh = Shared()
    traj = []

    rec = None
    if args.record:
        cw, ch = (int(v) for v in args.comp_size.lower().split("x"))
        rec = Compositor(scene_path, cw, ch, args.comp_fps, args.record,
                         args.cam_fovy, args.cam_dist, args.cam_elev,
                         preview=args.preview)
        print(f"recording chase view {cw}x{ch} -> {args.record}")

    comp = None
    if args.composite:
        cw, ch = (int(v) for v in args.comp_size.lower().split("x"))
        comp = Compositor(
            scene_path,
            cw, ch, args.comp_fps, args.composite,
            args.cam_fovy, args.cam_dist, args.cam_elev, preview=args.preview)
        print(f"compositing {cw}x{ch} @ {args.comp_fps}fps -> {args.composite}")

    thread = None
    if not args.no_world:
        thread = threading.Thread(
            target=lambda: asyncio.run(world_loop(sh, args)), daemon=True)
        thread.start()
    else:
        sh.status = "no world"

    # Control from the terminal as well as the viewer window: the viewer only
    # gets keys while it is focused, and focus is easy to lose.
    try:
        import termios
        TTY_SAVED = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        TTY_SAVED = None
    keys = threading.Thread(target=stdin_reader, args=(sh,), daemon=True)
    keys.start()

    print(__doc__.split("Controls")[1].split("Speed:")[0])
    print(f"sim speed: {args.speed}x   world: {'off' if args.no_world else 'on'}")
    print("keys work here in the terminal, or in the viewer window\n")
    show(sh)

    script = []
    if args.script:
        for item in args.script.split(","):
            when, _, key = item.partition(":")
            script.append((float(when), key))
        script.sort()
        print(f"scripted: {script}")

    counter = 0
    sim_t = 0.0
    last_sync = 0.0
    last_status = 0.0
    last_comp = 0.0
    dt = cfg["simulation_dt"]
    t0 = time.time()
    try:
        with mujoco.viewer.launch_passive(
                m, d, key_callback=make_key_callback(sh)) as viewer:
            while viewer.is_running() and time.time() - t0 < args.duration:
                # Render rate is decoupled from physics rate. This box has no
                # working NVIDIA driver, so MuJoCo software-renders a 64-mesh
                # model; syncing every 2 ms step ran the sim at 1/135th speed.
                target_sim = (time.time() - t0) * args.speed
                while script and sim_t >= script[0][0]:
                    apply_key(sh, script.pop(0)[1].lower())
                stepped = 0
                while sim_t < target_sim and stepped < MAX_STEPS_PER_FRAME:
                    tau = pd_control(target, d.qpos[7:], kps,
                                     np.zeros_like(kds), d.qvel[6:], kds)
                    d.ctrl[:] = tau
                    mujoco.mj_step(m, d)
                    counter += 1
                    sim_t += dt
                    stepped += 1

                    if counter % cfg["control_decimation"] == 0:
                        phase = (counter * dt) % 0.8 / 0.8
                        obs[:3] = d.qvel[3:6] * cfg["ang_vel_scale"]
                        obs[3:6] = get_gravity_orientation(d.qpos[3:7])
                        obs[6:9] = sh.cmd * np.array(cfg["cmd_scale"],
                                                     dtype=np.float32)
                        obs[9:9 + n] = (d.qpos[7:] - default) * cfg["dof_pos_scale"]
                        obs[9 + n:9 + 2 * n] = d.qvel[6:] * cfg["dof_vel_scale"]
                        obs[9 + 2 * n:9 + 3 * n] = action
                        obs[9 + 3 * n:9 + 3 * n + 2] = [np.sin(2 * np.pi * phase),
                                                        np.cos(2 * np.pi * phase)]
                        action = policy(torch.from_numpy(obs).unsqueeze(0)) \
                            .detach().numpy().squeeze()
                        target = action * cfg["action_scale"] + default
                        # Base pose, for later compositing work.
                        traj.append((counter * dt, *d.qpos[0:3], *d.qpos[3:7]))

                if stepped == 0:
                    time.sleep(0.001)          # ahead of schedule; yield

                now = time.time()
                if now - last_sync >= 1.0 / SYNC_HZ:
                    viewer.sync()
                    last_sync = now
                if now - last_status >= 1.0:
                    last_status = now
                    show(sh)
                if now - last_comp >= 1.0 / args.comp_fps:
                    last_comp = now
                    if comp is not None:
                        comp.frame(d, sh.frame)
                    if rec is not None:
                        rec.frame(d, RAW)
    except KeyboardInterrupt:
        pass
    finally:
        sh.quit = True
        if rec is not None:
            rec.close()
            print(f"\nchase view: {rec.n} frames -> {args.record}")
        if comp is not None:
            comp.close()
            if comp.n:
                print(f"\ncomposite: {comp.n} frames -> {args.composite}")
            else:
                print("\ncomposite: NO frames — the world model never delivered any.")
                print("  check the status above; --no-world runs the sim alone.")
        if thread:
            # Short and interruptible: a long join makes Ctrl-C feel like a hang,
            # and interrupting it mid-cleanup can segfault the GL teardown.
            print("\nclosing world session ...", flush=True)
            try:
                thread.join(timeout=20)
                if thread.is_alive():
                    print("  (still closing; exiting anyway)")
            except KeyboardInterrupt:
                print("  (interrupted; exiting now)")

    if traj:
        p = ROOT / "out" / "trajectory.csv"
        p.parent.mkdir(exist_ok=True)
        p.write_text("t,x,y,z,qw,qx,qy,qz\n" +
                     "\n".join(",".join(f"{v:.5f}" for v in row) for row in traj))
        print(f"\ntrajectory: {len(traj)} samples -> {p}")
        print(f"final pose: x={d.qpos[0]:+.2f} y={d.qpos[1]:+.2f} z={d.qpos[2]:.3f}")

    # The viewer's UI thread is not a daemon, so a normal return hangs the
    # process. Everything of ours (world teardown, trajectory) is already
    # flushed by this point.
    # os._exit skips normal cleanup, so put the terminal back by hand first —
    # otherwise the shell is left without echo.
    if TTY_SAVED is not None:
        try:
            import termios
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, TTY_SAVED)
        except Exception:
            os.system("stty sane")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
