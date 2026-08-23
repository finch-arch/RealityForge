#!/usr/bin/env python3
"""Build a MuJoCo scene for G1 that doesn't look like a 1990s demo.

G1's stock `scene.xml` is a black flat skybox, a blue checkerboard ground with
0.2 reflectance, and one hard directional light. This replaces all of that:
gradient sky, procedurally textured ground, fog, sun + ambient fill, and props.

Every prop is **at least 0.4 m tall**. The deployed policy was trained on a flat
plane and its 47-dim observation contains no terrain sensing at all, so it
cannot perceive a step — measured, a 6 cm one topples it. Tall props are never
stepped onto, only walked around, which keeps the physics real and the robot up.

Nothing under `unitree_rl_gym/` is modified; the patched scene is written beside
the original so its <include> resolves, and removed afterwards.
"""

import pathlib
import re

import numpy as np
import yaml
from PIL import Image

ROOT = pathlib.Path(__file__).parent
G1 = ROOT / "unitree_rl_gym"
TEX_DIR = ROOT / "out" / "textures"


def make_ground_texture(name: str = "ground.png", size: int = 512,
                        base_rgb=(74, 96, 52), dirt_rgb=(116, 98, 71),
                        contrast: float = 1.0) -> pathlib.Path:
    """Procedural ground. MuJoCo's builtins are only flat/checker/gradient, so a
    real texture has to come from a file. Colours vary per scene preset."""
    TEX_DIR.mkdir(parents=True, exist_ok=True)
    path = TEX_DIR / name
    rng = np.random.default_rng(7)

    # Layered value noise — coarse patches, then fine blade-scale detail.
    img = np.zeros((size, size, 3), np.float32)
    base = np.array(base_rgb, np.float32)
    dirt = np.array(dirt_rgb, np.float32)

    def octaves(seed_off, weights):
        f = np.zeros((size, size), np.float32)
        r = np.random.default_rng(7 + seed_off)
        for octave, weight in weights:
            small = r.random((octave, octave)).astype(np.float32)
            up = np.asarray(Image.fromarray((small * 255).astype(np.uint8))
                            .resize((size, size), Image.BICUBIC), np.float32) / 255.0
            f += up * weight
        f /= sum(w for _, w in weights)
        return (f - f.min()) / (f.max() - f.min() + 1e-9)

    patches = octaves(0, ((4, 1.0), (12, 0.6)))       # where dirt shows through
    blades = octaves(1, ((64, 1.0), (192, 0.7)))      # blade-scale variation

    img[:] = base
    # Dirt patches, thresholded so they read as distinct worn areas, not a wash.
    img += (dirt - base) * np.clip((patches - 0.45) * 2.6, 0, 1)[:, :, None]
    # Blade shading: real grass has strong local light/dark variation.
    img *= (1.0 - 0.28 * contrast + 0.56 * contrast * blades)[:, :, None]
    img += rng.normal(0, 9 * contrast, (size, size, 3)).astype(np.float32)

    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(path)
    return path


# Vertical props only — see the module docstring. Heights are half-extents, so
# size z=0.25 is a 0.5 m tall box.
PROPS = """
    <!-- crates: walk around, never over -->
    <geom name="crate1" type="box" pos="3.2 1.1 0.30" size="0.30 0.30 0.30" material="wood"/>
    <geom name="crate2" type="box" pos="5.4 -1.2 0.35" size="0.35 0.35 0.35" material="wood"/>
    <geom name="crate3" type="box" pos="8.1 1.4 0.25" size="0.25 0.25 0.25" material="wood"/>
    <!-- pillars -->
    <geom name="post1" type="cylinder" pos="4.3 -1.8 0.60" size="0.12 0.60" material="wood"/>
    <geom name="post2" type="cylinder" pos="7.0 1.9 0.60" size="0.12 0.60" material="wood"/>
    <!-- low walls that bound a corridor, so driving into one actually stops you -->
    <geom name="wall_l" type="box" pos="6.0 3.0 0.45" size="6.0 0.15 0.45" material="stone"/>
    <geom name="wall_r" type="box" pos="6.0 -3.0 0.45" size="6.0 0.15 0.45" material="stone"/>
    <!-- boulders -->
    <geom name="rock1" type="sphere" pos="2.4 -2.2 0.28" size="0.28" material="stone"/>
    <geom name="rock2" type="sphere" pos="9.3 -1.6 0.32" size="0.32" material="stone"/>
"""


