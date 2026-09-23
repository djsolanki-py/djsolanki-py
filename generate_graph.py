from datetime import datetime
from html import unescape
from pathlib import Path
import html
import re
import urllib.request
import xml.etree.ElementTree as ET


USERNAME = "djsolanki-py"
CONTRIBUTIONS_URL = f"https://github.com/users/{USERNAME}/contributions"

GRAPH_FILE = Path("contribution-graph.svg")
GRAPH_3D_FILE = Path("contribution-3d.svg")


def fetch_contributions():
    request = urllib.request.Request(
        CONTRIBUTIONS_URL,
        headers={
            "User-Agent": "github-activity-graph-generator/1.0",
            "Accept": "text/html",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        page = response.read().decode("utf-8", errors="replace")

    # GitHub's contribution page contains one element per day with
    # data-date and data-count attributes.
    pattern = re.compile(
        r'data-date="(?P<date>\d{4}-\d{2}-\d{2})"[^>]*'
        r'data-count="(?P<count>\d+)"'
    )

    rows = [
        {"date": m.group("date"), "count": int(m.group("count"))}
        for m in pattern.finditer(page)
    ]

    # Some GitHub HTML versions place data-count before data-date.
    if not rows:
        pattern = re.compile(
            r'data-count="(?P<count>\d+)"[^>]*'
            r'data-date="(?P<date>\d{4}-\d{2}-\d{2})"'
        )
        rows = [
            {"date": m.group("date"), "count": int(m.group("count"))}
            for m in pattern.finditer(page)
        ]

    if not rows:
        raise RuntimeError(
            "Could not read GitHub contribution data. "
            "GitHub may have changed the contribution page HTML."
        )

    rows.sort(key=lambda row: row["date"])
    return rows


def esc(value):
    return html.escape(str(value), quote=True)


def level(count, maximum):
    if count == 0:
        return 0
    if maximum <= 0:
        return 0

    ratio = count / maximum
    if ratio <= 0.25:
        return 1
    if ratio <= 0.50:
        return 2
    if ratio <= 0.75:
        return 3
    return 4


def write_svg(path, content):
    path.write_text(content, encoding="utf-8")


def make_calendar_svg(rows):
    # Keep the most recent 53 weeks, matching the normal GitHub-style view.
    rows = rows[-371:]
    maximum = max(row["count"] for row in rows)

    width = 1100
    cell = 12
    gap = 3
    left = 48
    top = 58
    week_width = cell + gap
    row_height = cell + gap
    height = top + 7 * row_height + 90

    colors = {
        0: "#161b22",
        1: "#0e4429",
        2: "#006d32",
        3: "#26a641",
        4: "#39d353",
    }

    # Align the first day to its weekday.
    first = datetime.strptime(rows[0]["date"], "%Y-%m-%d").date()
    start = first.fromordinal(first.toordinal() - ((first.weekday() + 1) % 7))

    positions = {}
    for row in rows:
        date = datetime.strptime(row["date"], "%Y-%m-%d").date()
        days = (date - start).days
        week = days // 7
        weekday = (days % 7)
        positions[row["date"]] = (week, weekday)

    weeks = max((w for w, _ in positions.values()), default=0) + 1
    width = max(width, left + weeks * week_width + 30)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" rx="12" fill="#0d1117"/>',
        f'<text x="{left}" y="28" fill="#f0f6fc" font-family="Arial, sans-serif" '
        f'font-size="18" font-weight="600">GitHub activity — {esc(USERNAME)}</text>',
        f'<text x="{left}" y="47" fill="#8b949e" font-family="Arial, sans-serif" '
        f'font-size="12">Daily contributions over the last year</text>',
    ]

    day_labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    for i, label in enumerate(day_labels):
        if i % 2 == 1:
            parts.append(
                f'<text x="8" y="{top + i * row_height + 10}" '
                f'fill="#8b949e" font-family="Arial, sans-serif" font-size="10">{label}</text>'
            )

    for row in rows:
        week, weekday = positions[row["date"]]
        x = left + week * week_width
        y = top + weekday * row_height
        color = colors[level(row["count"], maximum)]
        parts.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{color}">'
            f'<title>{esc(row["date"])}: {row["count"]} contributions</title></rect>'
        )

    total = sum(row["count"] for row in rows)
    legend_y = top + 7 * row_height + 22
    parts.append(
        f'<text x="{left}" y="{legend_y}" fill="#8b949e" '
        f'font-family="Arial, sans-serif" font-size="12">{total} contributions shown</text>'
    )

    legend_x = width - 170
    parts.append(
        f'<text x="{legend_x - 34}" y="{legend_y}" fill="#8b949e" '
        f'font-family="Arial, sans-serif" font-size="10">Less</text>'
    )
    for i in range(5):
        x = legend_x + i * 16
        parts.append(
            f'<rect x="{x}" y="{legend_y - 10}" width="12" height="12" rx="2" fill="{colors[i]}"/>'
        )
    parts.append(
        f'<text x="{legend_x + 56}" y="{legend_y}" fill="#8b949e" '
        f'font-family="Arial, sans-serif" font-size="10">More</text>'
    )

    parts.append("</svg>")
    write_svg(GRAPH_FILE, "\n".join(parts))


