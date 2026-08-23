# LingBot World 2 — measured API results

Measured 2026-08-22 against `reactor/lingbot-world-2` via `reactor-sdk` 1.1.1.
Replaces the guesses the docs left us with.

## Connectivity

Works. `Reactor(model_name=..., api_key=...)` handles the JWT exchange internally —
no manual `POST /tokens`. No `aiortc` needed; frames arrive decoded via `on_frame`.

The undocumented `set_image` param shape is confirmed:

```python
ref = await reactor.upload_file("seed.png")   # -> FileRef
await reactor.send_command("set_image", {"image": ref})
```

`reactor.request_schema()` returns the full OpenAPI 3.1 spec (24 KB) — 16 commands,
11 events. **It is far more detailed than the public docs** and is the authoritative
reference. Saved to `out/schema.json`.

## Measured numbers (25 s run, seed 42)

| Metric | Measured | Docs said |
|---|---|---|
| **Resolution** | **1664 × 960** | schema 1664×960 ✅ / specs page 480p–960p ❌ |
| **Delivered frame rate** | **36.5 fps** | schema 48 fps / specs page 16 fps — **neither** |
| **First-frame latency** | **1.12 s** | "<1 s" (slightly optimistic) |
| **Chunk cadence** | **0.456 s** mean (0.318–0.692) | undocumented |
| **Frames per chunk** | **~16** | undocumented |

### Generation speed — measured directly, and it is SLOW

An earlier inference here was **wrong**. Frames-per-chunk does not tell you how much
*media* a chunk contains. Polling `request_clip()` and reading `now_marker` gives the
real answer, and it was exactly constant across 10 samples:

| | Value |
|---|---|
| Media per chunk | **0.1333 s** (2/15), constant |
| Media per wall-second | **~0.25** |

So **generation runs ≈4× SLOWER than realtime**, not faster. A 6 s clip needs ~45 chunks
and ~24 s of generation; a 60 s clip needs ~450 chunks and ~4 minutes.

**Practical rate: ~$0.03 per second of output video.** A 30 s clip is ~$0.90 and ~6 min.
This is the number that governs whether any offline-render plan is affordable.

Frame rate is the one number that disagrees with both doc pages. 36.5 fps sustained may
be client-side decode or network limited rather than a server property — worth re-measuring
on another machine before treating it as authoritative.

## Control

Discrete controls work well and produce coherent, photorealistic motion:
`set_move_longitudinal`, `set_move_lateral`, `set_look_horizontal`, `set_look_vertical`.
No `command_error` across a 9-phase scripted run.

### `set_camera_pose` is persistent state, not a one-shot ⚠️

The single most important behavioural finding. A value stays applied to **every**
subsequent chunk until cleared with an empty list. So `[0,0,0,0.5,0,0]` held for 4 s
re-applies across ~9 chunks ≈ 4.5 units of accumulated translation.

Doing that **collapses image quality** — purple/violet trees, oversaturated teal grass,
camera pitching hard downward (see `out/contact_sheet.png`, bottom row). Recovery does
not happen on its own.

Practical rule: send **small** per-chunk deltas and clear to `[]` when motion should stop.
Treat it as a velocity, not a position.

### Axis directions (provisional)

From `out/calib_sheet.png`, magnitude 0.06 translation / 0.02 rad rotation:

| Probe | Observed | Reading |
|---|---|---|
| `+tx` | path swings left | camera moves **right** |
| `+ty` | ends at pebble/ground level | camera moves **down** |
| `+tz` | advances along the path | camera moves **forward** |
| `+rx`, `+ry` | visible reorientation | rotations confirmed live (radians, per schema) |

**These are provisional, and the method has a real flaw:** the generated world is
*non-reversible*. Clearing to `[]` stops further motion but does not return the camera,
so each probe starts from wherever the previous one ended and no two probes see the same
scene. Clean per-axis calibration requires **one fresh session per axis** — same seed,
same seed image, a single probe each.

### Scale is not metres

0.06 applied over ~5 chunks moved the camera from eye level to ground level — roughly a
human height. So one translation unit is **large**, on the order of several metres, and
the effect accumulates per chunk. Any robot-to-camera mapping needs the per-session
calibration above, not a guessed constant.

## Schema details the public docs omit

`set_camera_pose` description (from `request_schema()`):

- flat list, length a multiple of 6: `[rx, ry, rz, tx, ty, tz]` per step
- **rotations in radians, relative to current orientation**; translations relative to
  current position
- 6 values = one motion across the whole next chunk; one 6-tuple per frame = per-frame
  control; **any other length is resampled to fit the chunk**
