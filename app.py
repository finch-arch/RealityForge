#!/usr/bin/env python3
"""GUI for the world-model / MuJoCo humanoid pipeline.

    ./venv/bin/python app.py        then open the printed URL

A single guided sequence, because the pipeline is a sequence:

    1. create a world from text   (HappyOyster -> photoreal frame)
    2. build physics from it      (vision model -> MJCF, validated, walk-tested)
    3. teleoperate it             (MuJoCo, real collision)

Each step stays locked until the one before it succeeds, and its output is
carried forward automatically. Step 1 can be skipped by uploading your own
photograph — which also means a Reactor outage cannot block the demo.

The GUI orchestrates; it does not simulate. Each step shells out to the existing
CLI script so those remain the source of truth. Live WASD driving happens in
MuJoCo's native window, because a browser is the wrong place for 20 Hz keyboard
control.
"""

import pathlib
import re
import subprocess
import sys

import gradio as gr

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out"
PY = str(ROOT / "venv" / "bin" / "python")
NOISE = ("QFontDatabase", "GLFWError", "XDG_SESSION", "Note that Qt", "warnings.warn")


def run(cmd: list[str]) -> str:
    """Run a pipeline script and return its output, minus Wayland/Qt noise."""
    p = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    out, _ = p.communicate()
    return "\n".join(l for l in out.splitlines()
                     if l.strip() and not any(n in l for n in NOISE))


def presets() -> list[str]:
    names = ["meadow", "warehouse", "forest", "street", "courtyard", "medieval"]
    try:
        import importlib
        sys.path.insert(0, str(ROOT))
        sys.modules.pop("custom_presets", None)
        importlib.invalidate_caches()
        from custom_presets import CUSTOM
        names += [n for n in CUSTOM if n not in names]
    except Exception:
        pass
    return names


# ------------------------------------------------------------------ step 1


def step1(description, progress=gr.Progress()):
    locked = gr.update(interactive=False)
    if not description.strip():
        return None, "Describe a place first.", locked, None
    progress(0.2, desc="HappyOyster is building a world (~30 s)")
    img = OUT / "gui_world.png"
    img.unlink(missing_ok=True)
    log = run([PY, "oyster_seed.py", description, "--out", str(img)])

    if not img.exists():
        hint = ("\n\nReactor is at capacity (429). Wait a moment and retry — or skip "
                "this step and upload your own photo below." if "429" in log
                or "RATE_LIMITED" in log else "\n\nNo frame was produced.")
        return None, log + hint, locked, None
    return (str(img), log + "\n\n✓ World created. Step 2 is now unlocked.",
            gr.update(interactive=True), str(img))


def use_upload(path):
    """Skip step 1 with your own photograph."""
    if not path:
        return None, "Upload an image first.", gr.update(interactive=False), None
    return (path, f"Using {pathlib.Path(path).name}.\n\n✓ Step 2 is now unlocked.",
            gr.update(interactive=True), path)


# ------------------------------------------------------------------ step 2


def step2(image, name, progress=gr.Progress()):
    locked = gr.update(interactive=False)
    if not image:
        return None, "Complete step 1 first.", locked, gr.update(), None
    name = re.sub(r"[^a-z0-9_]+", "_", (name or "my_scene").lower())[:20] or "my_scene"

    progress(0.2, desc="reading the layout, validating, walk-testing (~60 s)")
    log = run([PY, "image_to_scene.py", str(image), "--save", name])
    if "VERDICT: WALKED" not in log:
        return (None, log + "\n\n✗ Rejected — the scene failed validation or the robot "
                "fell. Try a different image.", locked, gr.update(), None)

    progress(0.8, desc="rendering the derived scene")
    clip = OUT / f"gui_{name}.mp4"
    run([PY, "render_scene.py", "--preset", name, "--seconds", "9",
         "--cam-dist", "6.5", "--cam-elev", "-10", "--out", str(clip)])

    return (str(clip) if clip.exists() else None,
            log + f"\n\n✓ Scene '{name}' validated and walk-tested. Step 3 is unlocked.",
            gr.update(interactive=True),
            gr.update(choices=presets(), value=name), name)


# ------------------------------------------------------------------ step 3
#
# Driving runs as a long-lived subprocess so the buttons below can steer it while
# it is still going. `drive_g1.py` reads stdin, so a key is just a byte on the
# pipe — the same path the terminal uses.