def find_horizon(a: np.ndarray) -> int:
    """Row where sky meets ground, by the steepest fall in blueness."""
    h = a.shape[0]
    blue = (a[:, :, 2] - a[:, :, 0]).mean(axis=1)          # B - R per row
    lum = a.mean(axis=(1, 2))
    score = blue + 0.35 * lum
    lo, hi = int(h * 0.10), int(h * 0.80)
    d = np.diff(score[lo:hi])
    return lo + int(np.argmin(d)) + 1 if len(d) else h // 2


def rectified_ground(src: pathlib.Path, name: str, *, cam_h: float = 1.6,
                     hfov_deg: float = 65.0, near: float = 2.0, far: float = 26.0,
                     half_width: float = 9.0, size: int = 1024) -> tuple[pathlib.Path, float]:
    """Unwarp the image's ground plane into a top-down texture.

    A photograph's surface detail — lane markings, kerbs, paving — lives in a
    perspective-projected plane. Sampling a crop of it (as the simple path does)
    keeps the colour and loses the structure. Inverting the projection recovers
    the structure, so a road comes out as an actual road seen from above.

    Assumes a camera at `cam_h` metres looking horizontally, since a single
    photograph carries no intrinsics. Returns the texture and the metres it
    spans, for `texrepeat`.
    """
    im = Image.open(src).convert("RGB")
    a = np.asarray(im, np.float32)
    H, W, _ = a.shape
    y0 = find_horizon(a)
    f = (W / 2.0) / np.tan(np.radians(hfov_deg) / 2.0)     # focal length, px
    cx = W / 2.0

    # Output spans `far-near` metres ahead and 2*half_width across.
    span = far - near
    xs = near + (np.arange(size) + 0.5) / size * span          # distance ahead
    ys = -half_width + (np.arange(size) + 0.5) / size * 2 * half_width
    X, Y = np.meshgrid(xs, ys, indexing="ij")                  # [ahead, lateral]

    col = cx + f * Y / X
    row = y0 + f * cam_h / X
    ok = (col >= 0) & (col < W - 1) & (row >= 0) & (row < H - 1)
    ci = np.clip(col, 0, W - 1).astype(np.int32)
    ri = np.clip(row, 0, H - 1).astype(np.int32)

    tex = a[ri, ci]
    # Anything off-image takes the mean, so tiles do not show hard edges.
    tex[~ok] = a[int(H * 0.85):].reshape(-1, 3).mean(0)
    # Rows far from the camera are heavily stretched; fade them toward the mean
    # so the aliasing there does not read as banding.
    w = np.clip((far - X) / (far - near), 0.25, 1.0)[:, :, None]
    tex = tex * w + tex.mean(axis=(0, 1)) * (1 - w)

    img = Image.fromarray(np.clip(tex, 0, 255).astype(np.uint8))
    # The camera frustum covers a triangle of the ground plane; crop to the
    # centre band that is fully inside it, and drop the aliased far third.
    keep = int(size * 0.34)
    img = img.crop((size // 2 - keep, int(size * 0.30), size // 2 + keep, size))
    img = img.resize((size, size), Image.LANCZOS)
    # Rotate so the road's forward axis runs along the texture's u (width):
    # a box face maps u to its x extent, and the strip is long in x.
    img = img.transpose(Image.ROTATE_90)
    path = TEX_DIR / f"rect_{name}.png"
    img.save(path)
    # Lateral metres the kept band spans: keep fraction of the full 2*half_width.
    lat_span = 2 * half_width * (2 * keep / size)
    return path, span, lat_span


def textures_from_image(src: pathlib.Path, name: str) -> dict:
    """Derive a skybox and a ground texture from a photograph.

    A place is mostly *surface and horizon*, not objects — a desert highway is
    asphalt, lane markings and distant mountains, almost none of which is
    geometry. Placing boxes can never capture that, so take it from the image:
    the upper band becomes the skybox, the lower band the ground texture.

    Both are texture-level, so nothing here can affect the physics or trip the
    terrain-blind policy.
    """
    TEX_DIR.mkdir(parents=True, exist_ok=True)
    im = Image.open(src).convert("RGB")
    w, h = im.size

    # --- skybox: MuJoCo maps a single PNG onto all six cube faces, so it must
    # be SQUARE, and the image's vertical middle sits at the horizon. Rather
    # than pasting a photo band (whose below-horizon rows read as a grey
    # smear), sample the photo's real sky gradient row by row and paint the
    # whole face with it: zenith colour at the top, the photo's pale horizon
    # haze at the middle, held below the middle so a pitched camera never sees
    # an edge.
    S = 1024
    a_full = np.asarray(im, np.float32)
    y0 = max(8, find_horizon(a_full))
    # Stop the ramp well above the detected horizon: detection runs a few rows
    # low, and any ground rows leak a pink/tan cast into the sky gradient.
    ramp = a_full[:int(y0 * 0.82)].mean(axis=1)         # per-row sky colour
    # smooth the ramp so sensor noise/clouds do not band
    k = max(1, y0 // 24)
    kernel = np.ones(k) / k
    ramp = np.stack([np.convolve(ramp[:, c], kernel, mode="same") for c in range(3)], 1)
    top = np.asarray(Image.fromarray(np.clip(ramp, 0, 255).astype(np.uint8)[:, None, :])
                     .resize((1, S // 2), Image.LANCZOS), np.float32)[:, 0, :]
    horizon_rgb = ramp[-max(1, y0 // 12):].mean(0)
    sky_a = np.empty((S, S, 3), np.float32)
    sky_a[:S // 2] = top[:, None, :]
    # below the horizon: hold the haze colour, fading very slightly darker
    fade = np.linspace(1.0, 0.985, S - S // 2)[:, None, None]
    sky_a[S // 2:] = horizon_rgb[None, None, :] * fade
    sky = Image.fromarray(np.clip(sky_a, 0, 255).astype(np.uint8))
    sky_path = TEX_DIR / f"sky_{name}.png"
    sky.save(sky_path)
    # --- ground: the foreground band. Take it from near the bottom, where the
    # surface fills the frame, and tile it.
    g = im.crop((int(w * 0.18), int(h * 0.72), int(w * 0.82), h))
    g = g.resize((512, 512), Image.LANCZOS)
    a = np.asarray(g, np.float32)
    # flatten the lighting gradient so tiling does not band
    a -= a.mean(axis=(0, 1), keepdims=True) - a.mean()
    a = np.clip(a, 0, 255)
    # mirror-tile for a seamless repeat
    q = Image.fromarray(a.astype(np.uint8))
    tile = Image.new("RGB", (1024, 1024))
    tile.paste(q, (0, 0))
    tile.paste(q.transpose(Image.FLIP_LEFT_RIGHT), (512, 0))
    tile.paste(q.transpose(Image.FLIP_TOP_BOTTOM), (0, 512))
    tile.paste(q.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.FLIP_TOP_BOTTOM), (512, 512))
    gnd_path = TEX_DIR / f"gnd_{name}.png"
    tile.save(gnd_path)

    # Prefer the perspective-rectified ground — but as a LOCATED strip, not a
    # floor tile. A road is a feature at a place; tiling it everywhere turns the
    # world into a grid of roads. One long textured quad down +x carries the
    # road; the plane underneath keeps the sampled desert/ground tile.
    try:
        rect_path, span, lat_span = rectified_ground(src, name)
        strip = (f'    <geom name="road_strip" type="box" '
                 f'pos="20 0 0.012" size="30 {lat_span/2:.2f} 0.01" '
                 f'material="roadmat" contype="0" conaffinity="0"/>\n')
        mat = (f'    <texture type="2d" name="roadtex" file="{rect_path.resolve()}"/>\n'
               f'    <material name="roadmat" texture="roadtex" '
               f'texrepeat="{60/span:.2f} 1"/>\n')
        return {"skybox_file": str(sky_path.resolve()),
                "ground_file": str(gnd_path.resolve()),
                "extra_assets": mat, "extra_geoms": strip}
    except Exception as exc:
        print(f"  rectification failed ({type(exc).__name__}), plain crop only")
        return {"skybox_file": str(sky_path.resolve()),
                "ground_file": str(gnd_path.resolve())}

# Vertical props only — see the module docstring. Heights are half-extents, so
# size z=0.25 is a 0.5 m tall box.
PROPS = """
    <geom name="crate1" type="box" pos="3.2 1.1 0.30" size="0.30 0.30 0.30" material="wood"/>
    <geom name="crate2" type="box" pos="5.4 -1.2 0.35" size="0.35 0.35 0.35" material="wood"/>
    <geom name="crate3" type="box" pos="8.1 1.4 0.25" size="0.25 0.25 0.25" material="wood"/>
    <geom name="post1" type="cylinder" pos="4.3 -1.8 0.60" size="0.12 0.60" material="wood"/>
    <geom name="post2" type="cylinder" pos="7.0 1.9 0.60" size="0.12 0.60" material="wood"/>
    <geom name="wall_l" type="box" pos="6.0 3.0 0.45" size="6.0 0.15 0.45" material="stone"/>
    <geom name="wall_r" type="box" pos="6.0 -3.0 0.45" size="6.0 0.15 0.45" material="stone"/>
    <geom name="rock1" type="sphere" pos="2.4 -2.2 0.28" size="0.28" material="stone"/>
    <geom name="rock2" type="sphere" pos="9.3 -1.6 0.32" size="0.32" material="stone"/>
"""


def _wall(name, x, y, hx, hy, hz, mat="stone"):
    return (f'    <geom name="{name}" type="box" pos="{x} {y} {hz}" '
            f'size="{hx} {hy} {hz}" material="{mat}"/>\n')


def _warehouse():
    g = _wall("wall_l", 8, 3.2, 9, 0.15, 1.4) + _wall("wall_r", 8, -3.2, 9, 0.15, 1.4)
    for i, x in enumerate((3.0, 6.0, 9.0, 12.0)):
        for sgn in (1, -1):
            g += _wall(f"rack{i}{'l' if sgn>0 else 'r'}", x, sgn * 2.3, 0.5, 0.5, 0.9, "wood")
    for i, x in enumerate((4.5, 10.5)):
        g += (f'    <geom name="pil{i}" type="box" pos="{x} 0 1.5" '
              f'size="0.18 0.18 1.5" material="stone"/>\n')
    return g, dict(base_rgb=(122, 120, 116), dirt_rgb=(96, 94, 92), contrast=0.45,
                   sky=("0.28 0.30 0.34", "0.55 0.57 0.60"), repeat="3 3",
                   prompt="The interior of a large concrete warehouse, tall steel "
                          "racking along both walls, painted floor markings, roller "
                          "shutter doors, cool overhead strip lighting. Photorealistic.")


def _forest():
    g = ""
    rng = np.random.default_rng(3)
    for i in range(14):
        x = 2.0 + i * 0.95
        y = (2.0 + rng.random() * 1.8) * (1 if i % 2 else -1)
        r = 0.14 + rng.random() * 0.10
        g += (f'    <geom name="trunk{i}" type="cylinder" pos="{x:.2f} {y:.2f} 1.6" '
              f'size="{r:.2f} 1.6" material="wood"/>\n')
    for i in range(6):
        x = 3.0 + i * 2.1
        y = (1.9 + rng.random() * 1.2) * (-1 if i % 2 else 1)
        g += (f'    <geom name="rock{i}" type="sphere" pos="{x:.2f} {y:.2f} 0.30" '
              f'size="0.30" material="stone"/>\n')
    return g, dict(base_rgb=(62, 78, 44), dirt_rgb=(104, 84, 58), contrast=1.15,
                   sky=("0.34 0.52 0.72", "0.80 0.86 0.90"), repeat="2 2",
                   prompt="A dirt trail winding between tall pine trunks in a forest, "
                          "ferns and moss along the edges, dappled sunlight through "
                          "the canopy, scattered boulders. Photorealistic.")


def _street():
    g = _wall("fac_l", 9, 4.0, 10, 0.4, 3.0) + _wall("fac_r", 9, -4.0, 10, 0.4, 3.0)
    g += _wall("kerb_l", 9, 2.6, 10, 0.12, 0.45) + _wall("kerb_r", 9, -2.6, 10, 0.12, 0.45)
    for i, x in enumerate((3.5, 7.0, 10.5, 14.0)):
        for sgn in (1, -1):
            g += (f'    <geom name="bol{i}{"l" if sgn>0 else "r"}" type="cylinder" '
                  f'pos="{x} {sgn*2.2} 0.5" size="0.10 0.5" material="stone"/>\n')
    return g, dict(base_rgb=(104, 100, 96), dirt_rgb=(74, 72, 70), contrast=0.7,
                   sky=("0.42 0.46 0.58", "0.86 0.78 0.70"), repeat="1 1",
                   prompt="A narrow cobblestone street in an old European town at dusk, "
                          "shuttered shopfronts, warm lamplight on wet stone, stone "
                          "kerbs and iron bollards. Photorealistic, cinematic.")


def _courtyard():
    g = (_wall("cw_n", 14, 0, 0.3, 6, 1.6) + _wall("cw_s", -1, 0, 0.3, 6, 1.6)
         + _wall("cw_e", 6.5, 6, 8, 0.3, 1.6) + _wall("cw_w", 6.5, -6, 8, 0.3, 1.6))
    for i, (x, y) in enumerate(((3.5, 2.6), (3.5, -2.6), (8.5, 2.6), (8.5, -2.6))):
        g += _wall(f"plant{i}", x, y, 0.6, 0.6, 0.5, "wood")
    g += ('    <geom name="fount" type="cylinder" pos="6.0 0 0.45" '
          'size="0.9 0.45" material="stone"/>\n')
    return g, dict(base_rgb=(126, 120, 108), dirt_rgb=(98, 92, 84), contrast=0.55,
                   sky=("0.36 0.56 0.80", "0.86 0.90 0.94"), repeat="1.5 1.5",
                   prompt="A stone courtyard enclosed by low walls, flagstone paving, "
                          "raised planters and a round stone fountain at the centre, "
                          "warm afternoon light. Photorealistic.")


def _medieval():
    """Assassin's Creed-ish narrow alley; ~3.1 m wide, facades 4 m tall."""
    g = ""
    rng = np.random.default_rng(11)
    x = 1.0
    i = 0
    while x < 20:
        depth = 1.6 + rng.random() * 1.4
        for sgn in (1, -1):
            inset = 1.55 + rng.random() * 0.35
            g += (f'    <geom name="fac{i}{"l" if sgn>0 else "r"}" type="box" '
                  f'pos="{x + depth/2:.2f} {sgn*(inset + 1.6):.2f} 2.0" '
                  f'size="{depth/2:.2f} 1.6 2.0" material="stone"/>\n')
        i += 1
        x += depth + 0.35
    for j, (px, py, r, hz) in enumerate((
            (3.4, 1.15, 0.32, 0.45), (5.9, -1.20, 0.30, 0.42), (9.2, 1.25, 0.34, 0.48),
            (12.6, -1.15, 0.31, 0.44), (15.8, 1.20, 0.33, 0.46))):
        g += (f'    <geom name="barrel{j}" type="cylinder" pos="{px} {py} {hz}" '
              f'size="{r} {hz}" material="wood"/>\n')
    for j, (px, py) in enumerate(((7.2, -1.25), (11.0, 1.25), (17.5, -1.20))):
        g += (f'    <geom name="mcrate{j}" type="box" pos="{px} {py} 0.35" '
              f'size="0.40 0.40 0.35" material="wood"/>\n')
    g += ('    <geom name="well" type="cylinder" pos="19.5 1.15 0.50" '
          'size="0.75 0.50" material="stone"/>\n')
    return g, dict(base_rgb=(112, 106, 96), dirt_rgb=(82, 76, 68), contrast=0.75,
                   sky=("0.40 0.48 0.62", "0.88 0.82 0.72"), repeat="1 1",
                   prompt="A narrow medieval stone alley between tall weathered "
                          "buildings, cobblestone paving, wooden barrels and market "
                          "crates, timber shutters, a stone well, warm low sunlight "
                          "and long shadows. Photorealistic, historical, cinematic.")


def _meadow():
    return PROPS, dict(base_rgb=(74, 96, 52), dirt_rgb=(116, 98, 71), contrast=1.0,
                       sky=("0.32 0.52 0.78", "0.78 0.86 0.94"), repeat="2 2",
                       prompt="A sunlit gravel path through an open grassy meadow, "
                              "wooden crates and stone blocks beside the path, "
                              "distant rolling hills. Photorealistic.")


def _load_custom():
    """Presets written by scene_describe.py / image_to_scene.py, if any."""
    try:
        from custom_presets import CUSTOM
    except Exception:
        return {}
    return {name: (lambda e=entry: (e["geoms"], dict(e["look"])))
            for name, entry in CUSTOM.items()}


PRESETS = {"meadow": _meadow, "warehouse": _warehouse,
           "forest": _forest, "street": _street, "courtyard": _courtyard,
           "medieval": _medieval}
PRESETS.update(_load_custom())


def refresh() -> None:
    """Re-read custom_presets.py after a subprocess added a scene."""
    import importlib
    import sys as _sys
    _sys.modules.pop("custom_presets", None)
    importlib.invalidate_caches()
    PRESETS.update(_load_custom())


def preset_prompt(name: str) -> str:
    """The LingBot prompt describing the same place this preset builds."""
    return PRESETS[name]()[1]["prompt"]


VISUAL = """
  <visual>
    <headlight diffuse="0.35 0.35 0.35" ambient="0.28 0.30 0.33" specular="0.15 0.15 0.15"/>
    <rgba haze="0.62 0.72 0.85 1"/>
    <map fogstart="12" fogend="45" znear="0.05"/>
    <quality shadowsize="4096" offsamples="4"/>
    <global azimuth="-130" elevation="-18" offwidth="{w}" offheight="{h}"/>
  </visual>
"""

ASSETS_PHOTO = """
    <texture type="skybox" file="{skybox_file}"/>
    <texture type="2d" name="groundtex" file="{ground_file}"/>
    <material name="groundplane" texture="groundtex" texuniform="true" texrepeat="{repeat}"
              reflectance="0.0" shininess="0.02" specular="0.05"/>
    <material name="wood" rgba="0.52 0.38 0.24 1" reflectance="0.0" shininess="0.05"/>
    <material name="stone" rgba="0.55 0.54 0.51 1" reflectance="0.0" shininess="0.03"/>
"""

ASSETS = """
    <texture type="skybox" builtin="gradient" rgb1="{sky1}" rgb2="{sky2}"
             width="512" height="3072"/>
    <texture type="2d" name="groundtex" file="{ground}"/>
    <material name="groundplane" texture="groundtex" texuniform="true" texrepeat="{repeat}"
              reflectance="0.0" shininess="0.02" specular="0.05"/>
    <material name="wood" rgba="0.52 0.38 0.24 1" reflectance="0.0" shininess="0.05"/>
    <material name="stone" rgba="0.55 0.54 0.51 1" reflectance="0.0" shininess="0.03"/>
"""

LIGHTS = """
    <light name="sun" pos="4 -6 8" dir="-0.35 0.55 -0.85" directional="true"
           diffuse="0.85 0.82 0.75" specular="0.25 0.25 0.22" castshadow="true"/>
    <light name="fill" pos="-6 6 6" dir="0.5 -0.5 -0.7" directional="true"
           diffuse="0.22 0.26 0.32" specular="0 0 0" castshadow="false"/>
"""


def build(width: int = 1280, height: int = 704,
          props: bool = True, preset: str = "meadow") -> pathlib.Path:
    """Write a dressed-up copy of G1's scene for one preset; return its path."""
    if preset not in PRESETS:
        raise ValueError(f"unknown preset {preset!r}; have {sorted(PRESETS)}")
    geoms, look = PRESETS[preset]()

    cfg = yaml.safe_load((G1 / "deploy/deploy_mujoco/configs/g1.yaml").read_text())
    src = pathlib.Path(cfg["xml_path"].replace("{LEGGED_GYM_ROOT_DIR}", str(G1)))
    xml = src.read_text()

    ground = make_ground_texture(f"ground_{preset}.png",
                                 base_rgb=look.get("base_rgb", (74, 96, 52)),
                                 dirt_rgb=look.get("dirt_rgb", (116, 98, 71)),
                                 contrast=look.get("contrast", 1.0))

    xml = re.sub(r"<visual>.*?</visual>", VISUAL.format(w=width, h=height),
                 xml, flags=re.S)
    xml = re.sub(r'<texture type="skybox".*?/>', "", xml, flags=re.S)
    xml = re.sub(r'<texture type="2d" name="groundplane".*?/>', "", xml, flags=re.S)
    xml = re.sub(r'<material name="groundplane".*?/>', "", xml, flags=re.S)

    if look.get("skybox_file") and look.get("ground_file"):
        assets = ASSETS_PHOTO.format(skybox_file=look["skybox_file"],
                                     ground_file=look["ground_file"],
                                     repeat=look.get("repeat", "2 2"))
    else:
        assets = ASSETS.format(ground=ground.resolve(), repeat=look["repeat"],
                               sky1=look["sky"][0], sky2=look["sky"][1])
    xml = xml.replace("<asset>", "<asset>\n" + assets
                      + look.get("extra_assets", ""), 1)
    if look.get("extra_geoms"):
        xml = xml.replace("</worldbody>", look["extra_geoms"] + "</worldbody>", 1)
    xml = re.sub(r'<light pos="1 0 3\.5".*?/>', LIGHTS, xml, flags=re.S)
    if props:
        xml = xml.replace("</worldbody>", geoms + "</worldbody>", 1)

    out = src.parent / f"_scene_{preset}.xml"
    out.write_text(xml)
    return out


if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "meadow"
    p = build(preset=name)
    print(f"scene -> {p}")
    print(f"prompt -> {preset_prompt(name)[:70]}...")
    import mujoco
    m = mujoco.MjModel.from_xml_path(str(p))
    print(f"loaded OK: {m.ngeom} geoms, {m.nlight} lights, {m.ntex} textures")
    p.unlink(missing_ok=True)
