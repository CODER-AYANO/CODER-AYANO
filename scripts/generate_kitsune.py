
#!/usr/bin/env python3
import datetime as dt
import json
import math
import os
import urllib.request
import xml.sax.saxutils as xml

LOGIN = os.environ.get("PROFILE_LOGIN", "CODER-AYANO")
TOKEN = os.environ.get("GH_PROFILE_TOKEN")
OUT = os.environ.get("OUTPUT_SVG", "assets/kitsune-arcade.svg")

if not TOKEN:
    raise SystemExit("Missing GH_PROFILE_TOKEN secret.")

# Fetch the real GitHub contribution calendar.
today = dt.datetime.now(dt.timezone.utc).date()
start = today - dt.timedelta(days=364)

query = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
            contributionLevel
          }
        }
      }
    }
  }
}
"""

payload = {
    "query": query,
    "variables": {
        "login": LOGIN,
        "from": start.isoformat() + "T00:00:00Z",
        "to": today.isoformat() + "T23:59:59Z",
    },
}

request = urllib.request.Request(
    "https://api.github.com/graphql",
    data=json.dumps(payload).encode(),
    headers={
        "Authorization": "Bearer " + TOKEN,
        "Content-Type": "application/json",
        "User-Agent": "kitsune-breakout",
    },
)

with urllib.request.urlopen(request, timeout=30) as response:
    result = json.loads(response.read().decode())

if result.get("errors"):
    raise SystemExit(json.dumps(result["errors"]))

user = result.get("data", {}).get("user")
if not user:
    raise SystemExit(f"GitHub user not found: {LOGIN}")

calendar = user["contributionsCollection"]["contributionCalendar"]
weeks = calendar["weeks"]

# Calendar layout.
CELL = 12
GAP = 4
STEP = CELL + GAP
LEFT = 28
TOP = 58
COLS = len(weeks)
ROWS = 7

WIDTH = LEFT * 2 + COLS * STEP - GAP
GRID_BOTTOM = TOP + ROWS * STEP
PADDLE_Y = GRID_BOTTOM + 15
HEIGHT = GRID_BOTTOM + 66

COLORS = {
    "NONE": "#211c27",
    "FIRST_QUARTILE": "#5b2537",
    "SECOND_QUARTILE": "#923044",
    "THIRD_QUARTILE": "#d49b35",
    "FOURTH_QUARTILE": "#ffe09a",
}

blocks = []

for col, week in enumerate(weeks):
    for day in week["contributionDays"]:
        date = dt.date.fromisoformat(day["date"])
        row = (date.weekday() + 1) % 7  # Sunday first

        bx = LEFT + col * STEP
        by = TOP + row * STEP

        blocks.append({
            "x": bx,
            "y": by,
            "level": day["contributionLevel"],
            "date": day["date"],
            "count": day["contributionCount"],
            "alive": True,
            "hit_time": None,
        })

# Breakout physics.
BALL_R = 3.5
FPS = 30
DURATION = 30.0
FRAME_COUNT = int(FPS * DURATION)

MIN_X = LEFT + BALL_R
MAX_X = LEFT + COLS * STEP - GAP - BALL_R
MIN_Y = TOP + BALL_R
MAX_Y = GRID_BOTTOM + 3

x = LEFT + 30.0
y = GRID_BOTTOM - 4.0
vx = 2.8
vy = -2.4

# Each animation frame stores the ball position.
positions = []
hit_times = []
hit_blocks = set()

dt_step = 1.0 / FPS
substeps = 4

for frame in range(FRAME_COUNT + 1):
    positions.append((x, y))
    current_time = frame * dt_step

    for _ in range(substeps):
        sx = vx / substeps
        sy = vy / substeps

        old_x, old_y = x, y
        x += sx
        y += sy

        # Left and right wall collisions.
        if x < MIN_X:
            x = MIN_X
            vx = abs(vx)
        elif x > MAX_X:
            x = MAX_X
            vx = -abs(vx)

        # Top wall collision.
        if y < MIN_Y:
            y = MIN_Y
            vy = abs(vy)

        # Bottom paddle: centered and fixed, like a classic demo.
        paddle_width = 48
        paddle_center = LEFT + COLS * STEP / 2
        if vy > 0 and y + BALL_R >= PADDLE_Y:
            if abs(x - paddle_center) <= paddle_width / 2 + BALL_R:
                y = PADDLE_Y - BALL_R
                # A slight angle change makes the trajectory less repetitive.
                offset = (x - paddle_center) / (paddle_width / 2)
                vx = max(-4.0, min(4.0, vx + offset * 0.45))
                vy = -abs(vy)
            elif y > HEIGHT - 35:
                # Reset the ball when it misses the paddle.
                x = LEFT + 30.0
                y = GRID_BOTTOM - 4.0
                vx = 2.8 if frame % 2 == 0 else -2.8
                vy = -2.4

        # Circle-vs-cell collision. Remove each block at most once.
        for index, block in enumerate(blocks):
            if index in hit_blocks:
                continue

            bx, by = block["x"], block["y"]
            nearest_x = max(bx, min(x, bx + CELL))
            nearest_y = max(by, min(y, by + CELL))

            dx = x - nearest_x
            dy = y - nearest_y

            if dx * dx + dy * dy <= BALL_R * BALL_R:
                hit_blocks.add(index)
                block["hit_time"] = current_time
                hit_times.append(current_time)

                # Reflect using the axis of greatest penetration.
                if abs(dx) > abs(dy):
                    vx = -vx
                else:
                    vy = -vy

                # Move the ball away from the block to prevent repeated overlap.
                x = old_x
                y = old_y
                break

# Generate contribution cells and fade hit cells.
rect_markup = []

for block in blocks:
    color = COLORS.get(block["level"], COLORS["NONE"])
    title = xml.escape(
        f'{block["date"]}: {block["count"]} contributions'
    )

    animation = ""
    if block["hit_time"] is not None:
        animation = (
            f'<animate attributeName="opacity" '
            f'begin="{block["hit_time"]:.3f}s" '
            f'dur="0.15s" values="1;0.08" fill="freeze"/>'
        )

    rect_markup.append(
        f'<g><rect x="{block["x"]}" y="{block["y"]}" '
        f'width="{CELL}" height="{CELL}" rx="3" '
        f'fill="{color}" stroke="#f6d58a" '
        f'stroke-opacity=".12">'
        f'<title>{title}</title></rect>{animation}</g>'
    )

# SMIL keyframes drive the ball in two dimensions.
key_times = ";".join(
    f"{i / FRAME_COUNT:.6f}"
    for i in range(FRAME_COUNT + 1)
)

xs = ";".join(f"{p[0]:.2f}" for p in positions)
ys = ";".join(f"{p[1]:.2f}" for p in positions)

safe_login = xml.escape(LOGIN)

svg = f"""<svg xmlns="http://www.w3.org/2000/svg"
 width="{WIDTH}" height="{HEIGHT}"
 viewBox="0 0 {WIDTH} {HEIGHT}">