_DRIVE = {"proc": None, "out": None}


def drive_start(scene, seconds, cam_dist, cam_elev, use_world, seed_img):
    if not scene:
        return "Complete step 2 first.", gr.update(), gr.update()
    if _DRIVE["proc"] and _DRIVE["proc"].poll() is None:
        return "Already driving — stop it first.", gr.update(), gr.update()

    rec = OUT / "gui_drive.mp4"
    rec.unlink(missing_ok=True)
    cmd = [PY, "drive_g1.py", "--preset", scene, "--duration", str(int(seconds)),
           "--cam-dist", str(cam_dist), "--cam-elev", str(cam_elev), "--preview"]
    if use_world and seed_img:
        cmd += ["--image", str(seed_img), "--composite", str(rec)]
    else:
        cmd += ["--no-world", "--record", str(rec)]

    _DRIVE["proc"] = subprocess.Popen(
        cmd, cwd=str(ROOT), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, text=True, bufsize=1)
    _DRIVE["out"] = rec
    return ("Driving. Use the buttons, or W A S D in the MuJoCo window. "
            "Press Stop when you are done."), gr.update(interactive=False), \
           gr.update(interactive=True)


def drive_key(ch: str) -> str:
    p = _DRIVE["proc"]
    if not p or p.poll() is not None:
        return "Not driving — press Start."
    try:
        p.stdin.write(ch)
        p.stdin.flush()
    except Exception as exc:
        return f"could not send {ch!r}: {exc}"
    names = {"w": "forward", "s": "back", "a": "strafe left", "d": "strafe right",
             "q": "turn left", "e": "turn right", " ": "stop", "r": "reset world"}
    return f"sent: {names.get(ch, ch)}"


def drive_stop():
    p = _DRIVE["proc"]
    if not p:
        return None, "Not driving.", gr.update(interactive=True), gr.update(interactive=False)
    try:
        p.stdin.close()
    except Exception:
        pass
    try:
        p.wait(timeout=120)
    except Exception:
        p.terminate()
    rec = _DRIVE["out"]
    _DRIVE["proc"] = None
    ok = rec and rec.exists() and rec.stat().st_size > 1000
    return ((str(rec) if ok else None),
            "Saved." if ok else "No recording was written.",
            gr.update(interactive=True), gr.update(interactive=False))




# ---------------------------------------------------------------------- app

# xprobotics.ai design tokens, applied through Gradio's own theme system rather
# than fought with CSS overrides — otherwise its light defaults show through on
# every panel we did not explicitly select.
BG2, BG1, CARD, DARK = "#141416", "#1a1a1d", "#232325", "#1f1f23"
INK, INK2, MUTE = "#f2efee", "#c8d4d5", "#8f8f99"
CYAN, CYAN2 = "#00f0ff", "#22d3ee"
LINE, LINE_FAINT = "rgba(120,145,148,.22)", "rgba(120,145,148,.16)"

THEME = gr.themes.Base(
    font=[gr.themes.GoogleFont("Inter"), "sans-serif"],
    font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "monospace"],
    radius_size=gr.themes.sizes.radius_lg,
).set(
    body_background_fill=BG2, body_background_fill_dark=BG2,
    background_fill_primary=BG1, background_fill_primary_dark=BG1,
    background_fill_secondary=CARD, background_fill_secondary_dark=CARD,
    block_background_fill=BG1, block_background_fill_dark=BG1,
    panel_background_fill=BG1, panel_background_fill_dark=BG1,
    block_label_background_fill=BG1, block_label_background_fill_dark=BG1,
    block_title_background_fill=BG1, block_title_background_fill_dark=BG1,
    border_color_primary=LINE, border_color_primary_dark=LINE,
    block_border_color=LINE, block_border_color_dark=LINE,
    input_background_fill=DARK, input_background_fill_dark=DARK,
    input_border_color=LINE_FAINT, input_border_color_dark=LINE_FAINT,
    input_border_color_focus=CYAN2, input_border_color_focus_dark=CYAN2,
    body_text_color=INK, body_text_color_dark=INK,
    body_text_color_subdued=MUTE, body_text_color_subdued_dark=MUTE,
    block_label_text_color=MUTE, block_label_text_color_dark=MUTE,
    block_title_text_color=INK2, block_title_text_color_dark=INK2,
    button_primary_background_fill=CYAN, button_primary_background_fill_dark=CYAN,
    button_primary_background_fill_hover=CYAN2,
    button_primary_background_fill_hover_dark=CYAN2,
    button_primary_text_color="#0d0d0f", button_primary_text_color_dark="#0d0d0f",
    button_secondary_background_fill=CARD, button_secondary_background_fill_dark=CARD,
    button_secondary_text_color=INK2, button_secondary_text_color_dark=INK2,
    button_secondary_border_color=LINE, button_secondary_border_color_dark=LINE,
    block_shadow="none", block_shadow_dark="none",
)

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@300;400;600;700&display=swap');

