
#!/usr/bin/env python3
"""Photo in, world-model video out.

Seeds LingBot World 2 with your image, drives a camera motion, and downloads
the generated video.

    ./venv/bin/python generate_video.py photo.jpg
    ./venv/bin/python generate_video.py photo.jpg --prompt "a misty forest trail" \
        --seconds 12 --motion forward --out out/forest.mp4

Notes
-----
The video is encoded server-side and streamed straight to disk. Frames are
1664x960x3 = 4.8 MB each at ~36 fps, so buffering them locally is not viable
(it exhausts memory and drops the WebRTC data channel).

Generation runs faster than realtime, so `--seconds` is the *output video*
duration, not wall-clock. The loop waits on `chunk_complete` (~1 s of content
each) rather than a timer.
"""

import argparse
import asyncio
import pathlib
import subprocess
import sys
import tempfile
import time

from PIL import Image, ImageOps
from reactor_sdk import Reactor, ReactorStatus

ROOT = pathlib.Path(__file__).parent
MODEL = "reactor/lingbot-world-2"

# The model's native frame. Match it exactly so the seed is neither distorted
# nor upscaled — the prompt guide asks for 16:9 at this size.
OUT_ASPECT = 1664 / 960
SEED_WIDTH = 1664

# Per the prompt guide, the base layer must establish *world identity* — subject,
# environment, style — not just a look. Style-only prompts give the model no world
# to hold onto, and it drifts.
DEFAULT_PROMPT = (
    "A sunlit gravel path winding through an open grassy meadow, tall wheat on "
    "both sides, scattered oak trees, distant rolling hills under a clear sky. "
    "Photorealistic, warm natural light, steady handheld camera."
)

# The guide is explicit: negations render the thing they negate. "empty" and
# "no traffic" summon crowds and traffic. Positive phrasing only.
NEGATION_WORDS = ("no ", "not ", "without", "empty", "absent", "none", "never")

PROMPT_MAX_CHARS = 2000   # encoder truncates around here
PROMPT_MIN_CHARS = 40     # below this there is not enough world to hold

CREDITS_PER_SEC = 33
USD_PER_CREDIT = 11.88 / 3600 / 33

# Measured, and exactly constant across samples: one chunk is 0.1333 s (2/15) of
# media, and media accrues at ~0.25x wall clock — i.e. generation runs ~4x SLOWER
# than realtime. A 6 s clip therefore needs ~45 chunks and ~24 s of wall time.
MEDIA_PER_CHUNK = 2.0 / 15.0
MEDIA_PER_WALL = 0.25

# Extra chunks past the requested window. `request_clip(N)` returns [now-N, now],
# and the manifest only appears once the recording passes the end of the chunk
# holding that window — so keep generating a little beyond it.
CHUNK_MARGIN = 8
READY_TIMEOUT = 30.0

# Discrete axes produce clean coherent motion; raw set_camera_pose is
# persistent per-chunk state and visibly degrades quality when overdriven.
MOTIONS: dict[str, list[tuple[str, dict]]] = {
    "still":     [],
    "forward":   [("set_move_longitudinal", {"move_longitudinal": "forward"})],
    "back":      [("set_move_longitudinal", {"move_longitudinal": "back"})],
    "pan_left":  [("set_look_horizontal",   {"look_horizontal": "left"})],
    "pan_right": [("set_look_horizontal",   {"look_horizontal": "right"})],
    "orbit":     [("set_look_horizontal",   {"look_horizontal": "left"}),
                  ("set_rotation_speed_deg", {"rotation_speed_deg": 2.0})],
    "drift":     [("set_move_longitudinal", {"move_longitudinal": "forward"}),
                  ("set_look_horizontal",   {"look_horizontal": "right"}),
                  ("set_rotation_speed_deg", {"rotation_speed_deg": 1.0})],
}


def read_api_key() -> str:
    key_file = ROOT / "api.js"
    if not key_file.exists():
        sys.exit(f"missing {key_file} (should contain your rk_... Reactor key)")
    key = key_file.read_text().strip()
    if not key.startswith("rk_"):
        sys.exit(f"{key_file} does not look like a Reactor key (expected rk_...)")
    return key


def check_prompt(prompt: str) -> None:
    """Warn about the prompt-guide failure modes before we spend money on them."""
    warnings: list[str] = []

    if len(prompt) > PROMPT_MAX_CHARS:
        warnings.append(
            f"{len(prompt)} chars — the encoder truncates around {PROMPT_MAX_CHARS}, "
            "so the tail will be silently dropped. Trim detail, keep the world."
        )
    if len(prompt) < PROMPT_MIN_CHARS:
        warnings.append(
            f"only {len(prompt)} chars — likely too thin to hold a world. Describe "
            "subject, environment and style; the seed image supplies the rest."
        )

    lowered = prompt.lower()
    found = [w.strip() for w in NEGATION_WORDS if w in lowered]
    if found:
        warnings.append(
            f"contains negation(s) {found} — the model renders what you negate. "
            "'empty street' produces a busy one. Rephrase positively "
            "('the street ahead stays quiet')."
        )

    for w in warnings:
        print(f"  ! prompt: {w}")


