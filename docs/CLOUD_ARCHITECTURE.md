# ThesisMind 混合云端架构设计

## 1. 整体拓扑

```
┌─ 用户本机 (localhost:8765) ─────────────────────────┐
│                                                       │
│  浏览器 ── web_server.py (Python stdlib HTTP)          │
│   ├── 论文草稿 / 大纲 / 项目管理（本地 SQLite）         │
│   ├── LLM 扩写改写（用户 key，直连 DeepSeek/Claude）    │
│   ├── 方法卡片（cards.sqlite3，本地随包）               │
│   ├── 公式渲染 / Word PDF 导出（matplotlib）            │
│   ├── 基础格式检查                                     │
│   │                                                    │
│   └── HTTPS ──────────────── 调云端 API ──────────┐    │
│                                                     │    │
└─────────────────────────────────────────────────────┼────┘
                                                      │
                                                      ▼
┌─ 云端服务 (api.thesismind.com) ──────────────────────────┐
│                                                          │
│   FastAPI (Python 3.10+)                                  │
│   ├── POST /v1/license/validate      鉴权+签名响应       │
│   ├── POST /v1/trial/start           开始试用             │
│   ├── POST /v1/account/register      注册                 │
│   ├── POST /v1/knowledge/search      知识库语义检索       │
│   ├── POST /v1/ppt/generate          PPT 生成（任务式）   │
│   ├── POST /v1/blind-review           盲审检查            │
│   ├── POST /v1/aigc/check             AIGC 检测           │
│   ├── GET  /v1/release/latest        前端更新版本+URL     │
│   ├── GET  /v1/cards/version         卡片版本号           │
│   ├── GET  /v1/cards/delta           增量卡片（P2）       │
│   │                                                      │
│   └── PostgreSQL 16                                       │
│       ├── users              (id, email, created_at)      │
│       ├── licenses           (tier, features, expiry)     │
│       ├── activations        (device_id, bound_at)        │
│       ├── trials             (email, device_id, used)     │
│       ├── release_versions   (version, url, sha256)       │
│       ├── audit_logs         (action, actor, result)      │
│       └── ppt_tasks          (task state, result_url)     │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**铁律：论文草稿、大纲、项目内容、用户 API key 永不上传云端。数据流只出不进（本地→云端不传论文）。**

---

## 2. 云端 FastAPI 项目结构

```
cloud/
├── pyproject.toml           # Python 项目配置
├── alembic.ini              # DB 迁移配置
├── alembic/
│   └── versions/            # 迁移脚本
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app 入口
│   ├── config.py            # 配置（环境变量）
│   ├── dependencies.py      # FastAPI Depends（auth/DB session）
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py          # User ORM
│   │   ├── license.py       # License ORM
│   │   ├── activation.py    # Activation ORM
│   │   ├── trial.py         # Trial ORM
│   │   ├── release.py       # ReleaseVersion ORM
│   │   └── audit.py         # AuditLog ORM
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── license.py       # LicenseValidate request/response
│   │   ├── trial.py         # TrialStart request/response
│   │   ├── release.py       # ReleaseLatest response
│   │   └── common.py        # ErrorResponse, HealthResponse
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── license.py       # POST /v1/license/validate
│   │   ├── trial.py         # POST /v1/trial/start
│   │   ├── account.py       # POST /v1/account/*
│   │   ├── knowledge.py     # POST /v1/knowledge/search
│   │   ├── ppt.py           # POST /v1/ppt/generate + task poll
│   │   ├── review.py        # POST /v1/blind-review
│   │   ├── aigc.py          # POST /v1/aigc/*
│   │   ├── release.py       # GET /v1/release/latest
│   │   └── cards.py         # GET /v1/cards/version + /delta
│   ├── services/
│   │   ├── __init__.py
│   │   ├── license_signer.py    # Ed25519 签名逻辑
│   │   ├── trial_manager.py     # 试用期管理
│   │   ├── activation_manager.py # 设备绑定
│   │   ├── knowledge_search.py  # 向量检索
│   │   └── ppt_engine.py        # PPT 生成（从本地迁移）
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py      # Ed25519 验签/签发
│   │   ├── database.py      # SQLAlchemy engine + session
│   │   └── rate_limit.py    # 限流中间件
│   └── tests/
│       ├── conftest.py
│       ├── test_license.py
│       ├── test_trial.py
│       └── test_release.py
├── Dockerfile
├── docker-compose.yml       # app + postgres + redis(optional)
└── .env.example
```

---

## 3. API 设计

### 3.1 鉴权校验

```
POST /v1/license/validate

Request:
{
    "license_code": "TM-XXXX-XXXX-XXXX",   // 用户输入的激活码
    "device_id": "a1b2c3d4e5f6",           // 本地生成的设备指纹
    "client_version": "1.5.2",             // 客户端版本号
    "email": "user@example.com"            // 可选，用于绑定校验
}

