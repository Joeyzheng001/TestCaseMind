"""
盲审风险检查引擎。
加载风险卡，对论文草稿执行风险扫描，生成结构化风险报告。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CARDS_DB = PROJECT_ROOT / "knowledge_base" / "cards.sqlite3"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(CARDS_DB))
    conn.row_factory = sqlite3.Row
    return conn


def load_risk_cards(
    severity: Optional[List[str]] = None,
    category: Optional[str] = None,
    check_stage: Optional[str] = None,
    chapter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """从 SQLite 加载风险卡，支持按严重程度/类别/阶段/章节过滤。"""
    conn = _connect()
    try:
        query = "SELECT * FROM risk_cards WHERE status = 'reviewed' AND scope = 'platform'"
        params: List[Any] = []

        if severity:
            placeholders = ",".join("?" for _ in severity)
            query += f" AND severity IN ({placeholders})"
            params.extend(severity)
        if category:
            query += " AND category = ?"
            params.append(category)
        if check_stage:
            query += " AND check_stage = ?"
            params.append(check_stage)
        if chapter:
            query += " AND applicable_chapters LIKE ?"
            params.append(f"%{chapter}%")

        rows = conn.execute(query, params).fetchall()
        cards = []
        for row in rows:
            card = dict(row)
            for field in [
                "disciplines", "applicable_chapters", "trigger_conditions",
                "check_questions", "fix_strategy", "related_method_tags",
            ]:
                val = card.get(field)
                if isinstance(val, str):
                    try:
                        card[field] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
            cards.append(card)
        return cards
    finally:
        conn.close()


def check_single_risk(
    card: Dict[str, Any],
    content: str,
    chapter_title: str = "",
    chapter_number: str = "",
) -> Dict[str, Any]:
    """
    对单段内容执行单张风险卡的规则检查。
    基于触发条件中的关键词和模式进行匹配，不依赖 LLM。
    """
    triggered = False
    matched_conditions: List[str] = []
    evidence: List[str] = []

    trigger_conditions = card.get("trigger_conditions", [])
    if isinstance(trigger_conditions, str):
        trigger_conditions = [trigger_conditions]

    for condition in trigger_conditions:
        # 使用关键词匹配判断触发
        if _match_condition(content, condition, chapter_title):
            matched_conditions.append(condition)
            triggered = True

    # 提取相关证据片段
    if triggered:
        evidence = _extract_evidence(content, card.get("category", ""), max_snippets=3)

    return {
        "risk_id": card["id"],
        "risk_name": card["name"],
        "severity": card.get("severity", "medium"),
        "category": card.get("category", ""),
        "triggered": triggered,
        "matched_conditions": matched_conditions,
        "evidence": evidence,
        "check_questions": card.get("check_questions", []),
        "fix_strategy": card.get("fix_strategy", []),
    }


def _match_condition(content: str, condition: str, chapter_title: str = "") -> bool:
    """基于规则的触发条件匹配。"""
    content_lower = content.lower()
    condition_lower = condition.lower()

    # 模式1: 方法数量过多 —— 仅当条件显式提到"方法"时才触发
    if "方法" in condition and ("3 个以上" in condition or "多个" in condition or "堆砌" in condition):
        method_count = _count_method_mentions(content)
        if method_count >= 4 and _no_selection_rationale(content):
            return True

    # 模式2: 缺少专家信息
    if "专家" in condition and ("人数" in condition or "标准" in condition or "遴选" in condition):
        if not _has_expert_info(content):
            return True

    # 模式3: 缺少一致性检验
    if "一致性" in condition or "consistency" in condition_lower:
        if _mentions_ahp(content) and not _has_consistency_report(content):
            return True

    # 模式4: 样本量不足
    if "样本" in condition and ("不足" in condition or "30" in condition or "抽样" in condition):
        if _mentions_survey(content) and not _has_sample_justification(content):
            return True

    # 模式5: 引用陈旧
    if "陈旧" in condition or "近3" in condition or "outdated" in condition_lower:
        if _citation_outdated_signal(content):
            return True

    # 模式6: 章节断裂
    if "章节" in condition and ("断裂" in condition or "逻辑" in condition):
        if _chapter_disconnection_signal(content):
            return True

    # 模式7: 创新点空泛
    if "创新" in condition and ("空泛" in condition or "vague" in condition_lower):
        if _innovation_vague_signal(content):
            return True

    # 通用: 关键词出现在内容中但不能充分论证
    if _keyword_present_but_shallow(content, condition):
        return True

    return False


def _count_method_mentions(content: str) -> int:
    """统计内容中出现的独立方法数量，处理同义词去重。"""
    from src.method_registry import get_registry as _rc_reg
    _reg = _rc_reg()
    _aliases = _reg.get_aliases()
    method_groups: List[List[str]] = []
    for _canon, _als in _aliases.items():
        _group = [_canon] + [a for a in _als if a != _canon]
        # 为纯英文别名补充小写形式，确保大小写不敏感匹配
        _extra = []
        for _a in _group:
            if _a.isascii() and _a.upper() != _a.lower():
                _extra.append(_a.lower())
        method_groups.append(_group + _extra)
    content_lower = content.lower()
    found_groups: Set[str] = set()
    for group in method_groups:
        if any(kw.lower() in content_lower for kw in group):
            found_groups.add(group[0])
    return len(found_groups)


def _no_selection_rationale(content: str) -> bool:
    """检测是否缺少方法选择理由。"""
    method_count = _count_method_mentions(content)
    if method_count < 4:
        return False

    # 检查是否有"为什么选择X"的论证句式
    rationale_patterns = [
        "因为", "由于", "原因在于", "适合", "适用于", "因此选用",
        "基于.*选择", "考虑.*采用", "针对.*特点", "相比.*更", "优于",
        "第一，", "第二，", "第三，", "首先", "其次", "再次",
    ]
    import re
    rationale_count = sum(1 for p in rationale_patterns if re.search(p, content))

    # 如果论证密度极低（每个方法平均不到50字），判定缺理由
    chars_per_method = len(content) / method_count
    if chars_per_method < 50 and rationale_count < method_count:
        return True

    # 论证句数量应至少为方法数的 1/3
    return rationale_count < method_count * 0.33


def _has_expert_info(content: str) -> bool:
    import re
    expert_patterns = [
        r"\d+\s*位.{0,25}(专家|人员|工程师|经理)",
        r"\d+\s*名.{0,25}(专家|人员|工程师|经理)",
        r"\d+\s*年.{0,20}(经验|从业|资历|工作)",
        r"具备.{0,20}(背景|经验|资质)",
        r"(遴选|筛选|选择).{0,20}(专家|人员|标准|条件)",
    ]
    for pattern in expert_patterns:
        if re.search(pattern, content):
            return True
    return False


def _mentions_ahp(content: str) -> bool:
    return any(kw.lower() in content.lower() for kw in ["ahp", "层次分析", "判断矩阵"])


def _has_consistency_report(content: str) -> bool:
    import re
    return bool(re.search(
        r"CR\s*(?:值|值均)?\s*(?:[=<≤]|小于|大于|为|约|在)\s*0?\.?\d"
        r"|一致性.{0,15}(检验|比率|指标|CR)"
        r"|CR.{0,5}(小于|大于|通过|合格)",
        content,
    ))


def _mentions_survey(content: str) -> bool:
    return any(kw in content for kw in ["问卷", "样本", "调查", "受访"])


def _has_sample_justification(content: str) -> bool:
    import re
    return bool(re.search(r"(样本|问卷|回收|有效).{0,20}\d+", content))


def _citation_outdated_signal(content: str) -> bool:
    """检测引用陈旧的信号。"""
    # 检查是否有大量2000年前的年份
    import re
    years = re.findall(r"(19\d{2})", content)
    recent = re.findall(r"(202[0-9])", content)
    return len(years) > 3 and len(recent) < len(years)


def _chapter_disconnection_signal(content: str) -> bool:
    """检测章节断裂信号：承诺了但未兑现。"""
    promise_markers = ["将在.*章", "将在后文", "如下.*章", "见.*节"]
    fulfill_markers = ["如上文", "前述", "前文已"]
    return any(m in content for m in promise_markers) and not any(
        m in content for m in fulfill_markers
    )


def _innovation_vague_signal(content: str) -> bool:
    """检测创新点空泛。"""
    vague_terms = ["系统化", "全面", "综合", "深入", "完善"]
    specific_terms = ["首次", "提出.*模型", "构建.*框架", "验证.*关系", "发现"]
    import re
    has_vague = sum(1 for t in vague_terms if t in content)
    has_specific = sum(1 for t in specific_terms if re.search(t, content))
    return has_vague >= 2 and has_specific == 0


def _keyword_present_but_shallow(content: str, condition: str) -> bool:
    """通用浅层匹配：关键词出现但缺乏深度论述，且条件不是否定式。"""
    import re

    # 检查条件是否为否定式（"未说明X" / "缺少X"）——此时应检查内容是否真的缺少X
    negation_words = ["未", "没有", "缺乏", "缺少", "不足", "无", "不"]
    is_negative = any(w in condition for w in negation_words)
    if is_negative:
        # 否定条件不应通过浅层关键词匹配触发——交给具体的检测函数处理
        return False

    # 从条件中提取核心关键词
    key_terms = re.findall(r"[一-鿿]{2,6}", condition)
    if not key_terms:
        return False
    # 需要至少 4 个核心词同时在内容中出现才继续判断
    matched = [t for t in key_terms if t in content]
    if len(matched) < 4:
        return False
    depth_markers = ["具体", "例如", "数据", "如图", "见表", "说明", "分析"]
    if not any(m in content for m in depth_markers):
        return True
    return False


def _extract_evidence(content: str, category: str, max_snippets: int = 3) -> List[str]:
    """从内容中提取触发风险的证据片段。"""
    sentences = content.replace("\n", " ").split("。")
    evidence = []
    for sent in sentences:
        sent = sent.strip()
        if not sent or len(sent) < 10:
            continue
        evidence.append(sent[:150])
        if len(evidence) >= max_snippets:
            break
    return evidence


def run_risk_scan(
    content: str,
    chapter_title: str = "",
    chapter_number: str = "",
    severity_filter: Optional[List[str]] = None,
    category_filter: Optional[str] = None,
    chapter_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    主入口：对论文草稿执行完整风险扫描。
    返回结构化风险报告。
    """
    cards = load_risk_cards(
        severity=severity_filter,
        category=category_filter,
        chapter=chapter_type,
    )

    if not cards:
        return {
            "status": "ok",
            "total_risks": 0,
            "triggered": 0,
            "results": [],
            "summary": "未加载到风险卡，请先执行 build_risks。",
        }

    results = []
    for card in cards:
        result = check_single_risk(
            card, content, chapter_title=chapter_title, chapter_number=chapter_number
        )
        results.append(result)

    triggered = [r for r in results if r["triggered"]]
    critical_triggered = [r for r in triggered if r["severity"] == "critical"]
    high_triggered = [r for r in triggered if r["severity"] == "high"]

    # 生成摘要
    summary_parts = []
    if not triggered:
        summary_parts.append("未发现触发风险。")
    else:
        if critical_triggered:
            names = "、".join(r["risk_name"] for r in critical_triggered)
            summary_parts.append(f"严重风险 {len(critical_triggered)} 项：{names}")
        if high_triggered:
            names = "、".join(r["risk_name"] for r in high_triggered)
            summary_parts.append(f"高风险 {len(high_triggered)} 项：{names}")
        remaining = len(triggered) - len(critical_triggered) - len(high_triggered)
        if remaining > 0:
            summary_parts.append(f"其他风险 {remaining} 项")

    return {
        "status": "ok",
        "total_risks": len(results),
        "triggered": len(triggered),
        "critical_count": len(critical_triggered),
        "high_count": len(high_triggered),
        "results": results,
        "summary": "；".join(summary_parts),
    }


