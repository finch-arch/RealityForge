#!/usr/bin/env python3
"""Text -> a photoreal seed frame, via HappyOyster's world engine.

    ./venv/bin/python oyster_seed.py "a riverside ghat in Varanasi at golden hour"
    ./venv/bin/python oyster_seed.py "a Kyoto alley in the rain" --out out/kyoto.png

HappyOyster builds a persistent world from a paragraph of text in ~30 s and
returns its first frame. That frame is photoreal and *specific* — which is
exactly what LingBot World 2 needs as a seed and what a text prompt alone could
never give it.

So this closes the gap that made every generated scene look the same:

    text ──► HappyOyster ──► photoreal first frame ──► LingBot seed ──► navigable world
                                                                        │
                              MuJoCo G1 (real physics) ─────────────────┘  composite

The world id is printed too: HappyOyster worlds persist and can be re-attached
later with `attach_world`, so a good one is worth keeping.
"""

import argparse
import asyncio
import json
import pathlib
import sys
import time
import urllib.request

from reactor_sdk import Reactor, ReactorStatus

ROOT = pathlib.Path(__file__).parent
MODEL = "reactor/happy-oyster-adventure"


def read_api_key() -> str:
    key = (ROOT / "api.js").read_text().strip()
    if not key.startswith("rk_"):
        sys.exit("api.js does not contain a Reactor key")
    return key


async def build(prompt: str, perspective: str, timeout: float) -> dict:
    reactor = Reactor(model_name=MODEL, api_key=read_api_key())
    ready, done = asyncio.Event(), asyncio.Event()
    state: dict = {}

    @reactor.on_status(ReactorStatus.READY)
    async def on_ready(status):
        ready.set()

    @reactor.on_message
    def on_message(msg):
        t = msg.get("type")
        d = msg.get("data") or {}
        if t == "world_state":
            state.update(d)
            print(f"  {d.get('phase')}/{d.get('world_status')}")
            if d.get("world_status") in ("ready", "completed", "active"):
                done.set()
        elif t == "action_error":
            print(f"  action_error: {d}")
            done.set()
        elif t == "travel_credentials":
            state["credentials"] = d

    try:
        # Reactor connects intermittently time out; retry rather than fail the run.
        for attempt in range(1, 4):
            try:
                await reactor.connect()
                await asyncio.wait_for(ready.wait(), timeout=60)
                break
            except Exception as exc:
                print(f"  connect attempt {attempt} failed: {type(exc).__name__}")
                if attempt == 3:
                    raise
                await asyncio.sleep(6)
        print(f"building world ({perspective}) ...")
        t0 = time.monotonic()
        await reactor.send_command(
            "create_world", {"prompt": prompt, "perspective": perspective})
        try:
            await asyncio.wait_for(done.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            print("  timed out waiting for the world to become ready")
        state["elapsed"] = time.monotonic() - t0
        # Credentials are only useful for HappyOyster's own interactive "travel"
        # stream, which is a separate undocumented API. We want the frame.
        try:
            await reactor.send_command("get_credentials", {})
            await asyncio.sleep(4)
        except Exception:
            pass
    finally:
        try:
            await reactor.disconnect()
        except Exception:
            pass
    return state


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", help="describe the world, a sentence or a paragraph")
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "out" / "seed_world.png")
    ap.add_argument("--perspective", default="third_person",
                    choices=("third_person", "first_person"),
                    help="third_person frames the scene like a chase camera")
    ap.add_argument("--timeout", type=float, default=180.0)
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    state = asyncio.run(build(args.prompt, args.perspective, args.timeout))
    url = state.get("first_frame")
    if not url:
        sys.exit("no first frame returned — the world did not finish building")

    urllib.request.urlretrieve(url, args.out)
    size = args.out.stat().st_size

    print(f"\nseed frame : {args.out}  ({size/1000:.0f} KB)")
    print(f"built in   : {state.get('elapsed', 0):.0f}s")
    print(f"world id   : {state.get('encrypted_world_id', '?')}")
    (ROOT / "out" / "worlds.jsonl").open("a").write(json.dumps({
        "prompt": args.prompt, "perspective": args.perspective,
        "world_id": state.get("encrypted_world_id"),
        "first_frame": url, "seed": str(args.out)}) + "\n")

    print("\nnext:")
    print(f'  ./venv/bin/python generate_video.py {args.out} \\\n'
          f'      --prompt "{args.prompt}"')
    print(f'  ./venv/bin/python drive_g1.py --image {args.out} \\\n'
          f'      --composite out/demo.mp4')


if __name__ == "__main__":
    main()
