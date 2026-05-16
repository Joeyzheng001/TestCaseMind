"""
文档转换技能库 - PDF/DOCX 到 Markdown/文本
对应本地知识库入库前的资料清洗流程
"""

---
topics: ["文档转换", "PDF解析", "DOCX解析", "知识库入库", "Markdown"]
tags: ["document-conversion", "pdf", "docx", "markdown", "knowledge-base"]
priority: high
---

# 文档转换技能库

## 目标

将用户放入本地知识库的 PDF、DOCX、Markdown、BibTeX 等资料转换为统一的 Markdown/纯文本，再进入本地向量库。

## 默认流程

1. 扫描 `knowledge_base/` 下的资料文件。
2. 对 `.md`、`.txt`、`.json`、`.bib`、`.yaml` 直接读取文本。
3. 对 `.docx` 使用本地 `python-docx` 提取段落、标题和表格。
4. 对 `.pdf` 使用本地 `pypdf` 或 `PyPDF2` 提取可复制文本。
5. 把转换结果分块、向量化，写入 `knowledge_base/vector_store.sqlite3`。

## 使用原则

- 默认不调用外部 API，保证客户资料不出本机。
- 对扫描版 PDF，不做臆测；如果没有可提取文本，应提示需要 OCR。
- 转换结果优先保留标题层级、页码、段落和表格信息。
- 原始文件不修改，转换出的 Markdown 可放到 `knowledge_base/converted/`。
- 向量库索引时应记录原始文件路径，便于回答时引用来源。

## 推荐工具

- `convert_document`: 将单个 PDF/DOCX/文本文件转换为 Markdown 或 txt。
- `build_knowledge_index`: 扫描本地知识库并构建向量索引。
- `search_knowledge_base`: 从本地向量库检索相关内容。

## 常见失败处理

- PDF 解析库缺失：安装 `requirements.txt` 中的 `pypdf`。
- PDF 无文本：这是扫描件，需要 OCR 模块，不应返回空结果假装成功。
- DOCX 表格复杂：保留为 Markdown 表格，必要时在回答中说明表格结构可能被简化。
- 文件名包含中文或空格：保留原路径，避免重命名破坏用户资料管理。
