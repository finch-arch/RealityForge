#!/usr/bin/env python3
"""Map chunk_complete count -> recorded media time.

`request_clip(6)` produced a window of start=0.000 end=1.333 after 10 chunks,
so a chunk is NOT ~1 s of media and the recording lags generation. This polls
request_clip() (cheap — markers only, no download) at intervals to establish
the real relationship before any duration logic is written.
"""

import asyncio
import dataclasses
import pathlib
import time

from reactor_sdk import Reactor, ReactorStatus

ROOT = pathlib.Path(__file__).parent
MODEL = "reactor/lingbot-world-2"
SAMPLES = 10
SAMPLE_EVERY = 4.0     # seconds of wall clock


async def main() -> None:
    key = (ROOT / "api.js").read_text().strip()
    reactor = Reactor(model_name=MODEL, api_key=key)
    ready, cond = asyncio.Event(), asyncio.Event()
    chunks = 0
    frames = 0

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
        await reactor.send_command("set_prompt", {"prompt": "a gravel path in a meadow"})
        await asyncio.wait_for(cond.wait(), timeout=120)

        t0 = time.monotonic()
        await reactor.send_command("start", {})
        await reactor.send_command("set_move_longitudinal",
                                   {"move_longitudinal": "forward"})

        print(f"{'wall_s':>8}{'chunks':>8}{'frames':>8}"
              f"{'now_mark':>10}{'end_mark':>10}{'media/chunk':>13}{'media/wall':>12}")
        print("-" * 69)

        for _ in range(SAMPLES):
            await asyncio.sleep(SAMPLE_EVERY)
            wall = time.monotonic() - t0
            clip = await reactor.request_clip(3.0)
            now_m = clip.now_marker
            per_chunk = now_m / chunks if chunks else 0
            per_wall = now_m / wall if wall else 0
            print(f"{wall:8.1f}{chunks:8d}{frames:8d}"
                  f"{now_m:10.3f}{clip.end_marker:10.3f}"
                  f"{per_chunk:13.4f}{per_wall:12.3f}")

        print("\nlast clip object:")
        for f in dataclasses.fields(clip):
            print(f"  {f.name:<22} {getattr(clip, f.name)}")

    finally:
        try:
            await reactor.send_command("reset", {})
        except Exception:
            pass
        await reactor.disconnect()
        print("disconnected")


if __name__ == "__main__":
    asyncio.run(main())
