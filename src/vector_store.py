"""
本地向量数据库

商业化部署优先保证数据留在本机。当前实现使用 SQLite 持久化文本块、
元数据和本地哈希向量，不依赖外部服务；后续可以替换 embedding 后端。
"""

import hashlib
import json
import math
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from src.document_converter import DOCUMENT_EXTENSIONS, extract_text


DEFAULT_DB_PATH = Path("knowledge_base") / "vector_store.sqlite3"
DEFAULT_SOURCE_DIRS = ["knowledge_base", "skills"]
SUPPORTED_EXTENSIONS = DOCUMENT_EXTENSIONS
VECTOR_DIMENSIONS = 512
EMBEDDING_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
_embedding_model = None
EXCLUDED_SOURCE_PARTS = {
    ".git",
    "__pycache__",
    "templates",
}


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _resolve_path(path: Optional[str], default: Path) -> Path:
    root = _project_root()
    if not path:
        return (root / default).resolve()

    value = Path(path).expanduser()
    resolved = value.resolve() if value.is_absolute() else (root / value).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path outside project is not allowed: {path}") from exc
    return resolved


def _dedupe_lines(text: str) -> str:
    """去除连续重复的行（PDF水印/页眉页脚污染常见）"""
    lines = text.splitlines()
    deduped = []
    prev = None
    repeat_count = 0
    for line in lines:
        stripped = line.strip()
        if stripped == prev:
            repeat_count += 1
            if repeat_count > 3:
                continue
        else:
            repeat_count = 0
            prev = stripped
        deduped.append(line)
    return "\n".join(deduped)


def _clean_text(text: str) -> str:
    """
    清理 PDF/DOCX 抽取时偶发的非法 Unicode 代理字符，
    并去除重复行（水印/页眉页脚污染）。

    某些 PDF 字体映射会产生 lone surrogate，SQLite 和 UTF-8 hash 都无法
    稳定处理它们；这里用替换字符兜底，保证单篇文档不会拖垮整库索引。
    """
    if not text:
        return ""
    text = text.encode("utf-8", errors="replace").decode("utf-8")
    text = _dedupe_lines(text)
    return text


def _extract_keywords(text: str) -> List[str]:
    """
    从查询文本中提取有意义的关键词，用于强召回加权。
    中文2-4字词组 + 英文单词 + 英文缩写（大写2-6字母）。
    """
    keywords = []
    # 英文缩写 如 DID, PDCA, SWOT, AHP
    for m in re.finditer(r"\b[A-Z]{2,6}\b", text):
        keywords.append(m.group(0))
    # 英文单词
    for m in re.finditer(r"\b[a-zA-Z]{4,}\b", text.lower()):
        keywords.append(m.group(0))
    # 中文2-4字词组
    for m in re.finditer(r"[一-鿿]{2,4}", text):
        keywords.append(m.group(0))
    # 去重
    seen = set()
    unique = []
    for kw in keywords:
        if kw.lower() not in seen:
            seen.add(kw.lower())
            unique.append(kw)
    return unique


def _tokenize(text: str) -> List[str]:
    """
    分词：中文识别2-4字词组，英文保留单词。
    不再使用字符级 bigram，避免维度爆炸和稀疏。
    """
    tokens = []
    for match in re.finditer(r"[a-zA-Z0-9_]{2,}|[一-鿿]{2,4}", text.lower()):
        tokens.append(match.group(0))
    return tokens


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        except Exception:
            return None
    return _embedding_model


