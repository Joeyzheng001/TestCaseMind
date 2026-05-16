"""
生成论文研究框架/技术路线 SVG 图。

当前模板用于“新能源车载系统质量管理优化研究”。
"""

from pathlib import Path
from xml.sax.saxutils import escape


OUTPUT = Path("output/research_framework_new_energy_vehicle.svg")


WIDTH = 1500
HEIGHT = 820
MARGIN = 32
LABEL_W = 110
LANE_X = MARGIN
CONTENT_X = MARGIN + LABEL_W
LANE_W = WIDTH - MARGIN * 2
BOX_STROKE = "#6B7280"
BG = "#EEF3F6"
LANE_BG = "#E9EEF1"
WHITE = "#FFFFFF"
TEXT = "#1F2933"
MUTED = "#4B5563"
ARROW = "#7A8088"
DASH = "#9AA3AD"


def svg_text(x, y, text, size=18, anchor="middle", rotate=False, weight="400"):
    transform = f' transform="rotate(90 {x} {y})"' if rotate else ""
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}"{transform} '
        f'font-family="Arial, PingFang SC, Microsoft YaHei, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{TEXT}">'
        f"{escape(text)}</text>"
    )


def multiline_text(x, y, lines, size=16, line_gap=24, anchor="middle", rotate=False):
    if isinstance(lines, str):
        lines = [lines]
    if rotate:
        text = "".join(
            f'<tspan x="{x}" dy="{0 if index == 0 else line_gap}">{escape(line)}</tspan>'
            for index, line in enumerate(lines)
        )
        return (
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
            f'transform="rotate(90 {x} {y})" '
            f'font-family="Arial, PingFang SC, Microsoft YaHei, sans-serif" '
            f'font-size="{size}" fill="{TEXT}">{text}</text>'
        )

    start_y = y - (len(lines) - 1) * line_gap / 2
    text = "".join(
        f'<tspan x="{x}" y="{start_y + index * line_gap}">{escape(line)}</tspan>'
        for index, line in enumerate(lines)
    )
    return (
        f'<text text-anchor="{anchor}" '
        f'font-family="Arial, PingFang SC, Microsoft YaHei, sans-serif" '
        f'font-size="{size}" fill="{TEXT}">{text}</text>'
    )


def rect(x, y, w, h, fill=WHITE, stroke=BOX_STROKE, dash=None, radius=3):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.4"{dash_attr}/>'
    )


def arrow(x1, y1, x2, y2, dashed=False, width=2.2):
    dash_attr = ' stroke-dasharray="8 7"' if dashed else ""
    color = DASH if dashed else ARROW
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{color}" stroke-width="{width}" marker-end="url(#arrow)"{dash_attr}/>'
    )


def polyline_arrow(points, dashed=False, width=2.2):
    dash_attr = ' stroke-dasharray="8 7"' if dashed else ""
    color = DASH if dashed else ARROW
    point_text = " ".join(f"{x},{y}" for x, y in points)
    return (
        f'<polyline points="{point_text}" fill="none" '
        f'stroke="{color}" stroke-width="{width}" marker-end="url(#arrow)"{dash_attr}/>'
    )


def box(x, y, w, h, lines, fill=WHITE, size=17, rotate=False):
    content = [rect(x, y, w, h, fill=fill)]
    if rotate:
        content.append(multiline_text(x + w / 2, y + h / 2 + 6, lines, size=size))
    else:
        content.append(multiline_text(x + w / 2, y + h / 2 + 6, lines, size=size))
    return "\n".join(content)


def stage_header(x, w, text):
    return "\n".join(
        [
            rect(x, 44, w, 70, fill=WHITE, stroke="#B8BEC5", radius=0),
            svg_text(x + w / 2, 87, text, size=18),
        ]
    )


