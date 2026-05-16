"""
跨章节一致性引擎 — 提取每章的承诺项并在后续章节生成时强制对齐。
"""

import re
import json
from typing import Any, Dict, List, Optional, Tuple
from collections import OrderedDict

# ==================== 承诺提取 ====================

# 数量承诺: "6个核心问题"、"3个维度"、"5类风险"、"12项指标"
_QUANTITY_RE = re.compile(
    r"(\d+)\s*(个|项|类|种|条|大|方面|维度|环节|阶段|步骤|层)"
    r"\s*(\S{2,20}?(?:问题|风险|因素|指标|原因|方案|措施|策略|目标|原则|方法|维度|阶段|步骤|模块|要素))",
    re.UNICODE,
)

# 方法承诺: 在正文中明确声明将使用某方法
_METHOD_PROMISE_RE = re.compile(
    r"(?:本文|本研究|本章|将采用|拟采用|使用|运用|通过|应用|引入)"
    r"({methods})\s*(?:方法|法|模型|工具|技术|分析|评价|评估)?",
    re.UNICODE,
)

# 数据承诺: "50份问卷"、"30个样本"、"XX公司2025年Q1"
_DATA_RE = re.compile(
    r"(\d+)\s*(份|个|条|家|项|次)\s*"
    r"(?:有效)?\s*(问卷|样本|数据|案例|项目|访谈|企业|公司|部门)",
    re.UNICODE,
)

# 术语定义: "X 是指/定义为 X"
_DEFINITION_RE = re.compile(
    r"([^\s。，,；;]{2,30}(?:质量|管理|风险|流程|成本|进度|安全|资源|技术|债务|指标|体系|标准|模型|框架))"
    r"\s*(?:是指|定义为|指|即|指的是|特指)\s*(.+?)(?:[。；;]|$)",
    re.UNICODE,
)

# 从 web_server 复用方法论别名（避免循环导入，此处硬编码高频方法）
_METHOD_NAMES = [
    "层次分析法", "AHP", "模糊综合评价", "FCE", "PDCA", "DMAIC",
    "六西格玛", "鱼骨图", "5M1E", "SWOT", "WBS", "RBS", "帕累托",
    "德尔菲", "Scrum", "DevOps", "CMMI", "BIM", "EVM", "挣值管理",
    "CPM", "关键路径", "PERT", "BPR", "流程再造", "RACI", "BSC",
    "平衡计分卡", "TOPSIS", "熵权法", "DEA", "灰色关联", "因子分析",
    "主成分分析", "结构方程模型", "SEM", "回归分析", "DID", "双重差分",
    "根因分析", "RCA", "SPC", "控制图", "前后对比", "问卷调查",
    "访谈法", "文献研究", "案例研究", "现场调查", "德尔菲法",
    "精益管理", "敏捷管理", "标准化管理", "KPI", "绩效考核",
]

_METHODS_PATTERN = re.compile(
    "|".join(re.escape(m) for m in sorted(_METHOD_NAMES, key=len, reverse=True)),
    re.UNICODE,
)


def _extract_quantity_commitments(text: str) -> List[Dict[str, Any]]:
    commitments = []
    for m in _QUANTITY_RE.finditer(text):
        count = int(m.group(1))
        unit = m.group(2)
        subject = m.group(3)
        commitments.append({
            "type": "quantity",
            "count": count,
            "subject": f"{count}{unit}{subject}",
            "raw": m.group(0),
        })
    return commitments


def _extract_method_commitments(text: str) -> List[Dict[str, Any]]:
    found = set()
    for m in _METHODS_PATTERN.finditer(text):
        method = m.group(0)
        if method not in found:
            found.add(method)
    commitments = []
    for method in found:
        commitments.append({
            "type": "method",
            "method": method,
            "raw": f"承诺使用: {method}",
        })
    return commitments


def _extract_data_commitments(text: str) -> List[Dict[str, Any]]:
    commitments = []
    for m in _DATA_RE.finditer(text):
        commitments.append({
            "type": "data",
            "subject": m.group(0),
            "raw": m.group(0),
        })
    return commitments


def _extract_definition_commitments(text: str) -> List[Dict[str, Any]]:
    commitments = []
    for m in _DEFINITION_RE.finditer(text):
        term = m.group(1)
        definition = m.group(2).strip()[:80]
        commitments.append({
            "type": "definition",
            "term": term,
            "definition": definition,
            "raw": f"{term} 是指 {definition}",
        })
    return commitments


def extract_commitments(
    content: str, chapter_key: str, section_key: str = ""
) -> Dict[str, Any]:
    """从章节内容中提取所有承诺项，按来源段落分组。"""
    raw = {
        "quantities": _extract_quantity_commitments(content),
        "methods": _extract_method_commitments(content),
        "data": _extract_data_commitments(content),
        "definitions": _extract_definition_commitments(content),
    }
    # 合并去重
    merged = []
    seen_raw = set()
    total = 0
    for category, items in raw.items():
        for item in items:
            if item["raw"] not in seen_raw:
                seen_raw.add(item["raw"])
                merged.append(item)
        total += len(items)
    return {
        "chapter": chapter_key,
        "section": section_key,
        "count": len(merged),
        "items": merged,
        "extracted_at": "",
    }