/* Design tokens taken from xprobotics.ai */
:root {
  --font-display:"Space Grotesk",sans-serif; --font-body:"Inter",sans-serif;
  --accent-cyan:#00f0ff; --accent-mid:#22d3ee; --accent-light:#c3f5ff;
  --bg-secondary:#141416; --bg-primary:#1a1a1d; --bg-dark:#1f1f23;
  --bg-card:#232325; --bg-muted:#29282c; --bg-input:#3a3a3b;
  --ink:#f2efee; --ink-2:#c8d4d5; --mute:#8f8f99;
  --border-subtle:rgba(120,145,148,.22); --border-dim:rgba(120,145,148,.3);
  --border-faint:rgba(120,145,148,.16);
  --radius-sm:6px; --radius-md:12px; --radius-lg:32px;
  --shadow-card:0 0 20px 0 rgba(0,242,255,.15);
}
.gradio-container {max-width:1120px !important; margin:0 auto !important;}
body, .gradio-container {font-family:var(--font-body) !important;}
footer, .built-with, .show-api {display:none !important;}
h1,h2,h3 {font-family:var(--font-display) !important;}

/* hero — centred */
#hero {text-align:center; padding:52px 24px 40px;}
#hero .eyebrow {font-family:var(--font-display); font-size:11.5px; letter-spacing:.22em;
  text-transform:uppercase; color:var(--accent-mid); font-weight:600; margin-bottom:18px;}
#hero h1 {font-size:47px; font-weight:700; letter-spacing:-.025em; line-height:1.08;
  margin:0 0 18px; color:#fff;}
#hero h1 em {font-style:normal; color:var(--accent-cyan);
  text-shadow:0 0 26px rgba(0,242,255,.45);}
#hero .sub {font-size:16.5px; line-height:1.68; color:var(--ink-2); max-width:660px;
  margin:0 auto; font-weight:300;}
#hero .tags {margin-top:28px; display:flex; gap:10px; flex-wrap:wrap; justify-content:center;}
#hero .tag {font-family:var(--font-display); font-size:11px; letter-spacing:.1em;
  text-transform:uppercase; font-weight:600; color:var(--accent-light);
  border:1px solid var(--border-dim); background:var(--bg-primary);
  padding:7px 16px; border-radius:9999px;}

/* step cards — centred headings, left-aligned controls */
.step {background:var(--bg-primary) !important; border:1px solid var(--border-subtle) !important;
  border-radius:var(--radius-lg) !important; padding:38px 40px 32px !important;
  margin-top:26px !important; box-shadow:var(--shadow-card);}
.step .n {font-family:var(--font-display); font-size:11px; letter-spacing:.2em;
  text-transform:uppercase; color:var(--accent-mid); font-weight:600; text-align:center;
  margin-bottom:9px;}