def run_method_risk_scan(
    content: str,
    selected_methods: List[str],
    chapter_title: str = "",
) -> Dict[str, Any]:
    """
    基于用户选择的方法，只检查与方法卡 risk_tags 关联的风险。
    """
    conn = _connect()
    try:
        # 从方法卡获取 risk_tags（在 Python 中解析 JSON，避免依赖 SQLite JSON 扩展）
        placeholders = ",".join("?" for _ in selected_methods)
        rows = conn.execute(
            f"""
            SELECT risk_tags FROM cards
            WHERE cards.type = 'method_card'
            AND (name IN ({placeholders}) OR short_name IN ({placeholders}))
            """,
            selected_methods + selected_methods,
        ).fetchall()
        tags_seen: set = set()
        for r in rows:
            raw = r["risk_tags"]
            if not raw:
                continue
            try:
                tags = json.loads(raw)
                if isinstance(tags, list):
                    tags_seen.update(tags)
            except (json.JSONDecodeError, TypeError):
                pass
        method_risk_tags = sorted(tags_seen)
    finally:
        conn.close()

    if not method_risk_tags:
        return {
            "status": "ok",
            "total_risks": 0,
            "triggered": 0,
            "results": [],
            "summary": "未找到与方法关联的风险标签。",
        }

    # 加载关联的风险卡
    all_cards = load_risk_cards()
    relevant_cards = [
        c for c in all_cards
        if any(tag in c.get("related_method_tags", []) for tag in method_risk_tags)
    ]

    results = []
    for card in relevant_cards:
        result = check_single_risk(card, content, chapter_title=chapter_title)
        results.append(result)

    triggered = [r for r in results if r["triggered"]]

    return {
        "status": "ok",
        "total_risks": len(results),
        "triggered": len(triggered),
        "results": results,
        "summary": f"基于方法 '{'、'.join(selected_methods[:5])}' 检查 {len(results)} 项风险，触发 {len(triggered)} 项",
    }


