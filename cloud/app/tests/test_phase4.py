"""Test Phase 4: account registration, admin management, tier definitions."""


def test_account_route_registered():
    from cloud.app.main import app
    routes = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/v1/account/register" in routes


def test_admin_routes_registered():
    from cloud.app.main import app
    routes = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/v1/admin/licenses" in routes
    assert "/v1/admin/licenses/issue" in routes
    assert "/v1/admin/licenses/revoke" in routes
    assert "/v1/admin/activations/{license_id}" in routes
    assert "/v1/admin/activations/unbind" in routes
    assert "/v1/admin/audit-logs" in routes


def test_tier_definitions():
    from cloud.app.services.admin_manager import TIERS
    assert "basic" in TIERS
    assert "pro" in TIERS
    assert "vip" in TIERS
    assert "admin" in TIERS
    assert TIERS["basic"]["features"] == ["workflow"]
    assert TIERS["pro"]["features"] == ["workflow", "advanced"]
    assert TIERS["vip"]["features"] == ["workflow", "advanced", "vip"]
    assert TIERS["admin"]["features"] == ["workflow", "advanced", "vip", "admin"]


def test_license_code_format():
    from cloud.app.services.admin_manager import _generate_code
    code = _generate_code()
    parts = code.split("-")
    assert len(parts) == 4
    assert parts[0] == "TM"
    assert len(parts[1]) == 4
    assert len(parts[2]) == 4
    assert len(parts[3]) == 4
    codes = {_generate_code() for _ in range(100)}
    assert len(codes) == 100
