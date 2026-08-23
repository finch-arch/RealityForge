#!/usr/bin/env python3
"""Inverted pipeline test: MuJoCo does the physics, SANA-Streaming does the looks.

    ./venv/bin/python sana_restyle.py --seconds 6

Renders G1 walking through a MuJoCo scene that has *real geometry* — obstacles it
can actually collide with — then sends that clip to SANA-Streaming to be restyled
photorealistically.

This is the opposite of `drive_g1.py`. There, LingBot World 2 *is* the environment
and the robot is composited on top, with no physical relationship between them.
Here the environment is real MuJoCo geometry with full contact physics, and the
generative model is only a renderer. Nothing to composite, nothing to keep in
sync, and the robot can genuinely hit things.

Kept entirely separate from the LingBot code, which still works as before.
"""

import argparse
import asyncio
import pathlib
import re
import subprocess
import sys
import time

import mujoco
import numpy as np
import torch
import yaml
from reactor_sdk import Reactor, ReactorStatus

ROOT = pathlib.Path(__file__).parent
G1 = ROOT / "unitree_rl_gym"
MODEL = "reactor/sana-streaming"

sys.path.insert(0, str(G1))
sys.path.insert(0, str(G1 / "deploy" / "deploy_mujoco"))
from deploy_mujoco import get_gravity_orientation, pd_control  # noqa: E402

# SANA emits 1280x704. Render the source at the same shape so nothing is rescaled.
W, H = 1280, 704
FPS = 24                       # SANA chunks hold 24 frames
MIN_FRAMES = 33                # file mode rejects anything shorter

DEFAULT_PROMPT = (
    "A photorealistic humanoid robot walking along a dirt path through an open "
    "meadow, scattered boulders and wooden crates beside the path, warm afternoon "
    "sunlight, distant hills. Cinematic, natural lighting."
)

# Real geometry the robot can actually collide with — the whole point of inverting.
OBSTACLES = """
    <geom name="obs1" type="box" pos="3.0 0.6 0.15" size="0.3 0.3 0.15" rgba=".55 .5 .45 1"/>
    <geom name="obs2" type="box" pos="5.0 -0.7 0.2" size="0.25 0.4 0.2" rgba=".5 .45 .4 1"/>
    <geom name="obs3" type="cylinder" pos="7.0 0.5 0.25" size="0.25 0.25" rgba=".45 .42 .4 1"/>
    <geom name="obs4" type="box" pos="9.0 -0.4 0.12" size="0.4 0.3 0.12" rgba=".52 .48 .44 1"/>
"""


def read_api_key() -> str:
    key = (ROOT / "api.js").read_text().strip()
    if not key.startswith("rk_"):
        sys.exit("api.js does not contain a Reactor key")
    return key


def build_scene() -> pathlib.Path:
    """Patch G1's scene with a bigger framebuffer and real obstacles."""
    cfg = yaml.safe_load((G1 / "deploy/deploy_mujoco/configs/g1.yaml").read_text())
    src = pathlib.Path(cfg["xml_path"].replace("{LEGGED_GYM_ROOT_DIR}", str(G1)))
    xml = src.read_text()
    # G1's scene declares no offscreen framebuffer, so it defaults to 640x480.
    xml = re.sub(r"(<mujoco[^>]*>)",
                 rf'\1\n  <visual><global offwidth="{W}" offheight="{H}"/></visual>',
                 xml, count=1)
    xml = xml.replace("</worldbody>", OBSTACLES + "</worldbody>", 1)
    # Written beside the original so its <include> still resolves.
    out = src.parent / "_scene_sana.xml"
    out.write_text(xml)
    return out