def format_risk_report(scan_result: Dict[str, Any]) -> str:
    """将扫描结果格式化为可读的风险报告。"""
    if scan_result.get("status") != "ok":
        return f"风险扫描失败：{scan_result.get('summary', '未知错误')}"

    lines = ["# 盲审风险扫描报告", ""]
    lines.append(f"## 概览")
    lines.append(f"- 检查项：{scan_result['total_risks']}")
    lines.append(f"- 触发风险：{scan_result['triggered']}")
    lines.append(f"- 严重风险：{scan_result.get('critical_count', 0)}")
    lines.append(f"- 高风险：{scan_result.get('high_count', 0)}")
    lines.append("")

    if scan_result["triggered"] == 0:
        lines.append("未发现触发风险。")
        return "\n".join(lines)

    lines.append("## 触发的风险")

    for r in scan_result["results"]:
        if not r["triggered"]:
            continue
        severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
        icon = severity_icon.get(r["severity"], "⚪")
        lines.append(f"### {icon} {r['risk_name']} [{r['severity']}]")
        lines.append("")

        if r.get("matched_conditions"):
            lines.append("**匹配的触发条件：**")
            for cond in r["matched_conditions"]:
                lines.append(f"- {cond}")
            lines.append("")

        if r.get("check_questions"):
            lines.append("**检查问题：**")
            for q in r["check_questions"]:
                lines.append(f"- {q}")
            lines.append("")

        if r.get("fix_strategy"):
            lines.append("**修复建议：**")
            for s in r["fix_strategy"]:
                lines.append(f"- {s}")
            lines.append("")

        lines.append("---")

    return "\n".join(lines)