<title>Kitsune Breakout — {safe_login}</title>
<desc>Japanese-inspired contribution calendar with a simulated
Breakout ball, bouncing walls, block hits, and a paddle.</desc>
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop stop-color="#100e16"/>
    <stop offset="1" stop-color="#24101b"/>
  </linearGradient>
  <linearGradient id="ball">
    <stop stop-color="#ff405b"/>
    <stop offset=".55" stop-color="#ffbd59"/>
    <stop offset="1" stop-color="#fff0b5"/>
  </linearGradient>
  <filter id="glow" x="-100%" y="-100%" width="300%" height="300%">
    <feGaussianBlur stdDeviation="2" result="blur"/>
    <feMerge>
      <feMergeNode in="blur"/>
      <feMergeNode in="SourceGraphic"/>
    </feMerge>
  </filter>
</defs>

<rect width="100%" height="100%" rx="16"
 fill="url(#bg)" stroke="#a65a43" stroke-opacity=".6"/>

<text x="24" y="29" fill="#ffe5ad"
 font-family="monospace" font-size="16" font-weight="bold">
狐 KITSUNE BREAKOUT</text>
<text x="{WIDTH-24}" y="29" text-anchor="end"
 fill="#e4a6a6" font-family="monospace" font-size="10">
{safe_login}</text>
<path d="M20 40 H{WIDTH-20}"
 stroke="#a65a43" stroke-opacity=".5"/>

{''.join(rect_markup)}

<!-- Static paddle. SVG on GitHub cannot receive keyboard/mouse input. -->
<rect x="{LEFT + COLS*STEP/2 - 24:.1f}"
 y="{PADDLE_Y:.1f}" width="48" height="4" rx="2"
 fill="#d49b35" filter="url(#glow)"/>

<g filter="url(#glow)">
  <circle r="{BALL_R}" fill="url(#ball)"
   stroke="#fff0b5" stroke-width="1">
    <animate attributeName="cx" values="{xs}"
     keyTimes="{key_times}" dur="{DURATION}s"
     repeatCount="indefinite" calcMode="linear"/>
    <animate attributeName="cy" values="{ys}"
     keyTimes="{key_times}" dur="{DURATION}s"
     repeatCount="indefinite" calcMode="linear"/>
  </circle>
  <circle r="7.5" fill="none" stroke="#ff5269"
   stroke-width="1.2" opacity=".65">
    <animate attributeName="cx" values="{xs}"
     keyTimes="{key_times}" dur="{DURATION}s"
     repeatCount="indefinite" calcMode="linear"/>
    <animate attributeName="cy" values="{ys}"
     keyTimes="{key_times}" dur="{DURATION}s"
     repeatCount="indefinite" calcMode="linear"/>
  </circle>
</g>

<text x="24" y="{HEIGHT-18}" fill="#ffe5ad"
 font-family="monospace" font-size="11">
{calendar["totalContributions"]} contributions · Breakout simulation</text>
<text x="{WIDTH-24}" y="{HEIGHT-18}" text-anchor="end"
 fill="#c17b86" font-family="monospace" font-size="10">
赤 • 金 • 狐</text>
</svg>
"""

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
with open(OUT, "w", encoding="utf-8") as file:
    file.write(svg)

print(
    f"Generated {OUT}: {len(blocks)} cells, "
    f"{len(hit_blocks)} simulated block hits."
)
