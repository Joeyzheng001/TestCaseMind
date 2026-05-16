"""
Chart generation skill — creates publication-quality figures for academic papers.
Uses matplotlib with Chinese font support.

Usage:
    from skills.chart_skill import create_chart
    create_chart(data, "bar", "output/fig1.png")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union
import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    from matplotlib.font_manager import FontProperties
    import numpy as np

# Try to find a Chinese font
_CHINESE_FONT = None
_FONT_CANDIDATES = [
    "PingFang SC", "Heiti SC", "STHeiti", "SimHei",
    "Microsoft YaHei", "Noto Sans CJK SC", "WenQuanYi Micro Hei",
    "Arial Unicode MS", "Songti SC",
]

for _f in _FONT_CANDIDATES:
    try:
        fp = FontProperties(family=_f)
        # Test if font is available
        _CHINESE_FONT = _f
        break
    except Exception:
        continue

if _CHINESE_FONT:
    plt.rcParams["font.family"] = _CHINESE_FONT
else:
    plt.rcParams["font.family"] = "sans-serif"

plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 150
plt.rcParams["savefig.dpi"] = 300
plt.rcParams["savefig.bbox"] = "tight"
plt.rcParams["savefig.pad_inches"] = 0.1

# Academic color palette
COLORS = ["#1A568E", "#3A7CA5", "#F4A261", "#E76F51", "#2A9D8F",
          "#264653", "#8AB17D", "#D4A373", "#457B9D", "#9B5DE5"]


def create_chart(
    data: Union[dict, list],
    chart_type: str = "bar",
    output_path: str = "output/chart.png",
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    figsize: tuple = (8, 5),
    style: str = "academic",
) -> str:
    """
    Create a publication-quality chart and save to file.

    Args:
        data: For bar/line: {"labels": [...], "values": [...]} or {"series1": [...], ...}
              For pie: {"labels": [...], "values": [...]}
              For scatter: {"x": [...], "y": [...]}
        chart_type: "bar", "line", "pie", "scatter", "h_bar" (horizontal bar)
        output_path: File path for output image (PNG recommended)
        title: Chart title
        xlabel, ylabel: Axis labels
        figsize: Figure size in inches
        style: "academic" (clean), "presentation" (larger fonts), "dark" (dark bg)

    Returns the output_path.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    style_config = {
        "academic": {"title_size": 14, "label_size": 11, "tick_size": 9, "grid": True},
        "presentation": {"title_size": 18, "label_size": 14, "tick_size": 12, "grid": False},
        "dark": {"title_size": 14, "label_size": 11, "tick_size": 9, "grid": True},
    }
    cfg = style_config.get(style, style_config["academic"])

    if style == "dark":
        plt.style.use("dark_background")
    else:
        plt.style.use("default")

    fig, ax = plt.subplots(figsize=figsize)

    # Normalize data
    if isinstance(data, dict):
        # Single series: {"labels": [...], "values": [...]} or {"x": [...], "y": [...]}
        if "labels" in data and "values" in data:
            labels = data["labels"]
            values = data["values"]
            series = {"_": values}
        elif "x" in data and "y" in data:
            labels = data["x"]
            values = data["y"]
            series = {"_": values}
        else:
            # Multiple series: {"series1": [v1, v2, ...], "series2": [...]}
            # Need labels separately
            series = {k: v for k, v in data.items()}
            labels = list(range(len(list(series.values())[0]))) if series else []
    else:
        labels = list(range(len(data)))
        series = {"_": data}

    color_idx = 0

    if chart_type == "bar":
        if len(series) == 1:
            vals = list(series.values())[0]
            x = np.arange(len(vals))
            bars = ax.bar(x, vals, color=COLORS[:len(vals)], edgecolor="white", linewidth=0.5)
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=cfg["tick_size"])
            for bar, val in zip(bars, vals):
                if val > 0:
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(vals) * 0.01,
                            f"{val:.1f}", ha="center", va="bottom", fontsize=cfg["tick_size"] - 1)
        else:
            x = np.arange(len(labels)) if labels else np.arange(len(list(series.values())[0]))
            n_series = len(series)
            w = 0.8 / n_series
            for i, (name, vals) in enumerate(series.items()):
                offset = (i - n_series / 2 + 0.5) * w
                ax.bar(x + offset, vals, w, label=name, color=COLORS[i % len(COLORS)])
            ax.set_xticks(x)
            ax.set_xticklabels(labels or x, rotation=30, ha="right", fontsize=cfg["tick_size"])
            ax.legend(fontsize=cfg["tick_size"])

    elif chart_type == "h_bar":
        vals = list(series.values())[0]
        y = np.arange(len(vals))
        ax.barh(y, vals, color=COLORS[:len(vals)], edgecolor="white", linewidth=0.5)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=cfg["tick_size"])
        ax.invert_yaxis()
        for i, val in enumerate(vals):
            ax.text(val + max(vals) * 0.01, i, f"{val:.1f}", va="center", fontsize=cfg["tick_size"] - 1)

    elif chart_type == "line":
        if len(series) == 1:
            vals = list(series.values())[0]
            x = np.arange(len(vals))
            ax.plot(x, vals, color=COLORS[0], marker="o", linewidth=2, markersize=6)
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=cfg["tick_size"])
        else:
            for i, (name, vals) in enumerate(series.items()):
                ax.plot(vals, color=COLORS[i % len(COLORS)], marker="o",
                        linewidth=2, markersize=6, label=name)
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels or range(len(list(series.values())[0])),
                               rotation=30, ha="right", fontsize=cfg["tick_size"])
            ax.legend(fontsize=cfg["tick_size"])

    elif chart_type == "pie":
        vals = list(series.values())[0]
        wedges, texts, autotexts = ax.pie(
            vals, labels=labels, autopct="%1.1f%%",
            colors=COLORS[:len(vals)], startangle=90,
            textprops={"fontsize": cfg["tick_size"]}
        )
        for at in autotexts:
            at.set_fontsize(cfg["tick_size"] - 1)

    elif chart_type == "scatter":
        x_vals = list(series.values())[0] if series else []
        y_vals = list(series.values())[-1] if len(series) > 1 else x_vals
        if "x" in data and "y" in data:
            x_vals = data["x"]
            y_vals = data["y"]
        ax.scatter(x_vals, y_vals, c=COLORS[0], alpha=0.7, edgecolors="white", linewidth=0.5)

    # Styling
    ax.set_title(title, fontsize=cfg["title_size"], fontweight="bold", pad=12)
    ax.set_xlabel(xlabel, fontsize=cfg["label_size"])
    ax.set_ylabel(ylabel, fontsize=cfg["label_size"])
    ax.tick_params(labelsize=cfg["tick_size"])

    if cfg["grid"] and chart_type not in ("pie",):
        ax.grid(True, alpha=0.3, linestyle="--")
        ax.set_axisbelow(True)

    # Remove top/right spines for clean academic look
    if style != "dark" and chart_type != "pie":
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(output_path, facecolor="white" if style != "dark" else "none")
    plt.close(fig)
    return output_path


