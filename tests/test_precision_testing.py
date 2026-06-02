import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "precision_testing.py"
SPEC = importlib.util.spec_from_file_location("precision_testing", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PrecisionTestingTest(unittest.TestCase):
    def test_cli_generates_java_precision_testing_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "java-service"
            repo.mkdir()
            self.run_command(["git", "init"], cwd=repo)
            self.run_command(["git", "config", "user.email", "test@example.com"], cwd=repo)
            self.run_command(["git", "config", "user.name", "Test"], cwd=repo)
            source = repo / "src/main/java/com/example/UserController.java"
            source.parent.mkdir(parents=True)
            source.write_text(
                '@RestController\n@RequestMapping("/users")\n'
                "public class UserController {\n}\n",
                encoding="utf-8",
            )
            self.run_command(["git", "add", "."], cwd=repo)
            self.run_command(["git", "commit", "-m", "base"], cwd=repo)
            source.write_text(
                '@RestController\n@RequestMapping("/users")\n'
                "public class UserController {\n"
                '  @GetMapping("/{id}")\n'
                "  User get() { return null; }\n"
                "}\n",
                encoding="utf-8",
            )
            openapi_base = root / "openapi-base.json"
            openapi_current = root / "openapi-current.json"
            openapi_base.write_text('{"paths": {}}', encoding="utf-8")
            openapi_current.write_text(
                '{"paths": {"/users/{id}": {"get": {"responses": {"200": {}}}}}}',
                encoding="utf-8",
            )
            jacoco = root / "jacoco.xml"
            jacoco.write_text(
                '<report><package name="com/example">'
                '<sourcefile name="UserController.java">'
                '<line nr="5" mi="0" ci="1" mb="0" cb="0"/>'
                "</sourcefile></package></report>",
                encoding="utf-8",
            )
            output = root / "output"
            self.run_command(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo",
                    str(repo),
                    "--base-ref",
                    "HEAD",
                    "--target-ref",
                    "WORKTREE",
                    "--output",
                    str(output),
                    "--openapi-base",
                    str(openapi_base),
                    "--openapi-current",
                    str(openapi_current),
                    "--jacoco-xml",
                    str(jacoco),
                ]
            )
            context = json.loads((output / "review-context.json").read_text(encoding="utf-8"))
            self.assertEqual(context["controller_apis"][0]["path"], "/users/{id}")
            self.assertEqual(context["openapi_changes"][0]["kind"], "added")
            self.assertEqual(context["diff_coverage"]["diff_line_coverage_percent"], 100.0)
            self.assertTrue((output / "generated-tests/karate/impacted-apis.feature").exists())

    @staticmethod
    def run_command(command, cwd=None):
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            raise AssertionError(
                f"Command failed: {' '.join(command)}\nstdout={result.stdout}\nstderr={result.stderr}"
            )
        return result

    def test_parse_name_status_keeps_unicode_path(self):
        self.assertEqual(
            MODULE.parse_name_status("M\tdocs/精准测试.md\n"),
            {"docs/精准测试.md": "M"},
        )

    def test_parse_changed_lines_ignores_deleted_file_hunks(self):
        diff = """\
diff --git a/src/Old.java b/src/Old.java
--- a/src/Old.java
+++ /dev/null
@@ -1,2 +0,0 @@
-class Old {}
diff --git a/src/New.java b/src/New.java
--- a/src/New.java
+++ b/src/New.java
@@ -0,0 +10,2 @@
+line1
+line2
"""
        self.assertEqual(MODULE.parse_changed_lines(diff), {"src/New.java": {10, 11}})

    def test_extract_controller_apis(self):
        source = """\
@RestController
@RequestMapping("/users")
public class UserController {
  @GetMapping("/{id}")
  User get() { return null; }

  @PostMapping
  User create() { return null; }
}
"""
        self.assertEqual(
            MODULE.extract_controller_apis(source, "src/UserController.java"),
            [
                {
                    "method": "get",
                    "path": "/users/{id}",
                    "source_file": "src/UserController.java",
                },
                {
                    "method": "post",
                    "path": "/users",
                    "source_file": "src/UserController.java",
                },
            ],
        )

    def test_compare_openapi(self):
        base = {
            "paths": {
                "/users": {
                    "get": {"responses": {"200": {"description": "ok"}}},
                    "post": {"responses": {"201": {"description": "created"}}},
                }
            }
        }
        current = {
            "paths": {
                "/users": {
                    "get": {"responses": {"200": {"description": "changed"}}},
                },
                "/health": {
                    "get": {"responses": {"200": {"description": "ok"}}},
                },
            }
        }
        self.assertEqual(
            MODULE.compare_openapi(base, current),
            [
                {"kind": "added", "method": "GET", "path": "/health"},
                {"kind": "modified", "method": "GET", "path": "/users"},
                {"kind": "removed", "method": "POST", "path": "/users"},
            ],
        )

    def test_calculate_diff_coverage(self):
        xml = """\
<report name="demo">
  <package name="com/example">
    <sourcefile name="Demo.java">
      <line nr="10" mi="0" ci="2" mb="0" cb="0"/>
      <line nr="11" mi="2" ci="0" mb="0" cb="0"/>
    </sourcefile>
  </package>
</report>
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "jacoco.xml"
            path.write_text(xml, encoding="utf-8")
            coverage = MODULE.jacoco_lines(path)
        result = MODULE.calculate_diff_coverage(
            [
                MODULE.ChangedFile(
                    path="src/main/java/com/example/Demo.java",
                    status="M",
                    lines={10, 11, 12},
                )
            ],
            coverage,
        )
        self.assertEqual(result["executable_changed_lines"], 2)
        self.assertEqual(result["covered_changed_lines"], 1)
        self.assertEqual(result["missed_changed_lines"], 1)
        self.assertEqual(result["diff_line_coverage_percent"], 50.0)
        self.assertEqual(result["files"][0]["missed_lines"], [11])


if __name__ == "__main__":
    unittest.main()
