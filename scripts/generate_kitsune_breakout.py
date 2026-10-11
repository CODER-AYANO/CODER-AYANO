#!/usr/bin/env python3
import datetime as dt
import json
import math
import os
import urllib.request
import xml.sax.saxutils as xml

# Configuration constants (adapted from TypeScript version)
PADDING = 15
PADDLE_WIDTH = 75
PADDLE_HEIGHT = 10
PADDLE_RADIUS = 5
PADDLE_BRICK_GAP = 100
BALL_RADIUS = 8
BRICK_SIZE = 12
BRICK_GAP = 3
BRICK_RADIUS = 3
ANIMATE_STEP = 1
SECONDS_PER_FRAME = 1 / 30
MAX_FRAMES = 30000
BALL_SPEED = 10

login = os.environ.get("PROFILE_LOGIN", "CODER-AYANO")
token = os.environ.get("GH_PROFILE_TOKEN")
out = os.environ.get("OUTPUT_SVG", "assets/kitsune-arcade.svg")
enable_ghost_bricks = os.environ.get("ENABLE_GHOST_BRICKS", "true").lower() == "true"

if not token:
    raise SystemExit("Missing GH_PROFILE_TOKEN secret.")

today = dt.datetime.now(dt.timezone.utc).date()
start = today - dt.timedelta(days=364)

query = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
 user(login: $login) {
  contributionsCollection(from: $from, to: $to) {
   contributionCalendar {
    totalContributions
    weeks { contributionDays { date contributionCount contributionLevel } }
   }
  }
 }
}
"""

payload = {"query": query, "variables": {
    "login": login,
    "from": start.isoformat() + "T00:00:00Z",
    "to": today.isoformat() + "T23:59:59Z"
}}

req = urllib.request.Request("https://api.github.com/graphql",
    data=json.dumps(payload).encode(),
    headers={"Authorization": "Bearer " + token,
             "Content-Type": "application/json",
             "User-Agent": "kitsune-contribution-arcade"})

with urllib.request.urlopen(req, timeout=30) as response:
    result = json.loads(response.read().decode())

if result.get("errors"):
    raise SystemExit(json.dumps(result["errors"]))

user = result.get("data", {}).get("user")
if not user:
    raise SystemExit("GitHub user not found: " + login)

cal = user["contributionsCollection"]["contributionCalendar"]
weeks = cal["weeks"]

# Kitsune color palette (keeping your original theme)
colors = {
    "NONE": "#211c27",
    "FIRST_QUARTILE": "#5b2537",
    "SECOND_QUARTILE": "#923044",
    "THIRD_QUARTILE": "#d49b35",
    "FOURTH_QUARTILE": "#ffe09a"
}

# Build bricks from contribution data
bricks = []
for col_idx, week in enumerate(weeks):
    for day in week["contributionDays"]:
        weekday = dt.date.fromisoformat(day["date"]).weekday()
        row_idx = (weekday + 1) % 7
        brick_x = col_idx * (BRICK_SIZE + BRICK_GAP) + PADDING
        brick_y = row_idx * (BRICK_SIZE + BRICK_GAP) + PADDING
        color = colors.get(day["contributionLevel"], colors["NONE"])
        has_commit = day["contributionCount"] > 0
        title = xml.escape(day["date"] + ": " + str(day["contributionCount"]) + " contributions")
        bricks.append({
            "x": brick_x,
            "y": brick_y,
            "color": color,
            "status": "visible",
            "has_commit": has_commit,
            "title": title
        })

# Calculate canvas dimensions
brick_column_count = len(weeks)
canvas_width = brick_column_count * (BRICK_SIZE + BRICK_GAP) + PADDING * 2 - BRICK_GAP
bricks_total_height = 7 * (BRICK_SIZE + BRICK_GAP) - BRICK_GAP
paddle_y = PADDING + bricks_total_height + PADDLE_BRICK_GAP
canvas_height = paddle_y + PADDLE_HEIGHT + PADDING + 50  # Extra space for text

def circle_rect_collision(circle_x, circle_y, circle_radius, rect_x, rect_y, rect_width, rect_height):
    """Check if circle and rectangle are colliding."""
    closest_x = max(rect_x, min(circle_x, rect_x + rect_width))
    closest_y = max(rect_y, min(circle_y, rect_y + rect_height))
    dx = circle_x - closest_x
    dy = circle_y - closest_y
    return dx * dx + dy * dy <= circle_radius * circle_radius

def simulate_game(bricks, canvas_width, canvas_height, paddle_y, enable_ghost_bricks):
    """Simulate the breakout game physics."""
    # Initialize ball at center bottom
    ball_x = canvas_width / 2
    ball_y = canvas_height - 80

    # Launch angle (45 degrees upward)
    launch_angle = -math.pi / 4
    ball_velocity_x = BALL_SPEED * math.cos(launch_angle)
    ball_velocity_y = BALL_SPEED * math.sin(launch_angle)

    # Copy bricks for simulation
    simulated_bricks = [b.copy() for b in bricks]

    frame_history = []
    current_frame = 0
    paddle_x = (canvas_width - PADDLE_WIDTH) / 2

    # Main simulation loop
    while current_frame < MAX_FRAMES:
        # Check if game is complete
        remaining = any(
            b["status"] == "visible" and (not enable_ghost_bricks or b["has_commit"])
            for b in simulated_bricks
        )
        if not remaining:
            break

        # Paddle follows ball
        paddle_x = max(
            PADDING,
            min(canvas_width - PADDING - PADDLE_WIDTH, ball_x - PADDLE_WIDTH / 2)
        )

        # Update ball position
        ball_x += ball_velocity_x
        ball_y += ball_velocity_y

        # Wall collisions (left/right)
        if ball_x + ball_velocity_x > canvas_width - PADDING - BALL_RADIUS or \
           ball_x + ball_velocity_x < PADDING + BALL_RADIUS:
            ball_velocity_x = -ball_velocity_x

        # Wall collision (top)
        if ball_y + ball_velocity_y < PADDING + BALL_RADIUS:
            ball_velocity_y = -ball_velocity_y

        # Paddle collision
        ball_next_bottom = ball_y + ball_velocity_y + BALL_RADIUS
        if ball_velocity_y > 0 and ball_next_bottom >= paddle_y and ball_y + BALL_RADIUS <= paddle_y:
            ball_velocity_y = -abs(ball_velocity_y)
            ball_y = paddle_y - BALL_RADIUS

        # Brick collisions
        for brick in simulated_bricks:
            if brick["status"] == "visible" and \
               (not enable_ghost_bricks or brick["has_commit"]) and \
               circle_rect_collision(ball_x, ball_y, BALL_RADIUS,
                                   brick["x"], brick["y"], BRICK_SIZE, BRICK_SIZE):
                ball_velocity_y = -ball_velocity_y
                brick["status"] = "hidden"
                break

        # Clamp ball within bounds
        ball_x = max(PADDING + BALL_RADIUS, min(canvas_width - PADDING - BALL_RADIUS, ball_x))
        ball_y = max(PADDING + BALL_RADIUS, min(canvas_height - PADDING - BALL_RADIUS, ball_y))

        # Store frame state
        if current_frame % ANIMATE_STEP == 0:
            frame_history.append({
                "ball_x": ball_x,
                "ball_y": ball_y,
                "paddle_x": paddle_x,
                "bricks": [b["status"] for b in simulated_bricks]
            })

        current_frame += 1

    return frame_history

# Run simulation
states = simulate_game(bricks, canvas_width, canvas_height, paddle_y, enable_ghost_bricks)
animation_duration = len(states) * SECONDS_PER_FRAME * ANIMATE_STEP

# Extract animation values
ball_x_values = ";".join(str(int(s["ball_x"])) for s in states)
ball_y_values = ";".join(str(int(s["ball_y"])) for s in states)
paddle_x_values = ";".join(str(int(s["paddle_x"])) for s in states)

# Calculate brick animations
brick_anim_data = []
for i, brick in enumerate(bricks):
    first_hidden = -1
    for f_idx, state in enumerate(states):
        if state["bricks"][i] != "visible":
            first_hidden = f_idx
            break

    if first_hidden == -1:
        brick_anim_data.append({"animate": False})
    else:
        t = first_hidden / (len(states) - 1) if len(states) > 1 else 0
        key_times = f"0;{t:.4f};{t:.4f};1"
        if enable_ghost_bricks:
            # Animate to NONE color
            brick_anim_data.append({
                "animate": True,
                "key_times": key_times,
                "from_color": brick["color"],
                "to_color": colors["NONE"]
            })
        else:
            # Fade out
            brick_anim_data.append({
                "animate": True,
                "key_times": key_times,
                "opacity_values": "1;1;0;0"
            })

safe_login = xml.escape(login)

# Build SVG with kitsune theme
svg_parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{canvas_width}" height="{canvas_height}" viewBox="0 0 {canvas_width} {canvas_height}">
<title>Kitsune Contribution Arcade — {safe_login}</title>
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#100e16"/><stop offset="1" stop-color="#24101b"/></linearGradient>
<linearGradient id="fox"><stop stop-color="#ff405b"/><stop offset=".55" stop-color="#ffbd59"/><stop offset="1" stop-color="#fff0b5"/></linearGradient>
<linearGradient id="paddle-grad"><stop stop-color="#ff5269"/><stop offset="1" stop-color="#ffbd59"/></linearGradient>
<filter id="glow"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<rect width="100%" height="100%" rx="16" fill="url(#bg)" stroke="#a65a43" stroke-opacity=".6"/>
<text x="24" y="29" fill="#ffe5ad" font-family="monospace" font-size="16" font-weight="bold">狐 KITSUNE BREAKOUT</text>
<text x="{canvas_width-24}" y="29" text-anchor="end" fill="#e4a6a6" font-family="monospace" font-size="10">{safe_login}</text>
<path d="M20 40 H{canvas_width-20}" stroke="#a65a43" stroke-opacity=".5"/>
''']

# Add bricks
for i, brick in enumerate(bricks):
    anim = brick_anim_data[i]
    if anim["animate"]:
        if enable_ghost_bricks:
            # Animate fill color
            svg_parts.append(f'''<rect x="{brick["x"]}" y="{brick["y"]}" width="{BRICK_SIZE}" height="{BRICK_SIZE}" rx="{BRICK_RADIUS}" fill="{brick["color"]}">
<title>{brick["title"]}</title>
<animate attributeName="fill" values="{anim["from_color"]};{anim["from_color"]};{anim["to_color"]};{anim["to_color"]}" keyTimes="{anim["key_times"]}" dur="{animation_duration:.1f}s" fill="freeze" repeatCount="indefinite"/>
</rect>''')
        else:
            # Fade out
            svg_parts.append(f'''<rect x="{brick["x"]}" y="{brick["y"]}" width="{BRICK_SIZE}" height="{BRICK_SIZE}" rx="{BRICK_RADIUS}" fill="{brick["color"]}">
<title>{brick["title"]}</title>
<animate attributeName="opacity" values="{anim["opacity_values"]}" keyTimes="{anim["key_times"]}" dur="{animation_duration:.1f}s" fill="freeze" repeatCount="indefinite"/>
</rect>''')
    else:
        svg_parts.append(f'''<rect x="{brick["x"]}" y="{brick["y"]}" width="{BRICK_SIZE}" height="{BRICK_SIZE}" rx="{BRICK_RADIUS}" fill="{brick["color"]}"><title>{brick["title"]}</title></rect>''')

# Add paddle with kitsune gradient
svg_parts.append(f'''<g filter="url(#glow)">
<rect y="{paddle_y}" width="{PADDLE_WIDTH}" height="{PADDLE_HEIGHT}" rx="{PADDLE_RADIUS}" fill="url(#paddle-grad)" stroke="#fff0b5" stroke-width="1">
<animate attributeName="x" values="{paddle_x_values}" dur="{animation_duration:.1f}s" repeatCount="indefinite"/>
</rect>
</g>''')

# Add ball with kitsune glow effect
svg_parts.append(f'''<g filter="url(#glow)">
<circle r="{BALL_RADIUS}" fill="url(#fox)" stroke="#fff0b5" stroke-width="1.5">
<animate attributeName="cx" values="{ball_x_values}" dur="{animation_duration:.1f}s" repeatCount="indefinite"/>
<animate attributeName="cy" values="{ball_y_values}" dur="{animation_duration:.1f}s" repeatCount="indefinite"/>
</circle>
<circle r="{BALL_RADIUS * 1.5}" fill="none" stroke="#ff5269" stroke-width="1.5" opacity=".4">
<animate attributeName="cx" values="{ball_x_values}" dur="{animation_duration:.1f}s" repeatCount="indefinite"/>
<animate attributeName="cy" values="{ball_y_values}" dur="{animation_duration:.1f}s" repeatCount="indefinite"/>
</circle>
</g>''')

# Footer text
svg_parts.append(f'''<text x="24" y="{canvas_height-18}" fill="#ffe5ad" font-family="monospace" font-size="11">{cal["totalContributions"]} contributions in the last year</text>
<text x="{canvas_width-24}" y="{canvas_height-18}" text-anchor="end" fill="#c17b86" font-family="monospace" font-size="10">赤 • 金 • 狐</text>
</svg>''')

svg = ''.join(svg_parts)

os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    f.write(svg)

print("Generated", out, "for", login)
print(f"Animation: {animation_duration:.1f}s, {len(states)} frames")
