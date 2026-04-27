#!/usr/bin/env python3
"""
embedding_model.py - 共享嵌入模型单例

kb_rag.py 和 memory_rag.py 共用同一个 SentenceTransformer 实例，
避免重复加载 199MB 模型浪费内存。

用法:
    from embedding_model import get_embedding_function
    ef = get_embedding_function()
"""

from pathlib import Path

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
LOCAL_MODEL_DIR = (
    Path(__file__).parent / "models" / "paraphrase-multilingual-MiniLM-L12-v2"
)

_ef_singleton = None


def get_embedding_function():
    """返回共享的 SentenceTransformerEmbeddingFunction 单例。"""
    global _ef_singleton
    if _ef_singleton is not None:
        return _ef_singleton

    from chromadb.utils import embedding_functions

    model_path = str(LOCAL_MODEL_DIR) if LOCAL_MODEL_DIR.exists() else EMBED_MODEL
    if LOCAL_MODEL_DIR.exists():
        print(f"  [embed] 加载共享模型: {LOCAL_MODEL_DIR.name}", flush=True)
    else:
        print(f"  [embed] 本地模型不存在，尝试从网络下载: {EMBED_MODEL}", flush=True)

    _ef_singleton = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=model_path
    )
    return _ef_singleton
