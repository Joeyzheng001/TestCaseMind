"""
跨章节一致性引擎 — 提取每章的承诺项并在后续章节生成时强制对齐。
"""

import re
import json
import sqlite3
import os
from typing import Any, Dict, List, Optional, Tuple
from collections import OrderedDict

# ==================== 承诺提取 ====================

# 数量承诺: "6个核心问题"、"3个维度"、"5类风险"、"12项指标"
_QUANTITY_RE = re.compile(
    r"(\d+)\s*(个|项|类|种|条|大|方面|维度|环节|阶段|步骤|层)"
    r"\s*(\S{2,20}?(?:问题|风险|因素|指标|原因|方案|措施|策略|目标|原则|方法|维度|阶段|步骤|模块|要素))",
    re.UNICODE,
)

# 方法承诺: 在正文中明确声明将使用某方法 — 模板中 {methods} 由 _build_method_promise_re() 填入
_METHOD_PROMISE_TEMPLATE = (
    r"(?:本文(?:将|拟|)?(?:采用|使用|运用|通过|应用|引入)|"
    r"本研究(?:将|拟|)?(?:采用|使用|运用|通过|应用|引入)|"
    r"本章(?:将|拟|)?(?:采用|使用|运用|通过|应用|引入)|"
    r"将(?:采用|使用|运用|通过|应用|引入)|"
    r"拟采用|"
    r"采用|使用|运用|通过|应用|引入)"
    r"\s*({methods})\s*(?:方法|法|模型|工具|技术|分析|评价|评估)?"
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

# 兜底方法名列表（当卡片库不可用时使用，从注册中心动态加载）
def _get_fallback_method_names() -> List[str]:
    from src.method_registry import get_all_method_names
    names = get_all_method_names()
    if names:
        return names
    return []

_methods_pattern_cache: Optional[re.Pattern] = None


def _load_method_names_from_db() -> List[str]:
    """从 cards.sqlite3 动态加载全部方法名（含 short_name 去重）。"""
    db_path = os.path.join(
        os.path.dirname(__file__), "..", "knowledge_base", "cards.sqlite3"
    )
    names = []
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT name, short_name FROM cards "
            "WHERE type='method_card' AND scope='platform'"
        ).fetchall()
        conn.close()
        seen = set()
        for name, short_name in rows:
            for val in (name, short_name):
                v = (val or "").strip()
                if v and v not in seen:
                    seen.add(v)
                    names.append(v)
                for token in v.split():
                    token = token.strip()
                    if len(token) >= 2 and token not in seen:
                        seen.add(token)
                        names.append(token)
    except Exception:
        return []
    return names


def _get_methods_pattern() -> re.Pattern:
    """获取方法名匹配正则，优先从卡片库加载，失败时回退硬编码列表。"""
    global _methods_pattern_cache
    if _methods_pattern_cache is not None:
        return _methods_pattern_cache
    names = _load_method_names_from_db()
    if not names:
        names = _get_fallback_method_names()
    _methods_pattern_cache = re.compile(
        "|".join(re.escape(m) for m in sorted(names, key=len, reverse=True)),
        re.UNICODE,
    )
    return _methods_pattern_cache


def _invalidate_methods_pattern_cache() -> None:
    """在卡片库重建后清除缓存，使下次匹配使用最新方法列表。"""
    global _methods_pattern_cache, _method_promise_pattern_cache
    _methods_pattern_cache = None
    _method_promise_pattern_cache = None


_method_promise_pattern_cache: Optional[re.Pattern] = None


