#!/usr/bin/env python3
"""Turn a photo into a walkable MuJoCo scene whose layout matches it.

    ./venv/bin/python image_to_scene.py out/seed_banaras.png --save ghat

This is the link between the two halves of the project. HappyOyster turns text
into a photoreal frame; this reads that frame and writes MuJoCo geometry laid
out like it. The robot then walks in a scene that *corresponds* to the picture,
instead of one invented independently.

It is not photogrammetry. Depth reconstruction from a single generated image is
unreliable and multi-view inconsistent. This is a vision model *interpreting*
the layout — "pillars on the left at about 2 m, a wall on the right, open water
ahead" — which is a much easier problem and good enough to align a composite.

Two things it deliberately does not reproduce:
  * stairs, steps and slopes. The policy is terrain-blind and a 6 cm step topples
    it, so the floor is always flattened. A ghat's steps become a flat quay.
  * anything below 0.4 m, for the same reason.
The palette is sampled from the image directly rather than guessed, so the scene
also matches its colours.
"""

import argparse
import collections
import pathlib
import re
import subprocess
import sys

import numpy as np
from PIL import Image

import scene_describe
import scene_validate as sv

ROOT = pathlib.Path(__file__).parent

VISION_PROMPT = """\
Look at the image at {path}.

Write MuJoCo MJCF geometry that reproduces its LAYOUT — where the solid things are,
in plan view — as seen from a camera at the bottom centre looking forward along +x.

Output ONLY `<geom .../>` lines. No explanation, no markdown fences.

MAPPING
- +x is straight ahead into the image; +y is to the LEFT, -y to the RIGHT.
- Roughly 1 unit = 1 metre. The visible scene is about 20 m deep and 12 m wide.
- Emit a geom ONLY where the image actually shows a solid object taller than
  about half a metre: walls, buildings, pillars, boats, tree trunks, large rocks,
  furniture.
- **Do not invent objects to fill space.** An open road, a beach or an empty
  plain should return very few geoms, or none at all. Emptiness is a correct
  answer and is strongly preferred over decoration.
- Match the image: if pillars line the left, emit pillars along +y. If the right
  opens onto empty desert, emit nothing there.

HARD CONSTRAINTS — the robot's controller is terrain-blind and a 6 cm step makes
it fall, so these override faithfulness to the image:
1. Every geom must be at least 0.40 m tall (for a box pos_z == size_z >= 0.40;
   for a cylinder pos_z == size[1] >= 0.40).
2. NEVER emit steps, stairs, ramps, kerbs, platforms or anything walkable-onto.
   Flatten them — a flight of ghat steps becomes flat ground, not geometry.
3. Leave a clear corridor at least 1.8 m wide along +x from x=0 to x=20, with
   nothing within 0.9 m of the y=0 centreline.
4. Nothing within 1.0 m of the origin — the robot spawns there.
5. Do not emit a floor; the ground plane already exists.

STYLE: only type="box", type="cylinder", type="sphere". Use material="stone" or
material="wood". Unique names. Emit as many geoms as the image warrants and no
more — 0 for an empty landscape, 30+ only for a dense built scene.

Last line only, starting with `PROMPT:`, give a one-sentence photorealistic
description of this place for a video model."""


def palette_from_image(path: pathlib.Path) -> dict:
    """Sample the image for ground/sky colours, rather than guessing them."""
    im = Image.open(path).convert("RGB")
    a = np.asarray(im.resize((160, 90)), np.float32)
    h = a.shape[0]
    ground = a[int(h * 0.75):].reshape(-1, 3).mean(0)     # bottom quarter
    mid = a[int(h * 0.45):int(h * 0.7)].reshape(-1, 3).mean(0)
    sky_top = a[: int(h * 0.12)].reshape(-1, 3).mean(0)
    sky_horizon = a[int(h * 0.30):int(h * 0.42)].reshape(-1, 3).mean(0)
    return dict(
        base_rgb=tuple(int(v) for v in ground),
        dirt_rgb=tuple(int(v * 0.78) for v in mid),
        contrast=0.75,
        sky=(" ".join(f"{v/255:.2f}" for v in sky_top),
             " ".join(f"{v/255:.2f}" for v in sky_horizon)),
        repeat="1.5 1.5",
    )


