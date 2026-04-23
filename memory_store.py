"""
memory_store.py - s09 Memory System

跨会话积累测试经验。
- 长期记忆: memory/long_term.json  —— 跨需求文档的通用规律
- 短期记忆: memory/<req_stem>.json —— 该需求文档的专属经验

长期记忆结构:
  {
    "domain_patterns": ["风控因子类需求通常有主备数据源降级逻辑"],
    "quality_signals": ["需求文档有空占位符时评审分偏低"],
    "testpoint_hints": ["DWD表取值类因子必测: 主源/备源/降级/字段精度"],
    "risk_patterns":   ["IBOR因子与非IBOR因子取值逻辑不同，需对比测试"]
  }
"""

import json
import time
from pathlib import Path

MEMORY_DIR = Path(__file__).parent / "memory"
MEMORY_DIR.mkdir(exist_ok=True)

LONG_TERM_FILE = MEMORY_DIR / "long_term.json"

_LONG_TERM_TEMPLATE = {
    "domain_patterns": [],
    "quality_signals": [],
    "testpoint_hints": [],
    "risk_patterns": [],
    "updated_at": None,
}


class MemoryStore:
    def __init__(self, req_stem: str):
        self.req_stem = req_stem
        self.short_path = MEMORY_DIR / f"{req_stem}.json"
        self._lt = self._load(LONG_TERM_FILE, _LONG_TERM_TEMPLATE)
        self._st = self._load(self.short_path, {})

    def _load(self, path: Path, template: dict) -> dict:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return dict(template)

    def _save_lt(self):
        self._lt["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        LONG_TERM_FILE.write_text(
            json.dumps(self._lt, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _save_st(self):
        self._st["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.short_path.write_text(
            json.dumps(self._st, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── 读取接口 ──────────────────────────────────────────────────────────
    def get_context_for_review(self) -> str:
        """给需求评审子代理的记忆上下文。"""
        parts = []
        if self._lt.get("quality_signals"):
            parts.append(
                "【历史质量规律】\n"
                + "\n".join(f"- {s}" for s in self._lt["quality_signals"][-5:])
            )
        if self._lt.get("domain_patterns"):
            parts.append(
                "【领域模式】\n"
                + "\n".join(f"- {s}" for s in self._lt["domain_patterns"][-5:])
            )
        if self._st.get("last_review_issues"):
            parts.append(
                "【上次评审发现的问题】\n"
                + "\n".join(f"- {s}" for s in self._st["last_review_issues"][:3])
            )
        return "\n\n".join(parts) if parts else ""

    def get_context_for_testpoints(self) -> str:
        """给测试点生成子代理的记忆上下文。"""
        parts = []
        if self._lt.get("testpoint_hints"):
            parts.append(
                "【历史测试点经验】\n"
                + "\n".join(f"- {s}" for s in self._lt["testpoint_hints"][-8:])
            )
        if self._lt.get("risk_patterns"):
            parts.append(
                "【历史风险模式】\n"
                + "\n".join(f"- {s}" for s in self._lt["risk_patterns"][-5:])
            )
        if self._st.get("known_factors"):
            parts.append(
                "【本文档已知因子】\n"
                + "\n".join(f"- {f}" for f in self._st["known_factors"])
            )
        return "\n\n".join(parts) if parts else ""

    # ── 写入接口 ──────────────────────────────────────────────────────────
    def save_after_review(self, review: dict):
        """评审完成后更新记忆。"""
        score = review.get("score", 0)
        issues = review.get("completeness_issues", []) + review.get(
            "consistency_issues", []
        )
        features = review.get("testable_features", [])

        # 更新短期记忆
        self._st["last_score"] = score
        self._st["last_review_issues"] = issues[:5]
        self._st["known_features"] = features
        self._save_st()

        # 更新长期记忆：质量信号
        if score < 60 and issues:
            signal = f"低分需求({score}分)常见问题: {issues[0][:50]}"
            if signal not in self._lt["quality_signals"]:
                self._lt["quality_signals"].append(signal)
                self._lt["quality_signals"] = self._lt["quality_signals"][-20:]
                self._save_lt()

    def save_after_testpoints(self, testpoints: list, review: dict):
        """测试点生成完成后更新记忆。"""
        # 提取因子名（本文档专属）
        factors = list(
            {
                tp.get("functional_module", "")
                for tp in testpoints
                if tp.get("functional_module")
            }
        )
        self._st["known_factors"] = factors
        self._st["testpoint_count"] = len(testpoints)
        self._save_st()

        # 更新长期记忆：测试点规律
        risk_tps = [tp for tp in testpoints if tp.get("source") == "RISK"]
        for tp in risk_tps[:3]:
            hint = f"风险点: {tp.get('test_scenario', '')[:60]}"
            if hint not in self._lt["risk_patterns"]:
                self._lt["risk_patterns"].append(hint)

        # 从风险标记里提取领域模式
        risk_flags = review.get("risk_flags", [])
        for r in risk_flags[:2]:
            pattern = f"[{r.get('type', '?')}] {r.get('desc', '')[:60]}"
            if pattern not in self._lt["domain_patterns"]:
                self._lt["domain_patterns"].append(pattern)

        self._lt["domain_patterns"] = self._lt["domain_patterns"][-30:]
        self._lt["risk_patterns"] = self._lt["risk_patterns"][-30:]
        self._save_lt()

    def save_testpoint_hint(self, hint: str):
        """手动追加一条长期测试点经验。"""
        if hint and hint not in self._lt["testpoint_hints"]:
            self._lt["testpoint_hints"].append(hint)
            self._lt["testpoint_hints"] = self._lt["testpoint_hints"][-30:]
            self._save_lt()
            print(f"  [memory] 记忆已更新: {hint[:60]}")