Response (200):
{
    "status": "valid",                     // valid | expired | revoked | device_limit | not_found
    "tier": "pro",                         // free | basic | pro | vip
    "tier_label": "畅想版",
    "features": ["workflow", "advanced"],
    "expires_at": "2026-06-15T00:00:00Z",
    "device_limit": 2,
    "device_count": 1,
    "revoked": false,
    "user_email": "user@example.com",
    "signature": "ed25519:AbCdEf123456...", // Ed25519 签名覆盖以上所有字段
    "signed_at": "2026-05-22T08:00:00Z"
}

Response (401):
{
    "status": "invalid",
    "message": "许可证无效或已过期",
    "code": "LICENSE_EXPIRED"
}
```

**签名机制：**
- 云端用私钥签名 `status|tier|features|expires_at|device_limit|device_count|revoked|user_email|signed_at` 拼接字符串
- 本地用内置公钥验证 `ed25519:` 前缀签名
- 验签失败 → 基础版降级
- 响应中不含 HMAC，本地不内置 HMAC secret

### 3.2 试用期

```
POST /v1/trial/start

Request:
{
    "email": "user@example.com",
    "device_id": "a1b2c3d4e5f6"
}

Response (200):
{
    "status": "started",                   // started | already_used | rejected
    "trial_days_left": 3,
    "trial_end": "2026-05-25T00:00:00Z",
    "features": ["workflow"],
    "signature": "ed25519:..."
}

Response (409):
{
    "status": "already_used",
    "message": "此邮箱已参与过试用",
    "code": "TRIAL_ALREADY_USED"
}
```

**试用规则（云端执行）：**
- email + device_id 组合唯一，一个 email 最多绑定 2 个 device
- 同一 device_id 换 email 也会校验
- 试用期 3 天，从首次 trial/start 起算
- 到期自动标记 expired，不可续试
- 云端记录 audit_log: trial_start / trial_expire

### 3.3 设备绑定

设备绑定不单独提供 API。在 `/v1/license/validate` 中隐式完成：
- 首次 validate 时记录 device_id → activations 表
- device_count 超 device_limit 返回 status "device_limit"
- 管理后台可解绑旧设备

### 3.4 前端更新

```
GET /v1/release/latest

Response (200):
{
    "version": "1.5.3",
    "release_date": "2026-05-22",
    "url": "https://cdn.thesismind.com/releases/web-1.5.3.zip",
    "sha256": "abc123def456...",
    "signature": "ed25519:...",
    "changelog": "- 修复 XXX bug\n- 新增 YYY 功能\n",
    "min_client_version": "1.5.0"          // 最低兼容版本
}
```

**本地更新流程：**
1. 启动时调 GET /v1/release/latest
2. 比对本地 `web/version.txt` 中的版本号
3. 落后 → 下载 zip 到临时目录
4. 校验 SHA256
5. 验签 Ed25519（失败则丢弃）
6. 备份当前 `web/` → `web.backup/`
7. 解压覆盖 `web/`
8. 更新 `web/version.txt`
9. 启动服务
10. 解压/覆盖失败 → 回滚 `web.backup/` → 继续启动

### 3.5 知识库检索

```
POST /v1/knowledge/search

Request:
{
    "query": "层次分析法 判断矩阵",
    "top_k": 5,
    "license_ticket": "ed25519:..."      // 来自最近一次 validate 的签名
}

Response (200):
{
    "results": [
        {
            "title": "层次分析法步骤",
            "path": "methods/ahp.md",
            "content": "...",
            "score": 0.92
        }
    ]
}
```

**license_ticket 校验：**
- 本地每次 POST 高价值 API 时，附带最近一次 license validate 签名响应
- 服务端验签后处理请求
- 验签失败 → 401

### 3.6 PPT 生成

```
POST /v1/ppt/generate

Request:
{
    "ppt_type": "defense",                // proposal | midterm | defense
    "outline": {...},                     // 大纲结构（不含正文内容）
    "design_spec": {...},                 // 设计规格（可选）
    "license_ticket": "ed25519:..."
}

Response (200):
{
    "task_id": "uuid-xxxx",
    "status": "queued"
}

GET /v1/ppt/task/{task_id}

Response (200):
{
    "task_id": "uuid-xxxx",
    "status": "running",                  // queued | running | done | failed
    "progress": 65,
    "message": "正在生成第 8/12 页幻灯片…",
    "download_url": null                  // done 时返回下载链接
}

Response (200, status=done):
{
    "task_id": "uuid-xxxx",
    "status": "done",
    "progress": 100,
    "message": "PPT 生成完成",
    "download_url": "https://cdn.thesismind.com/ppt/uuid-xxxx.pptx",
    "expires_in": 3600                    // 下载链接 1 小时有效
}
```

### 3.7 盲审 / AIGC

```
POST /v1/blind-review
POST /v1/aigc/check
POST /v1/aigc/reduce

Request:
{
    "content": "...",                     // 待检测文本（仅在服务端处理，不持久化）
    "license_ticket": "ed25519:..."
}

Response (200):
{
    "report": {...}                       // 检测报告
}
```

---

## 4. 数据库 Schema

```sql
-- ============================================================
-- 用户表：仅存 email，不存密码（首次激活自动注册）
-- ============================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    display_name    VARCHAR(128),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ               -- soft delete
);
CREATE INDEX idx_users_email ON users (email);

