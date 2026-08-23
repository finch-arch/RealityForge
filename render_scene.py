#!/usr/bin/env python3
"""Walk G1 through the dressed scene and render it to mp4.

    ./venv/bin/python render_scene.py --seconds 8
    ./venv/bin/python render_scene.py --seconds 8 --plain   # stock scene, for comparison

Free — no API. Produces the source clip for `x2_restyle.py`, and doubles as the
regression check that dressing the scene did not break walking: props are all
>=0.4 m so the terrain-blind policy never tries to step onto one.
"""

import argparse
import pathlib
import subprocess
import sys

import mujoco
import numpy as np
import torch
import yaml

import scene_builder

ROOT = pathlib.Path(__file__).parent
G1 = ROOT / "unitree_rl_gym"
sys.path.insert(0, str(G1))
sys.path.insert(0, str(G1 / "deploy" / "deploy_mujoco"))
from deploy_mujoco import get_gravity_orientation, pd_control  # noqa: E402


def run(args) -> None:
    cfg = yaml.safe_load((G1 / "deploy/deploy_mujoco/configs/g1.yaml").read_text())

    if args.plain:
        scene = pathlib.Path(cfg["xml_path"].replace("{LEGGED_GYM_ROOT_DIR}", str(G1)))
        cleanup = False
        # The stock scene declares no offscreen framebuffer (defaults to 640x480).
        import re
        xml = re.sub(r"(<mujoco[^>]*>)",
                     rf'\1\n<visual><global offwidth="{args.width}" '
                     rf'offheight="{args.height}"/></visual>', scene.read_text(), count=1)
        scene = scene.parent / "_scene_plain.xml"
        scene.write_text(xml)
        cleanup = True
    else:
        scene = scene_builder.build(args.width, args.height,
                                    props=not args.no_props, preset=args.preset)
        cleanup = True

    try:
        m = mujoco.MjModel.from_xml_path(str(scene))
        d = mujoco.MjData(m)
        m.opt.timestep = cfg["simulation_dt"]
        policy = torch.jit.load(
            cfg["policy_path"].replace("{LEGGED_GYM_ROOT_DIR}", str(G1)))

        kps = np.array(cfg["kps"], dtype=np.float32)
        kds = np.array(cfg["kds"], dtype=np.float32)
        default = np.array(cfg["default_angles"], dtype=np.float32)
        n = cfg["num_actions"]
        target = default.copy()
        action = np.zeros(n, dtype=np.float32)
        obs = np.zeros(cfg["num_obs"], dtype=np.float32)
        cmd = np.array([args.vx, 0.0, 0.0], dtype=np.float32)

        renderer = mujoco.Renderer(m, height=args.height, width=args.width)
        cam = mujoco.MjvCamera()
        cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
        cam.trackbodyid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "pelvis")
        cam.distance, cam.elevation = args.cam_dist, args.cam_elev

        ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
             "-pix_fmt", "rgb24", "-s", f"{args.width}x{args.height}",
             "-r", str(args.fps), "-i", "-", "-c:v", "libx264",
             "-preset", "veryfast", "-pix_fmt", "yuv420p", str(args.out)],
            stdin=subprocess.PIPE)

        steps = int(args.seconds / cfg["simulation_dt"])
        every = max(1, int(round(1.0 / (args.fps * cfg["simulation_dt"]))))
        written, min_z = 0, 9.0
        for i in range(steps):
            d.ctrl[:] = pd_control(target, d.qpos[7:], kps,
                                   np.zeros_like(kds), d.qvel[6:], kds)
            mujoco.mj_step(m, d)
            if i % cfg["control_decimation"] == 0:
                ph = (i * cfg["simulation_dt"]) % 0.8 / 0.8
                obs[:3] = d.qvel[3:6] * cfg["ang_vel_scale"]
                obs[3:6] = get_gravity_orientation(d.qpos[3:7])
                obs[6:9] = cmd * np.array(cfg["cmd_scale"], dtype=np.float32)
                obs[9:9 + n] = (d.qpos[7:] - default) * cfg["dof_pos_scale"]
                obs[9 + n:9 + 2 * n] = d.qvel[6:] * cfg["dof_vel_scale"]
                obs[9 + 2 * n:9 + 3 * n] = action
                obs[9 + 3 * n:9 + 3 * n + 2] = [np.sin(2 * np.pi * ph),
                                                np.cos(2 * np.pi * ph)]
                action = policy(torch.from_numpy(obs).unsqueeze(0)) \
                    .detach().numpy().squeeze()
                target = action * cfg["action_scale"] + default
            if i > 500:
                min_z = min(min_z, d.qpos[2])
            if i % every == 0:
                qw, qx, qy, qz = d.qpos[3:7]
                yaw = np.arctan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))
                cam.azimuth = np.degrees(yaw) + 180.0
                cam.lookat[:] = d.qpos[0:3]
                renderer.update_scene(d, camera=cam)
                ff.stdin.write(renderer.render().astype(np.uint8).tobytes())
                written += 1

        ff.stdin.close(); ff.wait(timeout=90)
        renderer.close()

        upright = d.qpos[2] > 0.5 and min_z > 0.45
        print(f"{written} frames ({written/args.fps:.1f}s) -> {args.out}")
        print(f"walked to x={d.qpos[0]:+.2f} y={d.qpos[1]:+.2f}  "
              f"height={d.qpos[2]:.3f} (min {min_z:.3f})")
        print(f"VERDICT: {'WALKED' if upright else 'FELL'}")
    finally:
        if cleanup:
            scene.unlink(missing_ok=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=704)
    ap.add_argument("--vx", type=float, default=0.5)
    ap.add_argument("--cam-dist", type=float, default=3.2)
    ap.add_argument("--cam-elev", type=float, default=-10.0)
    ap.add_argument("--plain", action="store_true", help="stock scene, for comparison")
    ap.add_argument("--no-props", action="store_true")
    ap.add_argument("--preset", default="meadow",
                    help="scene preset: meadow|warehouse|forest|street|courtyard")
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "out" / "scene.mp4")
    run(ap.parse_args())
