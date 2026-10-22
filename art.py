"""Procedural SVG cover art for FL HUB."""
from __future__ import annotations

import html
import random

CATEGORY_LABELS = {
    "music": "MUSIC",
    "project": "PROJECT PACK",
    "instrument": "INSTRUMENT",
    "plugin": "PLUGIN",
    "drumkit": "DRUM KIT",
}

PALETTES = {
    "music": [
        ("#ff7a18", "#7a1fd0", "#ffd6a8"),
        ("#ff4d2e", "#5b0f6e", "#ffc4b0"),
        ("#ff9d2e", "#2b1055", "#ffe3a8"),
        ("#f8366b", "#2a0a4a", "#ffc2d4"),
    ],
    "project": [
        ("#6d5efc", "#131a45", "#c3bcff"),
        ("#8e2de2", "#1c0b3b", "#e0c4ff"),
        ("#2f6bff", "#0c1338", "#b9ccff"),
    ],
    "instrument": [
        ("#11998e", "#062b2a", "#a8ffe9"),
        ("#00b8a9", "#0a1f3d", "#b8f5ff"),
        ("#2bd96b", "#0a2a1b", "#c8ffd8"),
    ],
    "plugin": [
        ("#f7971e", "#3b1505", "#ffe3a3"),
        ("#ffb703", "#231303", "#fff0b8"),
        ("#ff5e00", "#2a0a12", "#ffd0b0"),
    ],
    "drumkit": [
        ("#ff416c", "#2a0714", "#ffc2cf"),
        ("#f953c6", "#230524", "#ffc9f2"),
        ("#ff2d55", "#1a0a12", "#ffc0cb"),
    ],
}


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _wrap_title(title: str, limit: int = 19) -> list[str]:
    words = title.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= limit or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > 2:
        lines = [lines[0], " ".join(lines[1:])]
    return lines


def _motif(category: str, accent: str, rnd: random.Random) -> str:
    parts: list[str] = []
    if category == "music":
        bars = 26
        width = 18
        gap = 6
        total = bars * (width + gap) - gap
        start_x = (640 - total) / 2
        for i in range(bars):
            height = rnd.randint(26, 190)
            x = start_x + i * (width + gap)
            y = 330 - height / 2
            opacity = 0.2 + rnd.random() * 0.55
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{width}" height="{height}" '
                f'rx="9" fill="{accent}" opacity="{opacity:.2f}"/>'
            )
    elif category == "project":
        for i in range(7):
            y = 150 + i * 32
            parts.append(
                f'<line x1="56" y1="{y}" x2="584" y2="{y}" stroke="{accent}" '
                f'stroke-width="1" opacity="0.18"/>'
            )
        for i in range(11):
            x = 90 + rnd.randint(0, 380)
            y = 150 + rnd.randint(0, 6) * 32 - 8
            w = rnd.randint(30, 150)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="16" rx="5" '
                f'fill="{accent}" opacity="{0.25 + rnd.random() * 0.5:.2f}"/>'
            )
        parts.append(
            f'<line x1="452" y1="120" x2="452" y2="390" stroke="#ffffff" '
            f'stroke-width="2" opacity="0.5"/>'
        )
    elif category == "instrument":
        key_w = 46
        start_x = (640 - key_w * 10) / 2
        for i in range(10):
            x = start_x + i * key_w
            parts.append(
                f'<rect x="{x}" y="120" width="{key_w - 3}" height="280" rx="8" '
                f'fill="{accent}" opacity="0.12"/>'
            )
        for i in [0, 1, 3, 4, 5, 7, 8]:
            x = start_x + (i + 1) * key_w - 20
            parts.append(
                f'<rect x="{x}" y="120" width="26" height="170" rx="6" '
                f'fill="#0b0b12" opacity="0.72"/>'
            )
    elif category == "plugin":
        positions = [(190, 255), (320, 225), (450, 255)]
        for idx, (cx, cy) in enumerate(positions):
            r = 58 - idx * 6
            parts.append(
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
                f'stroke="{accent}" stroke-width="10" opacity="0.2"/>'
            )
            end = rnd.randint(-120, 120)
            parts.append(
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{accent}" '
                f'stroke-width="10" stroke-linecap="round" stroke-dasharray="{r * 2.4:.0f} 999" '
                f'transform="rotate({end} {cx} {cy})" opacity="0.85"/>'
            )
            parts.append(
                f'<circle cx="{cx}" cy="{cy}" r="9" fill="{accent}" opacity="0.95"/>'
            )
    else:  # drumkit
        for idx, (cx, cy, r) in enumerate([(320, 250, 150), (320, 250, 105), (320, 250, 60)]):
            parts.append(
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{accent}" '
                f'stroke-width="{3 if idx else 2}" opacity="{0.45 - idx * 0.1:.2f}"/>'
            )
        for i in range(12):
            angle = i * 30
            parts.append(
                f'<circle cx="320" cy="250" r="176" fill="none" stroke="{accent}" '
                f'stroke-width="2" opacity="0.12" stroke-dasharray="4 22" '
                f'transform="rotate({angle} 320 250)"/>'
            )
        parts.append(
            f'<circle cx="320" cy="250" r="22" fill="{accent}" opacity="0.9"/>'
        )
    return "".join(parts)


