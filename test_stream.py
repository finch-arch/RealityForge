#!/usr/bin/env python3
"""Tests 1 & 2: connect, generate, and measure what the API actually does.

Measures resolution, frame rate, first-frame latency and chunk cadence —
the docs contradict themselves (schema page says 1664x960 @ 48fps, specs
page says 480p/960p @ 16fps) and every downstream decision depends on
which is true.

Usage:  ./venv/bin/python test_stream.py [--seconds 30] [--image out/seed.png]
"""

import argparse
import asyncio
import json
import pathlib
import time

from reactor_sdk import Reactor, ReactorStatus

ROOT = pathlib.Path(__file__).parent
MODEL = "reactor/lingbot-world-2"
PROMPT = (
    "A sunlit gravel path winding through an open grassy meadow, "
    "scattered trees, distant hills, clear sky, photorealistic"
)


def read_api_key() -> str:
    key = (ROOT / "api.js").read_text().strip()
    if not key.startswith("rk_"):
        raise SystemExit("api.js does not contain a Reactor key (expected rk_...)")
    return key


async def main(seconds: float, image_path: pathlib.Path, seed: int) -> None:
    reactor = Reactor(model_name=MODEL, api_key=read_api_key())

    ready = asyncio.Event()
    conditions_ready = asyncio.Event()
    events: list[tuple[float, str, dict]] = []
    frames: list[tuple[float, tuple]] = []
    t_start_cmd: float | None = None

    @reactor.on_status(ReactorStatus.READY)
    async def on_ready(status):
        ready.set()

    @reactor.on_message
    def on_message(msg):
        now = time.monotonic()
        mtype = msg.get("type", "?")
        data = msg.get("data", {})
        events.append((now, mtype, data))
        if mtype == "conditions_ready":
            conditions_ready.set()
        # `state` fires constantly; keep the log readable.
        if mtype != "state":
            print(f"  [{now:8.3f}] {mtype}: {json.dumps(data)[:160]}")

    @reactor.on_error
    def on_error(err):
        print(f"  [ERROR] {err.operation}: [{err.code}] {err.message}")

    try:
        print(f"connecting to {MODEL} ...")
        await reactor.connect()
        await asyncio.wait_for(ready.wait(), timeout=60)
        print(f"READY  session={reactor.get_session_id()}\n")

        video = reactor.track("main_video")

        @video.on_frame
        def on_frame(frame):
            frames.append((time.monotonic(), tuple(frame.shape)))

        print(f"uploading seed image {image_path} ...")
        ref = await reactor.upload_file(str(image_path))
        print(f"  FileRef: {ref}\n")

        await reactor.send_command("set_seed", {"seed": seed})
        await reactor.send_command("set_image", {"image": ref})
        await reactor.send_command("set_prompt", {"prompt": PROMPT})
        await reactor.send_command("set_kv_cache_reset", {"mode": "auto"})

        print("waiting for conditions_ready ...")
        await asyncio.wait_for(conditions_ready.wait(), timeout=120)
        print("conditions_ready — starting generation\n")

        t_start_cmd = time.monotonic()
        await reactor.send_command("start", {})

        await asyncio.sleep(seconds)
        await reactor.send_command("pause", {})
        print("\npaused (billing meter should stop here)")

    finally:
        # Every exit path tears the session down — it bills per second.
        try:
            await reactor.send_command("reset", {})
        except Exception as exc:
            print(f"  reset failed (continuing): {exc}")
        await reactor.disconnect()
        print("disconnected")

    report(frames, events, t_start_cmd, seconds, seed)


def report(frames, events, t_start_cmd, seconds, seed) -> None:
    print("\n" + "=" * 62)
    print("MEASUREMENTS")
    print("=" * 62)

    if not frames:
        print("NO FRAMES RECEIVED — check events above for command_error")
        return

    shapes = {s for _, s in frames}
    t0, t1 = frames[0][0], frames[-1][0]
    span = t1 - t0
    fps = (len(frames) - 1) / span if span > 0 else float("nan")

    print(f"frames received     : {len(frames)}")
    print(f"resolution(s)       : {shapes}")
    print(f"stream span         : {span:.2f} s")
    print(f"measured frame rate : {fps:.2f} fps")
    if t_start_cmd is not None:
        print(f"first-frame latency : {t0 - t_start_cmd:.3f} s  (start -> first frame)")

    chunks = [t for t, m, _ in events if m == "chunk_complete"]
    if len(chunks) > 1:
        gaps = [b - a for a, b in zip(chunks, chunks[1:])]
        print(f"chunk_complete count: {len(chunks)}")
        print(f"chunk cadence       : mean {sum(gaps)/len(gaps):.3f} s  "
              f"min {min(gaps):.3f}  max {max(gaps):.3f}")
    else:
        print(f"chunk_complete count: {len(chunks)} (too few to measure cadence)")

    kinds: dict[str, int] = {}
    for _, m, _ in events:
        kinds[m] = kinds.get(m, 0) + 1
    print(f"event counts        : {kinds}")

    est_cost = seconds * 33 / 1000 * 0.10  # 33 credits/s; ~$11.88/hr
    print(f"est. cost this run  : ~${est_cost:.3f} for {seconds:.0f}s of generation")

    out = ROOT / "out" / "measurements.json"
    out.write_text(json.dumps({
        "seed": seed,
        "frame_count": len(frames),
        "shapes": [list(s) for s in shapes],
        "span_s": span,
        "fps": fps,
        "first_frame_latency_s": (t0 - t_start_cmd) if t_start_cmd else None,
        "chunk_cadence_s": gaps if len(chunks) > 1 else [],
        "event_counts": kinds,
    }, indent=2))
    print(f"\nwritten to {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--image", type=pathlib.Path, default=ROOT / "out" / "seed.png")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    asyncio.run(main(a.seconds, a.image, a.seed))
