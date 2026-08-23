#!/usr/bin/env python3
"""Generate a simple synthetic seed image (sky + ground) for the API test.

A real photograph seeds a navigable world better, but the only local
candidates are a 13 MB product shot on white and a wiring diagram.
This gives a neutral, cheap starting frame that exercises the upload path.
"""

import pathlib

import numpy as np
from PIL import Image

W, H = 1024, 576
OUT = pathlib.Path(__file__).parent / "out" / "seed.png"


def main() -> None:
    y = np.linspace(0, 1, H)[:, None, None]
    horizon = 0.55

    sky_top = np.array([92, 138, 200])
    sky_bot = np.array([206, 222, 238])
    ground_near = np.array([88, 96, 72])
    ground_far = np.array([150, 152, 128])

    img = np.zeros((H, W, 3))
    sky_t = np.clip(y / horizon, 0, 1)
    img += (sky_top + (sky_bot - sky_top) * sky_t) * (y < horizon)
    gnd_t = np.clip((y - horizon) / (1 - horizon), 0, 1)
    img += (ground_far + (ground_near - ground_far) * gnd_t) * (y >= horizon)

    # A little texture so the model has something to latch onto.
    rng = np.random.default_rng(0)
    img += rng.normal(0, 4, (H, W, 3))

    OUT.parent.mkdir(exist_ok=True)
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(OUT)
    print(f"wrote {OUT}  ({OUT.stat().st_size} bytes, {W}x{H})")


if __name__ == "__main__":
    main()