def merge_commitments_to_memory(
    memory: Dict[str, Any], chapter_key: str, section_key: str, content: str
) -> Dict[str, Any]:
    """将新提取的承诺合并到 thesis_memory 中。"""
    new_commitment = extract_commitments(content, chapter_key, section_key)

    all_commitments: List[Dict[str, Any]] = memory.get("commitments", [])
    if not isinstance(all_commitments, list):
        all_commitments = []

    # 替换同章节的旧承诺
    all_commitments = [
        c for c in all_commitments if c.get("chapter") != chapter_key
    ]
    if new_commitment["items"]:
        all_commitments.append(new_commitment)

    memory["commitments"] = all_commitments
    memory["commitment_summary"] = _build_aggregate_summary(all_commitments)
    return memory


# ==================== 承诺注入 ====================


def _build_aggregate_summary(
    all_commitments: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """跨章节聚合：按类型合并，追踪闭合状态。"""
    by_type: Dict[str, List[Dict[str, Any]]] = OrderedDict()
    for chapter_block in all_commitments:
        for item in chapter_block.get("items", []):
            by_type.setdefault(item["type"], []).append({
                **item,
                "chapter": chapter_block["chapter"],
            })

    return {
        "total_quantities": [
            q for q in by_type.get("quantity", [])
        ],
        "promised_methods": [
            m for m in by_type.get("method", [])
        ],
        "data_sources": [
            d for d in by_type.get("data", [])
        ],
        "defined_terms": [
            d for d in by_type.get("definition", [])
        ],
    }


def build_commitment_brief(memory: Dict[str, Any]) -> str:
    """生成注入 prompt 的承诺约束块。"""
    commitments: List[Dict[str, Any]] = memory.get("commitments", [])
    if not commitments:
        return ""

    summary = memory.get("commitment_summary") or _build_aggregate_summary(
        commitments
    )
    lines = ["[一致性约束] 前文已做出的承诺，本章必须对齐："]

    def _fmt_ch(ch: str) -> str:
        """格式化章节标识，避免"第第一章章"重复。"""
        if ch.startswith("第") and ch.endswith("章"):
            return ch
        if ch.startswith("第"):
            return ch + "章"
        return f"第{ch}章"

    quantities = summary.get("total_quantities", [])
    if quantities:
        lines.append("- 数量承诺：")
        for q in quantities:
            lines.append(f"  {_fmt_ch(q.get('chapter', '?'))}: {q['raw']}")

    methods = summary.get("promised_methods", [])
    if methods:
        lines.append("- 方法承诺（后续章节必须实际应用这些方法）：")
        for m in methods:
            lines.append(f"  {_fmt_ch(m.get('chapter', '?'))}: {m['method']}")

    data_sources = summary.get("data_sources", [])
    if data_sources:
        lines.append("- 数据承诺（后续章节的数据来源必须一致）：")
        for d in data_sources:
            lines.append(f"  {_fmt_ch(d.get('chapter', '?'))}: {d['subject']}")

    definitions = summary.get("defined_terms", [])
    if definitions:
        lines.append("- 术语定义承诺（后续章节必须使用相同定义）：")
        for d in definitions:
            lines.append(f"  {_fmt_ch(d.get('chapter', '?'))}: {d['term']} — {d['definition']}")

    lines.append("")
    lines.append(
        "要求：本章内容必须与上述承诺对齐。如果承诺了 N 个问题，本章必须全部覆盖。"
        "如果承诺了某方法，本章必须出现该方法的具体应用（不能只提名字）。"
    )
    return "\n".join(lines)


# ==================== 闭合校验 ====================


def verify_commitments(
    content: str, memory: Dict[str, Any], current_chapter: str
) -> Dict[str, Any]:
    """检查当前章节内容是否覆盖了前文的承诺项。"""
    commitments: List[Dict[str, Any]] = memory.get("commitments", [])
    unresolved: List[Dict[str, Any]] = []
    resolved: List[str] = []

    for chapter_block in commitments:
        ch = chapter_block.get("chapter", "")
        if ch == current_chapter:
            continue
        for item in chapter_block.get("items", []):
            identifier = ""
            if item["type"] == "method":
                identifier = item.get("method", "")
            elif item["type"] == "quantity":
                identifier = item.get("subject", "")
            elif item["type"] == "definition":
                identifier = item.get("term", "")
            elif item["type"] == "data":
                identifier = item.get("subject", "")

            if identifier and identifier in content:
                resolved.append(identifier)
            else:
                unresolved.append(item)

    return {
        "total_commitments": sum(
            len(c.get("items", [])) for c in commitments
            if c.get("chapter") != current_chapter
        ),
        "resolved": len(resolved),
        "unresolved": len(unresolved),
        "unresolved_items": unresolved[:10],
    }


def build_unresolved_warning(memory: Dict[str, Any], current_chapter: str) -> str:
    """生成未闭合承诺的警告文本。"""
    commitments: List[Dict[str, Any]] = memory.get("commitments", [])
    previous = [
        c for c in commitments if c.get("chapter") != current_chapter
    ]
    if not previous:
        return ""

    def _fmt_ch(ch: str) -> str:
        if ch.startswith("第") and ch.endswith("章"):
            return ch
        if ch.startswith("第"):
            return ch + "章"
        return f"第{ch}章"

    # 收集所有前文章节的承诺项
    all_items = []
    for c in previous:
        for item in c.get("items", []):
            all_items.append(f"  {_fmt_ch(c['chapter'])}: {item['raw']}")

    if not all_items:
        return ""

    lines = [
        "[未闭合承诺] 以下承诺尚未在任何后续章节中兑现，本章需要覆盖：",
    ]
    lines.extend(all_items[:15])
    lines.append("生成本章时请确保覆盖上述承诺。")
    return "\n".join(lines)
