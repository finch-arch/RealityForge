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


def make_ground_texture(name: str = "ground.png", size: int = 512) -> pathlib.Path:
    """Procedural grass/dirt. MuJoCo's builtins are only flat/checker/gradient,
    so a real texture has to come from a file."""
    TEX_DIR.mkdir(parents=True, exist_ok=True)
    path = TEX_DIR / name
    rng = np.random.default_rng(7)

    # Layered value noise — coarse patches, then fine blade-scale detail.
    img = np.zeros((size, size, 3), np.float32)
    base = np.array([74, 96, 52], np.float32)      # grass green
    dirt = np.array([116, 98, 71], np.float32)     # worn earth

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
    img *= (0.72 + 0.56 * blades)[:, :, None]
    img += rng.normal(0, 9, (size, size, 3)).astype(np.float32)

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

VISUAL = """
  <visual>
    <headlight diffuse="0.35 0.35 0.35" ambient="0.28 0.30 0.33" specular="0.15 0.15 0.15"/>
    <rgba haze="0.62 0.72 0.85 1"/>
    <map fogstart="12" fogend="45" znear="0.05"/>
    <quality shadowsize="4096" offsamples="4"/>
    <global azimuth="-130" elevation="-18" offwidth="{w}" offheight="{h}"/>
  </visual>
"""

ASSETS = """
    <texture type="skybox" builtin="gradient" rgb1="0.32 0.52 0.78" rgb2="0.78 0.86 0.94"
             width="512" height="3072"/>
    <texture type="2d" name="groundtex" file="{ground}"/>
    <material name="groundplane" texture="groundtex" texuniform="true" texrepeat="2 2"
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
          props: bool = True) -> pathlib.Path:
    """Write a dressed-up copy of G1's scene and return its path."""
    cfg = yaml.safe_load((G1 / "deploy/deploy_mujoco/configs/g1.yaml").read_text())
    src = pathlib.Path(cfg["xml_path"].replace("{LEGGED_GYM_ROOT_DIR}", str(G1)))
    xml = src.read_text()

    ground = make_ground_texture()

    # Replace the stock <visual> block wholesale, and the stock assets/light.
    xml = re.sub(r"<visual>.*?</visual>", VISUAL.format(w=width, h=height),
                 xml, flags=re.S)
    xml = re.sub(r'<texture type="skybox".*?/>', "", xml, flags=re.S)
    xml = re.sub(r'<texture type="2d" name="groundplane".*?/>', "", xml, flags=re.S)
    xml = re.sub(r'<material name="groundplane".*?/>', "", xml, flags=re.S)
    xml = xml.replace("<asset>",
                      "<asset>\n" + ASSETS.format(ground=ground.resolve()), 1)
    xml = re.sub(r'<light pos="1 0 3\.5".*?/>', LIGHTS, xml, flags=re.S)
    if props:
        xml = xml.replace("</worldbody>", PROPS + "</worldbody>", 1)

    out = src.parent / "_scene_dressed.xml"
    out.write_text(xml)
    return out


if __name__ == "__main__":
    p = build()
    print(f"scene -> {p}")
    print(f"texture -> {TEX_DIR / 'ground.png'}")
    import mujoco
    m = mujoco.MjModel.from_xml_path(str(p))
    print(f"loaded OK: {m.ngeom} geoms, {m.nlight} lights, {m.ntex} textures")
    p.unlink(missing_ok=True)
