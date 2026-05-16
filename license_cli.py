#!/usr/bin/env python3
"""ThesisMind 许可证管理 CLI — 生成、验证、管理许可证。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.license_manager import LicenseManager, TrialLicense


def cmd_generate(args):
    manager = LicenseManager()
    try:
        code = manager.generate_license(
            license_type=args.type,
            user_email=args.email or "",
            custom_id=args.custom_id or "",
            machine_id=args.machine_id or "",
        )
    except Exception as exc:
        print(f"生成失败: {exc}")
        sys.exit(1)
    print(code)


def cmd_validate(args):
    manager = LicenseManager()
    ok, info = manager.validate_license(args.code)
    if ok:
        print("✓ 许可证有效")
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        print(f"✗ 许可证无效: {info.get('error')}")
        sys.exit(1)


def cmd_status(args):
    manager = LicenseManager()
    status = manager.get_license_status()
    print(json.dumps(status, ensure_ascii=False, indent=2))


def cmd_activate(args):
    manager = LicenseManager()
    ok, msg = manager.save_license(args.code, validate=True)
    print(msg)
    if not ok:
        sys.exit(1)


def cmd_remove(args):
    manager = LicenseManager()
    ok, msg = manager.remove_license()
    print(msg)


def cmd_trial_start(args):
    ok, msg = TrialLicense.start()
    print(msg)


def cmd_trial_check(args):
    ok, info = TrialLicense.check()
    if ok:
        print(f"✓ 试用有效，剩余 {info['days_left']} 天")
        print(f"  到期时间: {info['expires_at']}")
    else:
        print(f"✗ {info.get('error')}")
        if info.get("expired"):
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="ThesisMind 许可证管理工具")
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="生成许可证激活码")
    gen.add_argument("--type", choices=["free", "basic", "pro", "vip", "admin"], default="basic")
    gen.add_argument("--email")
    gen.add_argument("--custom-id")
    gen.add_argument("--machine-id", help="可选：绑定到指定机器 ID")

    val = sub.add_parser("validate", help="验证许可证激活码")
    val.add_argument("code")

    sub.add_parser("status", help="查看当前许可证状态")

    act = sub.add_parser("activate", help="保存并激活许可证")
    act.add_argument("code")

    sub.add_parser("remove", help="移除当前许可证")

    sub.add_parser("trial-start", help="开始3天免费试用")
    sub.add_parser("trial-check", help="检查试用状态")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    {
        "generate": cmd_generate,
        "validate": cmd_validate,
        "status": cmd_status,
        "activate": cmd_activate,
        "remove": cmd_remove,
        "trial-start": cmd_trial_start,
        "trial-check": cmd_trial_check,
    }[args.command](args)


if __name__ == "__main__":
    main()