-- ============================================================
-- 许可证表：一个用户可有多个 license（续费/升级产生新记录）
-- ============================================================
CREATE TABLE licenses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    license_code    VARCHAR(64) NOT NULL UNIQUE,  -- TM-XXXX-XXXX-XXXX
    tier            VARCHAR(16) NOT NULL,          -- free | basic | pro | vip | admin
    features        JSONB NOT NULL DEFAULT '[]',   -- ["workflow", "advanced"]
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL,
    device_limit    INT NOT NULL DEFAULT 1,
    revoked         BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at      TIMESTAMPTZ,
    revoked_reason  VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_licenses_user ON licenses (user_id);
CREATE INDEX idx_licenses_code ON licenses (license_code);
CREATE INDEX idx_licenses_expires ON licenses (expires_at) WHERE revoked = FALSE;

-- ============================================================
-- 激活记录表：每次新设备激活写入一行
-- ============================================================
CREATE TABLE activations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    license_id      UUID NOT NULL REFERENCES licenses(id),
    device_id       VARCHAR(128) NOT NULL,
    client_version  VARCHAR(32),
    ip_address      INET,
    activated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    deactivated_at  TIMESTAMPTZ,
    UNIQUE (license_id, device_id)
);
CREATE INDEX idx_activations_license ON activations (license_id);
CREATE INDEX idx_activations_device ON activations (device_id);

-- ============================================================
-- 试用表：记录试用申请，防重复
-- ============================================================
CREATE TABLE trials (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL,
    device_id       VARCHAR(128) NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL,
    status          VARCHAR(16) NOT NULL DEFAULT 'active', -- active | expired
    UNIQUE (email, device_id)
);
CREATE INDEX idx_trials_email ON trials (email);
CREATE INDEX idx_trials_device ON trials (device_id);

-- ============================================================
-- 发布版本表：用于客户端自动更新
-- ============================================================
CREATE TABLE release_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version         VARCHAR(32) NOT NULL UNIQUE,   -- "1.5.3"
    release_date    DATE NOT NULL,
    download_url    VARCHAR(512) NOT NULL,
    sha256          VARCHAR(64) NOT NULL,
    changelog       TEXT,
    min_client_version VARCHAR(32),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 审计日志：关键操作留痕
-- ============================================================
CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action          VARCHAR(64) NOT NULL,          -- license_validate, trial_start, ppt_generate...
    actor_type      VARCHAR(16) NOT NULL,          -- user | system | admin
    actor_id        UUID,                          -- users.id or NULL for system
    device_id       VARCHAR(128),
    ip_address      INET,
    metadata        JSONB,
    result          VARCHAR(16) NOT NULL,          -- success | failure | denied
    error_reason    VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_action ON audit_logs (action);
CREATE INDEX idx_audit_actor ON audit_logs (actor_id);
CREATE INDEX idx_audit_created ON audit_logs (created_at);
```

---

## 5. 本地 LicenseManager 改造方案

### 5.1 当前状态

`src/license_manager.py` 目前是**全功能本地 LicenseManager**，包含：
- Ed25519 签名签发（`generate_license`, `_sign_payload`）  ← 云端操作，本地不该有
- Ed25519 签名验证（`_verify_signature`）                   ← 保留
- HMAC 兼容层（`legacy_secret_key`）                        ← 删除
- 本地文件读写（`.license`, `.license_history.json`）        ← 降级为缓存
- 设备指纹（`machine_id` → uuid.getnode()）                 ← 保留
- 5 级授权体系（`LICENSE_TYPES`）                           ← 保留（作为 fallback 参考）
- `can_access_api` / `can_access_menu`                      ← 保留（本地功能门控）

### 5.2 改造后状态

```
src/license_manager.py  改造目标：

保留：
  - Ed25519 公钥加载（只读配置文件/环境变量）
  - _verify_signature()  验签
  - machine_id()          设备指纹
  - LICENSE_TYPES         功能分层定义
  - can_access_api()      本地功能门控（读缓存 features）
  - can_access_menu()     同上

删除：
  - _load_private_key_from_env()
  - generate_license()           签发 → 云端
  - HMAC legacy 兼容层          安全隐患
  - _sign_payload()              签发 → 云端

新增：
  - validate_with_cloud()        调 POST /v1/license/validate
  - _cache_license_state()       缓存签名响应到本地文件
  - _load_cached_license()       从缓存加载
  - _is_cache_valid()            24h 缓存校验
  - start_trial()                调 POST /v1/trial/start
  - get_cloud_base_url()         读取云端 API 地址