- while set, rotation **replaces** `look_*`; translation **adds to** `move_*`
- sanitised server-side: non-finite → 0, **rotations clamped to ±π, translation to ±100**
- empty list returns control to the `move_*` / `look_*` inputs
- `maxLength` 1536 (= 256 steps)

## Clips and recordings

`request_clip(N)` returns the window `[now - N, now]` (server-capped at 5 min);
`request_recording()` covers the whole session. Both require status `READY`, else
`InvalidStateError`. **Clips are deleted after 24 h** and their URLs expire.

Measured behaviour the docs do not state:

| | Finding |
|---|---|
| Clip resolution | **832×480 @ 30 fps** — half the live track's 1664×960 |
| Container | **MPEG-TS**, not MP4, from the Python SDK. Remux with `ffmpeg -c copy` |
| Duration granularity | segment-aligned — a 6 s request returned **8.02 s** |
| Readiness | the manifest appears only once the recording passes the end of the chunk holding the window, so **generation must continue** while waiting |

The readiness wait is the expensive part. `download` waits on `predicted_ready_at_ms`,
which the SDK docstring says is *"only right for a model running at real-time"* — and this
model is 4× off that, so the prediction is useless. Bound it with `ready_timeout` and
generate past the window before requesting.

**`generate_video.py` end state:** 6 s clip in **74.8 s / $0.18** (down from 191 s / $0.63).
Roughly half that wall time is still the post-request readiness wait, during which
generation keeps billing.

## Sustained motion drifts the camera into the ground ⚠️

The most important finding for any robot integration.

A 6 s clip generated with `set_move_longitudinal: "forward"` held continuously starts as a
convincing misty cobblestone street and ends **looking straight down at the pavement** —
the camera pitches progressively downward across the take (`out/street.mp4`,
`out/street_grid.png`).

This is **not** a `camera_pose` problem; no pose commands were sent. An earlier conclusion
here — that the discrete axes were "rock solid" — was drawn from a 5 s hold and does not
survive ~47 s of generated media.

The prompt guide predicts it: *"Keep holds brief; long continuous holds accumulate drift as
the model conditions on its own recent frames."*

**Implication for MuJoCo/G1:** a walking robot holds "forward" continuously, which is
precisely the failure mode. Mitigations to test: pulse the motion (forward ~2 s → idle
~0.5 s → repeat), periodic `trigger_kv_cache_reset`, and shorter takes stitched together.

## Cost is dominated by recording lag, and is variable

Two 6 s clips, same settings apart from prompt and seed size:

| Run | Seed | Wall | Cost | File |
|---|---|---|---|---|
| A — default prompt | 1024 px | 74.8 s | $0.18 | 0.4 MB |
| B — rich prompt | 1664 px | 206 s | $0.60 | 2.5 MB |

The generation loop itself only needs ~24–32 s. The rest is `download_clip` waiting for the
**recording pipeline to catch up**, which lags generation by a large and variable margin —
run B generated 352 chunks (~47 s of media) to deliver a 6 s clip.

**Consequence: short clips are the worst case.** The catch-up overhead is roughly fixed, so
a 30 s clip costs little more than a 6 s one in absolute terms and far less per second.
Generate long, trim afterwards, rather than making many short calls.

## Cost

All testing to date ≈ **$2.00**. The 33 credits/s ≈ $11.88/hr quote matches observed
billing. `pause` stops the meter; being merely connected does not generate.

## Gotchas hit in practice

1. **Frames are 4.8 MB each** (1664×960×3). Retaining them all blew memory to ~2.4 GB in
   15 s, stalled the event loop, and killed the WebRTC data channel with
   `TRANSPORT_ERROR: data channel send failed`. Downsample or discard on arrival.
2. `conditions_ready` fired **twice** in one session — treat it as level, not edge.
3. `try/finally` teardown proved its worth: the transport failure above still tore the
   session down cleanly with no billing leak.

## `attn_window` does not fix the speed ceiling

Tested because it was the only exposed knob that might change generation throughput.
Three sessions identical except `set_attn_window`, sent before `start`. Rate measured as
the slope of `now_marker` (recording media time) against wall clock, over the later half of
each run.

| attn_window | media/wall | media/chunk | chunks/s | × realtime |
|---|---|---|---|---|
| `auto` (control) | 0.258 | 0.1333 | 1.93 | 0.26× |
| `small` | **0.285** | 0.1333 | 2.14 | 0.29× |
| `large` | 0.268 | 0.1333 | 2.01 | 0.27× |

Control reproduced the earlier 0.25, so the measurement holds.