def create_multi_panel(
    charts: list[dict],
    output_path: str = "output/fig_panel.png",
    ncols: int = 2,
    figsize: tuple = (12, 5),
    suptitle: str = "",
) -> str:
    """Create a multi-panel figure with multiple sub-charts."""
    nrows = (len(charts) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
    if nrows == 1 and ncols == 1:
        axes = np.array([axes])
    axes = np.atleast_1d(axes).flatten()

    for i, (ax, ch) in enumerate(zip(axes, charts)):
        ch_type = ch.get("type", "bar")
        data = ch.get("data", {})
        labels = data.get("labels", [])
        values = data.get("values", [])

        if ch_type == "bar":
            ax.bar(range(len(values)), values, color=COLORS[:len(values)], edgecolor="white", linewidth=0.5)
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
        elif ch_type == "line":
            ax.plot(values, color=COLORS[0], marker="o", linewidth=1.5, markersize=4)

        ax.set_title(ch.get("title", ""), fontsize=10, fontweight="bold")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(True, alpha=0.3, linestyle="--")
        ax.set_axisbelow(True)

    # Hide unused axes
    for j in range(len(charts), len(axes)):
        axes[j].set_visible(False)

    if suptitle:
        fig.suptitle(suptitle, fontsize=14, fontweight="bold")

    fig.tight_layout()
    fig.savefig(output_path, facecolor="white")
    plt.close(fig)
    return output_path