def embed_text(text: str, dimensions: int = VECTOR_DIMENSIONS) -> List[float]:
    model = _get_embedding_model()
    if model is not None:
        try:
            embedding = model.encode([text], normalize_embeddings=True)
            return embedding[0].tolist()
        except Exception:
            pass

    vector = [0.0] * dimensions
    for token in _tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(left: List[float], right: List[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def _is_garbage_chunk(text: str) -> bool:
    """
    检测质量过低的 chunk：乱码、数字占比过高、表格碎片、PDF 编码污染。

    返回 True 表示应该丢弃该 chunk。
    """
    if not text or len(text) < 20:
        return True

    # 1. PDF CID 字体编码污染：/GXX 十六进制字形序列
    if re.search(r"/G[0-9A-Fa-f]{2,}", text):
        return True

    # 2. 混合乱码：老挝语、泰文、高棉语等非预期 Unicode 区块
    garbled_chars = len(re.findall(
        r"[຀-໿ༀ-࿿က-႟ក-៿᧠-᧿"
        r"-​-‏ - ﻿]",
        text,
    ))
    if garbled_chars > len(text) * 0.15:
        return True

    # 3. 中英文字符占比过低（纯数字/符号/表格碎片）
    cjk_alpha = len(re.findall(r"[一-鿿㐀-䶿a-zA-Z]", text))
    total = len(text.replace(" ", "").replace("\n", ""))
    if total > 0 and cjk_alpha / max(total, 1) < 0.25:
        return True

    # 4. 管道符表格碎片（>10 个 | 且无实质中文）
    pipe_count = text.count("|")
    if pipe_count > 10 and cjk_alpha < 30:
        return True

    # 5. 连续重复字符过多（PDF 乱码常产生 "AAAA" "=====" 类模式）
    repeats = [m.group() for m in re.finditer(r"(.)\1{8,}", text)]
    repeat_total = sum(len(m) for m in repeats)
    if repeat_total > len(text) * 0.3:
        return True

    return False


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> List[str]:
    """将文档切成重叠文本块，过滤低质量 chunk。"""
    clean = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not clean:
        return []

    if len(clean) <= chunk_size:
        return [clean] if not _is_garbage_chunk(clean) else []

    chunks = []
    start = 0
    while start < len(clean):
        end = min(start + chunk_size, len(clean))
        chunk = clean[start:end].strip()
        if chunk and not _is_garbage_chunk(chunk):
            chunks.append(chunk)

        if end == len(clean):
            break
        start = max(end - overlap, start + 1)

    return chunks


class LocalVectorStore:
    """SQLite 本地向量库。"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = _resolve_path(db_path, DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.connection.close()

    def _init_schema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE,
                title TEXT,
                content_hash TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                vector_json TEXT NOT NULL,
                token_count INTEGER NOT NULL,
                FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
            """
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id)"
        )
        self.connection.commit()

    def clear(self) -> None:
        self.connection.execute("DELETE FROM chunks")
        self.connection.execute("DELETE FROM documents")
        self.connection.commit()

    def upsert_document(
        self,
        file_path: Path,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: int = 900,
        overlap: int = 120,
    ) -> int:
        content = _clean_text(content)
        relative_path = str(file_path.relative_to(_project_root()))
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        title = _extract_title(content, file_path)
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)

        existing = self.connection.execute(
            "SELECT id, content_hash FROM documents WHERE path = ?", (relative_path,)
        ).fetchone()

        if existing and existing["content_hash"] == content_hash:
            return 0

        if existing:
            document_id = existing["id"]
            self.connection.execute(
                """
                UPDATE documents
                SET title = ?, content_hash = ?, metadata_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (title, content_hash, metadata_json, document_id),
            )
            self.connection.execute(
                "DELETE FROM chunks WHERE document_id = ?", (document_id,)
            )
        else:
            cursor = self.connection.execute(
                """
                INSERT INTO documents (path, title, content_hash, metadata_json)
                VALUES (?, ?, ?, ?)
                """,
                (relative_path, title, content_hash, metadata_json),
            )
            document_id = cursor.lastrowid

        chunks = chunk_text(content, chunk_size=chunk_size, overlap=overlap)
        for index, chunk in enumerate(chunks):
            vector = embed_text(chunk)
            self.connection.execute(
                """
                INSERT INTO chunks
                    (document_id, chunk_index, content, vector_json, token_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    index,
                    chunk,
                    json.dumps(vector),
                    len(_tokenize(chunk)),
                ),
            )

        self.connection.commit()
        return len(chunks)

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        query_vector = embed_text(query)
        rows = self.connection.execute(
            """
            SELECT
                chunks.id,
                chunks.chunk_index,
                chunks.content,
                chunks.vector_json,
                chunks.token_count,
                documents.path,
                documents.title,
                documents.metadata_json
            FROM chunks
            JOIN documents ON documents.id = chunks.document_id
            """
        ).fetchall()

        results = []
        for row in rows:
            vector = json.loads(row["vector_json"])
            score = cosine_similarity(query_vector, vector)
            if score <= 0:
                continue

            results.append(
                {
                    "score": round(score, 4),
                    "path": row["path"],
                    "title": row["title"],
                    "chunk_index": row["chunk_index"],
                    "content": row["content"],
                    "token_count": row["token_count"],
                    "metadata": json.loads(row["metadata_json"]),
                }
            )

        # 关键词强召回：对包含查询关键词的 chunk 额外加权
        query_keywords = _extract_keywords(query)
        if query_keywords:
            for r in results:
                content_lower = r["content"].lower()
                keyword_hits = sum(
                    1 for kw in query_keywords if kw.lower() in content_lower
                )
                if keyword_hits > 0:
                    hit_ratio = keyword_hits / len(query_keywords)
                    r["score"] = round(r["score"] * (1.0 + 0.5 * hit_ratio), 4)

        results.sort(key=lambda item: item["score"], reverse=True)
        return results[: max(limit, 1)]

    def stats(self) -> Dict[str, Any]:
        documents = self.connection.execute(
            "SELECT COUNT(*) AS count FROM documents"
        ).fetchone()["count"]
        chunks = self.connection.execute(
            "SELECT COUNT(*) AS count FROM chunks"
        ).fetchone()["count"]
        return {
            "db_path": str(self.db_path),
            "documents": documents,
            "chunks": chunks,
            "embedding": EMBEDDING_MODEL_NAME if _get_embedding_model() is not None else "local_hash",
            "dimensions": VECTOR_DIMENSIONS,
        }


