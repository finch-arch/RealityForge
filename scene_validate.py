#!/usr/bin/env python3
"""Validate (and repair) MJCF geoms so the terrain-blind G1 policy survives them.

The deployed policy has **no ground sensing** in its 47-dim observation and a
measured 6 cm step topples it. So a scene is only usable if the robot never has
to step onto anything: floor stays flat, props are tall enough that walking into
them is the only option, and there is somewhere to walk.

This is the part worth automating. Generating geometry is easy; guaranteeing the
robot stays upright in it is the actual work.
"""

import math
import re

MIN_PROP_H = 0.40      # below this the policy tries to step up, and falls
MIN_CORRIDOR = 1.5     # clear width along the walking axis, for third-person driving
SPAWN_CLEAR = 0.8      # radius around the spawn that must be empty
WALK_AXIS_LEN = 12.0   # how far down +x the corridor is checked

GEOM_RE = re.compile(
    r'<geom\s+([^>]*?)/>', re.S)
ATTR_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


def _attrs(tag: str) -> dict:
    return dict(ATTR_RE.findall(tag))


def _nums(s: str) -> list[float]:
    return [float(v) for v in s.split()] if s else []


def parse_geoms(xml_fragment: str) -> list[dict]:
    """Pull geoms out of an MJCF fragment as dicts of attributes."""
    return [_attrs(m.group(1)) for m in GEOM_RE.finditer(xml_fragment)]


def _extent(g: dict) -> tuple[float, float, float, float, float]:
    """(x, y, half_x, half_y, top_z) for a geom, in world terms."""
    pos = _nums(g.get("pos", "0 0 0")) or [0, 0, 0]
    size = _nums(g.get("size", "0"))
    t = g.get("type", "sphere")
    x, y, z = (pos + [0, 0, 0])[:3]
    if t == "box":
        hx, hy, hz = (size + [0, 0, 0])[:3]
    elif t == "cylinder":
        r, hz = (size + [0])[:2]
        hx = hy = r
    elif t == "sphere":
        r = size[0] if size else 0.0
        hx = hy = hz = r
    elif t == "capsule":
        r, hz = (size + [0])[:2]
        hx = hy = r
    else:                       # plane or unknown: treat as ground, not a prop
        return x, y, 0.0, 0.0, 0.0
    return x, y, hx, hy, z + hz


def validate(xml_fragment: str, *, repair: bool = True) -> tuple[str, list[str], list[str]]:
    """Check geoms against the policy's limits.

    Returns (possibly repaired fragment, errors, fixes-applied).
    Errors are conditions that cannot be repaired automatically.
    """
    errors: list[str] = []
    fixes: list[str] = []
    out = xml_fragment

    for g in parse_geoms(xml_fragment):
        name = g.get("name", "<unnamed>")
        t = g.get("type", "sphere")
        if t == "plane":
            continue
        x, y, hx, hy, top = _extent(g)

        # 1. Too short to walk around, too tall to ignore -> the policy falls.
        if 0 < top < MIN_PROP_H:
            if repair and t in ("box", "cylinder"):
                size = _nums(g["size"])
                pos = _nums(g["pos"])
                if t == "box":
                    size[2] = MIN_PROP_H
                else:
                    size[1] = MIN_PROP_H
                pos[2] = MIN_PROP_H
                old_tag = f'name="{name}"'
                for attr, vals in (("size", size), ("pos", pos)):
                    new = " ".join(f"{v:g}" for v in vals)
                    out = re.sub(
                        rf'(<geom[^>]*{re.escape(old_tag)}[^>]*?{attr}=")[^"]*(")',
                        rf'\g<1>{new}\g<2>', out)
                fixes.append(f"{name}: raised {top:.2f} m -> {MIN_PROP_H:.2f} m "
                             f"(a {top*100:.0f} cm step topples the policy)")
            else:
                errors.append(f"{name}: {top:.2f} m tall — below the {MIN_PROP_H} m "
                              f"minimum and not auto-raisable ({t})")

        # 2. Nothing may sit on the spawn point.
        if math.hypot(x, y) < SPAWN_CLEAR + max(hx, hy):
            errors.append(f"{name}: within {SPAWN_CLEAR} m of the spawn at origin")

    # 3. There must be a walkable corridor down +x.
    blocked = []
    for s in range(1, int(WALK_AXIS_LEN) + 1):
        gap_l, gap_r = 99.0, -99.0
        for g in parse_geoms(out):
            if g.get("type") == "plane":
                continue
            x, y, hx, hy, top = _extent(g)
            if top <= 0.05 or abs(x - s) > hx:
                continue
            if y >= 0:
                gap_l = min(gap_l, y - hy)
            else:
                gap_r = max(gap_r, y + hy)
        width = min(gap_l, 99.0) - max(gap_r, -99.0)
        if width < MIN_CORRIDOR:
            blocked.append((s, width))
    if blocked:
        worst = min(blocked, key=lambda b: b[1])
        errors.append(
            f"corridor pinches to {worst[1]:.2f} m at x={worst[0]} "
            f"(need {MIN_CORRIDOR} m) at {len(blocked)} point(s) along +x")

    return out, errors, fixes


if __name__ == "__main__":
    import sys
    frag = sys.stdin.read()
    fixed, errs, fx = validate(frag)
    for f in fx:
        print(f"  FIXED {f}")
    for e in errs:
        print(f"  ERROR {e}")
    print(f"\n{'PASS' if not errs else 'FAIL'}: {len(parse_geoms(fixed))} geoms, "
          f"{len(fx)} repaired, {len(errs)} unresolved")
    if not errs:
        print(fixed)