```

### 5.3 核心函数签名

```python
class LicenseManager:
    CLOUD_BASE_URL = "https://api.thesismind.com"  # 可环境变量覆盖
    CACHE_TTL_HOURS = 24
    PUBLIC_KEY_ENV = "THESISMIND_LICENSE_PUBLIC_KEY"

    def validate_with_cloud(self, license_code: str, email: str = "") -> Dict:
        """POST /v1/license/validate → 验签 → 缓存 → 返回状态"""
        ...

    def start_trial(self, email: str) -> Dict:
        """POST /v1/trial/start → 验签 → 缓存 → 返回状态"""
        ...

    def get_effective_status(self) -> Dict:
        """优先读缓存，缓存过期调 cloud 刷新，cloud 不可用降级基础版"""
        ...

    def _is_cache_valid(self) -> bool:
        """缓存存在 + 未超过 24h + 签名验证通过"""
        ...

    def can_access_api(self, api_path: str, method: str = "GET") -> bool:
        """读缓存 features 列表 + 公共 API 白名单判断"""
        ...
```

---

## 6. 本地启动流程

```
web_server.py main() 启动
│
├── 1. _init_user_data_root()           # 初始化本地目录
├── 2. _load_public_key()               # 加载环境变量中的 Ed25519 公钥
├── 3. _rebuild_cards_from_source()      # 重建卡片库（纯本地）
│
├── 4. _check_license()                  # ← 核心改点
│   ├── 有 license_code?
│   │   ├── 是 → manager.validate_with_cloud(code, email)
│   │   │       ├── cloud 可达 + 验签通过 → 缓存 24h → 激活对应 features
│   │   │       ├── cloud 可达 + 验签失败 → 警告 → 基础版
│   │   │       └── cloud 不可达 → 读本地缓存
│   │   │           ├── 缓存有效 (<24h) → 使用缓存
│   │   │           └── 缓存无效/不存在 → 基础版降级
│   │   └── 否 → 提示试用/激活 → 基础版（只开放基础功能）
│   │
│   └── 设置全局 license_state = {tier, features, expires_at, cache_valid_until}
│
├── 5. _check_update()                  # ← 新增
│   ├── GET /v1/release/latest
│   ├── 版本不落后 → 跳过
│   ├── 版本落后 → 下载 zip → SHA256 校验 → 签名验签
│   │   ├── 全部通过 → 备份 web/ → 解压覆盖 → 更新 version.txt
│   │   └── 任一步失败 → 保留旧版 → 日志警告 → 继续启动
│   └── 非关键路径，cloud 不可达时跳过
│
├── 6. 启动 HTTP 服务
│
└── 运行时 API 鉴权
    ├── 公开 API（/api/config, /api/license/status）→ 放行
    ├── 基础 API（/api/expand, /api/outline...）→ workflow feature
    ├── 高级 API（/api/ppt/generate...）
    │   ├── feature 已激活 → POST 云端 API，附 license_ticket
    │   │   └── 云端二次验签（防本地伪造 ticket）→ 执行 → 返回结果
    │   └── feature 未激活 → 403
    └── license 页面 → 始终可访问
```

---

## 7. 失败降级策略

| 场景 | 降级行为 | 用户看到 |
|------|---------|---------|
| 云端不可达（启动时） | 读本地缓存，缓存过期→基础版 | "无法连接授权服务器，基础功能可用" |
| 云端不可达（运行时） | 基础功能正常，高价值功能灰掉 | 功能按钮置灰 + tooltip"需要联网校验" |
| 缓存签名验证失败 | 丢弃缓存，降级基础版 | "许可证状态异常，已降级为基础版" |
| License 过期 | 基础版，高价值功能停用 | "许可证已过期，点击续费" |
| 激活码无效 | 基础版 | "激活码无效，请检查后重试" |
| 设备数超限 | 当前设备降级，旧设备正常 | "设备数已达上限（2/2），请解绑旧设备" |
| 前端更新下载失败 | 保留旧版，正常启动 | 日志警告，用户无感 |
| 前端更新 SHA256 不匹配 | 丢弃下载，保留旧版 | 日志警告 |
| 前端更新签名不匹配 | 丢弃下载，保留旧版 | 日志警告（防篡改） |
| 知识库 API 超时 (>3s) | Fallback 空结果，继续扩写 | "知识库暂不可用，已继续生成" |
| PPT 生成云端失败 | 返回错误 | "PPT 生成失败，请稍后重试" |
| web.backup/ 回滚失败 | 不阻止启动，记录错误 | 日志错误 |

**核心原则：任何云端故障不阻止本地基础功能启动。**

---

## 8. 安全风险与缓解

| 风险 | 等级 | 攻击面 | 缓解 |
|------|------|--------|------|
| 本地公钥被替换 | 高 | 用户/攻击者改 `.env` 中的公钥为自己生成的密钥对，配合自签 license | **无法完全防御**。但高价值功能云端执行 + license_ticket 云端二次验签，替换公钥只能解锁本地基础功能（workflow），解锁不了 PPT/盲审/AIGC |
| license_ticket 重放 | 中 | 抓包截取有效 ticket，修改请求参数重放 | ticket 绑定时间窗口（5min）+ 请求体哈希，服务端校验 freshness |
| 设备指纹伪造 | 中 | 改 `uuid.getnode()` 返回值 | 不做唯一依据，配合 email 绑定 + IP 异常检测 |
| 本地缓存文件篡改 | 低 | 直接编辑缓存 json，加 features/tier | 缓存带签名，启动时验签，失败丢弃 |
| 前端更新包被中间人篡改 | 高 | DNS 劫持 + 替换下载 URL | SHA256 + Ed25519 双重校验，任一失败不安装 |
| 云端数据库泄露 | 低 | 仅存 email+license，无论文数据 | DB 加密 + HTTPS only + 最小权限原则 |
| brute-force 激活码 | 低 | 遍历 license_code 空间 | 限流 5次/IP/小时，失败记录 audit_log |
| 旧版客户端绕过验证 | 中 | 用老版本不调 cloud API | min_client_version 强制升级；cloud 可拒绝对过旧版本签发 ticket |

**根本安全边界：真正需要保护的能力（PPT/盲审/AIGC/知识库检索）在云端执行，本地代码的信任度为零。**

---

## 9. 功能分层总览

```
                    Free(试用)    Basic      Pro        VIP
                    ────────     ─────      ───        ───