def make_3d_svg(rows):
    # Use all days from the last year, but only draw non-zero days as bars.
    rows = rows[-371:]
    maximum = max((row["count"] for row in rows), default=1)

    width = 1100
    height = 520
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" rx="12" fill="#0d1117"/>',
        '<text x="45" y="34" fill="#f0f6fc" font-family="Arial, sans-serif" '
        'font-size="18" font-weight="600">3D GitHub activity</text>',
        '<text x="45" y="54" fill="#8b949e" font-family="Arial, sans-serif" '
        'font-size="12">Bar height represents daily contribution count</text>',
    ]

    # Isometric projection.
    ox, oy = 550, 400
    sx, sy = 3.0, 1.55
    zscale = 24 / maximum if maximum else 1
    dx, dy = 5.0, 2.8

    # Draw a light isometric floor grid.
    for i in range(-55, 56, 10):
        x1 = ox + i * sx
        y1 = oy + i * sy
        x2 = ox + i * sx + 55 * sx
        y2 = oy + i * sy - 55 * sy
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            'stroke="#21262d" stroke-width="1"/>'
        )

    # Draw every 7th day as a bar to keep the 3D view readable.
    visible = rows[::7]
    for idx, row in enumerate(visible):
        count = row["count"]
        if count <= 0:
            continue

        col = idx % 53
        row_idx = idx // 53

        x = ox + (col - row_idx) * dx
        y = oy + (col + row_idx) * dy
        h = max(4, count * zscale)

        # Four projected corners.
        p1 = (x, y)
        p2 = (x + dx, y + dy)
        p3 = (x, y + 2 * dy)
        p4 = (x - dx, y + dy)

        top1 = (p1[0], p1[1] - h)
        top2 = (p2[0], p2[1] - h)
        top3 = (p3[0], p3[1] - h)
        top4 = (p4[0], p4[1] - h)

        def pts(values):
            return " ".join(f"{a:.1f},{b:.1f}" for a, b in values)

        parts.append(
            f'<polygon points="{pts([p4, p1, top1, top4])}" fill="#006d32" opacity="0.95"/>'
        )
        parts.append(
            f'<polygon points="{pts([p1, p2, top2, top1])}" fill="#26a641" opacity="0.95"/>'
        )
        parts.append(
            f'<polygon points="{pts([top1, top2, top3, top4])}" fill="#39d353">'
            f'<title>{esc(row["date"])}: {count} contributions</title></polygon>'
        )

    parts.append(
        '<text x="45" y="485" fill="#8b949e" font-family="Arial, sans-serif" '
        'font-size="11">Tip: open the SVG directly to see the daily tooltips.</text>'
    )
    parts.append("</svg>")
    write_svg(GRAPH_3D_FILE, "\n".join(parts))


def main():
    rows = fetch_contributions()
    make_calendar_svg(rows)
    make_3d_svg(rows)
    print(f"Generated {GRAPH_FILE} and {GRAPH_3D_FILE}")
    print(f"Days fetched: {len(rows)}")
    print(f"Total contributions: {sum(row['count'] for row in rows)}")


if __name__ == "__main__":
    main()