**`small` buys ~10%. Realtime needs 4×.** The verdict stands: **0.25× is a hard ceiling**
and any robot sim must be slowed to match.

Note `media/chunk` is **0.1333 in all three conditions** — the window does not change chunk
size at all, only chunk rate, and only slightly.

**Do not adopt `small` reflexively.** The schema says it trades *temporal stability* for
*responsiveness to camera motion* — and temporal stability is exactly what the drift problem
consumes. Trading it away for 10% throughput is likely a bad deal given that sustained
motion already pitches the camera into the ground. Test it against drift before using it.

(Frames received varied wildly across conditions — 776 / 75 / 628 — but frame delivery is
known to be noisy under `request_clip` polling, and `media/chunk` was identical throughout,
so this is a client-side artefact, not a model difference.)

## `drive_g1.py` — WASD control, verified

G1 + LingBot World 2 under keyboard control. Toggle semantics (press W to walk, Space to
stop) because `launch_passive(key_callback=...)` fires on press only — and because both G1's
`cmd` and the world model's `move_*`/`look_*` axes are persistent state, so they map exactly.

**Verified:**

| Check | Result |
|---|---|
| G1 walks under the pre-trained CPU policy | 4.59 m in 10 s ≈ 0.46 m/s vs 0.5 commanded |
| W / Q / Space / D drive `cmd` and mirror onto world axes | all correct, robot stayed upright |
| Sim speed scaling | 312 samples in 25 s wall = 6.24 s sim = **exactly 0.25×** |
| World session lifecycle | connect → seed → start → mirror → teardown, no `command_error` |
| Clean process exit | yes |

**Two bugs worth remembering:**

1. **Rendering must be decoupled from physics.** Syncing the viewer every 500 Hz physics step
   ran the sim at **1/135th speed** (22 control ticks in 60 s) — this machine has no working
   NVIDIA driver, so MuJoCo software-renders a 64-mesh model. Stepping physics to catch up to
   wall clock and syncing at 20 Hz fixed it: 748 samples in 15 s, full realtime.
2. **The viewer's UI thread is not a daemon**, so the process hangs after `main()` returns.
   `os._exit(0)` after our own teardown is the pragmatic fix.

**Not yet tested** (needs a human at the keyboard): whether interactive driving avoids the
camera drift that scripted continuous holds produced. A human naturally starts, stops and
turns rather than holding forward for 45 s, so it may largely self-mitigate — but that is a
hypothesis, not a result.

## Drift: much less severe in open scenes

A 40 s clip of **continuous forward** motion through the meadow prompt (`out/drive.ts`,
`out/drive_grid.png`) — the exact case that destroyed the street scene:

- **The horizon did not sink.** The camera stayed level for the whole take. This is the
  failure that made the cobblestone street unusable, and it did not reproduce.
- Artifacts that did appear: intermittent texture smearing, magenta streaks, blown-out
  grass — cosmetic degradation rather than geometric collapse.
- **It partially recovers.** Later frames are cleaner than mid-clip ones, so the damage is
  not purely cumulative.

Both runs used `set_kv_cache_reset: "auto"`, so that is not the difference. The standout
variable is **scene topology**:

| | Street (failed) | Meadow (held) |
|---|---|---|
| Scene | narrow corridor, buildings both sides | open field, distant horizon |
| Result | camera pitched into the pavement | horizon level for 40 s |

**Leading hypothesis: open scenes with a visible horizon sustain forward motion far better
than enclosed corridors.** A distant horizon gives the model a stable reference; a narrow
corridor gives it strong parallax on both sides and the geometry collapses.

This is n=1 per condition and the prompt is the only uncontrolled variable, so treat it as a
strong lead rather than a settled result. **Practical upshot for the demo: prefer open
outdoor scenes.** The drift risk is materially lower than feared.

## Keyboard control needed a terminal reader

The MuJoCo viewer only receives keys while its window is focused, and focus is easily lost —
keystrokes then land in the shell instead (observed: only the first `W` registered, the rest
appeared as `wddaszx` on the command line). `drive_g1.py` now reads stdin as well, in cbreak
mode with echo off, so you can watch the viewer and drive from the terminal. Terminal
settings are captured in `main` and restored before `os._exit`, so the shell is never left
without echo.

## The MuJoCo environment can be replaced visually — and is

`drive_g1.py --composite out.mp4` renders G1 with `enable_segmentation_rendering()`, cuts it
out, and pastes it over the live world-model frame. The sim keeps a bare floor so the robot
has something to stand on; **every visible pixel of scenery comes from the world model**.
No checkerboard, no skybox, no MuJoCo scenery at all.

