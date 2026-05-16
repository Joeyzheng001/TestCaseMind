"""
Table formatting skill — formats data into academic publication-ready tables.
Supports markdown, LaTeX, and plain-text output.

Usage:
    from skills.table_skill import format_table
    result = format_table(data, style="academic", output_format="markdown")
"""

from typing import Any, Optional, Union


def format_table(
    data: Union[list[dict], list[list]],
    columns: Optional[list[str]] = None,
    style: str = "academic",
    output_format: str = "markdown",
    caption: str = "",
    floatfmt: str = ".2f",
) -> str:
    """
    Format tabular data for academic papers.

    Args:
        data: List of dicts (records) or list of lists (rows). First row of
              list-of-lists is treated as header if columns is None.
        columns: Column names. Required if data is list-of-dicts.
        style: "academic" (default, clean grid), "minimal" (no borders),
               "latex" (LaTeX booktabs), "simple" (ASCII borders).
        output_format: "markdown" (pipe table), "latex" (tabular env),
                       "plain" (monospace aligned), "html" (HTML table).
        caption: Optional table caption/title.
        floatfmt: Float formatting spec for numbers.

    Returns formatted table string.
    """
    try:
        from tabulate import tabulate as _tabulate
        _has_tabulate = True
    except ImportError:
        _has_tabulate = False

    # Normalize data to list-of-lists
    if data and isinstance(data[0], dict):
        if columns is None:
            columns = list(data[0].keys())
        rows = [[row.get(col, "") for col in columns] for row in data]
    else:
        rows = list(data)
        if columns is None and rows:
            columns = rows[0]
            rows = rows[1:]

    if not columns or not rows:
        return f"{caption}\n(empty table)\n" if caption else "(empty table)"

    # Choose table format
    fmt_map = {
        "markdown": "pipe",
        "plain": "simple",
        "latex": "latex_booktabs",
        "html": "html",
    }

    if output_format == "markdown":
        tf = "pipe"
    elif output_format == "latex":
        tf = "latex_booktabs"
    elif output_format == "html":
        tf = "html"
    elif output_format == "plain":
        tf = "grid" if _has_tabulate else "simple"
    else:
        tf = "pipe"

    if _has_tabulate:
        result = _tabulate(rows, headers=columns, tablefmt=tf, floatfmt=floatfmt,
                           numalign="right", stralign="left")
    else:
        # Fallback: manual alignment
        widths = [max(len(str(col)), max((len(str(r[i])) for r in rows), default=0))
                  for i, col in enumerate(columns)]
        sep = " | "
        header = sep.join(str(c).ljust(widths[i]) for i, c in enumerate(columns))
        divider = sep.join("-" * w for w in widths)
        body = "\n".join(
            sep.join(str(v).ljust(widths[i]) for i, v in enumerate(row))
            for row in rows
        )
        result = f"{header}\n{divider}\n{body}"

    if caption:
        result = f"表: {caption}\n{result}"

    return result


def format_stats_table(
    stats: dict[str, dict[str, float]],
    caption: str = "描述性统计",
) -> str:
    """
    Format descriptive statistics as an academic table.

    stats: { "变量名": {"mean": 1.23, "std": 0.45, "min": 0, "max": 5}, ... }
    """
    columns = ["变量", "均值", "标准差", "最小值", "最大值"]
    rows = []
    for var, vals in stats.items():
        rows.append([
            var,
            f"{vals.get('mean', 0):.2f}",
            f"{vals.get('std', 0):.2f}",
            f"{vals.get('min', 0):.2f}",
            f"{vals.get('max', 0):.2f}",
        ])
    return format_table(rows, columns=columns, caption=caption, output_format="markdown")


def format_comparison_table(
    groups: list[dict],
    caption: str = "对比分析",
) -> str:
    """
    Format a comparison table from structured group data.

    groups: [{"name": "方案A", "指标1": "值", "指标2": "值", ...}, ...]
    """
    if not groups:
        return "(empty)"
    columns = list(groups[0].keys())
    rows = [[g.get(c, "") for c in columns] for g in groups]
    return format_table(rows, columns=columns, caption=caption, output_format="markdown")
