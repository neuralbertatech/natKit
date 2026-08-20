"""Generate the ADL placeholder stimuli.

Kept as a script rather than a one-off so the set can be regenerated identically
when a task's wording changes -- and so the real assets, when they arrive, are a
deliberate replacement of a known set rather than a diff against hand-made files.
"""
import subprocess, sys
from PIL import Image, ImageDraw, ImageFont

# id, display name, spoken instruction -- copied from AdlExperiment/tasks.ts
TASKS = [
    ("drink_cup",      "Drinking",           "Pick up the cup and take a drink"),
    ("brush_teeth",    "Brushing Teeth",     "Simulate brushing your teeth"),
    ("comb_hair",      "Combing Hair",       "Comb or brush your hair"),
    ("eat_fork",       "Eating with Fork",   "Simulate eating with a fork"),
    ("eat_spoon",      "Eating with Spoon",  "Simulate eating with a spoon"),
    ("reach_overhead", "Reaching Overhead",  "Reach up as if getting something from a high shelf"),
    ("open_door",      "Opening Door",       "Simulate opening a door"),
    ("button_shirt",   "Buttoning Shirt",    "Simulate buttoning a shirt"),
    ("turn_key",       "Turning Key",        "Simulate turning a key in a lock"),
    ("pour_water",     "Pouring Water",      "Simulate pouring water from a pitcher"),
]

W, H = 960, 540

def resolve_font_file():
    """Ask fontconfig instead of guessing paths.

    ⚠️ Hardcoded DejaVu paths do not exist on this box, and PIL's silent fallback
    is `load_default()` -- a BITMAP face that ignores the size argument entirely.
    The first run produced ten images whose 72pt heading rendered at about 8pt,
    which is unreadable at participant distance and would have shipped looking
    like a broken renderer rather than a placeholder.
    """
    out = subprocess.run(
        ["fc-match", "-f", "%{file}", "sans-serif:bold"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if not out:
        raise SystemExit("no sans-serif font found; refusing to fall back to a bitmap face")
    return out

FONT_FILE = resolve_font_file()

def font(size):
    # No try/except: a failure here must be loud, not silently unreadable.
    return ImageFont.truetype(FONT_FILE, size)

def centered(draw, y, text, f, fill):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=f)
    draw.text(((W - (right - left)) / 2 - left, y), text, font=f, fill=fill)
    return bottom - top

for task_id, name, instruction in TASKS:
    # Diagonal hatching: unmistakably synthetic at a glance, so nobody mistakes
    # this for the real stimulus even in a screenshot of a running session.
    img = Image.new("RGB", (W, H), (24, 28, 38))
    d = ImageDraw.Draw(img)
    for x in range(-H, W + H, 32):
        d.line([(x, 0), (x + H, H)], fill=(32, 38, 52), width=8)
    d.rectangle([12, 12, W - 12, H - 12], outline=(90, 105, 130), width=3)

    centered(d, 92, "PLACEHOLDER", font(40), (250, 196, 110))
    centered(d, 190, name, font(72), (232, 238, 246))
    centered(d, 300, instruction, font(30), (150, 168, 190))
    centered(d, 400, f"({task_id})", font(26), (110, 126, 148))
    centered(d, 462, "not a real stimulus - replace before any study run", font(22), (250, 196, 110))

    img.save(f"placeholder-{task_id}.png")

    # flite's voice is robotic, which is the point: it says the instruction so the
    # timing is realistic, and nobody could mistake it for a finished prompt.
    subprocess.run(
        ["flite", "-t", f"Placeholder. {instruction}", "-o", f"placeholder-{task_id}.wav"],
        check=True,
    )
    print(f"  {task_id}: png + wav")
