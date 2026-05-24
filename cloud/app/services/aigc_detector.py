"""AIGC detection service — rule-based AI-generated content detection."""

from __future__ import annotations

import re
from typing import Any

# AI-generated text indicators
AI_PATTERNS: list[tuple[str, str]] = [
    # Lexical: overused connectors & fillers
    (r"值得注意的是[,，]", "AI高频转折"),
    (r"总的来说[,，]", "AI总结句式"),
    (r"综上所述[,，]", "AI总结句式"),
    (r"此外[,，]", "AI过渡词密度"),
    (r"另外[,，]", "AI过渡词密度"),
    (r"与此同时[,，]", "AI并列过渡"),
    (r"不可忽视的是", "AI强调句式"),
    (r"不容忽视的是", "AI强调句式"),
    (r"需要指出的是", "AI严谨指示词"),
    (r"需要强调的是", "AI严谨指示词"),
    (r"具有重要的意义", "AI空洞表达"),
    (r"具有重要的(理论|现实|实践)意义", "AI空洞表达"),
    (r"具有十分重要的意义", "AI空洞表达"),
    (r"发挥着(至关)?重要的作用", "AI空洞表达"),
    (r"在当今(社会|时代|背景下)", "AI开篇模板"),
    (r"随着[^。]{1,40}的(不断|持续|深入)发展", "AI背景套话"),
    (r"在(新|当前)(时代|形势|阶段)下", "AI时代套话"),
    (r"可以这样说[,，]", "AI口语句式"),
    (r"换句话说[,，]", "AI释义句式"),
    (r"简而言之[,，]", "AI释义句式"),
    (r"毋庸置疑[,，]", "AI断言句式"),
    (r"显而易见[,，]", "AI断言句式"),
    # Syntactic: template sentence structures
    (r"不仅[^。]{1,30}而且", "AI递进句式"),
    (r"既[^。]{1,20}又[^。]{1,20}", "AI并列句式"),
    (r"一方面[^。]{1,30}另一方面", "AI正反句式"),
    (r"首先[^。]{1,20}其次[^。]{1,20}最后", "AI列举模板"),
    (r"第一[,，][^。]{1,20}第二[,，][^。]{1,20}第三", "AI列举模板"),
    (r"通过[^。]{1,30}可以看出", "AI分析句式"),
    (r"通过对[^。]{1,30}的分析", "AI分析句式"),
    (r"为[^。]{1,30}提供了(有力|重要|坚实)的(支撑|依据|保障)", "AI结论套话"),
    # Discourse: paragraph-level patterns
    (r"^本文[^。]{1,50}(旨在|通过|基于|从|以)", "AI论文开篇"),
    (r"^随着[^。]{1,40}，[^。]{1,30}问题(日益|越来越|逐渐)", "AI论文开篇递进"),
    (r"^在[^。]{1,40}的(大背景|背景|语境)下", "AI语境铺垫"),
    # Stylistic
    (r"从某种(意义|程度)上(说|讲)", "AI模糊限定"),
    (r"在一定(程度|意义)上", "AI模糊限定"),
    (r"需要(我们)?(清醒地)?认识到", "AI说教句式"),
    (r"必须(清醒地)?(认识|意识)到", "AI说教句式"),
]

# Human-like indicators
HUMAN_PATTERNS: list[tuple[str, str]] = [
    (r"例如[^，,]{1,30}(项目|案例|企业|公司|单位|部门)", "具体案例引用"),
    (r"(比如|譬如|像)[^，,]{1,30}(项目|案例|企业|公司)", "具体举例"),
    (r"\d{4}年", "时间具体化"),
    (r"\d+年\d+月", "精确时间"),
    (r"(第|该|本)[^，]{1,10}(项目|案例|企业|公司|单位|工程)", "实体指代"),
    (r"(笔者|本人|我们|我)(在|参与|负责|主持)", "亲身参与"),
    (r"(调查|访谈|实地|问卷|走访)了?\d+", "实证数据痕迹"),
    (r"以[^，]{1,20}(项目|工程|企业)为例", "案例详述"),
    (r"(数据|资料|信息)(来源|取自|来自|源于)", "数据来源说明"),
    (r"(如表|见图|如图|见表)[\d一二三四五六七八九十]", "图表引用"),
    (r"(根据|依据|按照)[^，]{1,30}(标准|规范|规定|要求)", "标准规范引用"),
]


