import unittest

from src.license_manager import LicenseManager


def _manager_with_features(features, status="active", tier_label="测试版"):
    manager = LicenseManager()
    manager.get_license_status = lambda: {
        "status": status,
        "tier_label": tier_label,
        "features": features,
    }
    return manager


class LicenseManagerSecurityTest(unittest.TestCase):
    def test_vip_all_does_not_grant_admin(self):
        manager = _manager_with_features(["all"], tier_label="VIP版")

        self.assertTrue(manager.can_access_menu("blind_review")[0])
        self.assertTrue(manager.can_access_api("/api/blind-review-check")[0])

        self.assertFalse(manager.can_access_menu("license_generate")[0])
        self.assertFalse(manager.can_access_api("/api/license/generate")[0])
        self.assertFalse(manager.check_feature("admin")[0])

    def test_admin_feature_allows_admin_apis(self):
        manager = _manager_with_features(["all", "admin"], tier_label="管理员版")

        self.assertTrue(manager.can_access_menu("license_generate")[0])
        self.assertTrue(manager.can_access_api("/api/license/generate")[0])
        self.assertTrue(manager.check_feature("admin")[0])

    def test_unmapped_api_is_denied_by_default(self):
        manager = _manager_with_features(["all", "admin"], tier_label="管理员版")

        allowed, reason = manager.can_access_api("/api/new-unmapped-endpoint")

        self.assertFalse(allowed)
        self.assertIn("未授权", reason)

    def test_workspace_and_chat_test_are_explicitly_gated(self):
        manager = _manager_with_features(["workflow"], tier_label="基础版")

        self.assertTrue(manager.can_access_api("/api/workspace")[0])
        self.assertTrue(manager.can_access_api("/api/workspace/value")[0])
        self.assertTrue(manager.can_access_api("/api/chat/test")[0])

    def test_config_get_is_public_but_post_requires_workflow(self):
        unlicensed = _manager_with_features([], status="no_license", tier_label="未激活")
        workflow = _manager_with_features(["workflow"], tier_label="基础版")

        self.assertTrue(unlicensed.can_access_api("/api/config", method="GET")[0])
        self.assertFalse(unlicensed.can_access_api("/api/config", method="POST")[0])
        self.assertTrue(workflow.can_access_api("/api/config", method="POST")[0])

    def test_task_status_requires_license(self):
        unlicensed = _manager_with_features([], status="no_license", tier_label="未激活")
        workflow = _manager_with_features(["workflow"], tier_label="基础版")

        self.assertFalse(unlicensed.can_access_api("/api/tasks/example", method="GET")[0])
        self.assertTrue(workflow.can_access_api("/api/tasks/example", method="GET")[0])


if __name__ == "__main__":
    unittest.main()