# ============================================================
#  公式校验 — 基于规则检查论文草稿中研究方法公式是否正确
# ============================================================

# 每个方法的公式检查规则：关键词列表，至少匹配一个即算通过
FORMULA_RULES: Dict[str, Dict[str, Any]] = {
    "层次分析法": {
        "aliases": ["AHP", "ahp"],
        "required": [
            # 判断矩阵
            {"patterns": [r"a_{ij}", r"a_\{ij\}", "判断矩阵", "成对比较"],
             "label": "判断矩阵定义"},
            # 权重计算
            {"patterns": [r"w_i", r"w_\{i\}", r"\\prod", "方根法", "特征向量法", "和积法"],
             "label": "权重计算公式"},
            # 一致性检验
            {"patterns": [r"\bCR\b", r"CI\b", r"RI\b", r"\\lambda_\{?\\max\}?", "一致性检验", "一致性比率"],
             "label": "一致性检验（CR/CI/RI）"},
        ],
        "severity": "high",
    },
    "模糊综合评价法": {
        "aliases": ["FCE", "模糊评价", "模糊综合"],
        "required": [
            {"patterns": ["隶属度", "隶属函数", r"r_\{?ij\}?"],
             "label": "隶属度矩阵"},
            {"patterns": [r"B\s*=\s*W", "模糊合成", "综合评价向量", r"b_j"],
             "label": "模糊合成公式"},
        ],
        "severity": "high",
    },
    "熵权法": {
        "aliases": ["EWM", "熵值法"],
        "required": [
            {"patterns": ["标准化", "无量纲化", "归一化", r"x'_"],
             "label": "数据标准化"},
            {"patterns": ["信息熵", r"e_j", r"\\ln", "熵值"],
             "label": "信息熵计算"},
            {"patterns": [r"w_j", "权重", "差异系数"],
             "label": "熵权计算"},
        ],
        "severity": "high",
    },
    "TOPSIS法": {
        "aliases": ["TOPSIS", "topsis", "逼近理想解"],
        "required": [
            {"patterns": ["正理想解", "负理想解", r"A\^\+", r"A\^\-", "理想解"],
             "label": "正负理想解"},
            {"patterns": ["相对贴近度", "贴近度", r"C_i", "欧氏距离"],
             "label": "距离计算或相对贴近度"},
        ],
        "severity": "high",
    },
    "灰色关联分析法": {
        "aliases": ["GRA", "灰色关联", "灰色关联度"],
        "required": [
            {"patterns": ["关联系数", r"\\xi", "关联度", r"r_i", "分辨系数", r"\\rho"],
             "label": "关联系数或关联度公式"},
        ],
        "severity": "medium",
    },
    "回归分析法": {
        "aliases": ["回归", "regression"],
        "required": [
            {"patterns": [r"Y\s*=", r"R\^2", r"R\^\{?2\}?", "回归方程", "回归系数", "F检验", "t检验"],
             "label": "回归方程或拟合指标"},
        ],
        "severity": "medium",
    },
    "FMEA失效模式与影响分析": {
        "aliases": ["FMEA", "fmea", "失效模式"],
        "required": [
            {"patterns": [r"RPN", r"S\s*\\?times\s*O\s*\\?times\s*D", "风险优先数",
                          "严重度.*频度.*检测", "SOD", r"S\s*×\s*O\s*×\s*D"],
             "label": "RPN 风险优先数公式"},
        ],
        "severity": "high",
    },
    "挣值分析": {
        "aliases": ["EVM", "挣值法", "挣值管理"],
        "required": [
            {"patterns": [r"\bEV\b", r"\bAC\b", r"\bPV\b", r"\bCPI\b", r"\bSPI\b",
                          "挣值", "成本偏差", "进度偏差"],
             "label": "挣值指标（EV/AC/PV/CPI/SPI）"},
        ],
        "severity": "medium",
    },
    "统计过程控制": {
        "aliases": ["SPC", "spc", "控制图"],
        "required": [
            {"patterns": [r"UCL", r"LCL", r"C_\{?pk\}?", r"过程能力", "控制上限", "控制下限",
                          r"3\\sigma", r"3σ"],
             "label": "控制限或过程能力指数"},
        ],
        "severity": "medium",
    },
    "关键路径法": {
        "aliases": ["CPM", "cpm", "关键路径"],
        "required": [
            {"patterns": [r"t_e", r"t_o", r"t_p", r"t_m", "三时估计", "浮动时间",
                          r"ES", r"LS", r"EF", r"LF", "关键路径"],
             "label": "三时估计或浮动时间公式"},
        ],
        "severity": "medium",
    },
    "QFD质量功能展开": {
        "aliases": ["QFD", "qfd", "质量屋"],
        "required": [
            {"patterns": [r"W_j", "重要度", "关系矩阵", "质量屋", "需求-技术"],
             "label": "重要度转换或关系矩阵"},
        ],
        "severity": "medium",
    },
    "主成分分析法": {
        "aliases": ["PCA", "pca", "主成分"],
        "required": [
            {"patterns": ["特征值", r"\\lambda", "方差贡献", "累积贡献", "KMO", "Bartlett"],
             "label": "特征值或方差贡献率"},
        ],
        "severity": "medium",
    },
    "DEA数据包络分析": {
        "aliases": ["DEA", "dea", "数据包络"],
        "required": [
            {"patterns": [r"\\theta", r"\\lambda_j", "DMU", "决策单元", "CCR", "BCC",
                          "投入导向", "产出导向", "效率值"],
             "label": "DEA效率模型"},
        ],
        "severity": "high",
    },
    "蒙特卡洛模拟法": {
        "aliases": ["蒙特卡洛", "Monte Carlo", "monte carlo"],
        "required": [
            {"patterns": ["模拟次数", r"N\s*=", "概率分布", "随机抽样",
                          r"\\hat\{\\theta\}", "收敛", "三角分布", "正态分布"],
             "label": "蒙特卡洛模拟公式或参数"},
        ],
        "severity": "medium",
    },
    "因子分析法": {
        "aliases": ["因子分析", "factor analysis"],
        "required": [
            {"patterns": ["因子载荷", r"a_\{?ij\}?", "公因子", "方差贡献", "旋转",
                          "Varimax", "KMO"],
             "label": "因子模型或载荷矩阵"},
        ],
        "severity": "medium",
    },
    "结构方程模型": {
        "aliases": ["SEM", "sem", "结构方程"],
        "required": [
            {"patterns": [r"\\Lambda", r"\\xi", r"\\eta", "测量模型", "结构模型",
                          "RMSEA", "CFI", "GFI", "路径系数", "拟合指标"],
             "label": "测量/结构模型或拟合指标"},
        ],
        "severity": "high",
    },
}