def generate_cover_svg(title: str, category: str, seed_key: str = "") -> str:
    rnd = random.Random(f"{seed_key}|{title}|{category}")
    palette = PALETTES.get(category, PALETTES["music"])
    bg1, bg2, accent = palette[rnd.randrange(len(palette))]
    title_lines = _wrap_title(title)
    label = CATEGORY_LABELS.get(category, "FL HUB")

    line_markup = ""
    if len(title_lines) == 1:
        line_markup = (
            f'<text x="48" y="556" font-family="Manrope, Arial, sans-serif" '
            f'font-size="42" font-weight="700" fill="#ffffff">{_esc(title_lines[0])}</text>'
        )
    else:
        line_markup = (
            f'<text x="48" y="512" font-family="Manrope, Arial, sans-serif" '
            f'font-size="38" font-weight="700" fill="#ffffff">{_esc(title_lines[0])}</text>'
            f'<text x="48" y="558" font-family="Manrope, Arial, sans-serif" '
            f'font-size="38" font-weight="700" fill="#ffffff">{_esc(title_lines[1])}</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="640" viewBox="0 0 640 640">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{bg1}"/>
    <stop offset="1" stop-color="{bg2}"/>
  </linearGradient>
  <radialGradient id="glow" cx="50%" cy="42%" r="62%">
    <stop offset="0" stop-color="{accent}" stop-opacity="0.34"/>
    <stop offset="1" stop-color="{accent}" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="shade" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#050509" stop-opacity="0"/>
    <stop offset="0.55" stop-color="#050509" stop-opacity="0.45"/>
    <stop offset="1" stop-color="#050509" stop-opacity="0.92"/>
  </linearGradient>
</defs>
<rect width="640" height="640" fill="url(#bg)"/>
<rect width="640" height="640" fill="url(#glow)"/>
<g transform="rotate(-14 320 280)">{_motif(category, accent, rnd)}</g>
<circle cx="{rnd.randint(420, 560)}" cy="{rnd.randint(60, 140)}" r="{rnd.randint(90, 150)}"
        fill="none" stroke="#ffffff" stroke-width="1.5" opacity="0.16"/>
<circle cx="{rnd.randint(60, 160)}" cy="{rnd.randint(420, 520)}" r="{rnd.randint(50, 110)}"
        fill="none" stroke="#ffffff" stroke-width="1.5" opacity="0.1"/>
<rect y="300" width="640" height="340" fill="url(#shade)"/>
<text x="48" y="58" font-family="Manrope, Arial, sans-serif" font-size="16" font-weight="700"
      letter-spacing="5" fill="#ffffff" opacity="0.78">FL HUB</text>
<text x="592" y="58" text-anchor="end" font-family="Manrope, Arial, sans-serif" font-size="12"
      font-weight="600" letter-spacing="3" fill="#ffffff" opacity="0.55">{label}</text>
{line_markup}
<text x="48" y="604" font-family="Manrope, Arial, sans-serif" font-size="12" font-weight="600"
      letter-spacing="4" fill="{accent}" opacity="0.9">FLSTUDIO COMMUNITY</text>
</svg>"""
