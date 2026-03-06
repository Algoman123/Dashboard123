"""SVG radar/spider chart for P123 ranking composite node scores."""

import math


def get_top_level_indices(
    ids: list[int], parents: list[int], total: int = 0,
) -> list[int]:
    """Return indices of top-level nodes using the parent IDs from the API.

    The API returns ``ids`` and ``parents`` for every composite node.
    Index 0 in our stored data corresponds to the first node *after* the
    root (Overall), whose ``parent`` points to the root id (``ids[0]`` of
    the raw response, which equals 0).  Top-level nodes are those whose
    ``parent`` equals that root id.

    Args:
        ids:     Node IDs (root/Overall already stripped).
        parents: Parent node IDs (root/Overall already stripped).
        total:   Fallback node count when ids/parents are missing (old data).

    Returns:
        List of array indices for top-level composite nodes.
    """
    if not ids or not parents:
        # Old data without hierarchy info — show all nodes as fallback
        return list(range(total))

    # The root id is 0 (the Overall node that was stripped at fetch time).
    root_id = 0
    return [i for i, p in enumerate(parents) if p == root_id]


def generate_radar_svg(
    title: str,
    categories: list[str],
    values: list[float],
    weights: list[int],
    colors: dict,
    size: int = 350,
    chart_id: str = "radar0",
) -> str:
    """Generate an SVG radar chart with radial gradient fill and glow.

    Args:
        title:      Chart title (ranking system name).
        categories: Node names (e.g. ["Value", "Growth", "Momentum"]).
        values:     Scores 0-100 for each category.
        weights:    Weight % for each category.
        colors:     Theme color dict (bg_card, text_muted, text, border, green).
        size:       SVG viewport size in pixels.
        chart_id:   Unique ID prefix for SVG defs (avoid collisions).

    Returns:
        HTML string containing the SVG.
    """
    n = len(categories)
    if n < 3 or len(values) != n:
        return ""

    # --- Layout: add padding around the chart for labels ---
    pad_x = 95      # horizontal padding for label text
    pad_top = 30     # top padding for title
    pad_bot = 25     # bottom padding
    vw = size + 2 * pad_x        # viewBox width
    vh = size + pad_top + pad_bot  # viewBox height
    cx = vw / 2
    cy = pad_top + size / 2
    radius = size * 0.32
    max_val = 100.0
    max_label_len = 20  # truncate long category names

    # Theme colors
    grid_color = f"{colors['border']}44"
    text_color = colors["text_muted"]
    value_color = colors["text"]
    accent = "#636EFA"
    title_color = colors["text"]

    def _fmt_weight(w: float) -> str:
        return f"{w:g}%"

    def _truncate(s: str, limit: int = max_label_len) -> str:
        return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"

    # ---- Grid rings (polygonal, 5 levels) ----
    grid_rings = ""
    for level in (0.2, 0.4, 0.6, 0.8, 1.0):
        r = radius * level
        pts = []
        for i in range(n):
            angle = (2 * math.pi * i / n) - math.pi / 2
            pts.append(f"{cx + r * math.cos(angle):.1f},{cy + r * math.sin(angle):.1f}")
        grid_rings += (
            f'<polygon points="{" ".join(pts)}" '
            f'fill="none" stroke="{grid_color}" stroke-width="1"/>\n'
        )

    # ---- Axis lines ----
    axes = ""
    for i in range(n):
        angle = (2 * math.pi * i / n) - math.pi / 2
        x2 = cx + radius * math.cos(angle)
        y2 = cy + radius * math.sin(angle)
        axes += (
            f'<line x1="{cx:.1f}" y1="{cy:.1f}" '
            f'x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{grid_color}" stroke-width="1"/>\n'
        )

    # ---- Data polygon points ----
    data_pts = []
    for i, v in enumerate(values):
        angle = (2 * math.pi * i / n) - math.pi / 2
        r = (min(v, max_val) / max_val) * radius
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        data_pts.append((x, y))
    poly_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in data_pts)

    # ---- Labels (name + weight on two lines) and score values ----
    labels = ""
    score_labels = ""
    for i, (cat, val, wt) in enumerate(zip(categories, values, weights)):
        angle = (2 * math.pi * i / n) - math.pi / 2
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        # Label position (outside grid)
        label_r = radius + 22
        lx = cx + label_r * cos_a
        ly = cy + label_r * sin_a

        # Text anchor based on position
        if abs(cos_a) < 0.15:
            anchor = "middle"
        elif cos_a > 0:
            anchor = "start"
        else:
            anchor = "end"

        # Vertical nudge for top/bottom
        dy_attr = ""
        if sin_a < -0.7:
            dy_attr = 'dy="-6"'
        elif sin_a > 0.7:
            dy_attr = 'dy="6"'

        short_name = _truncate(cat)
        wt_str = _fmt_weight(wt)
        labels += (
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
            f'dominant-baseline="central" {dy_attr} '
            f'fill="{text_color}" font-size="11" font-family="sans-serif" font-weight="600">'
            f'{short_name}'
            f'<tspan x="{lx:.1f}" dy="13" font-size="10" font-weight="400">'
            f'{wt_str}</tspan></text>\n'
        )

        # Score value near each data point (slightly outward from the point)
        score_r = (min(val, max_val) / max_val) * radius
        nudge = 14
        sx = cx + (score_r + nudge) * cos_a
        sy = cy + (score_r + nudge) * sin_a
        score_labels += (
            f'<text x="{sx:.1f}" y="{sy:.1f}" text-anchor="middle" '
            f'dominant-baseline="central" '
            f'fill="{value_color}" font-size="10" font-family="sans-serif" '
            f'font-weight="700">{val:.0f}</text>\n'
        )

    # ---- Vertex dots ----
    dots = ""
    for x, y in data_pts:
        dots += (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" '
            f'fill="{accent}" stroke="white" stroke-width="1.2"/>\n'
        )

    # ---- Title ----
    title_html = (
        f'<text x="{cx:.1f}" y="{pad_top / 2 + 2:.1f}" text-anchor="middle" '
        f'fill="{title_color}" font-size="13" font-family="sans-serif" '
        f'font-weight="700">{title}</text>\n'
    )

    # ---- Assemble SVG ----
    svg = f"""<svg viewBox="0 0 {vw} {vh}" xmlns="http://www.w3.org/2000/svg"
     width="100%" style="max-width:{vw}px;display:block;margin:0 auto;">
  <defs>
    <radialGradient id="{chart_id}_grad" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.50"/>
      <stop offset="100%" stop-color="{accent}" stop-opacity="0.06"/>
    </radialGradient>
    <filter id="{chart_id}_glow">
      <feGaussianBlur stdDeviation="2.5" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  {title_html}
  {grid_rings}
  {axes}
  <polygon points="{poly_str}"
    fill="url(#{chart_id}_grad)"
    stroke="{accent}" stroke-width="2"
    filter="url(#{chart_id}_glow)"/>
  {dots}
  {labels}
  {score_labels}
</svg>"""
    return svg