def _resolve_method_name(method: str) -> Optional[str]:
    """将用户搜索/输入的方法名解析为 FORMULA_RULES 中的规范名。"""
    method_lower = method.strip().lower()
    for canon, rule in FORMULA_RULES.items():
        if method_lower == canon.lower():
            return canon
        for alias in rule.get("aliases", []):
            if method_lower == alias.lower():
                return canon
    # 模糊匹配
    for canon in FORMULA_RULES:
        if canon[:4].lower() in method_lower or method_lower in canon.lower():
            return canon
    return None


def check_formula_for_method(content: str, method: str) -> Dict[str, Any]:
    """检查某方法在内容中的公式是否完整。"""
    canon = _resolve_method_name(method)
    if canon is None:
        return {
            "method": method,
            "checked": False,
            "reason": "方法不在公式规则库中",
        }

    rule = FORMULA_RULES[canon]
    import re
    results = []
    for req in rule["required"]:
        matched = any(re.search(p, content) for p in req["patterns"])
        results.append({
            "label": req["label"],
            "matched": matched,
        })

    missing = [r["label"] for r in results if not r["matched"]]
    all_ok = len(missing) == 0

    return {
        "method": canon,
        "checked": True,
        "ok": all_ok,
        "missing": missing,
        "severity": rule["severity"],
        "details": results,
    }