论文草稿/大纲         ✓            ✓         ✓          ✓
LLM 扩写(用户key)     ✓            ✓         ✓          ✓
Word/PDF 导出         ✓            ✓         ✓          ✓
方法卡片              ✓            ✓         ✓          ✓
基础格式检查           ✓            ✓         ✓          ✓
──────────────────────────────────────────────────
开题报告              ✗            ✓         ✓          ✓
知识库检索            ✗            ✓         ✓          ✓
──────────────────────────────────────────────────
PPT 生成              ✗            ✗         ✓          ✓
盲审检查              ✗            ✗         ✗          ✓
AIGC 检测             ✗            ✗         ✗          ✓
──────────────────────────────────────────────────
设备数                1            1         2          3
有效期                3天          1年       2年        2年
```

---

## 10. 分阶段实施计划

### Phase 0：基础设施（2-3 天）

```
□ T0.1  搭建 FastAPI 项目骨架
        文件: cloud/app/main.py, config.py, dependencies.py
        验收: GET /health 返回 200, Swagger UI 可访问

□ T0.2  配置 PostgreSQL + SQLAlchemy
        文件: cloud/app/core/database.py, cloud/app/models/*.py
        验收: Alembic migration 成功建表 6 张

□ T0.3  实现 Ed25519 签名工具
        文件: cloud/app/core/security.py
        验收: sign(payload) → verify(payload, sig) 通过

□ T0.4  部署开发环境
        文件: Dockerfile, docker-compose.yml
        验收: docker compose up 单命令启动
```

### Phase 1：License 云端化（3-4 天）

```
□ T1.1  实现 POST /v1/license/validate
        文件: cloud/app/routers/license.py, cloud/app/services/license_signer.py
        接口: 见 3.1 节
        验收: curl 发请求，返回签名响应，本地公钥可验签

□ T1.2  实现 admin license 签发
        文件: cloud/app/routers/admin/license.py
        功能: 管理后台输入 email + tier → 签发 license_code → 写入 DB
        验收: 签发后 curl validate 返回 valid

□ T1.3  重构本地 LicenseManager
        文件: src/license_manager.py
        改动:
          - 删除 generate_license, _sign_payload, HMAC legacy
          - 新增 validate_with_cloud(), _cache_license_state(), _is_cache_valid()
          - 公钥仅从环境变量加载
        验收:
          1. 无 license → 基础版
          2. 有效 license + cloud 可达 → 激活 features
          3. 有效 license + cloud 不可达 → 读缓存
          4. 缓存过期 → 降级基础版
          5. 伪造缓存签名 → 丢弃降级

□ T1.4  改造 web_server.py 启动流程
        文件: src/web_server.py (main 函数附近)
        改动: 插入 _check_license() 步骤
        验收: 启动日志打印 license 状态

□ T1.5  实现 POST /v1/trial/start
        文件: cloud/app/routers/trial.py, cloud/app/services/trial_manager.py
        接口: 见 3.2 节
        验收: 同一 email 第二次申请返回 already_used
```

### Phase 2：自动更新 + 知识库（2-3 天）

```
□ T2.1  实现 GET /v1/release/latest
        文件: cloud/app/routers/release.py
        接口: 见 3.4 节
        验收: curl 返回版本号 + sha256 + 签名

□ T2.2  实现本地更新逻辑
        文件: src/updater.py（新文件）
        函数: check_update(), download_release(), verify_and_install()
        流程: 下载 → sha256 → 验签 → backup → 覆盖 → 回滚
        验收:
          1. 版本落后 → 自动更新
          2. sha256 不匹配 → 丢弃
          3. 签名无效 → 丢弃
          4. 磁盘满/权限不足 → 回滚 + 继续启动
          5. 云端不可达 → 跳过 + 日志

□ T2.3  实现 POST /v1/knowledge/search
        文件: cloud/app/routers/knowledge.py, cloud/app/services/knowledge_search.py
        功能: 向量检索，license_ticket 验签，返回结果
        验收: curl 发 query，返回相关卡片/资料

□ T2.4  改造本地 search_knowledge_base
        文件: src/web_server.py (search_knowledge_base 函数)
        改动: 优先调 cloud API，失败/超时 fallback 本地搜索
        验收: cloud 可达 → 云端结果；不可达 → fallback
```

### Phase 3：高价值功能迁移（3-4 天）

```
□ T3.1  PPT 生成迁移
        文件: cloud/app/routers/ppt.py, cloud/app/services/ppt_engine.py
        接口: 见 3.6 节
        改动: 从 src/ppt_engine/ 迁移核心逻辑到 cloud
        本地: /api/ppt/generate → 转发 POST /v1/ppt/generate
        验收: 本地调 API，云端生成，task poll 拿到下载链接

□ T3.2  盲审检查迁移
        文件: cloud/app/routers/review.py
        接口: POST /v1/blind-review
        本地: /api/blind-review-check → 转发
        验收: 本地提交，云端返回报告

□ T3.3  AIGC 检测迁移
        文件: cloud/app/routers/aigc.py
        接口: POST /v1/aigc/check, POST /v1/aigc/reduce
        本地: 转发
        验收: 同上

□ T3.4  本地高价值 API 改为转发层
        文件: src/web_server.py (ppt/blind/aigc handler)
        改动: 不执行本地逻辑，调 cloud API + 附带 license_ticket
        验收: 本地无代码可执行这些功能，改本地代码绕过无效
```

### Phase 4：支付 + 用户系统（2-3 天）

```
□ T4.1  注册/登录页面
        文件: web/（新增激活页面）
        功能: 输入 email → 输入激活码 → 调 cloud validate → 保存 license_code 本地
        验收: 激活成功后本地显示 tier + features

□ T4.2  管理后台
        文件: cloud/app/routers/admin/
        功能: license 列表、签发、吊销、设备解绑、audit 查询
        验收: admin license 登录后可操作

□ T4.3  支付对接（支付宝/微信）
        文件: cloud/app/routers/payment.py
        功能: 创建订单 → 支付回调 → 自动签发 license → 邮件通知
        验收: 模拟支付完成 → license 自动生成
```

---

## 11. 开发任务清单（可直接执行）

### T0.1 搭建 FastAPI 项目骨架

- **目标：** 创建 cloud/ 目录，FastAPI 项目可启动，/health 返回 200
- **涉及文件：**
  - `cloud/pyproject.toml` — 依赖声明（fastapi, uvicorn, sqlalchemy, asyncpg, cryptography）
  - `cloud/app/main.py` — FastAPI app, CORS, /health
  - `cloud/app/config.py` — DATABASE_URL, LICENSE_PRIVATE_KEY, 环境变量
- **接口定义：**
  - `GET /health → {"status": "ok", "version": "1.0.0"}`
- **验收标准：** `uvicorn app.main:app --reload` 启动，`curl localhost:8000/health` 返回 200
- **测试方式：** `pytest cloud/app/tests/test_health.py`

### T0.2 配置 PostgreSQL + SQLAlchemy + Alembic

- **目标：** 建表 6 张，migration 可重复执行
- **涉及文件：**
  - `cloud/app/core/database.py` — engine, SessionLocal, Base
  - `cloud/app/models/*.py` — 6 个 ORM 模型
  - `cloud/alembic.ini`, `cloud/alembic/env.py`
- **验收标准：** `alembic upgrade head` 建表成功，`psql` 可查 6 张表
- **测试方式：** `pytest cloud/app/tests/test_models.py` — 写入/查询每条表

### T0.3 实现 Ed25519 签名工具

- **目标：** 云端签名 + 本地验签的代码库
- **涉及文件：**
  - `cloud/app/core/security.py` — `sign_payload(payload: str) -> str`, `verify_signature(payload: str, sig: str, public_key_bytes: bytes) -> bool`
  - `cloud/app/tests/test_security.py`
- **验收标准：**
  - 生成 keypair → sign("test") → verify 通过
  - 篡改 payload → verify 失败
  - 用错误公钥 → verify 失败
- **测试方式：** 单元测试 3 个 case

### T1.1 实现 POST /v1/license/validate

- **目标：** 云端 license 校验 API，返回签名响应
- **涉及文件：**
  - `cloud/app/routers/license.py` — 路由
  - `cloud/app/schemas/license.py` — Pydantic request/response
  - `cloud/app/services/license_signer.py` — 查 DB → 组装响应 → 签名
- **接口定义：** 见 3.1 节
- **验收标准：**
  1. 有效 license_code → status=valid, 含签名
  2. 过期 license → status=expired
  3. 吊销 license → status=revoked
  4. 设备数超限 → status=device_limit
  5. 本地公钥验签通过
- **测试方式：** 先 seed DB 插入一条 effective license，curl 验证 4 种状态

### T1.3 重构本地 LicenseManager

- **目标：** 本地 LicenseManager 改为云端客户端 + 本地缓存
- **涉及文件：** `src/license_manager.py`
- **改动：**
  1. 删除 `generate_license`, `_sign_payload`, HMAC legacy
  2. 新增 `validate_with_cloud()`, `_cache_license_state()`, `_is_cache_valid()`
  3. `can_access_api()` 读缓存 features 判断
- **验收标准（5 个场景）：**
  1. 无 license → 基础版（features=[]）
  2. 有效 license + cloud 可达 → 激活 features
  3. cloud 不可达 + 缓存未过期 → 使用缓存
  4. cloud 不可达 + 缓存过期 → 基础版
  5. 缓存文件签名被篡改 → 丢弃 → 基础版
- **测试方式：** mock cloud API 响应，分别测试 5 个场景

### T1.4 改造 web_server.py 启动流程

- **目标：** 启动时检查 license，运行时高价值 API 转发云端
- **涉及文件：** `src/web_server.py`
- **改动：**
  - 在 `main()` 中插入 `_check_license()` 步骤（在 rebuild_cards 之后，start server 之前）
  - PPT/blind/AIGC handler 改为调 cloud API 转发
- **验收标准：**
  1. 启动日志打印 `[license] tier=basic features=workflow cached=True`
  2. 高价值 API 不执行本地逻辑，只转发
- **测试方式：** 启动服务 → 查看日志 → curl license status 端点

### T1.5 实现 POST /v1/trial/start

- **目标：** 云端管理试用期，防重复
- **涉及文件：**
  - `cloud/app/routers/trial.py`
  - `cloud/app/schemas/trial.py`
  - `cloud/app/services/trial_manager.py`
- **接口定义：** 见 3.2 节
- **验收标准：**
  1. 首次 trial → status=started, days_left=3
  2. 同 email 再次 → status=already_used
  3. 同 device 换 email → status=already_used
  4. 到期后 validate → status=expired
- **测试方式：** seed clean DB，curl 正常流程 + 重复申请 + 到期

### T2.1-2.2 前端自动更新

- **目标：** 启动时检查云端新版本，自动下载覆盖
- **涉及文件：**
  - `cloud/app/routers/release.py` — GET /v1/release/latest
  - `src/updater.py` — 新文件，下载/校验/备份/覆盖/回滚
- **接口定义：** 见 3.4 节
- **验收标准：**
  1. 版本落后 → 自动更新 → 新版本启动
  2. sha256 不匹配 → 丢弃
  3. 签名无效 → 丢弃
  4. 下载失败 → 跳过，旧版正常启动
  5. 解压失败 → 回滚 web.backup/ → 旧版正常启动
- **测试方式：** 手动构造错误 sha256/错误签名的 zip，验证防御

### T2.3-2.4 知识库检索迁移

- **目标：** 知识库检索走云端 API，本地做 fallback
- **涉及文件：**
  - `cloud/app/routers/knowledge.py`
  - `cloud/app/services/knowledge_search.py`
  - `src/web_server.py` 中 `search_knowledge_base()` 函数
- **接口定义：** 见 3.5 节
- **验收标准：**
  1. cloud 可达 → 返回云端检索结果
  2. cloud 超时 (>3s) → fallback 本地检索
  3. 无效 license_ticket → 401
- **测试方式：** 1) 正常查询 2) 关云端测 fallback 3) 假 ticket 测拒绝

### T3.1 PPT 生成迁移

- **目标：** PPT 生成逻辑只在云端执行
- **涉及文件：**
  - `cloud/app/routers/ppt.py`
  - `cloud/app/services/ppt_engine.py`（从 src/ppt_engine/ 迁移）
  - `src/web_server.py` handler 改为转发
- **接口定义：** 见 3.6 节
- **验收标准：**
  1. 本地 POST /api/ppt/generate → 云端任务排队 → 返回 task_id
  2. 轮询 task → 完成 → 返回 download_url
  3. 删掉本地 ppt_engine 后功能仍正常（证明逻辑全在云端）
- **测试方式：** 本地调 API → 等待 → 下载 pptx 文件

### T3.2-3.3 盲审/AIGC 迁移

- **目标：** 盲审 + AIGC 只在云端执行
- **涉及文件：**
  - `cloud/app/routers/review.py`, `cloud/app/routers/aigc.py`
  - `src/web_server.py` handler 改为转发
- **接口定义：** 见 3.7 节
- **验收标准：** 本地调 API → 云端返回报告 → 本地展示
- **测试方式：** curl 提交文本 → 验证返回报告格式

---

## 12. 云服务厂商选型（国外部署）

### 12.1 方案 A：Railway（推荐，零运维）

| 资源 | 规格 | 月费 |
|------|------|------|
| App 托管 | 自动扩缩 | $5-25 |
| PostgreSQL | 内置 PG | 含在 App 费 |
| 对象存储 | 内置或 S3 | 含在 App 费 |
| **合计** | | **$5-25/月** |

优势：Git push 即部署，内置 PG + Redis，美西/欧洲机房。零运维成本，适合 MVP。

### 12.2 方案 B：Fly.io（性价比 + 亚洲节点）

| 资源 | 规格 | 月费 |
|------|------|------|
| VM | shared-cpu-1x, 256MB | $0（免费额度） |
| PG | 由 Supabase 管理 | $0-25 |
| Volume | 3GB 持久存储 | 含在免费额度 |
| **合计** | | **$0-25/月** |

优势：全球边缘节点（含香港/东京/新加坡），国内访问延迟优于 Railway。免费额度够跑 MVP。

### 12.3 方案 C：AWS Lightsail / EC2（企业级 + 亚洲区）

| 资源 | 规格 | 月费 |
|------|------|------|
| EC2 t3.micro | 1核1G | ~$8 |
| RDS PostgreSQL | db.t3.micro | ~$15 |
| S3 + CloudFront | CDN 全球分发 | ~$5 |
| **合计** | | **~$28/月** |

优势：新加坡/东京/首尔 region 对国内友好（50-120ms 延迟），IAM 权限细粒度，合规认证全。

### 12.4 国内用户访问国外云的延迟

| 源 | 目的地 | 典型延迟 | 体验 |
|------|--------|----------|------|
| 国内电信 | 美西 (us-west) | 150-220ms | 可感知卡顿 |
| 国内电信 | 新加坡 | 80-120ms | 可接受 |
| 国内电信 | 东京 | 50-80ms | 良好 |
| 国内电信 | 香港 | 30-50ms | 接近国内 |

**建议**：选 Fly.io 香港/东京节点，或 AWS 新加坡/东京 region。API 调用延迟可控（<120ms），页面首次加载稍慢但可接受。

### 12.5 网络代理与反爬

**OpenAlex / 学术 API**：当前由用户本地 `literature_hunter.py` 直接调用，不经过云端。云端不调学术 API，不存在集中 IP 反爬问题。

**LLM API（OpenAI / Claude / DeepSeek）**：
- PPT 生成、盲审、AIGC 在云端执行时需要调 LLM API
- 商业 LLM API 不限云服务器 IP（不同于学术网站的反爬策略）
- DeepSeek 国内 API 可能从国外云不可达，需要代理或走 DeepSeek 国际端点

**云端预留代理配置**（`cloud/.env`）：
```bash
# 代理（可选，用于云端调国内 DeepSeek API 等场景）
HTTPS_PROXY=
HTTP_PROXY=
NO_PROXY=localhost,127.0.0.1
```

### 12.6 容量估算

| 指标 | MVP（$0-25/月） | 成长期（$28-70/月） |
|------|----------------|-------------------|
| 注册用户 | 500-1000 | 2000-5000 |
| 日活 | 50-100 | 200-500 |
| 并发 API | 20-30 | 100-200 |
| PPT 并发任务 | 3-5 | 10-20 |

瓶颈在 PPT 生成（单次耗 LLM token 大 + SVG 渲染）。先撞墙就加 queue worker。

### 12.7 扩容路径

```
MVP（$0-25/月）              成长期（$28-70/月）           规模化（$100+/月）
─────────────────          ──────────────────         ──────────────────
Railway/Fly.io 单实例        Fly.io ×2 / EC2 t3.small    EC2 ×2 + ALB
内置 PG                      Supabase Pro / RDS          RDS Multi-AZ
S3 + CloudFront CDN          CDN 多 region                CDN 全球加速
—                            Redis 缓存 + Queue           Queue Worker Pool
撑 500-1000 注册              撑 2000-5000 注册            撑 10000+ 注册
```

## 附录 A：本地配置变更

`.env` 文件新增：

```bash
# Cloud API endpoint
THESISMIND_CLOUD_URL=https://api.thesismind.com

# License public key (Ed25519, base64url encoded)
THESISMIND_LICENSE_PUBLIC_KEY=<32-byte-base64url>

# 删除：
# THESISMIND_LICENSE_KEY (HMAC legacy, 不再使用)
# THESISMIND_LICENSE_PRIVATE_KEY (签发密钥，只放云端)
```

## 附录 B：云端环境变量

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/thesismind

# License signing keypair
LICENSE_PRIVATE_KEY=<Ed25519 private key, PEM or base64url 32 bytes>
LICENSE_PUBLIC_KEY=<Ed25519 public key, PEM or base64url 32 bytes>

# CDN base URL for release/PPT downloads
CDN_BASE_URL=https://cdn.thesismind.com

# Rate limiting
RATE_LIMIT_PER_IP=100/hour

# Trial config
TRIAL_DAYS=3
MAX_DEVICES_PER_LICENSE_BASIC=1
MAX_DEVICES_PER_LICENSE_PRO=2
MAX_DEVICES_PER_LICENSE_VIP=3
```

## 附录 C：降级状态矩阵

```
cloud 可用    缓存有效    最终状态
─────────    ────────    ────────
  ✅          ✅         激活 features（缓存在有效期内）
  ✅          ❌         调 cloud → 验签 → 新缓存
  ❌          ✅         使用缓存（24h 内有效）
  ❌          ❌         基础版（features=[]，仅基础功能）
  ✅          签名损坏    丢弃缓存 → 调 cloud → 重新缓存
  ❌          签名损坏    基础版
```
