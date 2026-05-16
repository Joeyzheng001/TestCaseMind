import re
import unittest
from pathlib import Path

from src.api_registry import (
    API_MENU_MAP,
    API_PREFIX_MENU_MAP,
    MENU_FEATURE_MAP,
    is_registered_api_path,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_SERVER = PROJECT_ROOT / "src" / "web_server.py"
WEB_APP = PROJECT_ROOT / "web" / "app.js"


def _backend_api_paths():
    text = WEB_SERVER.read_text(encoding="utf-8")
    paths = set(re.findall(r'path\s*==\s*"(/api/[^"]+)"', text))
    paths.update(re.findall(r'"(/api/[^"]+)"', "\n".join(re.findall(r"path\s+in\s+\{([^}]+)\}", text))))
    return {path.split("?", 1)[0].rstrip("/") for path in paths}


def _frontend_api_paths():
    text = WEB_APP.read_text(encoding="utf-8")
    paths = set(re.findall(r'["`](/api/[^"`?${]+)', text))
    return {path.split("?", 1)[0].rstrip("/") for path in paths}


class ApiRegistryTest(unittest.TestCase):
    def test_registered_menus_have_feature_definitions(self):
        menu_ids = set(API_MENU_MAP.values()) | set(API_PREFIX_MENU_MAP.values())
        missing = sorted(menu_id for menu_id in menu_ids if menu_id not in MENU_FEATURE_MAP)

        self.assertEqual([], missing)

    def test_backend_api_paths_are_registered_for_license_gating(self):
        missing = sorted(
            path for path in _backend_api_paths()
            if path.startswith("/api/") and not is_registered_api_path(path)
        )

        self.assertEqual([], missing)

    def test_frontend_api_calls_are_registered_for_license_gating(self):
        missing = sorted(
            path for path in _frontend_api_paths()
            if path.startswith("/api/") and not is_registered_api_path(path)
        )

        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