def read_layout(path: pathlib.Path, hint: str = "") -> tuple[str, str]:
    prompt = VISION_PROMPT.format(path=path)
    if hint:
        prompt += f"\n\nYour previous attempt was rejected: {hint}"
    proc = subprocess.run(["claude", "-p", prompt], capture_output=True,
                          text=True, timeout=420, stdin=subprocess.DEVNULL)
    if proc.returncode != 0:
        sys.exit(f"claude CLI failed:\n{proc.stderr[:400]}")
    text = proc.stdout
    look = ""
    m = re.search(r"^PROMPT:\s*(.+)$", text, re.M)
    if m:
        look = m.group(1).strip()
        text = text[:m.start()]
    geoms = "\n".join("    " + g.group(0)
                      for g in re.finditer(r"<geom\s+[^>]*?/>", text, re.S))
    return geoms + "\n", look


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=pathlib.Path)
    ap.add_argument("--save", default=None, help="preset name")
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--no-walk-test", action="store_true")
    args = ap.parse_args()
    if not args.image.exists():
        sys.exit(f"no such image: {args.image}")

    name = args.save or "img_" + re.sub(r"[^a-z0-9]+", "_", args.image.stem.lower())[:18]
    look = palette_from_image(args.image)
    # The image also supplies the horizon and the ground surface — a place is
    # mostly surface and backdrop, which geometry alone can never reproduce.
    import scene_builder
    look.update(scene_builder.textures_from_image(args.image, name))
    look["repeat"] = "3 3"
    print(f"palette from image: ground={look['base_rgb']}")
    print("skybox and ground texture derived from the image")

    hint = ""
    for attempt in range(1, args.retries + 2):
        print(f"\n[{attempt}] reading layout from {args.image.name} ...")
        geoms, prompt_text = read_layout(args.image, hint)
        n = len(sv.parse_geoms(geoms))
        print(f"    {n} geoms")
        if not n:
            hint = "You returned no <geom/> lines."
            continue

        types = collections.Counter(re.findall(r'type="(\w+)"', geoms))
        print(f"    shapes: {dict(types)}")

        fixed, errors, fixes = sv.validate(geoms)
        for f in fixes:
            print(f"    repaired: {f}")
        if errors:
            for e in errors:
                print(f"    REJECTED: {e}")
            hint = "; ".join(errors)
            continue

        print(f"    validation PASSED ({len(fixes)} repairs)")
        scene_describe.save_preset(name, fixed, prompt_text)
        # save_preset writes a default palette; replace it with the image's.
        import json
        cp = ROOT / "custom_presets.py"
        data = json.loads(re.search(r"CUSTOM = (\{.*\})\s*$", cp.read_text(), re.S).group(1))
        data[name]["look"].update(look)
        cp.write_text('"""Scenes generated from text or images. Auto-appended."""\n'
                      "import json\n\n" f"CUSTOM = {json.dumps(data, indent=2)}\n")
        print(f"    saved preset '{name}' with the image's palette")

        if args.no_walk_test:
            return
        print("    walk-testing ...")
        if scene_describe.walk_test(name):
            print(f"\nOK:\n  ./venv/bin/python drive_g1.py --preset {name} "
                  f"--no-world --preview\n")
            print("and the same place through the world model:")
            print(f"  ./venv/bin/python drive_g1.py --image {args.image} "
                  f"--composite out/demo.mp4 --preview\n")
            return
        hint = "The robot fell. Widen the corridor and keep geometry off the centreline."
        print("    walk test FAILED, retrying")

    sys.exit("could not derive a walkable scene from that image")


if __name__ == "__main__":
    main()
