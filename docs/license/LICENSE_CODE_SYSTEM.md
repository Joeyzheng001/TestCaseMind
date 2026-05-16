# ThesisMind License Code 系统

本文档描述当前代码实现的许可证技术方案。商业条款另见 `LICENSE_COMMERCIAL.md`。

## 授权等级

| 等级 | 标识 | 有效期 | 功能 |
| --- | --- | --- | --- |
| 免费试用 | trial/free | 3 天 | 基础工作流 |
| 基础版 | basic | 1 年 | 01-07 基础论文工作流 |
| 畅想版 | pro | 2 年 | 基础工作流 + 增值服务 |
| VIP 版 | vip | 2 年 | 全部用户功能 |
| 管理员版 | admin | 10 年 | 全部功能 + 管理能力 |

## 安全模型

当前实现使用 Ed25519 非对称签名：

- 私钥只存在于许可证签发环境，用于生成 License Code。
- 客户端/交付包只配置公钥，用于离线验签。
- 源码中不包含默认签名密钥。
- 旧版 HMAC 仅作为显式兼容路径：只有设置 `THESISMIND_LICENSE_KEY` 时才会尝试验证旧码。

这避免了旧方案中“客户端既能验签也能签发”的共享密钥问题。

## 环境变量

客户端/交付包：

```bash
export THESISMIND_LICENSE_PUBLIC_KEY="base64url_raw_public_key"
```

许可证签发机：

```bash
export THESISMIND_LICENSE_PRIVATE_KEY="base64url_raw_private_key"
```

旧版 HMAC 兼容验证，默认不要配置：

```bash
export THESISMIND_LICENSE_KEY="legacy_hmac_key"
```

## 生成测试密钥

```bash
python -c "import base64; from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; from cryptography.hazmat.primitives import serialization; k=Ed25519PrivateKey.generate(); print('PRIVATE=' + base64.urlsafe_b64encode(k.private_bytes(encoding=serialization.Encoding.Raw, format=serialization.PrivateFormat.Raw, encryption_algorithm=serialization.NoEncryption())).decode().rstrip('=')); print('PUBLIC=' + base64.urlsafe_b64encode(k.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)).decode().rstrip('='))"
```

## CLI

查看状态：

```bash
python license_cli.py status
```

开始试用：

```bash
python license_cli.py trial-start
```

激活许可证：

```bash
python license_cli.py activate "TM-..."
```

验证许可证：

```bash
python license_cli.py validate "TM-..."
```

签发许可证，仅在配置私钥的签发环境运行：

```bash
python license_cli.py generate --type basic --email user@example.com
python license_cli.py generate --type vip --email user@example.com --machine-id 123456789
```

## 本地文件

默认写入用户配置目录：

```text
~/.thesismind/
├── .license                # 已激活许可证和本机 machine_id
├── .license_history.json   # 本机生成/激活历史摘要
└── .trial                  # 免费试用记录
```

可通过 `THESISMIND_CONFIG_DIR` 指定测试目录。

## 服务端 API 授权

`src.api_registry` 维护公开 API、API 到功能菜单的映射、任务类型到权限的映射。`src.license_manager.LicenseManager.can_access_api()` 只负责根据该注册表和当前许可证做判定；`src/web_server.py` 在处理 `/api/` 请求入口统一调用 `_check_license_api()`，避免只依赖前端隐藏菜单。

公开 API：

- `GET /api/config`
- `GET /api/license/status`
- `POST /api/license/activate`
- `POST /api/license/trial`

其他已映射功能 API 会根据 `workflow`、`advanced`、`vip`、`admin` 权限校验；未知 `/api/` 端点默认拒绝，避免新增接口绕过授权。

## 已知边界

- 本地离线许可证无法阻止用户直接修改源码。强商业部署应叠加服务端激活、吊销列表、设备数量限制和发布包完整性校验。
- 本机 `.trial` 删除后仍可能重新开始试用；这需要服务端激活记录或更强设备指纹才能彻底治理。
- 旧版 HMAC 码只适合作迁移兼容，不建议继续签发。
