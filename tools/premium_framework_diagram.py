"""
生成商业版论文研究框架图。

相比 roadmap_diagram.py，这个模板更强调商业展示质量：
- 严格三列网格
- 模块级连接，避免线条交叉
- 方法区作为支撑卡片，不画复杂依赖线
- 适合产品演示和论文正文初稿
"""

from pathlib import Path
from xml.sax.saxutils import escape


SVG_OUTPUT = Path("output/research_framework_new_energy_vehicle_premium.svg")

WIDTH = 1600
HEIGHT = 980
BG = "#F7F9FB"
PAPER = "#FFFFFF"
TEXT = "#1F2937"
MUTED = "#5B6573"
LINE = "#7B8794"
SOFT_LINE = "#B7C0CA"
BLUE = "#EAF3FF"
BLUE_STROKE = "#4F81BD"
AMBER = "#FFF4E6"
AMBER_STROKE = "#D9822B"
GREEN = "#EAF7EA"
GREEN_STROKE = "#4E9A51"
PURPLE = "#F3EAFB"
PURPLE_STROKE = "#8E5BBF"


def text(x, y, value, size=18, anchor="middle", weight="400", fill=TEXT):
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
        f'font-family="Arial, PingFang SC, Microsoft YaHei, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">'
        f"{escape(value)}</text>"
    )


def multiline(x, y, lines, size=17, gap=26, anchor="middle", weight="400", fill=TEXT):
    if isinstance(lines, str):
        lines = [lines]
    start = y - (len(lines) - 1) * gap / 2
    spans = "".join(
        f'<tspan x="{x}" y="{start + index * gap}">{escape(line)}</tspan>'
        for index, line in enumerate(lines)
    )
    return (
        f'<text text-anchor="{anchor}" '
        f'font-family="Arial, PingFang SC, Microsoft YaHei, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">{spans}</text>'
    )


def rect(x, y, w, h, fill=PAPER, stroke=SOFT_LINE, radius=10, width=1.4, dash=None):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"{dash_attr}/>'
    )


def line_arrow(x1, y1, x2, y2, dashed=False, width=2.1):
    dash = ' stroke-dasharray="8 7"' if dashed else ""
    color = "#99A3AF" if dashed else LINE
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{color}" stroke-width="{width}" marker-end="url(#arrow)"{dash}/>'
    )


def card(x, y, w, h, title, lines, fill=PAPER, stroke=SOFT_LINE):
    parts = [rect(x, y, w, h, fill=fill, stroke=stroke, radius=8)]
    if title:
        parts.append(text(x + 18, y + 30, title, size=15, anchor="start", weight="700", fill=MUTED))
        parts.append(multiline(x + w / 2, y + h / 2 + 16, lines, size=17))
    else:
        parts.append(multiline(x + w / 2, y + h / 2 + 6, lines, size=17))
    return "\n".join(parts)


def chip(x, y, w, h, lines, fill=PAPER, stroke=SOFT_LINE):
    return "\n".join(
        [
            rect(x, y, w, h, fill=fill, stroke=stroke, radius=7),
            multiline(x + w / 2, y + h / 2 + 5, lines, size=14, gap=20),
        ]
    )


def stage_panel(x, title, subtitle, fill, stroke, cards):
    y = 145
    w = 380
    h = 500
    parts = [
        rect(x, y, w, h, fill="#FFFFFF", stroke=stroke, radius=14, width=1.8),
        rect(x, y, w, 70, fill=fill, stroke=stroke, radius=14, width=1.8),
        text(x + w / 2, y + 33, title, size=22, weight="700"),
        text(x + w / 2, y + 58, subtitle, size=14, fill=MUTED),
    ]

    card_y = y + 98
    for item in cards:
        parts.append(card(x + 28, card_y, w - 56, item["height"], item.get("title"), item["lines"]))
        card_y += item["height"] + 22
    return "\n".join(parts)