def prepare_seed(src: pathlib.Path) -> pathlib.Path:
    """Centre-crop to the output aspect and downscale, so nothing is distorted."""
    if not src.exists():
        sys.exit(f"no such image: {src}")

    img = Image.open(src)
    img = ImageOps.exif_transpose(img)   # honour camera rotation
    img = img.convert("RGB")             # drop alpha / handle CMYK

    w, h = img.size
    if w / h > OUT_ASPECT:               # too wide -> trim sides
        new_w = int(h * OUT_ASPECT)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:                                # too tall -> trim top/bottom
        new_h = int(w / OUT_ASPECT)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))

    img = img.resize((SEED_WIDTH, int(SEED_WIDTH / OUT_ASPECT)), Image.LANCZOS)

    tmp = pathlib.Path(tempfile.mkstemp(suffix=".png", prefix="seed_")[1])
    img.save(tmp)
    print(f"seed image : {src.name} {w}x{h} -> {img.size[0]}x{img.size[1]}")
    return tmp


async def generate(args: argparse.Namespace) -> None:
    seed_path = prepare_seed(args.photo)
    out_path = args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Defined up front so the remux below is reachable even if we fail early.
    ts_path = out_path.with_suffix(".ts")

    reactor = Reactor(model_name=MODEL, api_key=read_api_key())
    ready = asyncio.Event()
    conditions_ready = asyncio.Event()
    chunks = 0
    errors: list[str] = []

    @reactor.on_status(ReactorStatus.READY)
    async def on_ready(status):
        ready.set()

    @reactor.on_message
    def on_message(msg):
        nonlocal chunks
        mtype = msg.get("type")
        if mtype == "chunk_complete":
            chunks += 1
        elif mtype == "conditions_ready":
            conditions_ready.set()     # level, not edge — this can fire twice
        elif mtype == "command_error":
            errors.append(str(msg.get("data")))
            print(f"  [command_error] {msg.get('data')}")
        elif mtype == "generation_complete":
            print("  [generation_complete] chunk quota exhausted")

    @reactor.on_error
    def on_error(err):
        print(f"  [ERROR] {err.operation}: [{err.code}] {err.message}")

    t0 = time.monotonic()
    gen_seconds = 0.0

    try:
        print(f"connecting to {MODEL} ...")
        await reactor.connect()
        await asyncio.wait_for(ready.wait(), timeout=60)

        ref = await reactor.upload_file(str(seed_path))
        await reactor.send_command("set_seed", {"seed": args.seed})
        await reactor.send_command("set_image", {"image": ref})
        await reactor.send_command("set_prompt", {"prompt": args.prompt})
        await reactor.send_command("set_kv_cache_reset", {"mode": "auto"})
        await asyncio.wait_for(conditions_ready.wait(), timeout=120)

        print(f"prompt     : {args.prompt}")
        print(f"motion     : {args.motion}")
        print(f"target     : {args.seconds:.0f}s of video")
        # Documented behaviour, not a fault: fresh sessions drop input while the
        # scene materialises, so early frames still look like the seed.
        print("             (first few seconds resemble the seed while the "
              "scene materialises)\n")

        t_gen = time.monotonic()
        await reactor.send_command("start", {})
        for cmd, params in MOTIONS[args.motion]:
            await reactor.send_command(cmd, params)

        # Generate past the requested window so the recording has moved beyond it.
        target = round(args.seconds / MEDIA_PER_CHUNK) + CHUNK_MARGIN
        # Wall-clock budget from the measured 0.25x media rate, doubled as slack.
        deadline = time.monotonic() + max(60.0, args.seconds / MEDIA_PER_WALL * 2)
        last_shown = -1
        while chunks < target and time.monotonic() < deadline:
            await asyncio.sleep(0.2)
            if chunks != last_shown:          # only on change, so logs stay readable
                last_shown = chunks
                media = chunks * MEDIA_PER_CHUNK
                print(f"\r  generating: {chunks}/{target} chunks  "
                      f"({media:.1f}/{args.seconds:.0f}s of video)", end="", flush=True)
        print()

        if time.monotonic() >= deadline:
            print("  (wall-clock cap hit — video may be shorter than requested)")

        # Download BEFORE pausing: per the SDK docs a clip "becomes ready because
        # the model keeps generating", so pausing first stalls the wait forever.
        #
        # And keep ready_timeout tight. `download` waits on
        # `predicted_ready_at_ms`, which the SDK docstring says is "only right for
        # a model running at real-time" — LingBot runs ~2.2x faster, so that
        # prediction overshoots badly and we'd bill the whole overshoot.
        print(f"\ndownloading {args.seconds:.0f}s clip ...")

        def progress(done: int, total: int) -> None:
            pct = f"{100 * done / total:.0f}%" if total else f"{done}B"
            print(f"\r  {pct}", end="", flush=True)

        await reactor.download_clip(
            args.seconds, ts_path, on_progress=progress, ready_timeout=READY_TIMEOUT
        )
        print()

        await reactor.send_command("pause", {})
        gen_seconds = time.monotonic() - t_gen

    finally:
        try:
            await reactor.send_command("reset", {})
        except Exception:
            pass
        await reactor.disconnect()
        seed_path.unlink(missing_ok=True)

    # The SDK streams MPEG-TS; swap the container so the .mp4 is genuinely MP4.
    # `-c copy` is a remux, not a re-encode: fast and lossless.
    if ts_path.exists() and ts_path.stat().st_size > 0:
        proc = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(ts_path),
             "-c", "copy", str(out_path)],
            capture_output=True, text=True,
        )
        if proc.returncode == 0:
            ts_path.unlink(missing_ok=True)
        else:
            print(f"  remux failed, keeping {ts_path}:\n{proc.stderr.strip()}")

    elapsed = time.monotonic() - t0
    cost = gen_seconds * CREDITS_PER_SEC * USD_PER_CREDIT

    print("\n" + "=" * 52)
    if out_path.exists():
        print(f"video      : {out_path}")
        print(f"size       : {out_path.stat().st_size / 1e6:.1f} MB")
    elif ts_path.exists():
        print(f"video      : {ts_path}  (MPEG-TS; remux failed)")
    else:
        print("video      : NOT WRITTEN — check errors above")
    print(f"chunks     : {chunks}")
    print(f"generating : {gen_seconds:.1f}s   total {elapsed:.1f}s")
    print(f"est. cost  : ~${cost:.3f}")
    if errors:
        print(f"errors     : {errors}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate a video from a photo using LingBot World 2.")
    ap.add_argument("photo", type=pathlib.Path, help="seed image")
    ap.add_argument("--prompt", default=None,
                    help="scene description: subject + environment + style, phrased "
                         "positively (negations render what they negate)")
    ap.add_argument("--prompt-file", type=pathlib.Path, default=None,
                    help="read the prompt from a file, for long structured prompts")
    ap.add_argument("--seconds", type=float, default=10.0,
                    help="output video duration (default 10)")
    ap.add_argument("--motion", default="forward", choices=sorted(MOTIONS),
                    help="camera motion preset (default forward)")
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "out" / "video.mp4")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--yes", action="store_true", help="skip the long-clip prompt")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate the prompt and seed image, then exit without "
                         "connecting (costs nothing)")
    args = ap.parse_args()

    if args.prompt_file and args.prompt:
        sys.exit("pass --prompt or --prompt-file, not both")
    if args.prompt_file:
        if not args.prompt_file.exists():
            sys.exit(f"no such prompt file: {args.prompt_file}")
        args.prompt = args.prompt_file.read_text().strip()
    elif args.prompt is None:
        args.prompt = DEFAULT_PROMPT

    check_prompt(args.prompt)

    if args.dry_run:
        chunks = round(args.seconds / MEDIA_PER_CHUNK) + CHUNK_MARGIN
        wall = args.seconds / MEDIA_PER_WALL
        cost = wall * CREDITS_PER_SEC * USD_PER_CREDIT
        seed = prepare_seed(args.photo)
        seed.unlink(missing_ok=True)
        print(f"\nprompt     : {args.prompt}")
        print(f"length     : {len(args.prompt)} chars")
        print(f"motion     : {args.motion}")
        print(f"would need : {chunks} chunks, ~{wall:.0f}s generating, ~${cost:.2f}")
        print("\ndry run — nothing sent, nothing billed")
        return

    if args.seconds > 60 and not args.yes:
        est = args.seconds / 2 * CREDITS_PER_SEC * USD_PER_CREDIT
        reply = input(f"{args.seconds:.0f}s is a long clip (~${est:.2f}). Continue? [y/N] ")
        if reply.strip().lower() not in ("y", "yes"):
            sys.exit("aborted")

    asyncio.run(generate(args))


if __name__ == "__main__":
    main()
