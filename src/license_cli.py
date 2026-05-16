"""
License Code 命令行工具
用于生成、验证、管理License Code
"""

import sys
import argparse
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.license_manager import LicenseManager, TrialLicense
import json


def cmd_generate(args):
    """生成License Code"""
    manager = LicenseManager()

    try:
        code = manager.generate_license(
            license_type=args.type,
            user_email=args.email or "",
            custom_id=args.customer_id or "",
            machine_id=args.machine_id or "",
        )
    except Exception as exc:
        print(f"\n✗ License Code generation failed: {exc}\n")
        sys.exit(1)

    print(f"\n✓ License Code generated successfully:\n")
    print(f"  {code}\n")

    # 验证生成的Code
    is_valid, info = manager.validate_license(code)
    if is_valid:
        print(f"✓ License verified successfully")
        print(f"  Type: {info['type']}")
        print(f"  Expires: {info['expires_at']}")
        print(f"  Features: {', '.join(info['features'])}\n")


def cmd_activate(args):
    """激活License Code"""
    manager = LicenseManager()

    success, msg = manager.save_license(args.code, validate=True)

    if success:
        print(f"\n✓ {msg}\n")

        # 显示License信息
        status = manager.get_license_status()
        print(f"License Status:")
        print(f"  Type: {status.get('tier')}")
        print(f"  Email: {status.get('user_email')}")
        print(f"  Days Left: {status.get('days_left')}")
        print(f"  Features: {', '.join(status.get('features', []))}\n")
    else:
        print(f"\n✗ {msg}\n")
        sys.exit(1)


def cmd_status(args):
    """显示License状态"""
    manager = LicenseManager()
    status = manager.get_license_status()

    print(f"\n=== License Status ===\n")
    print(f"Status: {status['status'].upper()}")

    if status["status"] in {"active", "trial", "expired"}:
        print(f"Type: {status.get('tier')}")
        print(f"Label: {status.get('tier_label')}")
        if status.get("user_email"):
            print(f"Email: {status['user_email']}")
        if status.get("issued_at"):
            print(f"Issued: {status['issued_at']}")
        if status.get("expires_at"):
            print(f"Expires: {status['expires_at']}")
        print(f"Days Left: {status.get('days_left', 0)}")
        print(f"Features: {', '.join(status.get('features', []))}\n")
    else:
        print(f"Message: {status.get('message', '')}\n")


def cmd_verify(args):
    """验证License Code"""
    manager = LicenseManager()
    is_valid, info = manager.validate_license(args.code)

    print(f"\n=== License Verification ===\n")
    print(f"Code: {args.code}")
    print(f"Valid: {'Yes' if is_valid else 'No'}\n")

    if is_valid:
        print(f"License Information:")
        print(f"  Type: {info['type']}")
        print(f"  User Email: {info.get('user_email')}")
        print(f"  Issued: {info['issued_at']}")
        print(f"  Expires: {info['expires_at']}")
        print(f"  Features: {', '.join(info['features'])}\n")
    else:
        print(f"Error: {info.get('error')}\n")


def cmd_remove(args):
    """删除激活的License"""
    manager = LicenseManager()
    success, msg = manager.remove_license()

    if success:
        print(f"\n✓ {msg}\n")
    else:
        print(f"\n✗ {msg}\n")
        sys.exit(1)


def cmd_trial(args):
    """创建试用License"""
    success, msg = TrialLicense.start()

    if success:
        print(f"\n✓ {msg}\n")

        is_valid, info = TrialLicense.check()
        if is_valid:
            print(f"Trial License Info:")
            print(f"  Days Left: {info['days_left']}")
            print(f"  Expires: {info['expires_at']}\n")
    else:
        print(f"\n✗ {msg}\n")
        sys.exit(1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="ThesisMind License Code Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a basic license (issuer machine only; requires THESISMIND_LICENSE_PRIVATE_KEY)
  python -m src.license_cli generate --type basic --email user@example.com
  
  # Activate a license
  python license_cli.py activate "TM-XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX"
  
  # Check license status
  python license_cli.py status
  
  # Verify a license code
  python license_cli.py verify "TM-XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX"
  
  # Create trial license
  python license_cli.py trial
  
  # Remove activated license
  python license_cli.py remove
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate a license code")
    gen_parser.add_argument(
        "--type",
        choices=["free", "basic", "pro", "vip", "admin"],
        default="basic",
        help="License type",
    )
    gen_parser.add_argument("--email", help="User email")
    gen_parser.add_argument("--customer-id", help="Customer ID")
    gen_parser.add_argument("--machine-id", help="Optional target machine ID")
    gen_parser.set_defaults(func=cmd_generate)

    # Activate command
    act_parser = subparsers.add_parser("activate", help="Activate a license code")
    act_parser.add_argument("code", help="License code")
    act_parser.set_defaults(func=cmd_activate)

    # Status command
    stat_parser = subparsers.add_parser("status", help="Show license status")
    stat_parser.set_defaults(func=cmd_status)

    # Verify command
    ver_parser = subparsers.add_parser("verify", help="Verify a license code")
    ver_parser.add_argument("code", help="License code to verify")
    ver_parser.set_defaults(func=cmd_verify)

    # Remove command
    rem_parser = subparsers.add_parser("remove", help="Remove activated license")
    rem_parser.set_defaults(func=cmd_remove)

    # Trial command
    trial_parser = subparsers.add_parser("trial", help="Create trial license")
    trial_parser.set_defaults(func=cmd_trial)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
    else:
        args.func(args)


if __name__ == "__main__":
    main()