Verified: 744 composite frames / 74 s of video from a 95 s scripted drive.

**Render cost is not a problem, even software-rendering:**

| resolution | rgb | segmentation | total | fps |
|---|---|---|---|---|
| 1664×960 | 37 ms | 63 ms | 100 ms | 10.0 |
| 832×480 | 24 ms | 17 ms | 41 ms | 24.6 |
| 640×368 | 25 ms | 12 ms | 37 ms | 27.0 |

Against a ~4 fps requirement (0.25× sim × 16 fps media), there is 2.5–6× headroom.

Implementation notes:
- G1's `scene.xml` declares **no offscreen framebuffer**, so it defaults to 640×480 and any
  larger `Renderer` raises. Inject `<visual><global offwidth=… offheight=…/></visual>`,
  writing the patched XML *beside* the original so its `<include>` still resolves.
- The segmentation buffer's channel 0 is the geom id; `-1` is empty space. Excluding the
  `floor` geom leaves exactly the robot — verified against a magenta background, clean edges,
  no floor bleed.
- Composite in the **main thread** from the sim loop; the `Renderer` is not shared with the
  viewer's thread. The newest world frame sits in a single overwritten slot.
- The world model gives no depth, so the cutout is always drawn in front and reads as
  floating. A **soft elliptical contact shadow** under the mask's bottom edge fixes most of
  that — the standard compositing trick.
- Skip compositing until the first world frame arrives (~1.1 s), or the opening frames show
  MuJoCo's checkerboard.

### Turning degrades the world faster than moving forward

Refines the earlier drift finding. In a scripted drive (`w` … `q` … `w` … `e` … `w`) the
frames before the first turn are clean; everything after shows smearing, streaking and
oversaturated cyan. A 40 s pure-forward drive stayed clean throughout.

Plausible reason: rotating the camera exposes scene content that must be invented, whereas
moving forward mostly extends structure that already exists.

**Practical: turn sparingly, and consider `trigger_kv_cache_reset` after each turn.**

## Operational gotchas found while driving

- **A slow connect looks like a hang.** Status now steps through
  `[connecting]` → `[uploading]` → `[waiting for model]` → `[live]`, so a stall is visible.
  Worst case before going live is ~3 minutes (60 s connect + 120 s `conditions_ready`).
- **If the world never goes live, the composite writes zero frames** — correct behaviour
  (better than emitting MuJoCo checkerboard) but it must say so loudly, which it now does.
- **Never `join()` a cleanup thread for 90 s.** It makes Ctrl-C feel like a hang, and
  interrupting mid-join segfaulted the GL teardown. Now 20 s and interruptible.
- Reactor connect failures are transient: an identical run failed once with
  "session not ready after 20 polls" and succeeded on retry. Retry before debugging.

## Inverted pipeline (SANA) — built, but blocked on model availability

`sana_restyle.py` implements MuJoCo-does-physics / SANA-does-looks, kept **entirely
separate** from the LingBot code, which is untouched and still works.

The MuJoCo half is done and free to run (`--render-only`): G1 walks through a scene with
**real collidable geometry** (boxes and a cylinder at x=3,5,7,9), rendered at 1280×704 @
24 fps to match SANA's output. 167 frames verified.

**The API half cannot run.** Model availability on this key:

| model | connect | responds to commands |
|---|---|---|
| `lingbot-world-2` | ✓ | ✓ |
| `helios` | ✓ | ✓ |
| `longlive-v2` | ✓ | ✓ |
| **`sana-streaming`** | ✓ | **✗ — silent** |
| **`x2`** | **✗ 403 Forbidden** | — |

`sana-streaming` connects and accepts an uploaded file, then never answers: no `state`
message on connect (the docs say it should emit one), and every `send_command` /
`request_schema` times out at the SDK's 10 s limit. Reproduced across three attempts, so it
is not transient. `x2` — the only other video-to-video model — returns a clean 403, i.e. not
authorised for this key.

Neither remaining model can substitute: `helios` takes **image input only** (its schema
declares just one `out` track, no inbound), and `longlive-v2` is text-only.

**So the inverted pipeline is blocked on Reactor, not on our design.** `sana_restyle.py`
should run unchanged if `sana-streaming` starts responding or `x2` gets enabled.

Useful detail found while reading SANA's docs, should it become available: it is
substantially faster than LingBot — 24-frame chunks at ~1–1.5 s each, i.e. roughly
**0.67–1.0× realtime** against LingBot's measured 0.25× — and it has built-in drift
mitigation via `set_anchor_interval(chunks)`, which re-grounds every N chunks.