def _get_method_promise_pattern() -> re.Pattern:
    """构建方法承诺正则：只匹配「本文将采用 X 方法」等明确承诺句式。"""
    global _method_promise_pattern_cache
    if _method_promise_pattern_cache is not None:
        return _method_promise_pattern_cache
    names = _load_method_names_from_db()
    if not names:
        names = _get_fallback_method_names()
    methods_alt = "|".join(re.escape(m) for m in sorted(names, key=len, reverse=True))
    _method_promise_pattern_cache = re.compile(
        _METHOD_PROMISE_TEMPLATE.replace("{methods}", methods_alt),
        re.UNICODE,
    )
    return _method_promise_pattern_cache


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
    # 第一轮：明确承诺句式「本文将采用 X 方法」
    promise_pattern = _get_method_promise_pattern()
    promised: Dict[str, str] = {}  # method_name → matched raw text
    for m in promise_pattern.finditer(text):
        # group(1) is the method name captured from the alternation group
        method = m.group(1)
        if method and method not in promised:
            promised[method] = m.group(0)

    # 第二轮：其余方法名称出现（作为已使用方法）
    simple_pattern = _get_methods_pattern()
    used: Dict[str, str] = {}
    for m in simple_pattern.finditer(text):
        method = m.group(0)
        if method and method not in promised and method not in used:
            used[method] = m.group(0)

    commitments: List[Dict[str, Any]] = []
    for method, raw in promised.items():
        commitments.append({
            "type": "method",
            "method": method,
            "source": "promise",
            "raw": raw,
        })
    for method, raw in used.items():
        commitments.append({
            "type": "method",
            "method": method,
            "source": "usage",
            "raw": raw,
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

    # 替换同小节的旧承诺（section 级别去重，支持同章内一致性校验）
    full_key = section_key if section_key else chapter_key
    all_commitments = [
        c for c in all_commitments if c.get("section_key") != full_key
    ]
    new_commitment["section_key"] = full_key
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

    all_methods = by_type.get("method", [])
    return {
        "total_quantities": [
            q for q in by_type.get("quantity", [])
        ],
        "promised_methods": [
            m for m in all_methods if m.get("source") == "promise"
        ],
        "used_methods": [
            m for m in all_methods if m.get("source") != "promise"
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

    def _fmt_sk(sk: str) -> str:
        """格式化小节标识，如 1.2.1。"""
        if not sk:
            return "?"
        return sk

    quantities = summary.get("total_quantities", [])
    if quantities:
        lines.append("- 数量承诺：")
        seen_q = set()
        for q in quantities:
            key = q.get("raw", "")
            if key not in seen_q:
                seen_q.add(key)
                lines.append(f"  小节{_fmt_sk(q.get('section_key', q.get('chapter', '?')))}: {q['raw']}")

    promised = summary.get("promised_methods", [])
    if promised:
        lines.append("- 已承诺使用的方法（后续小节必须实际应用，不能只提名字）：")
        seen_m = set()
        for m in promised:
            key = m.get("method", "")
            if key not in seen_m:
                seen_m.add(key)
                lines.append(f"  小节{_fmt_sk(m.get('section_key', m.get('chapter', '?')))}: {m['method']}（明确承诺）")

    used = summary.get("used_methods", [])
    if used:
        lines.append("- 前文已出现的方法（后续小节可复用，不作硬性要求）：")
        seen_u = set()
        for m in used:
            key = m.get("method", "")
            if key not in seen_u and key not in seen_m:
                seen_u.add(key)
                lines.append(f"  小节{_fmt_sk(m.get('section_key', m.get('chapter', '?')))}: {m['method']}")

    data_sources = summary.get("data_sources", [])
    if data_sources:
        lines.append("- 数据承诺（后续小节的数据来源必须一致）：")
        seen_ds = set()
        for d in data_sources:
            key = d.get("subject", "")
            if key not in seen_ds:
                seen_ds.add(key)
                lines.append(f"  小节{_fmt_sk(d.get('section_key', d.get('chapter', '?')))}: {d['subject']}")

    definitions = summary.get("defined_terms", [])
    if definitions:
        lines.append("- 术语定义承诺（后续小节必须使用相同定义）：")
        seen_d = set()
        for d in definitions:
            key = d.get("term", "")
            if key not in seen_d:
                seen_d.add(key)
                lines.append(f"  小节{_fmt_sk(d.get('section_key', d.get('chapter', '?')))}: {d['term']} — {d['definition']}")

    lines.append("")
    lines.append(
        "要求：本章内容必须与上述承诺对齐。如果承诺了 N 个问题，本章必须全部覆盖。"
        "如果承诺了某方法，本章必须出现该方法的具体应用（不能只提名字）。"
    )
    return "\n".join(lines)


# ==================== 闭合校验 ====================


def _check_definition_drift(
    content: str, term: str, committed_def: str, source_chapter: str
) -> Optional[Dict[str, Any]]:
    """检查术语在内容中是否被重新定义为不同含义。

    如果内容中重新定义了同一术语但含义不同，返回 drift 信息。
    如果定义一致或只是使用术语（未重新定义），返回 None。
    """
    escaped = re.escape(term)
    redefine_re = re.compile(
        escaped + r"\s*(?:是指|定义为|指|即|指的是|特指)\s*(.+?)(?:[。；;]|$)",
        re.UNICODE,
    )
    m = redefine_re.search(content)
    if not m:
        return None
    new_def = m.group(1).strip()[:80]
    # 简单比较：用公共子串比例判断定义是否漂移
    if _definition_similarity(committed_def, new_def) < 0.3:
        return {
            "term": term,
            "source_chapter": source_chapter,
            "committed_definition": committed_def,
            "found_definition": new_def,
            "warning": f"术语「{term}」在{source_chapter}章定义为「{committed_def}」，但当前内容重定义为「{new_def}」",
        }
    return None


def _definition_similarity(def_a: str, def_b: str) -> float:
    """简单相似度：基于公共字符比例。"""
    a_chars = set(def_a.replace(" ", ""))
    b_chars = set(def_b.replace(" ", ""))
    if not a_chars or not b_chars:
        return 0.0
    intersection = a_chars & b_chars
    return len(intersection) / max(len(a_chars), len(b_chars))


def verify_commitments(
    content: str, memory: Dict[str, Any], current_section_key: str
) -> Dict[str, Any]:
    """检查当前小节内容是否覆盖了前文的承诺项。

    承诺项分两级：
    - hard: 数量/数据/术语/明确承诺的方法 → 缺失即未闭合
    - soft: 仅在前文出现过的使用方法 → 缺失仅提示，不算未闭合
    """
    commitments: List[Dict[str, Any]] = memory.get("commitments", [])
    hard_unresolved: List[Dict[str, Any]] = []
    soft_unresolved: List[Dict[str, Any]] = []
    resolved: List[str] = []

    definition_drifts: List[Dict[str, Any]] = []

    for chapter_block in commitments:
        sk = chapter_block.get("section_key", "")
        # Skip self: exact match for section keys, prefix match for chapter keys
        if sk == current_section_key:
            continue
        if sk.startswith(current_section_key + "."):
            continue
        for item in chapter_block.get("items", []):
            identifier = ""
            is_hard = True
            if item["type"] == "method":
                identifier = item.get("method", "")
                if item.get("source") != "promise":
                    is_hard = False
            elif item["type"] == "quantity":
                identifier = item.get("subject", "")
            elif item["type"] == "definition":
                identifier = item.get("term", "")
                # 术语不仅检查是否出现，还检查定义是否一致
                if identifier and identifier in content:
                    committed_def = item.get("definition", "")
                    if committed_def:
                        # 在内容中查找该术语被重新定义的情况
                        drift = _check_definition_drift(
                            content, identifier, committed_def, ch
                        )
                        if drift:
                            definition_drifts.append(drift)
                            hard_unresolved.append(item)
                            continue
                    resolved.append(identifier)
                    continue
            elif item["type"] == "data":
                identifier = item.get("subject", "")

            if identifier and identifier in content:
                resolved.append(identifier)
            elif is_hard:
                hard_unresolved.append(item)
            else:
                soft_unresolved.append(item)

    return {
        "total_commitments": sum(
            len(c.get("items", [])) for c in commitments
            if c.get("section_key") != current_section_key
        ),
        "resolved": len(resolved),
        "hard_unresolved": len(hard_unresolved),
        "soft_unresolved": len(soft_unresolved),
        "unresolved": len(hard_unresolved),
        "unresolved_items": hard_unresolved[:10],
        "soft_unresolved_items": soft_unresolved[:5],
        "definition_drifts": definition_drifts,
    }


def build_unresolved_warning(memory: Dict[str, Any], current_section_key: str) -> str:
    """生成未闭合承诺的警告文本。"""
    commitments: List[Dict[str, Any]] = memory.get("commitments", [])
    previous = [
        c for c in commitments
        if c.get("section_key") != current_section_key
        and not c.get("section_key", "").startswith(current_section_key + ".")
    ]
    if not previous:
        return ""

    def _fmt_sk(sk: str) -> str:
        return sk or "?"

    # 收集所有前文的承诺项
    all_items = []
    for c in previous:
        for item in c.get("items", []):
            all_items.append(f"  小节{_fmt_sk(c.get('section_key', '?'))}: {item['raw']}")

    if not all_items:
        return ""

    lines = [
        "[未闭合承诺] 以下承诺尚未在任何后续章节中兑现，本章需要覆盖：",
    ]
    lines.extend(all_items[:15])
    lines.append("生成本章时请确保覆盖上述承诺。")
    return "\n".join(lines)


# ==================== 引用校验 ====================

_CITATION_MARKER_RE = re.compile(
    r"\[(\d+(?:[,，\-—]\d+)*)\]", re.UNICODE
)


def verify_citations(
    content: str,
    expected_indices: List[int],
    citation_pool: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """检查生成内容中的引用标记是否与要求的引用一致。

    Args:
        content: 生成的正文
        expected_indices: 要求引用的文献序号列表（0-based）
        citation_pool: 当前引用库
    Returns:
        {properly_cited, missing, unknown, fabricated_marks, total_expected}
    """
    if not expected_indices:
        # 没有要求引用 → 检查是否误加了引用
        found = set()
        for m in _CITATION_MARKER_RE.finditer(content):
            found.update(_parse_citation_indices(m.group(0)))
        return {
            "properly_cited": [],
            "missing": [],
            "unknown": list(found) if found else [],
            "fabricated_indices": [],
            "total_expected": 0,
            "any_found": len(found) > 0,
        }

    # 从内容中提取实际引用的序号（转为 0-based）
    cited: set = set()
    for m in _CITATION_MARKER_RE.finditer(content):
        cited.update(_parse_citation_indices(m.group(0)))

    expected = set(expected_indices)
    properly_cited = sorted(expected & cited)
    missing = sorted(expected - cited)
    unknown = sorted(cited - expected)

    # 检查是否有超出引用库范围的序号
    max_index = len(citation_pool) - 1
    fabricated = [i for i in cited if i > max_index]

    return {
        "properly_cited": properly_cited,
        "missing": missing,
        "unknown": unknown,
        "fabricated_indices": fabricated,
        "total_expected": len(expected),
    }


def _parse_citation_indices(marker: str) -> List[int]:
    """解析引用标记中的序号。支持 [1], [2,3], [1-3], [1—3] 等格式。返回 0-based 序号列表。"""
    inner = marker.strip("[]")
    indices: List[int] = []
    for part in re.split(r"[,，]", inner):
        part = part.strip()
        range_match = re.match(r"(\d+)\s*[\-—]\s*(\d+)", part)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            indices.extend(range(start, end + 1))
        else:
            try:
                indices.append(int(part))
            except ValueError:
                pass
    return [i - 1 for i in indices if i >= 1]