def _extract_title(content: str, file_path: Path) -> str:
    in_front_matter = False
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped in {'"""', "'''"}:
            continue
        if stripped == "---":
            in_front_matter = not in_front_matter
            continue
        if in_front_matter:
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
        if not stripped.startswith(("topics:", "tags:", "priority:")):
            return stripped[:80]
    return file_path.stem


def _iter_source_files(source_dirs: Iterable[str]) -> Iterable[Path]:
    root = _project_root()
    for source_dir in source_dirs:
        base = _resolve_path(source_dir, Path(source_dir))
        if not base.exists():
            continue

        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if EXCLUDED_SOURCE_PARTS.intersection(path.relative_to(base).parts):
                continue
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            if path.name.startswith("."):
                continue
            if path.resolve() == (root / DEFAULT_DB_PATH).resolve():
                continue
            yield path


def build_index(
    source_dirs: Optional[List[str]] = None,
    db_path: Optional[str] = None,
    reset: bool = False,
    progress_callback: Optional[Callable[[int, int, Path], None]] = None,
) -> Dict[str, Any]:
    store = LocalVectorStore(db_path=db_path)
    try:
        if reset:
            store.clear()

        indexed_files = 0
        indexed_chunks = 0
        skipped_files = 0
        errors = []
        source_files = list(_iter_source_files(source_dirs or DEFAULT_SOURCE_DIRS))
        total_files = len(source_files)

        for file_index, file_path in enumerate(source_files, 1):
            try:
                content = extract_text(file_path)
            except Exception as exc:
                skipped_files += 1
                errors.append({"path": str(file_path), "error": str(exc)})
                if progress_callback:
                    progress_callback(file_index, total_files, file_path)
                continue

            chunks = store.upsert_document(
                file_path,
                content,
                metadata={
                    "source": str(file_path.parent.name),
                    "file_type": file_path.suffix.lower().lstrip("."),
                },
            )
            indexed_files += 1
            indexed_chunks += chunks
            if progress_callback:
                progress_callback(file_index, total_files, file_path)

        stats = store.stats()
        stats.update(
            {
                "indexed_files": indexed_files,
                "indexed_chunks": indexed_chunks,
                "skipped_files": skipped_files,
                "errors": errors[:20],
            }
        )
        return stats
    finally:
        store.close()


def search_index(
    query: str,
    limit: int = 5,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    store = LocalVectorStore(db_path=db_path)
    try:
        return {
            "query": query,
            "results": store.search(query, limit=limit),
            "stats": store.stats(),
        }
    finally:
        store.close()