## Correction: SANA and X2 were never gated — and X2 works

`GET https://api.reactor.inc/models` (plain API key, no JWT) returns **24 models**, far more
than the 7 in the public docs. Both "blocked" models are `status: active, is_public: true`,
and a token request scoped to `reactor/sana-streaming` returns a valid JWT.

**The 403 was my error: X2's slug is `xmax/x2`, not `reactor/x2`.** Different namespace.

### X2 validates the inverted architecture

`x2_restyle.py` pushed a 167-frame MuJoCo clip (G1 walking past real collidable obstacles)
to X2's `source` track and received **122 restyled frames in 33 s**. It works.

| | result |
|---|---|
| Structure preserved | **yes** — same pose, same floor, same obstacle, frame for frame |
| Robot motion | **real** — G1's actual gait, not invented |
| Appearance changed | yes — blue/white robot livery, warm sunset relighting |
| **Environment replaced** | **no** — the checkerboard stayed a checkerboard |

The prompt asked for "a dirt path in an open meadow" and got a relit checkerboard. That is
consistent with X2's stated purpose: *"character swap / insertion"* guided by a prompt and an
optional reference image **of the character**. It edits subjects, not environments.

**So the architecture is proven — physics real, motion real, structure preserved — but no
available model does wholesale sim→photoreal environment replacement.**

### Models that do not respond

`reactor/cosmos-transfer` (NVIDIA Cosmos Transfer 2.5, and on paper the ideal fit — it takes
`edge | depth | seg | vis` conditioning, all of which MuJoCo renders natively) connects but
times out on every `request_schema`, across three attempts. It has **no public docs** either.
`reactor/sana-streaming` behaves identically. Both are in the catalog as active.

### What this implies

Since no model will replace the environment, the environment has to be built well in MuJoCo:
textures instead of the default checkerboard, a real skybox, decent lighting. X2 can then add
photorealistic polish on top of geometry that is already plausible — which is exactly what a
subject/relighting model is good at.

Also worth noting from the catalog: `reactor/groot-n17` (GR00T N1.7), `cosmos-nano-policy-droid`
and `xr1-robocasa365` are video-in → **action-out** VLA policies. That is the LingBot-VA
direction available as a hosted API, though all target manipulation embodiments, not legs.

## Three working paths, compared

`out/THREE_WAY.png` — same robot, same policy, three pipelines.

| | scenery | physics with scene | robot motion | artefacts |
|---|---|---|---|---|
| **1. LingBot composite** (`drive_g1.py`) | photorealistic, best | **none** | real, but pasted over | drift/smearing after ~45 s |
| **2. MuJoCo dressed scene** (`render_scene.py`) | clean, game-like | **real collision** | real | none |
| **3. X2 on (2)** (`x2_restyle.py`) | (2) + material and lighting polish | **real collision** | real, preserved frame-for-frame | none |

### Dressing the MuJoCo scene was the bigger win

G1's stock `scene.xml` was a **flat black skybox**, a blue checkerboard with 0.2 reflectance,
and a single hard light. Replacing that (gradient sky, procedural grass/dirt texture, sun +
ambient fill, fog, props) transformed the render on its own, for free, with no API.

Two details that mattered: the first texture had a standard deviation of only ~6–8 and read
as flat green — layered octave noise with thresholded dirt patches raised it to ~12–17. And
`texrepeat="14 14"` under `texuniform` spans **14 metres per tile**, so no detail was visible
over a 10 m walk; `2 2` fixed it.

**G1 still walks it**: x=+4.11 m, height 0.770, min 0.763 — identical to the flat baseline.
Props are all ≥0.4 m tall precisely so the terrain-blind policy never attempts to step onto
one.

### X2 adds polish, not photorealism

215 frames in, 178 back in 37.8 s. It contributes visible material detail (wood grain on the
crates), softer lighting, and a more refined finish on the robot — a real improvement, but
incremental. It will not replace an environment, exactly as its "character swap / insertion"
description implies.

### Choosing

The two demos tell different stories and both work:
- **"World models as robot environments"** → path 1. Best-looking, on-theme, no physics.
- **"Physically-grounded simulation"** → path 3. Real collision, real footing, no drift, and
  it holds up for arbitrarily long takes.

## Scene presets: design with LingBot, physics in MuJoCo, dress with X2

`scene_builder.py` now has five parameterised presets, each emitting MJCF geometry, a ground
palette, a sky gradient **and** a matching LingBot prompt (`preset_prompt(name)`), so the
simulated place and the imagined place describe the same thing.