def render_clip(seconds: float, out_path: pathlib.Path) -> int:
    """Walk G1 through the scene and write a plain MuJoCo render."""
    cfg = yaml.safe_load((G1 / "deploy/deploy_mujoco/configs/g1.yaml").read_text())
    scene = build_scene()
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
        cmd = np.array([0.5, 0.0, 0.0], dtype=np.float32)

        renderer = mujoco.Renderer(m, height=H, width=W)
        cam = mujoco.MjvCamera()
        cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
        cam.trackbodyid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "pelvis")
        cam.distance, cam.elevation = 3.0, -8.0

        ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
             "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
             "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
             str(out_path)],
            stdin=subprocess.PIPE)

        steps = int(seconds / cfg["simulation_dt"])
        every = max(1, int(round(1.0 / (FPS * cfg["simulation_dt"]))))
        written = 0
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
            if i % every == 0:
                yaw = np.arctan2(2 * (d.qpos[3] * d.qpos[6] + d.qpos[4] * d.qpos[5]),
                                 1 - 2 * (d.qpos[5] ** 2 + d.qpos[6] ** 2))
                cam.azimuth = np.degrees(yaw) + 180.0
                cam.lookat[:] = d.qpos[0:3]
                renderer.update_scene(d, camera=cam)
                ff.stdin.write(renderer.render().astype(np.uint8).tobytes())
                written += 1

        ff.stdin.close(); ff.wait(timeout=60)
        renderer.close()
        print(f"rendered {written} frames ({written/FPS:.1f}s) -> {out_path}")
        print(f"robot walked to x={d.qpos[0]:+.2f} (obstacles at x=3,5,7,9)")
        return written
    finally:
        scene.unlink(missing_ok=True)


async def restyle(src: pathlib.Path, dst: pathlib.Path, prompt: str,
                  seed: int, anchor: int) -> None:
    reactor = Reactor(model_name=MODEL, api_key=read_api_key())
    ready, cond, done = asyncio.Event(), asyncio.Event(), asyncio.Event()
    frames = 0
    ff = None

    @reactor.on_status(ReactorStatus.READY)
    async def on_ready(status):
        ready.set()

    @reactor.on_message
    def on_message(msg):
        t = msg.get("type")
        if t == "conditions_ready":
            cond.set()
        elif t == "generation_complete":
            done.set()
        elif t in ("video_accepted", "generation_started", "anchored"):
            print(f"  {t}: {msg.get('data')}")
        elif t == "command_error":
            print(f"  [command_error] {msg.get('data')}")

    try:
        print(f"connecting to {MODEL} ...")
        await reactor.connect()
        await asyncio.wait_for(ready.wait(), timeout=60)

        ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
             "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
             "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
             str(dst)],
            stdin=subprocess.PIPE)

        @reactor.track("main_video").on_frame
        def on_frame(frame):
            nonlocal frames
            ff.stdin.write(np.asarray(frame).astype(np.uint8).tobytes())
            frames += 1

        ref = await reactor.upload_file(str(src))
        await reactor.send_command("set_mode", {"mode": "file"})
        await reactor.send_command("set_video", {"video": ref})
        await reactor.send_command("set_prompt", {"prompt": prompt})
        await reactor.send_command("set_seed", {"seed": seed})
        if anchor:
            # Re-ground every N chunks; SANA's built-in drift mitigation.
            await reactor.send_command("set_anchor_interval", {"chunks": anchor})

        await asyncio.wait_for(cond.wait(), timeout=120)
        t0 = time.monotonic()
        await reactor.send_command("start", {})
        print("restyling ...")

        # File mode completes on its own.
        try:
            await asyncio.wait_for(done.wait(), timeout=300)
        except asyncio.TimeoutError:
            print("  (timed out waiting for generation_complete)")
        print(f"  {frames} frames in {time.monotonic()-t0:.1f}s wall")
    finally:
        try:
            await reactor.send_command("reset", {})
        except Exception:
            pass
        await reactor.disconnect()
        if ff:
            try:
                ff.stdin.close(); ff.wait(timeout=60)
            except Exception:
                pass
    print(f"\nsource : {src}\nrestyled: {dst}  ({frames} frames)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--anchor", type=int, default=4,
                    help="re-ground every N chunks (0 disables)")
    ap.add_argument("--src", type=pathlib.Path, default=ROOT / "out" / "sana_src.mp4")
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "out" / "sana_out.mp4")
    ap.add_argument("--render-only", action="store_true",
                    help="render the MuJoCo clip and stop (free)")
    args = ap.parse_args()
    args.src.parent.mkdir(exist_ok=True)

    n = render_clip(args.seconds, args.src)
    if n < MIN_FRAMES:
        sys.exit(f"only {n} frames; SANA file mode needs at least {MIN_FRAMES}")
    if args.render_only:
        print("render-only: stopping before the API call")
        return
    asyncio.run(restyle(args.src, args.out, args.prompt, args.seed, args.anchor))


if __name__ == "__main__":
    main()