.step h2 {font-size:27px !important; font-weight:600 !important; letter-spacing:-.02em;
  color:#fff !important; text-align:center; margin:0 0 12px !important;}
.step .lead {font-size:14.5px !important; line-height:1.72 !important; color:var(--mute) !important;
  text-align:center; max-width:680px; margin:0 auto 26px !important; font-weight:300;}
.step .lead strong {color:var(--ink-2); font-weight:600;}

label span, .gr-box label {color:var(--mute) !important; font-size:12px !important;
  font-weight:600 !important; letter-spacing:.06em !important; text-transform:uppercase;}
textarea, input[type=text], input[type=number] {
  background:var(--bg-dark) !important; border:1px solid var(--border-faint) !important;
  color:var(--ink) !important; border-radius:var(--radius-md) !important;
  font-family:var(--font-body) !important; font-size:14.5px !important;}
textarea:focus, input:focus {border-color:var(--accent-mid) !important;
  box-shadow:0 0 0 3px rgba(0,242,255,.1) !important;}

button.primary, .gr-button-primary {
  background:var(--accent-cyan) !important; color:#0d0d0f !important; border:none !important;
  font-family:var(--font-display) !important; font-weight:600 !important;
  letter-spacing:.02em; border-radius:9999px !important; font-size:14px !important;
  padding:13px 26px !important; box-shadow:0 0 22px rgba(0,242,255,.28) !important;}
button.primary:hover:not(:disabled) {background:var(--accent-mid) !important;
  box-shadow:0 0 30px rgba(0,242,255,.45) !important;}
button.secondary, .gr-button-secondary {background:var(--bg-card) !important;
  border:1px solid var(--border-dim) !important; color:var(--ink-2) !important;
  font-family:var(--font-display) !important; font-weight:500 !important;
  border-radius:9999px !important;}
button:disabled {opacity:.32 !important; box-shadow:none !important; cursor:not-allowed !important;}

/* keypad */
#pad button {font-family:var(--font-display) !important; background:var(--bg-card) !important;
  border:1px solid var(--border-subtle) !important; border-bottom-width:3px !important;
  color:var(--ink-2) !important; border-radius:var(--radius-md) !important;
  font-size:12px !important; font-weight:600 !important; letter-spacing:.05em;
  min-height:56px !important; white-space:pre-line !important; line-height:1.4 !important;
  box-shadow:none !important;}
#pad button:hover:not(:disabled) {border-color:var(--accent-mid) !important; color:#fff !important;
  box-shadow:0 0 16px rgba(0,242,255,.18) !important;}
#pad button:active {transform:translateY(2px); border-bottom-width:1px !important;}
#pad .stop button {color:#ffb4bd !important; border-color:rgba(255,120,140,.3) !important;}

#log1 textarea, #log2 textarea, #log3 textarea {
  font-family:ui-monospace,"SF Mono",Menlo,monospace !important; font-size:11.8px !important;
  background:var(--bg-secondary) !important; color:#93a6a8 !important;
  border-radius:var(--radius-md) !important; line-height:1.6 !important;}
.gr-video, .gr-image, video, img {border-radius:var(--radius-md) !important;}
.gr-accordion {border:1px solid var(--border-faint) !important;
  border-radius:var(--radius-md) !important; background:var(--bg-dark) !important;}
#foot p {color:var(--mute) !important; font-size:12.5px !important; text-align:center !important;
  line-height:1.85 !important; margin:36px 0 24px !important; font-weight:300;}
#foot code {font-family:ui-monospace,monospace; color:var(--accent-light);}
"""

HERO = """
<div id="hero">
  <div class="eyebrow">Physical AI · World Models · MuJoCo</div>
  <h1>A humanoid that walks<br>in <em>worlds you describe</em></h1>
  <p class="sub">A Unitree G1 driven with WASD through environments built from a sentence
  or a photograph — generated for their looks, simulated for their physics.</p>
  <div class="tags">
    <span class="tag">Unitree G1 · 12 DOF</span>
    <span class="tag">MuJoCo Physics</span>
    <span class="tag">HappyOyster · LingBot · X2</span>
    <span class="tag">Steps 2–3 Offline</span>
  </div>
