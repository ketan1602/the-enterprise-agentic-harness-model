"""SVG chart generators using the dark-theme colour palette."""
from __future__ import annotations

# Palette hex values (CSS variables not available in SVG)
BG = "#0f1117"
SURFACE = "#1a1d27"
BORDER = "#2a2d3a"
TEXT = "#e2e8f0"
MUTED = "#6b7280"
ACCENT = "#6366f1"
SUCCESS = "#22c55e"
WARNING = "#f59e0b"
ERROR = "#ef4444"


def horizontal_bar_chart(
    categories: list[str],
    values: list[float],
    max_value: float,
    title: str,
    color: str = ACCENT,
    width: int = 480,
    height: int = 240,
) -> str:
    """Horizontal bar chart. Category labels left, value labels right."""
    pad_left, pad_right, pad_top, pad_bottom = 160, 60, 40, 20
    chart_w = width - pad_left - pad_right
    n = len(categories)
    row_h = (height - pad_top - pad_bottom) / max(n, 1)
    bar_h = row_h * 0.55

    rows = []
    for i, (cat, val) in enumerate(zip(categories, values)):
        y = pad_top + i * row_h + (row_h - bar_h) / 2
        bar_w = chart_w * min(val / max_value, 1.0) if max_value > 0 else 0
        rows.append(
            f'<text x="{pad_left - 8}" y="{y + bar_h / 2 + 5}" '
            f'text-anchor="end" fill="{TEXT}" font-size="12">{cat}</text>'
            f'<rect x="{pad_left}" y="{y}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
            f'rx="3" fill="{color}" opacity="0.85"/>'
            f'<text x="{pad_left + bar_w + 6}" y="{y + bar_h / 2 + 5}" '
            f'fill="{MUTED}" font-size="11">{val:.0f}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" rx="6" fill="{SURFACE}"/>'
        f'<text x="{width // 2}" y="24" text-anchor="middle" fill="{TEXT}" '
        f'font-size="13" font-weight="600">{title}</text>'
        + "".join(rows)
        + "</svg>"
    )


def progress_bar(
    value: float,
    label: str,
    color: str = SUCCESS,
    width: int = 400,
    height: int = 48,
) -> str:
    """Single progress bar. value is 0.0-1.0."""
    clamped = max(0.0, min(1.0, value))
    pad_x, pad_y = 12, 8
    bar_y = pad_y + 18
    bar_h = height - bar_y - pad_y
    bar_w = width - pad_x * 2
    fill_w = bar_w * clamped
    pct = f"{clamped * 100:.0f}%"

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" rx="6" fill="{SURFACE}"/>'
        f'<text x="{pad_x}" y="{pad_y + 12}" fill="{TEXT}" font-size="12">{label}</text>'
        f'<text x="{width - pad_x}" y="{pad_y + 12}" text-anchor="end" '
        f'fill="{color}" font-size="12" font-weight="600">{pct}</text>'
        f'<rect x="{pad_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" '
        f'rx="3" fill="{BORDER}"/>'
        f'<rect x="{pad_x}" y="{bar_y}" width="{fill_w:.1f}" height="{bar_h}" '
        f'rx="3" fill="{color}" opacity="0.9"/>'
        "</svg>"
    )


def stat_card(
    value: str,
    label: str,
    sublabel: str = "",
    color: str = ACCENT,
    width: int = 200,
    height: int = 120,
) -> str:
    """Stat card with large value, label, and optional sublabel."""
    sub_line = (
        f'<text x="{width // 2}" y="{height - 14}" text-anchor="middle" '
        f'fill="{MUTED}" font-size="10">{sublabel}</text>'
        if sublabel
        else ""
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" rx="6" fill="{SURFACE}" '
        f'stroke="{BORDER}" stroke-width="1"/>'
        f'<text x="{width // 2}" y="{height // 2 - 4}" text-anchor="middle" '
        f'fill="{color}" font-size="28" font-weight="700">{value}</text>'
        f'<text x="{width // 2}" y="{height // 2 + 20}" text-anchor="middle" '
        f'fill="{TEXT}" font-size="12">{label}</text>'
        + sub_line
        + "</svg>"
    )


def two_stat_comparison(
    left_value: str,
    left_label: str,
    right_value: str,
    right_label: str,
    width: int = 480,
    height: int = 120,
) -> str:
    """Side-by-side stat comparison card: left (before) vs right (after)."""
    mid = width // 2
    pad_y = 20
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" rx="6" fill="{SURFACE}" '
        f'stroke="{BORDER}" stroke-width="1"/>'
        f'<line x1="{mid}" y1="12" x2="{mid}" y2="{height - 12}" '
        f'stroke="{BORDER}" stroke-width="1"/>'
        f'<text x="{mid // 2}" y="{pad_y + 8}" text-anchor="middle" '
        f'fill="{MUTED}" font-size="11">{left_label}</text>'
        f'<text x="{mid // 2}" y="{height // 2 + 14}" text-anchor="middle" '
        f'fill="{ERROR}" font-size="32" font-weight="700">{left_value}</text>'
        f'<text x="{mid + mid // 2}" y="{pad_y + 8}" text-anchor="middle" '
        f'fill="{MUTED}" font-size="11">{right_label}</text>'
        f'<text x="{mid + mid // 2}" y="{height // 2 + 14}" text-anchor="middle" '
        f'fill="{SUCCESS}" font-size="32" font-weight="700">{right_value}</text>'
        "</svg>"
    )
