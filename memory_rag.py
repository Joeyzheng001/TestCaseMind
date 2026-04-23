#!/usr/bin/env python3
"""
memory_rag.py - 长期记忆向量检索

把 memory_store.py 的长期记忆条目建立向量索引，
每次启动时语义检索"和当前需求最相关的历史经验"，
比全量注入更精准，不会因为记忆条目增多而撑爆 context。

和 kb_rag.py 共用同一个嵌入模型，不额外占用资源。
"""

import json
import hashlib
from pathlib import Path

MEMORY_DIR = Path(__file__).parent / "memory"
INDEX_DIR = Path(__file__).parent / ".memory_index"
LOCAL_MODEL = Path(__file__).parent / "models" / "paraphrase-multilingual-MiniLM-L12-v2"
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class MemoryRAG:
    """长期记忆向量检索器，和 KBRetriever 共用嵌入模型。"""

    def __init__(self):
        self._collection = None
        self._ready = False

    def _lazy_init(self):
        if self._ready:
            return
        import chromadb
        from chromadb.utils import embedding_functions

        INDEX_DIR.mkdir(exist_ok=True)
        model_path = str(LOCAL_MODEL) if LOCAL_MODEL.exists() else EMBED_MODEL

        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model_path
        )
        client = chromadb.PersistentClient(path=str(INDEX_DIR))

        # 检查记忆是否有变化
        current_hash = self._memory_hash()
        hash_file = INDEX_DIR / "memory_hash.txt"
        stored_hash = hash_file.read_text().strip() if hash_file.exists() else ""

        if current_hash != stored_hash:
            self._rebuild(client, ef, current_hash, hash_file)
        else:
            try:
                self._collection = client.get_collection(
                    "memory_index", embedding_function=ef
                )
            except Exception:
                self._rebuild(client, ef, current_hash, hash_file)

        self._ready = True

    def _memory_hash(self) -> str:
        h = hashlib.md5()
        lt_file = MEMORY_DIR / "long_term.json"
        if lt_file.exists():
            h.update(lt_file.read_bytes())
        return h.hexdigest()

    def _rebuild(self, client, ef, current_hash: str, hash_file: Path):
        """把长期记忆所有条目建立向量索引。"""
        try:
            client.delete_collection("memory_index")
        except Exception:
            pass

        self._collection = client.create_collection(
            "memory_index", embedding_function=ef, metadata={"hnsw:space": "cosine"}
        )

        lt_file = MEMORY_DIR / "long_term.json"
        if not lt_file.exists():
            hash_file.write_text(current_hash)
            return

        lt = json.loads(lt_file.read_text(encoding="utf-8"))
        docs, ids, metas = [], [], []

        categories = {
            "domain_patterns": "领域模式",
            "quality_signals": "质量信号",
            "testpoint_hints": "测试点经验",
            "risk_patterns": "风险模式",
        }
        for field, label in categories.items():
            for i, item in enumerate(lt.get(field, [])):
                if not item:
                    continue
                docs.append(f"[{label}] {item}")
                ids.append(f"{field}_{i}")
                metas.append({"category": field, "label": label})

        if docs:
            self._collection.add(documents=docs, ids=ids, metadatas=metas)

        hash_file.write_text(current_hash)

    def search(self, query: str, top_k: int = 6) -> str:
        """
        检索与当前需求最相关的历史经验，返回格式化字符串。
        为空时返回空字符串。
        """
        self._lazy_init()
        if not self._collection or self._collection.count() == 0:
            return ""

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(top_k, self._collection.count()),
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            return ""

        docs = results["documents"][0]
        distances = results["distances"][0]

        # 只取相关度 > 0.4 的条目
        hits = [doc for doc, dist in zip(docs, distances) if (1 - dist) > 0.4]

        if not hits:
            return ""

        lines = ["【相关历史经验（语义检索）】"]
        lines.extend(f"- {h}" for h in hits)
        return "\n".join(lines)

    def invalidate(self):
        """记忆更新后调用，下次检索时重建索引。"""
        hash_file = INDEX_DIR / "memory_hash.txt"
        if hash_file.exists():
            hash_file.unlink()
        self._ready = False