def run_formula_check(
    content: str,
    selected_methods: List[str],
    chapter_title: str = "",
) -> Dict[str, Any]:
    """
    对论文草稿执行公式校验。

    Args:
        content: 章节正文（字符串）
        selected_methods: 用户选择的方法名列表
        chapter_title: 章节标题（用于报告中标注上下文）

    Returns:
        结构化校验结果，格式与 run_risk_scan() 兼容。
    """
    results = []
    for method in selected_methods:
        r = check_formula_for_method(content, method)
        if r.get("checked") and not r.get("ok"):
            results.append({
                "risk_id": f"formula_{r['method']}",
                "risk_name": f"公式不完整: {r['method']}",
                "severity": r.get("severity", "medium"),
                "category": "formula",
                "triggered": True,
                "matched_conditions": [f"缺少 {m}" for m in r["missing"]],
                "evidence": [f"在 {chapter_title or '正文'} 中未找到完整的 {r['method']} 公式。"],
                "check_questions": [f"是否包含了 {r['method']} 的所有核心公式？"] * len(r["missing"]),
                "fix_strategy": [f"补充 {m} 的公式定义和变量说明。" for m in r["missing"]],
                "formula_detail": r,
            })

    triggered = len(results)

    return {
        "status": "ok",
        "total_risks": len(selected_methods),
        "triggered": triggered,
        "results": results,
        "summary": (
            f"公式校验完成：检查 {len(selected_methods)} 个方法，"
            f"发现 {triggered} 个公式不完整"
            if triggered
            else "所有方法公式完整。"
        ),
    }
