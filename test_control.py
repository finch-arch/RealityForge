#!/usr/bin/env python3
"""Tests 3 & 4: does control actually work, and which way do the axes point?

Runs scripted phases (still / forward / look-left / camera_pose probes),
tagging every frame with the phase active when it arrived, then writes a
contact sheet so the motion can be judged by eye.

The schema documents rotations as radians relative to current orientation
and translations as relative to current position, but never states the
translation *unit* — that's what the +tx / +tz probes are for.

Usage:  ./venv/bin/python test_control.py
"""

import asyncio
import json
import pathlib
import time

import numpy as np
from PIL import Image
from reactor_sdk import Reactor, ReactorStatus

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out"
MODEL = "reactor/lingbot-world-2"
PROMPT = (
    "A sunlit gravel path winding through an open grassy meadow, "
    "scattered trees, distant hills, clear sky, photorealistic"
)

# (label, seconds, command, params)
PHASES = [
    ("still",        3.0, None,                    None),
    ("forward",      5.0, "set_move_longitudinal", {"move_longitudinal": "forward"}),
    ("stop",         2.0, "set_move_longitudinal", {"move_longitudinal": "idle"}),
    ("look_left",    4.0, "set_look_horizontal",   {"look_horizontal": "left"}),
    ("look_idle",    2.0, "set_look_horizontal",   {"look_horizontal": "idle"}),
    # Camera-pose probes: one 6-tuple = one motion across the whole next chunk.
    ("pose_+tx",     4.0, "set_camera_pose",       {"camera_pose": [0, 0, 0, 0.5, 0, 0]}),
    ("pose_+tz",     4.0, "set_camera_pose",       {"camera_pose": [0, 0, 0, 0, 0, 0.5]}),
    ("pose_+ry",     4.0, "set_camera_pose",       {"camera_pose": [0, 0.05, 0, 0, 0, 0]}),
    ("pose_release", 2.0, "set_camera_pose",       {"camera_pose": []}),
]


def read_api_key() -> str:
    key = (ROOT / "api.js").read_text().strip()
    if not key.startswith("rk_"):
        raise SystemExit("api.js does not contain a Reactor key (expected rk_...)")
    return key


async def main() -> None:
    reactor = Reactor(model_name=MODEL, api_key=read_api_key())
    ready = asyncio.Event()
    conditions_ready = asyncio.Event()

    phase = {"name": "init", "t": time.monotonic()}
    stats: dict[str, dict] = {}
    errors: list[str] = []

    @reactor.on_status(ReactorStatus.READY)
    async def on_ready(status):
        ready.set()

    @reactor.on_message
    def on_message(msg):
        if msg.get("type") == "conditions_ready":
            conditions_ready.set()
        elif msg.get("type") == "command_error":
            errors.append(json.dumps(msg.get("data", {})))
            print(f"  [command_error] {msg.get('data')}")

    @reactor.on_error
    def on_error(err):
        print(f"  [ERROR] {err.operation}: [{err.code}] {err.message}")

    try:
        await reactor.connect()
        await asyncio.wait_for(ready.wait(), timeout=60)
        print(f"READY  session={reactor.get_session_id()}")

        video = reactor.track("main_video")

        @video.on_frame
        def on_frame(frame):
            # Frames are 1664x960x3 = 4.8 MB each. Keeping them all blows up
            # memory (~2.4 GB over a 15 s run) and stalls the event loop until
            # the WebRTC data channel drops. Keep counts + one sample per phase.
            now = time.monotonic()
            name = phase["name"]
            st = stats.setdefault(name, {"n": 0, "t0": now, "t1": now, "img": None})
            st["n"] += 1
            st["t1"] = now
            # Sample ~1 s in, once the phase's motion has taken effect.
            if st["img"] is None and now - phase["t"] >= 1.0:
                st["img"] = np.asarray(frame).copy()

        ref = await reactor.upload_file(str(OUT / "seed.png"))
        await reactor.send_command("set_seed", {"seed": 42})
        await reactor.send_command("set_image", {"image": ref})
        await reactor.send_command("set_prompt", {"prompt": PROMPT})
        await asyncio.wait_for(conditions_ready.wait(), timeout=120)

        await reactor.send_command("start", {})
        print("generating ...\n")

        for name, secs, cmd, params in PHASES:
            phase["name"] = name
            phase["t"] = time.monotonic()
            print(f"  phase {name:<14} {secs:>4.1f}s  {cmd or ''} {params or ''}")
            if cmd:
                # A transport hiccup on one command shouldn't lose the whole run.
                try:
                    await reactor.send_command(cmd, params)
                except Exception as exc:
                    errors.append(f"{cmd}: {exc}")
                    print(f"    !! {exc}")
                    break
            await asyncio.sleep(secs)

        try:
            await reactor.send_command("pause", {})
        except Exception:
            pass
    finally:
        try:
            await reactor.send_command("reset", {})
        except Exception as exc:
            print(f"  reset failed (continuing): {exc}")
        await reactor.disconnect()
        print("\ndisconnected")

    save_results(stats, errors)


def save_results(stats: dict[str, dict], errors: list[str]) -> None:
    if not stats:
        print("NO FRAMES RECEIVED")
        return

    print("\n" + "=" * 62)
    print(f"{'phase':<16}{'frames':>8}{'span_s':>9}{'fps':>8}")
    print("=" * 62)
    for name, st in stats.items():
        span = st["t1"] - st["t0"]
        fps = (st["n"] - 1) / span if span > 0 else 0
        print(f"{name:<16}{st['n']:>8}{span:>9.2f}{fps:>8.1f}")

    shots = [(name, st["img"]) for name, st in stats.items() if st["img"] is not None]
    if not shots:
        print("\nno sampled frames (phases shorter than the 1 s sample delay?)")
        return

    frames_dir = OUT / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for name, img in shots:
        Image.fromarray(img).save(frames_dir / f"{name}.png")

    # Contact sheet: thumbnails in a grid, easiest way to eyeball motion.
    tw, th = 416, 240
    cols = 3
    rows = (len(shots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (20, 20, 20))
    for i, (name, img) in enumerate(shots):
        thumb = Image.fromarray(img).resize((tw, th))
        sheet.paste(thumb, ((i % cols) * tw, (i // cols) * th))
    sheet_path = OUT / "contact_sheet.png"
    sheet.save(sheet_path)

    print(f"\nper-phase frames -> {frames_dir}")
    print(f"contact sheet    -> {sheet_path}")
    print(f"phase order      : {[n for n, _ in shots]}")
    if errors:
        print(f"\ncommand_errors   : {errors}")
    else:
        print("\ncommand_errors   : none")


if __name__ == "__main__":
    asyncio.run(main())
