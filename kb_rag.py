#!/usr/bin/env python3
"""
kb_rag.py - 知识库向量检索模块

把 knowledge_base/ 目录下的所有 md 文件建立向量索引，
供 agent.py 的阶段B使用语义检索，精准获取相关知识库内容。

用法:
    from kb_rag import KBRetriever
    retriever = KBRetriever()
    results = retriever.search("持仓数量计算因子", top_k=8)

索引文件保存在 .kb_index/ 目录，知识库文件未变化时直接复用。
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

KB_DIR = Path(__file__).parent / "knowledge_base"
INDEX_DIR = Path(__file__).parent / ".kb_index"

# 每个段落的最大字符数（超过则切分）
CHUNK_SIZE = 800
# 段落间重叠字符数（保持上下文连贯）
CHUNK_OVERLAP = 100
# 默认嵌入模型（本地，无需联网）
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# 本地模型目录（huggingface-cli download 下载后自动使用，无需联网）
LOCAL_MODEL_DIR = (
    Path(__file__).parent / "models" / "paraphrase-multilingual-MiniLM-L12-v2"
)


class KBRetriever:
    """
    知识库语义检索器。
    首次调用时建立向量索引，后续复用。
    """

    def __init__(
        self,
        kb_dir: Path = KB_DIR,
        index_dir: Path = INDEX_DIR,
        embed_model: str = EMBED_MODEL,
    ):
        self.kb_dir = kb_dir
        self.index_dir = index_dir
        self.embed_model = embed_model
        self._client = None
        self._collection = None
        self._ready = False

    def _lazy_init(self):
        """延迟初始化：只在第一次检索时加载模型和索引。"""
        if self._ready:
            return
        try:
            import chromadb
            from chromadb.utils import embedding_functions
        except ImportError:
            print("错误: 请先安装 pip install chromadb sentence-transformers")
            sys.exit(1)

        self.index_dir.mkdir(exist_ok=True)

        # 优先使用本地模型（离线），找不到才用远程名称
        model_path = (
            str(LOCAL_MODEL_DIR) if LOCAL_MODEL_DIR.exists() else self.embed_model
        )
        if LOCAL_MODEL_DIR.exists():
            print(f"  [RAG] 使用本地模型: {LOCAL_MODEL_DIR.name}", flush=True)
        else:
            print(
                f"  [RAG] 本地模型不存在，尝试从网络下载: {self.embed_model}",
                flush=True,
            )
            print(
                f"  [RAG] 建议先运行: HF_ENDPOINT=https://hf-mirror.com huggingface-cli download "
                f"{self.embed_model} --local-dir ./models/{LOCAL_MODEL_DIR.name} "
                f"--local-dir-use-symlinks False",
                flush=True,
            )

        # 用本地 sentence-transformers 模型做嵌入
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model_path
        )

        self._client = chromadb.PersistentClient(path=str(self.index_dir))
        self._ef = ef

        # 检查知识库是否有变化
        current_hash = self._kb_hash()
        hash_file = self.index_dir / "kb_hash.txt"
        stored_hash = hash_file.read_text().strip() if hash_file.exists() else ""

        if current_hash != stored_hash:
            print("  [RAG] 知识库有变化，重建索引...", flush=True)
            self._build_index(ef, current_hash, hash_file)
        else:
            print("  [RAG] 加载已有索引", flush=True)
            self._collection = self._client.get_collection(
                name="kb_index", embedding_function=ef
            )

        self._ready = True

    def _kb_hash(self) -> str:
        """计算知识库所有 md 文件的哈希，用于判断是否需要重建索引。"""
        h = hashlib.md5()
        for f in sorted(self.kb_dir.rglob("*.md")):
            h.update(f.name.encode())
            h.update(str(f.stat().st_mtime).encode())
        return h.hexdigest()

    def _build_index(self, ef, current_hash: str, hash_file: Path):
        """切分知识库文件，建立向量索引。"""
        # 删除旧集合（如果存在）
        try:
            self._client.delete_collection("kb_index")
        except Exception:
            pass

        self._collection = self._client.create_collection(
            name="kb_index", embedding_function=ef, metadata={"hnsw:space": "cosine"}
        )

        # 收集所有段落
        all_docs = []
        all_ids = []
        all_metas = []

        md_files = list(self.kb_dir.rglob("*.md"))
        print(f"  [RAG] 处理 {len(md_files)} 个知识库文件...", flush=True)

        for md_file in sorted(md_files):
            try:
                text = md_file.read_text(encoding="utf-8")
            except Exception:
                continue

            rel_path = str(md_file.relative_to(self.kb_dir))
            chunks = self._split_text(text, md_file.stem)

            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue
                doc_id = f"{rel_path}::{i}"
                all_docs.append(chunk)
                all_ids.append(doc_id)
                all_metas.append(
                    {
                        "source": rel_path,
                        "filename": md_file.name,
                        "chunk_id": i,
                    }
                )

        print(f"  [RAG] 共 {len(all_docs)} 个段落，开始向量化...", flush=True)

        # 分批插入（避免一次性太多）
        batch_size = 100
        for i in range(0, len(all_docs), batch_size):
            self._collection.add(
                documents=all_docs[i : i + batch_size],
                ids=all_ids[i : i + batch_size],
                metadatas=all_metas[i : i + batch_size],
            )
            print(
                f"  [RAG] 已处理 {min(i + batch_size, len(all_docs))}/{len(all_docs)}",
                flush=True,
            )

        hash_file.write_text(current_hash)
        print(f"  [RAG] 索引建立完成", flush=True)

    def _split_text(self, text: str, source_name: str) -> list:
        """
        按 Markdown 标题和段落切分文本。
        优先按 ## / ### 标题切分，保持语义完整性。
        """
        chunks = []

        # 先按二级标题切分
        sections = re.split(r"\n(?=#{1,3} )", text)

        for section in sections:
            if len(section) <= CHUNK_SIZE:
                if section.strip():
                    chunks.append(section.strip())
            else:
                # 长段落进一步按换行切分
                lines = section.splitlines()
                cur_chunk = []
                cur_len = 0
                for line in lines:
                    line_len = len(line)
                    if cur_len + line_len > CHUNK_SIZE and cur_chunk:
                        chunks.append("\n".join(cur_chunk))
                        # 重叠：保留最后几行
                        overlap_lines = []
                        overlap_len = 0
                        for l in reversed(cur_chunk):
                            if overlap_len + len(l) > CHUNK_OVERLAP:
                                break
                            overlap_lines.insert(0, l)
                            overlap_len += len(l)
                        cur_chunk = overlap_lines
                        cur_len = overlap_len
                    cur_chunk.append(line)
                    cur_len += line_len
                if cur_chunk:
                    chunks.append("\n".join(cur_chunk))

        return [c for c in chunks if c.strip()]

    def search(
        self, query: str, top_k: int = 8, filter_source: Optional[str] = None
    ) -> list:
        """
        语义检索知识库，返回最相关的段落列表。

        Args:
            query:         检索查询（需求文档内容摘要或关键词）
            top_k:         返回段落数量
            filter_source: 限制只在某个文件中检索（可选）

        Returns:
            [{"content": str, "source": str, "score": float}, ...]
        """
        self._lazy_init()

        where = {"source": {"$eq": filter_source}} if filter_source else None

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(top_k, self._collection.count()),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            print(f"  [RAG] 检索失败: {e}")
            return []

        hits = []
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0]

        for doc, meta, dist in zip(docs, metas, distances):
            score = 1 - dist  # cosine distance → similarity
            hits.append(
                {
                    "content": doc,
                    "source": meta.get("source", ""),
                    "score": round(score, 4),
                }
            )

        return hits

    def search_for_requirement(self, req_content: str, top_k: int = 10) -> str:
        """
        针对需求文档内容做检索，返回格式化后的知识库上下文字符串。
        供直接插入 prompt 使用。

        Args:
            req_content: 需求文档内容（或摘要）
            top_k:       检索段落数

        Returns:
            格式化的知识库上下文字符串
        """
        # 用需求文档前2000字符作为查询
        query = req_content[:2000]
        results = self.search(query, top_k=top_k)

        if not results:
            return ""

        lines = ["【知识库相关内容（语义检索结果）】\n"]
        prev_source = None
        for hit in results:
            if hit["source"] != prev_source:
                lines.append(
                    f"\n--- 来源: {hit['source']} (相关度: {hit['score']:.2f}) ---"
                )
                prev_source = hit["source"]
            lines.append(hit["content"])

        return "\n".join(lines)

    def rebuild(self):
        """强制重建索引（知识库更新后调用）。"""
        self._ready = False
        hash_file = self.index_dir / "kb_hash.txt"
        if hash_file.exists():
            hash_file.unlink()
        self._lazy_init()


# ── 命令行工具：测试检索效果 ─────────────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(description="知识库 RAG 检索测试")
    parser.add_argument("query", nargs="?", help="检索查询词")
    parser.add_argument("--rebuild", action="store_true", help="强制重建索引")
    parser.add_argument("--top-k", type=int, default=5, help="返回结果数（默认5）")
    args = parser.parse_args()

    retriever = KBRetriever()

    if args.rebuild:
        retriever.rebuild()
        print("索引重建完成")
        return

    if not args.query:
        # 默认测试
        retriever._lazy_init()
        count = retriever._collection.count()
        print(f"知识库索引状态: {count} 个段落已索引")
        print("\n用法: python kb_rag.py '持仓数量因子计算' --top-k 5")
        return

    print(f"\n检索: {args.query}\n{'─' * 50}")
    results = retriever.search(args.query, top_k=args.top_k)
    for i, r in enumerate(results, 1):
        print(f"\n[{i}] 来源: {r['source']}  相关度: {r['score']:.4f}")
        print(r["content"][:300])
        if len(r["content"]) > 300:
            print("...")


if __name__ == "__main__":
    main()
