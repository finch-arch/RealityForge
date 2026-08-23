# Humanoid in a generated world

A **Unitree G1 humanoid you drive with WASD**, walking with real MuJoCo physics through
environments you create from a sentence or a photograph.

Built on a laptop with a **broken NVIDIA driver**, with **no training**, for **under $5** of
API spend.

---

## Run it

```bash
./venv/bin/python app.py          # then open the printed URL
```

Three steps, each unlocking the next:

1. **Create a world** — describe a place; HappyOyster builds it in ~30 s and returns a
   photoreal frame. *(Or upload your own photo and skip this.)*
2. **Build the physics** — a vision model reads that image and writes MuJoCo geometry laid
   out like it. Validated and walk-tested before you are allowed to drive it.
3. **Teleoperate** — WASD, on screen or in the MuJoCo window. Real collision.

Or from the terminal:

```bash
./venv/bin/python oyster_seed.py "a riverside ghat in Varanasi at golden hour"
./venv/bin/python image_to_scene.py out/seed_world.png --save ghat
./venv/bin/python drive_g1.py --preset ghat --no-world --preview --record out/t.mp4
```

Steps 2 and 3 run **fully offline** — no network, no cost, nothing that can be rate-limited.

---

## The question we set out to answer

**Can a generative world model be a robot's environment?**

We answered it by building both architectures and comparing them:

| | World model as environment | Simulator as environment |
|---|---|---|
| Scenery | photorealistic | built geometry |
| **Physics with the scene** | **none** | **real collision, real footing** |
| Robot motion | real, but composited on top | real, structure preserved |
| Usable take length | ~8–10 s before drift | unlimited |

**The finding: world models emit observations, not state.** Physics needs state you can query
and integrate, so a world model can be a robot's *scenery* — never its *environment*. That
isn't an opinion; it falls out of both builds.

So we use each for what it is good at:

```
text ──► HappyOyster ──► photoreal frame ─┬──► LingBot ──► navigable world   (what you see)
                                          │
                                          └──► image_to_scene ──► MuJoCo     (what you touch)
```

One generated image feeds **both** halves, so the world you look at and the world you collide
with derive from the same source.

---

## Measured, because the documentation was wrong

The vendor's two documentation pages contradict each other on frame rate and resolution.
**Both are wrong.** We measured everything that mattered:

| | Documented | Measured |
|---|---|---|
| Resolution | 1664×960 *or* 480p | **1664×960** |
| Frame rate | 48 fps *or* 16 fps | **neither** — 36.5 fps delivered |
| Generation speed | "<1 s latency" | **0.25× realtime**, 0.1333 s media/chunk, constant |
| First-frame latency | "<1 s" | **1.12 s** |
| Models available | 7 in the docs | **24** via `GET /models` |

Other findings, all reproducible:

- **`attn_window` does not change throughput.** Tested all three settings against a control:
  `auto` 0.258, `small` 0.285, `large` 0.268 media/wall. `small` buys ~10%; realtime needs 4×.
- **`set_camera_pose` is persistent state, not a one-shot.** Overdriving it visibly destroys
  the image — purple foliage, geometry collapse.
- **Drift is scene-dependent.** Open scenes with a horizon survive 40 s of forward motion;
  enclosed corridors collapse.
- **The locomotion policy is terrain-blind.** Its 47-dim observation contains no ground
  sensing, and a **6 cm step topples it** — measured, not assumed.
- **X2 preserves structure frame-for-frame** but will not replace an environment; it is a
  subject-swap model, and its prompt must be an *edit instruction*, not a scene description.

Full detail and method in [`out/RESULTS.md`](out/RESULTS.md).

---

## The engineering worth mentioning

- **135× speedup** by decoupling render rate from physics rate. Syncing the viewer every
  500 Hz step ran the sim at 1/135th speed on a machine with no working GPU driver.
- **A validator that encodes the robot's real limits.** Every generated scene is checked —
  props ≥0.4 m, corridor ≥1.5 m, spawn clear — auto-repaired where possible, then
  **walk-tested headlessly** before it can be driven. Generating geometry is easy;
  guaranteeing the robot survives it is the work.
- **Segmentation-mask compositing** with a synthetic contact shadow, since the world model
  provides no depth.

---

## What we used

| | |
|---|---|
| **HappyOyster** (`reactor/happy-oyster-adventure`) | text → persistent photoreal world |
| **LingBot World 2** (`reactor/lingbot-world-2`) | seed image → navigable world video |
| **X2** (`xmax/x2`) | video-to-video restyling of MuJoCo renders |
| **Claude** (via the Claude Code CLI) | image/text → MuJoCo geometry |
| **Unitree G1 policy** (`motion.pt`) | pre-trained, CPU, 47 obs → 12 actions |
| **MuJoCo 3.12** | physics, offscreen rendering, segmentation |

Nothing was trained. The locomotion policy ships with `unitree_rl_gym`; every other model is
hosted.

---

## Honest limits

- **The robot cannot collide with the world-model scenery.** That composite is a 2D paste-over
  with a drawn shadow, not a physical relationship.
- **Generated geometry is blocks.** Boxes, cylinders and spheres arranged like the photograph
  — correct in plan view, not detailed.
- **No rough terrain.** Stairs and slopes would need a policy retrained with height sensing,
  and a working GPU.
- **World-model takes cap at ~8–10 s** before drift. Short takes, re-seeded, beat one long one.
- **HappyOyster's walkable stream is unreachable.** Its interactive world lives behind an
  undocumented gateway; credentials authenticate, but no route is published. We use the first
  frame.