def _compute_risk_level(score_per_1k: float) -> str:
    if score_per_1k < 15:
        return "low"
    elif score_per_1k < 35:
        return "medium"
    return "high"


def check_aigc(payload: dict) -> dict[str, Any]:
    chapters = payload.get("chapters", []) or []
    if not chapters:
        return {"status": "error", "message": "暂无已写内容可供检测"}

    total_score = 0
    total_chars = 0
    chapter_results = []

    for ch in chapters:
        content = ch.get("content", "").strip()
        if not content:
            continue
        chars = len(content)
        total_chars += chars

        chapter_score = 0
        results = []
        for pattern, label in AI_PATTERNS:
            matches = list(re.finditer(pattern, content))
            count = len(matches)
            if count > 0:
                density = count / max(chars, 1) * 1000
                triggered = density > 0.15 or count >= 2
                chapter_score += count * 3
                snippets = []
                for m in matches[:3]:
                    start = max(0, m.start() - 20)
                    end = min(len(content), m.end() + 30)
                    snippets.append(content[start:end].replace("\n", " "))
                results.append({
                    "risk_id": f"aigc_{label}",
                    "label": label,
                    "triggered": triggered,
                    "severity": "medium" if triggered else "low",
                    "detail": f"出现 {count} 次（密度 {density:.2f}/千字）",
                    "snippet": " ... ".join(snippets[:2]) if snippets else "",
                })

        for pattern, label in HUMAN_PATTERNS:
            matches = list(re.finditer(pattern, content))
            count = len(matches)
            if count > 0:
                chapter_score -= count * 2
                results.append({
                    "risk_id": f"human_{label}",
                    "label": f"✓ {label}",
                    "triggered": False,
                    "severity": "none",
                    "detail": f"发现 {count} 处具体指代（人工特征）",
                    "snippet": "",
                })

        # Sentence length variance check
        sentences = re.split(r'[。！？；\n]', content)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]
        if len(sentences) >= 3:
            lengths = [len(s) for s in sentences]
            mean_len = sum(lengths) / len(lengths)
            if mean_len > 0:
                variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
                std_dev = variance ** 0.5
                cv = (std_dev / mean_len) * 100
                if cv < 35:
                    chapter_score += 5
                    results.append({
                        "risk_id": "aigc_sentence_uniformity",
                        "label": "句长高度均匀",
                        "triggered": True,
                        "severity": "medium",
                        "detail": f"句长变异系数 {cv:.1f}%（AI文本句长更均匀）",
                        "snippet": "",
                    })

        # Paragraph opening diversity
        paragraphs = [p.strip() for p in content.split("\n") if p.strip() and len(p.strip()) > 20]
        if len(paragraphs) >= 3:
            openings = [p[:6] for p in paragraphs]
            unique_openings = len(set(openings))
            diversity = unique_openings / len(openings)
            if diversity < 0.4:
                chapter_score += 4
                results.append({
                    "risk_id": "aigc_opening_diversity",
                    "label": "段落开头重复",
                    "triggered": True,
                    "severity": "medium",
                    "detail": f"段落开头多样性 {diversity:.1%}（低于40%）",
                    "snippet": "",
                })

        total_score += chapter_score
        score_per_1k = chapter_score / max(chars, 1) * 1000
        risk_level = _compute_risk_level(score_per_1k)

        explanation_parts = []
        if risk_level == "high":
            explanation_parts.append("AIGC风险较高，建议大幅修改句式结构和用词")
        elif risk_level == "medium":
            explanation_parts.append("部分段落存在AI特征，建议适当润色")
        else:
            explanation_parts.append("AIGC风险较低")

        chapter_results.append({
            "title": ch.get("title", ""),
            "score": round(score_per_1k, 1),
            "risk_level": risk_level,
            "highlights": results,
            "explanation": "；".join(explanation_parts),
        })

    avg_score = total_score / max(total_chars, 1) * 1000
    return {
        "status": "ok",
        "overall_score": round(avg_score, 1),
        "overall_risk": _compute_risk_level(avg_score),
        "total_chars": total_chars,
        "results": chapter_results,
    }
