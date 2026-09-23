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

    # Current GitHub contribution HTML stores:
    # - the date and activity level on each contribution <td>
    # - the exact contribution count in a matching <tool-tip>
    #
    # Older versions of this script expected a data-count attribute
    # directly on the <td>. GitHub no longer exposes it that way.

    tooltip_counts = {}

    tooltip_pattern = re.compile(
        r'<tool-tip\b[^>]*\bfor="(?P<id>[^"]+)"[^>]*>'
        r'(?P<text>.*?)'
        r'</tool-tip>',
        re.IGNORECASE | re.DOTALL,
    )

    for match in tooltip_pattern.finditer(page):
        tooltip_text = re.sub(r"<[^>]+>", " ", match.group("text"))
        tooltip_text = unescape(tooltip_text)
        count_match = re.search(
            r"(?P<count>[\d,]+)\s+contributions?",
            tooltip_text,
            re.IGNORECASE,
        )
        tooltip_counts[match.group("id")] = (
            int(count_match.group("count").replace(",", ""))
            if count_match
            else 0
        )

    rows = []

    # Read each contribution day cell.
    cell_pattern = re.compile(r"<td\b[^>]*>", re.IGNORECASE)

    for cell in cell_pattern.finditer(page):
        tag = cell.group(0)

        date_match = re.search(
            r'\bdata-date="(?P<date>\d{4}-\d{2}-\d{2})"',
            tag,
            re.IGNORECASE,
        )
        id_match = re.search(
            r'\bid="(?P<id>contribution-day-component-[^"]+)"',
            tag,
            re.IGNORECASE,
        )

        if not date_match or not id_match:
            continue

        cell_id = id_match.group("id")
        count = tooltip_counts.get(cell_id, 0)

        rows.append(
            {
                "date": date_match.group("date"),
                "count": count,
            }
        )

    # Remove accidental duplicates while keeping the latest value.
    unique = {}
    for row in rows:
        unique[row["date"]] = row

    rows = sorted(unique.values(), key=lambda row: row["date"])

    if not rows:
        raise RuntimeError(
            "Could not read GitHub contribution data. "
            "GitHub may have changed the contribution page HTML."
        )

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
    # Draw every day as a small isometric bar.
    # The calendar is arranged as 53 weeks x 7 days.
    rows = rows[-371:]
    maximum = max((row["count"] for row in rows), default=1)

    width = 1100
    height = 620
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" rx="12" fill="#0d1117"/>',
        '<text x="45" y="34" fill="#f0f6fc" font-family="Arial, sans-serif" '
        'font-size="18" font-weight="600">3D GitHub activity</text>',
        '<text x="45" y="54" fill="#8b949e" font-family="Arial, sans-serif" '
        'font-size="12">Bar height represents daily contribution count</text>',
    ]

    # Isometric calendar projection.
    origin_x = 545
    origin_y = 480
    x_step = 6.2
    y_step = 8.0
    height_scale = 55 / maximum if maximum else 1

    # Light floor/grid lines.
    for week in range(54):
        x1 = origin_x + week * x_step
        y1 = origin_y + week * y_step
        x2 = x1 - 7 * y_step
        y2 = y1 + 7 * x_step
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            'stroke="#21262d" stroke-width="1"/>'
        )

    for day in range(8):
        x1 = origin_x - day * y_step
        y1 = origin_y + day * x_step
        x2 = x1 + 53 * x_step
        y2 = y1 + 53 * y_step
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            'stroke="#21262d" stroke-width="1"/>'
        )

    # One bar per day. Zero-contribution days are skipped, but every
    # non-zero day remains visible.
    for index, row in enumerate(rows):
        count = row["count"]
        if count <= 0:
            continue

        week = index // 7
        weekday = index % 7

        # Isometric base position.
        x = origin_x + week * x_step - weekday * y_step
        y = origin_y + week * y_step + weekday * x_step

        h = max(4, count * height_scale)

        # Diamond-shaped base.
        half_x = 3.0
        half_y = 2.8

        p1 = (x, y)
        p2 = (x + half_x, y + half_y)
        p3 = (x, y + 2 * half_y)
        p4 = (x - half_x, y + half_y)

        top1 = (p1[0], p1[1] - h)
        top2 = (p2[0], p2[1] - h)
        top3 = (p3[0], p3[1] - h)
        top4 = (p4[0], p4[1] - h)

        def pts(values):
            return " ".join(f"{a:.1f},{b:.1f}" for a, b in values)

        parts.append(
            f'<polygon points="{pts([p4, p1, top1, top4])}" '
            'fill="#006d32" opacity="0.95"/>'
        )
        parts.append(
            f'<polygon points="{pts([p1, p2, top2, top1])}" '
            'fill="#26a641" opacity="0.95"/>'
        )
        parts.append(
            f'<polygon points="{pts([top1, top2, top3, top4])}" '
            'fill="#39d353">'
            f'<title>{esc(row["date"])}: {count} contributions</title></polygon>'
        )

    parts.append(
        '<text x="45" y="590" fill="#8b949e" font-family="Arial, sans-serif" '
        'font-size="11">Each visible bar represents a day with at least one contribution.</text>'
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
