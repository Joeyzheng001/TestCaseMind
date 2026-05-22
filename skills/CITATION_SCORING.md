# 引用评分技能库

## 评分维度

引用质量评分从五个维度综合评估，加权计算总分。

### 1. 真实性 (35%)
通过 CrossRef API + Semantic Scholar API 交叉验证：
- DOI 是否可解析
- 作者姓名是否匹配记录
- 标题是否与数据库一致
- 被引次数等文献计量数据

### 2. 格式完整 (20%)
GB/T 7714-2015 格式字段完整度检查：
- 期刊文章：作者 · 标题 · 年份 · 期刊名
- 图书：作者 · 标题 · 年份 · 出版社
- 学位论文：作者 · 标题 · 年份 · 授予单位
- 会议论文：作者 · 标题 · 年份 · 会议名称
- 加分项：DOI、ISSN、页码、卷号、期号

### 3. 学术权威 (20%)
- 核心期刊目录匹配（北大核心 / CSSCI / CSCD / SCI / SSCI）
- 期刊影响因子等级
- H-index 和被引量
- 出版社声誉（大学出版社 > 商业出版社 > 自出版）

### 4. 时效性 (15%)
发表年份距今时间：
- ≤3年：满分
- ≤5年：0.9
- ≤10年：0.6
- ≤15年：0.3
- >15年：0.05-0.15 经典文献

### 5. 来源可靠 (10%)
- 同行评审期刊/会议 > 学位论文 > 预印本 > 网络资源
- 撤稿检测（Retraction Watch DB）
- 是否来自已知掠夺性期刊

## 评分等级

| 分数 | 等级 | 含义 |
|-----|------|------|
| 90-100 | A | 权威可信 |
| 75-89 | B | 可用 |
| 60-74 | C | 需人工审核 |
| <60 | D | 不建议引用 |

## 使用方式

```
POST /api/citation-cards/score
POST /api/citation-cards/score-batch
```

单条评分含外部验证（慢但准确），批量评分默认离线模式（快）。

## 参考开源项目

- sciwrite-lint — 23项检查，SciLint Score 评分方法
- bibliography-verification-tool — CrossRef/PubMed 交叉验证 + 模糊匹配
- ref-checker — DOI/Semantic Scholar 双重验证 + 置信度评分
- ReadyCite — ML-based NLI 引用事实核查
- HaRC — 幻觉引用检测（Semantic Scholar/DBLP/Google Scholar）