def build_svg():
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        "<defs>",
        '<marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">',
        f'<path d="M0,0 L0,6 L9,3 z" fill="{ARROW}"/>',
        "</marker>",
        "</defs>",
        rect(0, 0, WIDTH, HEIGHT, fill="#FFFFFF", stroke="#FFFFFF", radius=0),
    ]

    # Lanes
    lanes = [
        (MARGIN, 28, LANE_W, 100, "研究思路"),
        (MARGIN, 154, LANE_W, 420, "研究内容"),
        (MARGIN, 596, LANE_W, 190, "研究方法"),
    ]
    for x, y, w, h, label in lanes:
        parts.append(rect(x, y, w, h, fill=LANE_BG, stroke="#111827", dash="6 5", radius=0))
        parts.append(svg_text(x + 54, y + h / 2 + 6, label, size=18))

    # Header stages
    parts.append(stage_header(140, 500, "发现问题"))
    parts.append(stage_header(700, 390, "解决问题"))
    parts.append(stage_header(1140, 290, "验证问题"))

    # Content lane: left vertical method/framework
    parts.append(box(138, 208, 52, 288, ["理论", "基础", "与", "研究", "方法"], size=16, rotate=True))
    parts.append(arrow(190, 352, 230, 352))

    # Problem discovery blocks
    parts.append(box(230, 208, 116, 70, ["研发流程", "梳理"], size=16))
    parts.append(box(230, 300, 116, 86, ["质量数据", "统计"], size=16))
    parts.append(box(230, 408, 116, 88, ["访谈问卷", "调研"], size=16))

    parts.append(arrow(346, 243, 382, 243))
    parts.append(arrow(346, 343, 382, 343))
    parts.append(arrow(346, 452, 382, 452))

    parts.append(box(386, 208, 124, 70, ["需求变更", "问题"], size=16))
    parts.append(box(386, 300, 124, 86, ["流程质量", "问题"], size=16))
    parts.append(box(386, 408, 124, 88, ["测试验证", "问题"], size=16))

    parts.append(arrow(510, 243, 552, 243))
    parts.append(arrow(510, 343, 552, 343))
    parts.append(arrow(510, 452, 552, 452))

    parts.append(box(556, 208, 120, 70, ["问题", "归类"], size=16))
    parts.append(box(556, 300, 120, 86, ["成因", "分析"], size=16))
    parts.append(box(556, 408, 120, 88, ["关键问题", "排序"], size=16))

    # Merge to solution core
    parts.append(arrow(676, 352, 724, 352))
    parts.append(box(724, 208, 210, 288, ["CMMI过程改进", "PDCA质量闭环", "车载系统质量", "管理优化方案"], fill="#FFFFFF", size=17))

    # Evaluation
    parts.append(arrow(934, 352, 990, 352))
    parts.append(box(990, 208, 116, 288, ["优化", "效果", "评价"], size=17))
    parts.append(arrow(1106, 352, 1170, 352))
    parts.append(box(1170, 208, 116, 288, ["质量", "改进", "趋势"], size=17))

    # Method lane
    method_boxes = [
        (135, 638, 60, 104, ["文献", "研究法"], 164, 496),
        (230, 638, 116, 104, ["案例研究法", "CMMI模型"], 288, 496),
        (420, 638, 54, 104, ["访谈", "问卷"], 447, 496),
        (486, 638, 54, 104, ["鱼骨图", "5Why"], 513, 496),
        (556, 638, 74, 104, ["AHP", "德尔菲"], 616, 496),
        (724, 638, 210, 104, ["PDCA循环", "CMMI过程域映射"], 829, 496),
        (990, 638, 116, 104, ["前后对比", "评价"], 1048, 496),
        (1170, 638, 116, 104, ["趋势", "分析"], 1228, 496),
    ]
    for x, y, w, h, lines, target_x, target_y in method_boxes:
        parts.append(box(x, y, w, h, lines, size=15))
        start_x = x + w / 2
        if abs(start_x - target_x) < 0.1:
            parts.append(arrow(start_x, y, target_x, target_y, dashed=True, width=1.8))
        else:
            mid_y = y - 28
            parts.append(
                polyline_arrow(
                    [(start_x, y), (start_x, mid_y), (target_x, mid_y), (target_x, target_y)],
                    dashed=True,
                    width=1.8,
                )
            )

    # Small labels
    parts.append(svg_text(615, 186, "核心问题识别", size=15, weight="600"))
    parts.append(svg_text(830, 186, "方案构建", size=15, weight="600"))
    parts.append(svg_text(1138, 186, "效果验证", size=15, weight="600"))

    parts.append("</svg>")
    return "\n".join(parts)


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build_svg(), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
