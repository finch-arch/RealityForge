#!/usr/bin/env python3
"""Test 4 (corrected): isolate each camera_pose axis to read its direction.

The first attempt applied large values (0.5) continuously. Because
camera_pose is *persistent per-chunk state* rather than a one-shot, each
value re-applied every chunk (~0.45 s), accumulating several units of
drift and collapsing image quality — purple trees, teal grass.

This version: small magnitudes, each probe released back to neutral
before the next, and kv_cache_reset on auto to counter drift.

Usage:  ./venv/bin/python calibrate_pose.py
"""

import asyncio
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

REST = 2.5   # let the scene re-stabilise between probes
PROBE = 2.5  # short, so drift stays small
M = 0.06     # translation magnitude (units unknown — that's the point)
R = 0.02     # rotation magnitude, radians (documented by the schema)

NEUTRAL = {"camera_pose": []}

PHASES = [
    ("settle",   6.0, None),
    ("base",     REST, NEUTRAL),
    ("+tx",      PROBE, {"camera_pose": [0, 0, 0, M, 0, 0]}),
    ("rest1",    REST, NEUTRAL),
    ("+ty",      PROBE, {"camera_pose": [0, 0, 0, 0, M, 0]}),
    ("rest2",    REST, NEUTRAL),
    ("+tz",      PROBE, {"camera_pose": [0, 0, 0, 0, 0, M]}),
    ("rest3",    REST, NEUTRAL),
    ("+rx",      PROBE, {"camera_pose": [R, 0, 0, 0, 0, 0]}),
    ("rest4",    REST, NEUTRAL),
    ("+ry",      PROBE, {"camera_pose": [0, R, 0, 0, 0, 0]}),
    ("rest5",    REST, NEUTRAL),
]


def read_api_key() -> str:
    key = (ROOT / "api.js").read_text().strip()
    if not key.startswith("rk_"):
        raise SystemExit("api.js does not contain a Reactor key (expected rk_...)")
    return key


async def main() -> None:
    reactor = Reactor(model_name=MODEL, api_key=read_api_key())
    ready = asyncio.Event()
    cond = asyncio.Event()
    phase = {"name": "init", "t": time.monotonic()}
    stats: dict[str, dict] = {}
    errors: list[str] = []

    @reactor.on_status(ReactorStatus.READY)
    async def on_ready(status):
        ready.set()

    @reactor.on_message
    def on_message(msg):
        if msg.get("type") == "conditions_ready":
            cond.set()
        elif msg.get("type") == "command_error":
            errors.append(str(msg.get("data")))
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
            now = time.monotonic()
            st = stats.setdefault(phase["name"], {"n": 0, "img": None})
            st["n"] += 1
            # Sample near the END of each phase, so the motion has accumulated
            # but before the next command lands.
            if now - phase["t"] >= PROBE - 0.6:
                st["img"] = np.asarray(frame).copy()

        ref = await reactor.upload_file(str(OUT / "seed.png"))
        await reactor.send_command("set_seed", {"seed": 7})
        await reactor.send_command("set_image", {"image": ref})
        await reactor.send_command("set_prompt", {"prompt": PROMPT})
        await reactor.send_command("set_kv_cache_reset", {"mode": "auto"})
        await asyncio.wait_for(cond.wait(), timeout=120)

        await reactor.send_command("start", {})
        print("generating ...\n")

        for name, secs, params in PHASES:
            phase["name"] = name
            phase["t"] = time.monotonic()
            tag = params["camera_pose"] if params else "-"
            print(f"  {name:<9} {secs:>4.1f}s  {tag}")
            if params is not None:
                try:
                    await reactor.send_command("set_camera_pose", params)
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
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
        except Exception:
            pass
        await reactor.disconnect()
        print("\ndisconnected")

    save(stats, errors)


def save(stats: dict[str, dict], errors: list[str]) -> None:
    shots = [(n, s["img"]) for n, s in stats.items()
             if s["img"] is not None and not n.startswith("rest")]
    if not shots:
        print("no sampled frames")
        return

    d = OUT / "calib"
    d.mkdir(parents=True, exist_ok=True)
    for n, img in shots:
        Image.fromarray(img).save(d / f"{n.replace('+','plus_')}.png")

    tw, th = 416, 240
    cols = 3
    rows = (len(shots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (20, 20, 20))
    for i, (n, img) in enumerate(shots):
        sheet.paste(Image.fromarray(img).resize((tw, th)),
                    ((i % cols) * tw, (i // cols) * th))
    sheet.save(OUT / "calib_sheet.png")

    print(f"\nprobe order: {[n for n, _ in shots]}")
    print(f"frames -> {d}")
    print(f"sheet  -> {OUT / 'calib_sheet.png'}")
    print(f"errors : {errors or 'none'}")


if __name__ == "__main__":
    asyncio.run(main())
