#!/usr/bin/env python3
"""Does `set_attn_window` change the generation rate?

Generation was measured at 0.25x realtime on `auto`, which is what blocks
driving a robot at wall-clock realtime. `attn_window` is the only exposed knob
that might move it.

Method: poll request_clip() (markers only, no download) and read `now_marker`,
the recording's media-time position. Its slope against wall clock IS the
generation rate. Three sessions identical except attn_window; `auto` is the
control and must reproduce ~0.25 or the comparison is void.

Usage:  ./venv/bin/python measure_attn.py
"""

import asyncio
import pathlib
import time

from reactor_sdk import Reactor, ReactorStatus

ROOT = pathlib.Path(__file__).parent
MODEL = "reactor/lingbot-world-2"
PROMPT = (
    "A sunlit gravel path winding through an open grassy meadow, tall wheat on "
    "both sides, scattered oak trees, distant rolling hills under a clear sky. "
    "Photorealistic, warm natural light, steady handheld camera."
)

CONDITIONS = ["auto", "small", "large"]   # auto first: it is the control
SAMPLE_EVERY = 4.0
SAMPLES = 7                               # ~28 s of generation per condition


def read_api_key() -> str:
    key = (ROOT / "api.js").read_text().strip()
    if not key.startswith("rk_"):
        raise SystemExit("api.js does not contain a Reactor key")
    return key


async def measure(attn: str) -> dict:
    reactor = Reactor(model_name=MODEL, api_key=read_api_key())
    ready, cond = asyncio.Event(), asyncio.Event()
    chunks = 0
    frames = 0
    errors: list[str] = []

    @reactor.on_status(ReactorStatus.READY)
    async def on_ready(status):
        ready.set()

    @reactor.on_message
    def on_message(msg):
        nonlocal chunks
        t = msg.get("type")
        if t == "chunk_complete":
            chunks += 1
        elif t == "conditions_ready":
            cond.set()
        elif t == "command_error":
            errors.append(str(msg.get("data")))
            print(f"    [command_error] {msg.get('data')}")

    samples: list[tuple[float, float, int]] = []   # (wall, now_marker, chunks)

    try:
        await reactor.connect()
        await asyncio.wait_for(ready.wait(), timeout=60)

        video = reactor.track("main_video")

        @video.on_frame
        def on_frame(frame):
            nonlocal frames
            frames += 1

        ref = await reactor.upload_file(str(ROOT / "out" / "seed.png"))
        await reactor.send_command("set_seed", {"seed": 42})
        await reactor.send_command("set_image", {"image": ref})
        await reactor.send_command("set_prompt", {"prompt": PROMPT})
        # Before start, so it applies from chunk 0.
        await reactor.send_command("set_attn_window", {"attn_window": attn})
        await asyncio.wait_for(cond.wait(), timeout=120)

        t0 = time.monotonic()
        await reactor.send_command("start", {})
        await reactor.send_command("set_move_longitudinal",
                                   {"move_longitudinal": "forward"})

        for _ in range(SAMPLES):
            await asyncio.sleep(SAMPLE_EVERY)
            clip = await reactor.request_clip(3.0)
            samples.append((time.monotonic() - t0, clip.now_marker, chunks))
            w, m, c = samples[-1]
            print(f"    t={w:5.1f}s  media={m:6.3f}  chunks={c:4d}  "
                  f"rate={m/w:.3f}")
    finally:
        try:
            await reactor.send_command("reset", {})
        except Exception:
            pass
        await reactor.disconnect()

    # Slope over the later half, so session start-up doesn't skew it.
    mid = len(samples) // 2
    (w0, m0, c0), (w1, m1, c1) = samples[mid], samples[-1]
    media_per_wall = (m1 - m0) / (w1 - w0)
    media_per_chunk = (m1 - m0) / (c1 - c0) if c1 > c0 else float("nan")
    chunks_per_wall = (c1 - c0) / (w1 - w0)

    return {
        "attn": attn,
        "media_per_wall": media_per_wall,
        "media_per_chunk": media_per_chunk,
        "chunks_per_wall": chunks_per_wall,
        "frames": frames,
        "total_media": samples[-1][1],
        "errors": errors,
    }


async def main() -> None:
    results = []
    for attn in CONDITIONS:
        print(f"\n=== attn_window = {attn} ===")
        try:
            results.append(await measure(attn))
        except Exception as exc:
            print(f"    FAILED: {exc}")
            results.append({"attn": attn, "media_per_wall": float("nan"),
                            "media_per_chunk": float("nan"),
                            "chunks_per_wall": float("nan"), "frames": 0,
                            "total_media": 0.0, "errors": [str(exc)]})
        await asyncio.sleep(5)   # let the previous session fully close

    print("\n" + "=" * 74)
    print(f"{'attn_window':<14}{'media/wall':>12}{'media/chunk':>14}"
          f"{'chunks/s':>11}{'frames':>9}{'x realtime':>13}")
    print("=" * 74)
    for r in results:
        print(f"{r['attn']:<14}{r['media_per_wall']:>12.3f}"
              f"{r['media_per_chunk']:>14.4f}{r['chunks_per_wall']:>11.2f}"
              f"{r['frames']:>9d}{r['media_per_wall']:>12.2f}x")

    base = next((r for r in results if r["attn"] == "auto"), None)
    print()
    if base and 0.20 <= base["media_per_wall"] <= 0.30:
        print(f"control OK: auto = {base['media_per_wall']:.3f} "
              "(reproduces the earlier 0.25)")
        best = max(results, key=lambda r: r["media_per_wall"])
        gain = best["media_per_wall"] / base["media_per_wall"]
        if best["attn"] != "auto" and gain >= 1.15:
            print(f"WINNER: '{best['attn']}' is {gain:.2f}x faster than auto "
                  f"({best['media_per_wall']:.3f} media/wall)")
            print(f"  -> a robot sim would run at {best['media_per_wall']:.2f}x "
                  "realtime, still not 1.0x" if best["media_per_wall"] < 1.0
                  else "  -> realtime is reachable")
        else:
            print("NO MEANINGFUL DIFFERENCE — attn_window does not change throughput.")
            print("  -> 0.25x is a hard ceiling; run the sim slowed to match.")
    else:
        got = base["media_per_wall"] if base else float("nan")
        print(f"CONTROL FAILED: auto = {got:.3f}, expected ~0.25.")
        print("  -> the measurement is unreliable; ignore the comparison above.")


if __name__ == "__main__":
    asyncio.run(main())
