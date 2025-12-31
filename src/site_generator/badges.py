"""SVG badge generation for provider compliance status.

Generates shields.io-style static SVG badges showing:
- Individual provider compliance status
- Overall compliance summary
"""

import html
import os
from pathlib import Path


# Badge colors following shields.io conventions
BADGE_COLORS = {
    "pass": "#4c1",      # Green
    "fail": "#e05d44",   # Red
    "error": "#e05d44",  # Red (same as fail - errors are serious)
}

# Status labels for badges
STATUS_LABELS = {
    "pass": "Compliant",
    "fail": "Non-Compliant",
    "error": "Error",
}


def generate_badge(provider_name: str, status: str) -> str:
    """Generate an SVG badge for a provider.

    Args:
        provider_name: Display name of the provider
        status: One of 'pass', 'fail', 'error'

    Returns:
        SVG string for the badge
    """
    # Escape HTML special characters
    safe_name = html.escape(provider_name)

    color = BADGE_COLORS.get(status, BADGE_COLORS["error"])
    label = STATUS_LABELS.get(status, "Unknown")

    # Calculate widths based on text length (approximate)
    name_width = len(provider_name) * 7 + 10
    label_width = len(label) * 7 + 10
    total_width = name_width + label_width

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20">
  <linearGradient id="b" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="a">
    <rect width="{total_width}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#a)">
    <path fill="#555" d="M0 0h{name_width}v20H0z"/>
    <path fill="{color}" d="M{name_width} 0h{label_width}v20H{name_width}z"/>
    <path fill="url(#b)" d="M0 0h{total_width}v20H0z"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="{name_width / 2}" y="15" fill="#010101" fill-opacity=".3">{safe_name}</text>
    <text x="{name_width / 2}" y="14">{safe_name}</text>
    <text x="{name_width + label_width / 2}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{name_width + label_width / 2}" y="14">{label}</text>
  </g>
</svg>'''


def generate_overall_badge(results: dict[str, dict]) -> str:
    """Generate an overall summary badge.

    Args:
        results: Dict of provider_key -> {"status": "pass"|"fail"|"error", ...}

    Returns:
        SVG string for the overall badge
    """
    total = len(results)
    passed = sum(1 for r in results.values() if r.get("status") == "pass")
    has_fail = any(r.get("status") == "fail" for r in results.values())
    has_error = any(r.get("status") == "error" for r in results.values())

    # Determine color
    if has_fail:
        color = BADGE_COLORS["fail"]
    elif has_error:
        color = BADGE_COLORS["error"]
    else:
        color = BADGE_COLORS["pass"]

    name = "S3 Enforcement"
    label = f"{passed}/{total} Passing"

    name_width = len(name) * 7 + 10
    label_width = len(label) * 7 + 10
    total_width = name_width + label_width

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20">
  <linearGradient id="b" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="a">
    <rect width="{total_width}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#a)">
    <path fill="#555" d="M0 0h{name_width}v20H0z"/>
    <path fill="{color}" d="M{name_width} 0h{label_width}v20H{name_width}z"/>
    <path fill="url(#b)" d="M0 0h{total_width}v20H0z"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="{name_width / 2}" y="15" fill="#010101" fill-opacity=".3">{name}</text>
    <text x="{name_width / 2}" y="14">{name}</text>
    <text x="{name_width + label_width / 2}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{name_width + label_width / 2}" y="14">{label}</text>
  </g>
</svg>'''


def write_badges(results: dict[str, dict], output_dir: str) -> None:
    """Write badge SVG files for all providers.

    Args:
        results: Dict of provider_key -> {"name": str, "status": str, ...}
        output_dir: Directory to write badge files
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Write individual provider badges
    for provider_key, provider_data in results.items():
        name = provider_data.get("name", provider_key)
        status = provider_data.get("status", "error")

        svg = generate_badge(name, status)
        badge_path = os.path.join(output_dir, f"{provider_key}.svg")

        with open(badge_path, "w", encoding="utf-8") as f:
            f.write(svg)

    # Write overall badge
    overall_svg = generate_overall_badge(results)
    overall_path = os.path.join(output_dir, "overall.svg")

    with open(overall_path, "w", encoding="utf-8") as f:
        f.write(overall_svg)