</div>
"""

FORCE_DARK = """
function() {
  document.body.classList.add('dark');
  document.documentElement.classList.add('dark');
}
"""

with gr.Blocks(title="Humanoid in a generated world", css=CSS, theme=THEME,
               js=FORCE_DARK, fill_width=False) as app:
    seed_state = gr.State(None)
    scene_state = gr.State(None)

    gr.HTML(HERO)

    # ------------------------------------------------------------- step 1
    with gr.Group(elem_classes="step"):
        gr.HTML('<div class="n">Step 1</div><h2>Create a world</h2>'
                '<p class="lead">HappyOyster builds a <strong>persistent, photoreal</strong> '
                'world from text in about 30 seconds. No seed image needed.</p>')
        with gr.Row():
            with gr.Column(scale=5):
                desc = gr.Textbox(label="Describe a place", lines=3, show_label=True,
                                  placeholder="a riverside ghat in Varanasi at golden hour, "
                                              "sandstone steps to the Ganges, carved "
                                              "pillars, wooden boats moored at the water")
                b1 = gr.Button("Build world", variant="primary")
                with gr.Accordion("Use my own photograph instead", open=False):
                    up = gr.Image(label="", type="filepath", height=130)
                    b1b = gr.Button("Use this photo", variant="secondary")
            with gr.Column(scale=4):
                frame = gr.Image(label="The world", type="filepath", height=268)
        log1 = gr.Textbox(label="Output", lines=4, max_lines=9, elem_id="log1")

    # ------------------------------------------------------------- step 2
    with gr.Group(elem_classes="step"):
        gr.HTML('<div class="n">Step 2</div><h2>Build the physics</h2>'
                '<p class="lead">A vision model reads that image and writes MuJoCo geometry '
                'laid out like it. Every scene is <strong>validated</strong> — props ≥0.4 m, '
                'a clear corridor, spawn kept clear — and <strong>walk-tested</strong>, '
                'because the controller is terrain-blind and a 6 cm step topples it.</p>')
        with gr.Row():
            with gr.Column(scale=5):
                sname = gr.Textbox(label="Name this scene", value="my_scene")
                b2 = gr.Button("Build physics scene", variant="primary", interactive=False)
            with gr.Column(scale=4):
                derived = gr.Video(label="What the robot will walk in", height=268)
        log2 = gr.Textbox(label="Validation and walk test", lines=7, max_lines=15,
                          elem_id="log2")

    # ------------------------------------------------------------- step 3
    with gr.Group(elem_classes="step"):
        gr.HTML('<div class="n">Step 3</div><h2>Teleoperate</h2>'
                '<p class="lead">Real collision, real footing. Drive with the keys below or '
                'in the MuJoCo window that opens. Commands are <strong>toggles</strong> — '
                'forward keeps walking until you stop it.</p>')
        with gr.Row():
            with gr.Column(scale=4):
                scene_dd = gr.Dropdown(presets(), label="Scene", value=None)
                secs = gr.Slider(10, 180, 60, step=10, label="Time limit (s)")
                cdist = gr.Slider(1.5, 10, 3.2, step=0.1, label="Camera distance")
                celev = gr.Slider(-30, 5, -8, step=1, label="Camera elevation")
                world = gr.Checkbox(False, label="Composite the world model on top "
                                                 "(prettier — but no collision with it)")
                with gr.Row():
                    b3 = gr.Button("Start driving", variant="primary", interactive=False)
                    b3stop = gr.Button("Stop and save", variant="secondary",
                                       interactive=False)
            with gr.Column(scale=2, elem_id="pad"):
                with gr.Row():
                    kW = gr.Button("W\nforward")
                with gr.Row():
                    kA = gr.Button("A\n← strafe")
                    kS = gr.Button("S\nback")
                    kD = gr.Button("D\nstrafe →")
                with gr.Row():
                    kQ = gr.Button("Q\n↺ turn")
                    kSpace = gr.Button("SPACE\nstop", elem_classes="stop")
                    kE = gr.Button("E\nturn ↻")
                with gr.Row():
                    kR = gr.Button("R\nreset world context")
            with gr.Column(scale=4):
                outvid = gr.Video(label="Your recording", height=300)
        log3 = gr.Textbox(label="Output", lines=3, max_lines=8, elem_id="log3")

    gr.HTML('<div id="foot"><p>Physics: MuJoCo 3.12 · Policy: Unitree G1 pre-trained, CPU · '
            'Worlds: HappyOyster, LingBot World 2 · Restyling: X2 · Geometry: Claude<br>'
            'The robot is physically simulated; world-model scenery is not. '
            'See <code>DEMO.md</code>.</p></div>')

    b1.click(step1, [desc], [frame, log1, b2, seed_state])
    b1b.click(use_upload, [up], [frame, log1, b2, seed_state])
    b2.click(step2, [seed_state, sname], [derived, log2, b3, scene_dd, scene_state])
    b3.click(drive_start, [scene_dd, secs, cdist, celev, world, seed_state],
             [log3, b3, b3stop])
    b3stop.click(drive_stop, None, [outvid, log3, b3, b3stop])
    for _btn, _ch in ((kW, "w"), (kA, "a"), (kS, "s"), (kD, "d"),
                      (kQ, "q"), (kE, "e"), (kSpace, " "), (kR, "r")):
        _btn.click(drive_key, gr.State(_ch), log3)

if __name__ == "__main__":
    app.launch(server_name="127.0.0.1")
