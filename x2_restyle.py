#!/usr/bin/env python3
"""Inverted pipeline via xmax/x2: MuJoCo does the physics, X2 does the looks.

    ./venv/bin/python x2_restyle.py                    # uses out/sana_src.mp4
    ./venv/bin/python x2_restyle.py --src my_clip.mp4 --prompt "..."

X2 is streaming video-to-video: publish frames to the `source` track, receive
restyled frames on `main_video`. There is no `start` command — generation
follows the frames.

Unlike `drive_g1.py` (LingBot composite), the robot and the scenery here have a
real physical relationship: the source clip is a MuJoCo render of G1 walking
through geometry it can actually collide with. The model only changes how it
looks.
"""

import argparse
import asyncio
import pathlib
import subprocess
import sys
import time

import numpy as np
from reactor_sdk import Reactor, ReactorStatus

ROOT = pathlib.Path(__file__).parent
MODEL = "xmax/x2"

DEFAULT_PROMPT = (
    "A photorealistic humanoid robot walking along a dirt path in an open meadow, "
    "warm afternoon sunlight, grass and scattered rocks, distant hills, cinematic."
)


def read_api_key() -> str:
    key = (ROOT / "api.js").read_text().strip()
    if not key.startswith("rk_"):
        sys.exit("api.js does not contain a Reactor key")
    return key


def probe_size(path: pathlib.Path) -> tuple[int, int]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(path)],
        capture_output=True, text=True).stdout.strip()
    w, h = (int(v) for v in out.split("x")[:2])
    return w, h


def frame_reader(path: pathlib.Path, w: int, h: int):
    """Decode the source clip to raw RGB frames, one at a time."""
    p = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE)
    n = w * h * 3
    try:
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                return
            yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
    finally:
        p.stdout.close(); p.wait(timeout=10)


async def run(args) -> None:
    w, h = probe_size(args.src)
    print(f"source: {args.src.name}  {w}x{h}")

    reactor = Reactor(model_name=MODEL, api_key=read_api_key())
    ready = asyncio.Event()
    got = 0
    ff = None

    @reactor.on_status(ReactorStatus.READY)
    async def on_ready(status):
        ready.set()

    @reactor.on_message
    def on_message(msg):
        t = msg.get("type")
        if t not in ("state",):
            print(f"  {t}: {str(msg.get('data'))[:140]}")

    @reactor.on_error
    def on_error(err):
        print(f"  [ERROR] {err.operation}: [{err.code}] {err.message}")

    try:
        print(f"connecting to {MODEL} ...")
        await reactor.connect()
        await asyncio.wait_for(ready.wait(), timeout=60)
        print("READY")

        ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
             "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(args.fps),
             "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
             "-pix_fmt", "yuv420p", str(args.out)],
            stdin=subprocess.PIPE)

        @reactor.track("main_video").on_frame
        def on_frame(frame):
            nonlocal got
            a = np.asarray(frame)
            if a.shape[:2] != (h, w):        # keep the writer's geometry fixed
                from PIL import Image
                a = np.asarray(Image.fromarray(a).resize((w, h)))
            ff.stdin.write(a.astype(np.uint8).tobytes())
            got += 1

        await reactor.send_command("set_prompt", {"prompt": args.prompt})
        print(f"prompt: {args.prompt[:70]}...")

        source = await reactor.track("source").publish()
        print("published `source`; streaming frames ...")

        t0 = time.monotonic()
        sent = 0
        for frame in frame_reader(args.src, w, h):
            source.push_frame(frame)
            sent += 1
            if sent % 24 == 0:
                print(f"\r  sent {sent}  received {got}", end="", flush=True)
            await asyncio.sleep(1.0 / args.fps)
        print(f"\r  sent {sent}  received {got}   (source exhausted)")

        # Let the tail of the stream come back.
        for _ in range(int(args.drain * 2)):
            await asyncio.sleep(0.5)
            print(f"\r  draining: received {got}", end="", flush=True)
        print()
        print(f"\nsent {sent} frames, received {got} in "
              f"{time.monotonic()-t0:.1f}s")
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
    print(f"restyled -> {args.out}" if got else
          "NO frames received — check the messages above")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=pathlib.Path, default=ROOT / "out" / "sana_src.mp4")
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "out" / "x2_out.mp4")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--fps", type=int, default=12, help="push rate")
    ap.add_argument("--drain", type=float, default=15.0,
                    help="seconds to keep receiving after the source ends")
    args = ap.parse_args()
    if not args.src.exists():
        sys.exit(f"no source clip at {args.src} — run sana_restyle.py --render-only")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