def method_group(x, title, chips, fill, stroke):
    y = 705
    w = 380
    h = 145
    parts = [
        rect(x, y, w, h, fill=fill, stroke=stroke, radius=14, width=1.6),
        text(x + 22, y + 31, title, size=15, anchor="start", weight="700", fill=MUTED),
    ]
    chip_w = (w - 64) / 2
    chip_h = 40
    for index, item in enumerate(chips):
        cx = x + 24 + (index % 2) * (chip_w + 16)
        cy = y + 52 + (index // 2) * 50
        parts.append(chip(cx, cy, chip_w, chip_h, item))
    return "\n".join(parts)


def output_group(x, lines, fill, stroke):
    y = 885
    w = 380
    h = 54
    return "\n".join(
        [
            rect(x, y, w, h, fill=fill, stroke=stroke, radius=12, width=1.5),
            multiline(x + w / 2, y + h / 2 + 5, lines, size=15, gap=20, weight="700"),
        ]
    )


def build_svg():
    x1, x2, x3 = 150, 610, 1070
    panel_top = 145
    panel_bottom = 645
    method_top = 705

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        "<defs>",
        '<marker id="arrow" markerWidth="12" markerHeight="10" refX="10" refY="5" orient="auto" markerUnits="strokeWidth">',
        f'<path d="M0,0 L12,5 L0,10 z" fill="{LINE}"/>',
        "</marker>",
        '<filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">',
        '<feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#D8DEE6" flood-opacity="0.55"/>',
        "</filter>",
        "</defs>",
        rect(0, 0, WIDTH, HEIGHT, fill=BG, stroke=BG, radius=0),
        rect(34, 28, WIDTH - 68, HEIGHT - 56, fill=PAPER, stroke="#DDE3EA", radius=18, width=1.2),
        text(WIDTH / 2, 86, "新能源车载系统质量管理优化研究框架", size=28, weight="700"),
    ]

    parts.append(
        stage_panel(
            x1,
            "发现问题",
            "从现状到核心问题",
            BLUE,
            BLUE_STROKE,
            [
                {"title": "对象界定", "lines": ["新能源车载系统", "研发质量管理边界"], "height": 82},
                {"title": "现状诊断", "lines": ["研发流程梳理", "质量数据统计", "访谈问卷调研"], "height": 126},
                {"title": "问题识别", "lines": ["需求变更问题", "流程质量问题", "测试验证问题"], "height": 126},
            ],
        )
    )

    parts.append(
        stage_panel(
            x2,
            "解决问题",
            "从成因到优化方案",
            GREEN,
            GREEN_STROKE,
            [
                {"title": "成因分析", "lines": ["问题归类", "根因分析", "关键问题排序"], "height": 112},
                {"title": "方案构建", "lines": ["CMMI过程改进", "PDCA质量闭环", "车载系统质量管理优化"], "height": 140},
                {"title": "实施机制", "lines": ["组织保障", "制度保障", "工具与人员保障"], "height": 104},
            ],
        )
    )

    parts.append(
        stage_panel(
            x3,
            "验证问题",
            "从实施到效果评价",
            PURPLE,
            PURPLE_STROKE,
            [
                {"title": "效果评价", "lines": ["缺陷率变化", "返工率变化", "问题关闭周期"], "height": 126},
                {"title": "趋势判断", "lines": ["版本交付稳定性", "客户满意度", "质量改进趋势"], "height": 126},
                {"title": "结论输出", "lines": ["优化效果判断", "后续改进方向"], "height": 92},
            ],
        )
    )

    # Main flow between panels.
    parts.append(line_arrow(x1 + 380, 395, x2, 395, width=2.6))
    parts.append(line_arrow(x2 + 380, 395, x3, 395, width=2.6))

    # Method support groups.
    parts.append(
        method_group(
            x1,
            "研究方法支撑",
            [["文献研究法"], ["案例研究法"], ["访谈问卷"], ["质量数据分析"]],
            BLUE,
            BLUE_STROKE,
        )
    )
    parts.append(
        method_group(
            x2,
            "优化方法支撑",
            [["鱼骨图/5Why"], ["AHP/德尔菲"], ["CMMI模型"], ["PDCA循环"]],
            GREEN,
            GREEN_STROKE,
        )
    )
    parts.append(
        method_group(
            x3,
            "验证方法支撑",
            [["前后对比评价"], ["趋势分析"], ["指标跟踪"], ["满意度评价"]],
            PURPLE,
            PURPLE_STROKE,
        )
    )

    # Vertical support arrows: one per stage, perfectly aligned to the panel center.
    for x in [x1, x2, x3]:
        cx = x + 190
        parts.append(line_arrow(cx, method_top, cx, panel_bottom, dashed=True, width=1.9))

    # Outputs.
    parts.append(output_group(x1, ["输出：问题清单与诊断依据"], BLUE, BLUE_STROKE))
    parts.append(output_group(x2, ["输出：质量管理优化方案"], GREEN, GREEN_STROKE))
    parts.append(output_group(x3, ["输出：效果评价与改进结论"], PURPLE, PURPLE_STROKE))

    # Row labels.
    parts.append(text(78, 395, "研究内容", size=18, weight="700", fill=MUTED))
    parts.append(text(78, 785, "研究方法", size=18, weight="700", fill=MUTED))
    parts.append(text(78, 920, "阶段输出", size=18, weight="700", fill=MUTED))

    parts.append("</svg>")
    return "\n".join(parts)


def main():
    SVG_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    SVG_OUTPUT.write_text(build_svg(), encoding="utf-8")
    print(SVG_OUTPUT)


if __name__ == "__main__":
    main()