| preset | geoms | G1 walk test |
|---|---|---|
| meadow | 69 | WALKED — x=+4.11, height 0.770 |
| warehouse | 72 | WALKED — x=+4.09, height 0.769 |
| forest | 80 | WALKED — x=+4.11, height 0.770 |
| street | 72 | WALKED — x=+4.11, height 0.770 |
| courtyard | 69 | WALKED — x=+4.11, height 0.770 |

All five match the flat baseline exactly, which is the point: **every prop is ≥0.4 m tall**,
so the terrain-blind policy never attempts a step-up. See `out/PRESETS.png`.

Usage:
```bash
./venv/bin/python render_scene.py --preset warehouse --seconds 9   # free render
./venv/bin/python drive_g1.py --no-world --dressed --record out/t.mp4   # teleop
./venv/bin/python x2_restyle.py --src out/scene_warehouse.mp4 --prompt "Make this..."
```

### X2: the prompt style was the problem

The schema calls `set_prompt` *"the editing instruction"*. Re-running the warehouse with an
**edit instruction** ("make this photorealistic: weathered concrete, painted steel racking
with worn paint and rust…") instead of a scene description produced visibly more material
detail — real concrete grain, wood grain on the walls — where the earlier description-style
prompt only relit the scene. See `out/X2_BEFORE_AFTER.png`.

Two caveats, both honest:
- **It also turned the robot dark**, which was not requested. X2 edits the whole frame and
  the subject is not protected. Prompts naming only surfaces still leak onto the robot.
- **`set_keep_backlog: true` barely helped** — 184/215 frames returned versus 178/215 with
  the default. The promised in-order 1:1 consumption did not materialise at a 12 fps push
  rate; the bottleneck is inference speed, not the backlog policy.

X2 remains a polish pass, not a photorealism engine. The dressed MuJoCo scene is doing most
of the visual work, and it is free.

## Scenes from a text description

`scene_describe.py "a ruined temple courtyard with broken stone pillars" --save temple`

Generation goes through the **`claude` CLI**, so it uses existing Claude Code auth — no
separate API key, and no `ANTHROPIC_API_KEY` is set on this machine. First attempt produced
30 geoms, passed validation with zero repairs, passed the walk test, and returned a matching
LingBot prompt for the same place.

### The validator is the part that matters

Generating geometry is easy; guaranteeing the terrain-blind policy survives it is the work.
`scene_validate.py` enforces, and where possible repairs:

| check | rule | why |
|---|---|---|
| prop height | ≥0.40 m | a measured 6 cm step topples the policy — auto-raised for box/cylinder |
| corridor | ≥1.5 m clear along +x | the operator drives in third person |
| spawn | nothing within 0.8 m of origin | the robot starts there |
| floor | flat, no ramps or steps | no ground sensing in the 47-dim observation |

Verified against a deliberately broken scene: it auto-raised a 12 cm kerb, and rejected both
a prop on the spawn and a corridor pinching to 0.20 m. The hand-written `medieval` preset
passes clean (25 geoms, 0 repairs).

Accepted scenes are cached in `custom_presets.py`, which `scene_builder` imports, so they
work immediately with `drive_g1.py --preset <name>`.

### The full loop, now closed

```bash
./venv/bin/python scene_describe.py "a rooftop with chimneys" --save rooftop
./venv/bin/python drive_g1.py --preset rooftop --no-world --record out/t.mp4
./venv/bin/python x2_restyle.py --src out/t.mp4 --prompt "Make this photorealistic: ..."
```

`scene_describe` also prints the matching LingBot prompt, so `generate_video.py` can produce
a visual reference of the *same* place.

**Caveat:** the model places geometry to satisfy the constraints, not to compose a shot. The
temple's pillars ended up spread wide and largely out of frame. Composition still needs a
human — either tighter wording ("pillars 2 m either side of the path, every 3 m") or hand
editing afterwards.

## HappyOyster seeding — text becomes a real place

`reactor/happy-oyster-adventure` solved the "every scene looks the same" problem outright.

`create_world(prompt, perspective)` builds a **persistent** world from a paragraph of text in
**~30 s** and returns a photoreal first frame. No seed image needed — text alone. Asked for a
Varanasi ghat, it produced carved pillars, sandstone steps, moored boats, saffron cloth,
incense smoke and golden-hour light. `perspective="third_person"` even frames it like a chase
camera.

That frame is exactly what LingBot World 2 wants as a seed, which closes the loop:

```
text ──► HappyOyster ──► photoreal first frame ──► LingBot ──► navigable world
                                                                  │
                         MuJoCo G1 (real physics) ────────────────┘ composite
```

```bash
./venv/bin/python oyster_seed.py "A riverside ghat in Varanasi at golden hour: ..."
./venv/bin/python drive_g1.py --image out/seed_banaras.png --composite out/demo.mp4
```

Result: G1 walking the ghat steps beside the Ganges, boats and reflections in frame — a real
place, not grey blocks (`out/banaras_world.mp4`).

Other schema facts: `attach_world(encrypted_world_id)` re-opens a world later, so good ones
are worth keeping (ids logged to `out/worlds.jsonl`). `get_credentials` returns a ticket for
HappyOyster's own interactive "travel" stream on an external Alibaba Cloud endpoint — that is
a separate, undocumented API, and not needed for seeding.

### Drift is now the binding constraint

Sampling the 33 s composite (`out/banaras_decay.png`):

| ~time | state |
|---|---|
| 2 s | excellent — ghat, boat, water, reflections |
| 6 s | still excellent |
| **10 s** | **degradation begins** — water speckling purple |
| 14 s | significant |
| 20 s+ | destroyed — blue spike artefacts |

**Usable window is ~8–10 s per take.** The seed fixes *what* the world is; it does not fix how
long LingBot can hold it. Short takes, re-seeded, beat one long one.

## Image → MuJoCo scene: the link between the two halves

`image_to_scene.py out/seed_banaras.png --save ghat`

A vision model reads a still and writes MJCF laid out like it. This is **not**
photogrammetry — single-image depth reconstruction from generated frames is unreliable and
multi-view inconsistent, which is why it was rejected earlier. This is a vision model
*interpreting* the layout, a far easier problem and good enough to align a composite.

It works. From the HappyOyster Varanasi frame it produced 25 geoms that map onto the image:

| derived geom | in the image |
|---|---|
| `pillar_left_near`, `pillar_right_near` at y=±2.4 | the two foreground pillars |
| `wall_left_*`, `building_left_*` at y=+4…+7 | the ghat wall on the left |
| `boat_1`…`boat_5` at y=−3.6…−4.5 | the moored boats, **on the correct side** |
| `temple_tower`, `temple_dome` at x=18.8 | the far bank |

The palette is **sampled from the image directly** (PIL, by image region) rather than guessed,
so the ground and sky match too — warm sandstone, golden horizon.

Validation passed with zero repairs; the walk test passed. See `out/IMAGE_TO_SCENE.png`.

### What it deliberately will not reproduce

The vision model correctly reported *"Ground: stepped — wide stone ghat stairs descending
toward the water."* Those stairs are **flattened on purpose**: the policy is terrain-blind and
a 6 cm step topples it, so the prompt forbids steps, ramps and kerbs outright. A ghat becomes
a flat quay with the right things standing on it.

So the correspondence is in **plan view** — where the solid masses are, and what colour
everything is. Not elevation, and not detail. It is blocks arranged like the photograph, which
is exactly enough to make the composite line up.

### Why this closes the loop

```
text ──► HappyOyster ──► photoreal frame ──┬──► LingBot ──► navigable world (no physics)
                                           │
                                           └──► image_to_scene ──► MuJoCo geometry (physics)
```

One frame now feeds **both** halves, so the world you look at and the world you collide with
are finally derived from the same source instead of invented independently.

## HappyOyster's walkable stream is out of reach without the protocol

HappyOyster builds a **persistent, walkable** world, not a single frame. We use only the
first frame, because the Reactor session is a broker: its one track is `status_video` (build
progress), and the interactive stream lives on HappyOyster's own gateway, reached with the
credentials from `get_credentials`.

Probed it inside a 20-minute timebox, with a freshly minted ticket:

- **The gateway is reachable and the token authenticates.** Responses are well-formed Alibaba
  MaaS envelopes — `{"request_id": …, "output": {…}}` — not 401/403. We are talking to the
  right service with valid credentials.
- **It does not self-describe.** `/openapi.json`, `/docs`, `/schema`, `/swagger.json`,
  `/.well-known/openapi.json` all return 404 inside the envelope.
- **No guessed route worked** — `/travels`, `/travel`, `/sessions`, `/enter`, `/rtc`,
  `/worlds/{id}`, `/v2/travels`, and POSTs carrying the ticket, all 404.
- **No SDK to learn from:** `@reactor-models/happy-oyster-adventure` is not on npm (404),
  though `@reactor-models/lingbot-world-2` exists at 0.5.0, so the convention is right and
  this one is simply unpublished. Its docs pages 404 too.

Stopped there rather than brute-forcing an undocumented gateway against single-use 30-minute
tickets. **The route to it is to ask Reactor for the travel protocol**, not to guess.

Worth having established, though: the credentials are valid and the endpoint is live, so this
is a documentation gap, not a permissions or availability problem. If the protocol turns up,
it would remove the drift ceiling that currently caps takes at ~8–10 s.

## Matching a photograph: geometry is only a third of the problem

Deriving geometry from an image gets the *objects* right and the place still wrong. A desert
highway is asphalt, lane markings, cracks and distant mountains — almost none of which is
geometry. Placing boxes can never reproduce it.

So the image now supplies three things, not one:

| from the image | how |
|---|---|
| **layout** | vision model → MJCF geoms (objects, in plan view) |
| **palette** | PIL region sampling → ground/sky colours |
| **surface + horizon** | crops → MuJoCo ground texture and skybox |

The last row is new and made the largest visual difference: the road scene went from uniform
brown desert under a gradient sky to grey asphalt under the photo's own blue. See
`out/SURFACE.png`.

**MuJoCo gotcha:** a single-file skybox is mapped onto all six cube faces, so the PNG must be
**square**. A 1024×512 image fails with *"PNG size must be integer multiple of gridsize"*.
1024×1024 works.

### What still does not match, and why

- **No lane markings** — the ground crop landed between them, and one tiled texture cannot
  vary across the plane (asphalt everywhere, no desert shoulder).
- **No distant mountains** — the skybox band sits below the camera's eyeline at typical chase
  angles.

Closing this would need the ground texture to be **perspective-rectified**: assume a camera
height and FOV, compute a homography from the image's ground quad to a top-down rectangle,
and tile *that* along +x. For a straight road shot from eye level it would recover the
markings. Real technique, but it needs assumed camera intrinsics and is a genuine piece of
work — not a tweak.

**Honest summary:** the derived scene matches a photograph in layout, palette, surface tone
and sky. It does not match it in surface *structure* or distant detail, and no amount of
box-placing will change that.

## Perspective-rectified ground: surface structure recovered

`rectified_ground()` in `scene_builder.py` inverts the camera projection to unwarp a
photograph's ground plane into a top-down texture. For a camera at height `h` with the
horizon at row `y0`, a ground point at distance `x`, lateral offset `y` projects to
`row = y0 + f·h/x`, `col = cx + f·y/x`; sampling that inverse over a metric grid gives the
plane seen from above.

A single photo carries no intrinsics, so it assumes **cam_h 1.6 m, hfov 65°**, and detects
the horizon as the steepest fall in per-row blueness (`B − R` plus a luminance term).

**It works.** The desert-highway photo produced a top-down texture with the **centre dashes
and both solid edge lines intact**, plus the gravel shoulders — structure a plain crop
throws away entirely.

Two gotchas, both cost a render to find:
- **A single-file skybox is mapped to all six cube faces, so the PNG must be square.**
  1024×512 fails with *"PNG size must be integer multiple of gridsize"*.
- **`texrepeat` counts repeats, not metres.** Setting it to the span (24) tiled the road 24
  times into a brick pattern; the correct value is `1/span` (0.0417) for one tile per 24 m.

Limits: the rectified region is a diamond, since the view frustum only covers a triangle of
the ground plane — outside it the texture falls back to the mean colour. And it only helps
images with a strong, roughly flat ground plane; an interior or a close-up gains nothing.

## The road, matched (and a lesson about located features)

Final state of the photo→scene pipeline on the desert highway (`out/ROAD_MATCH.png`):
asphalt road with centre dashes and yellow edge lines running to the horizon, desert either
side, sky from the photo — and zero invented objects.

Three fixes got it there, each a distinct lesson:

1. **The prompt demanded 15–40 geoms**, so the model decorated an empty road with boulders.
   Rewritten so *emptiness is a correct answer*: it now emits 4 distant rocks instead of 24
   inventions. Constraint prompts must not force a count.
2. **A road is a located feature, not a surface.** Tiling the rectified road texture over the
   floor turned the world into a grid of roads. It is now a single 60 m textured quad
   (`contype=0` — visual only, cannot trip the robot) over a desert-textured plane.
3. **Texture-mapping units, twice over:** with `texuniform`, `texrepeat` is per *metre*;
   without, per *face*. And a box face maps texture-u along its x extent, so the rectified
   image needed a 90° rotation for the road to run lengthwise.

Also from this session: `scene_builder.py` was accidentally truncated by careless string
surgery (everything below the texture functions deleted). Rebuilt from the session
transcript; all presets verified loading again afterwards. git had only the pre-preset
version — **commit more often.**
