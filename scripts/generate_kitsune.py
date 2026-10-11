#!/usr/bin/env python3
import datetime as dt
import json
import os
import urllib.request
import xml.sax.saxutils as xml

login = os.environ.get("PROFILE_LOGIN", "CODER-AYANO")
token = os.environ.get("GH_PROFILE_TOKEN")
out = os.environ.get("OUTPUT_SVG", "assets/kitsune-arcade.svg")
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
cell, gap, step, left, top = 12, 4, 16, 28, 58
width = left * 2 + len(weeks) * step - gap
height = top + 7 * step + 44
colors = {"NONE":"#211c27", "FIRST_QUARTILE":"#5b2537",
          "SECOND_QUARTILE":"#923044", "THIRD_QUARTILE":"#d49b35",
          "FOURTH_QUARTILE":"#ffe09a"}
rects, points = [], []
for x, week in enumerate(weeks):
    for day in week["contributionDays"]:
        weekday = dt.date.fromisoformat(day["date"]).weekday()
        y = (weekday + 1) % 7
        px, py = left + x * step, top + y * step
        title = xml.escape(day["date"] + ": " + str(day["contributionCount"]) + " contributions")
        rects.append(f'<rect x="{px}" y="{py}" width="{cell}" height="{cell}" rx="3" fill="{colors.get(day["contributionLevel"], colors["NONE"])}"><title>{title}</title></rect>')
        points.append((px + cell/2, py + cell/2))
path = " ".join(("M" if i == 0 else "L") + f" {x:.1f} {y:.1f}" for i, (x,y) in enumerate(points))
duration = max(18, min(38, len(points) * 0.075))
safe_login = xml.escape(login)
svg = f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<title>Kitsune Contribution Arcade — {safe_login}</title>
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#100e16"/><stop offset="1" stop-color="#24101b"/></linearGradient>
<linearGradient id="fox"><stop stop-color="#ff405b"/><stop offset=".55" stop-color="#ffbd59"/><stop offset="1" stop-color="#fff0b5"/></linearGradient>
<filter id="glow"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<path id="trail" d="{path}"/>
</defs>
<rect width="100%" height="100%" rx="16" fill="url(#bg)" stroke="#a65a43" stroke-opacity=".6"/>
<text x="24" y="29" fill="#ffe5ad" font-family="monospace" font-size="16" font-weight="bold">狐 KITSUNE ARCADE</text>
<text x="{width-24}" y="29" text-anchor="end" fill="#e4a6a6" font-family="monospace" font-size="10">{safe_login}</text>
<path d="M20 40 H{width-20}" stroke="#a65a43" stroke-opacity=".5"/>
{''.join(rects)}
<g filter="url(#glow)">
<circle r="5.5" fill="url(#fox)" stroke="#fff0b5">
<animateMotion dur="{duration:.1f}s" repeatCount="indefinite"><mpath xlink:href="#trail"/></animateMotion>
</circle>
<circle r="10" fill="none" stroke="#ff5269" stroke-width="1.5" opacity=".65">
<animateMotion dur="{duration:.1f}s" repeatCount="indefinite"><mpath xlink:href="#trail"/></animateMotion>
</circle>
</g>
<text x="24" y="{height-18}" fill="#ffe5ad" font-family="monospace" font-size="11">{cal["totalContributions"]} contributions in the last year</text>
<text x="{width-24}" y="{height-18}" text-anchor="end" fill="#c17b86" font-family="monospace" font-size="10">赤 • 金 • 狐</text>
</svg>"""
os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    f.write(svg)
print("Generated", out, "for", login)
