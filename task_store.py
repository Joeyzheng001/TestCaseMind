"""
task_store.py - s07 Task System

文件持久化任务图，记录四个阶段的执行状态。
每次启动先检查磁盘，已完成的阶段直接跳过，从失败/未完成的阶段续跑。

任务文件: .tasks/<req_stem>_<ts>.json
状态: pending → running → done | failed
"""

import json
import time
from pathlib import Path
from typing import Optional

TASKS_DIR = Path(__file__).parent / ".tasks"
TASKS_DIR.mkdir(exist_ok=True)


class TaskStore:
    STAGES = ["review", "testpoints", "testcases", "export"]

    def __init__(self, req_stem: str, ts: int):
        self.path = TASKS_DIR / f"{req_stem}_{ts}.json"
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
            print(f"  [task] 恢复任务进度: {self.path.name}")
        else:
            self._data = {
                "req_stem": req_stem,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "stages": {
                    s: {
                        "status": "pending",
                        "result": None,
                        "error": None,
                        "updated_at": None,
                    }
                    for s in self.STAGES
                },
            }
            self._save()

    def _save(self):
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def status(self, stage: str) -> str:
        return self._data["stages"][stage]["status"]

    def is_done(self, stage: str) -> bool:
        return self.status(stage) == "done"

    def get_result(self, stage: str):
        return self._data["stages"][stage]["result"]

    def start(self, stage: str):
        self._data["stages"][stage]["status"] = "running"
        self._data["stages"][stage]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._save()

    def done(self, stage: str, result=None):
        self._data["stages"][stage]["status"] = "done"
        self._data["stages"][stage]["result"] = result
        self._data["stages"][stage]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._save()

    def fail(self, stage: str, error: str):
        self._data["stages"][stage]["status"] = "failed"
        self._data["stages"][stage]["error"] = error
        self._data["stages"][stage]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._save()

    def summary(self) -> str:
        parts = []
        icons = {"pending": "○", "running": "→", "done": "✓", "failed": "✗"}
        for s in self.STAGES:
            st = self.status(s)
            parts.append(f"{icons.get(st, '?')} {s}({st})")
        return "  ".join(parts)

    @classmethod
    def find_latest(cls, req_stem: str) -> Optional["TaskStore"]:
        """找到该需求文档最新的未完成任务，用于续跑。"""
        files = sorted(TASKS_DIR.glob(f"{req_stem}_*.json"), reverse=True)
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            stages = data.get("stages", {})
            # 有任意阶段未完成则可续跑
            if any(
                s["status"] in ("pending", "running", "failed") for s in stages.values()
            ):
                # 提取 ts
                ts = int(f.stem.split("_")[-1])
                store = cls.__new__(cls)
                store.path = f
                store._data = data
                return store
        return None
