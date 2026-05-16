import unittest

from src.tools import check_document_format, extract_paper_metadata, run_command
from src.vector_store import _resolve_path


class PathSecurityTest(unittest.TestCase):
    def test_extract_paper_metadata_rejects_paths_outside_project(self):
        result = extract_paper_metadata("/tmp/outside-project.docx")

        self.assertIn("error", result)
        self.assertIn("outside project", result["error"])

    def test_vector_store_rejects_absolute_paths_outside_project(self):
        with self.assertRaises(ValueError):
            _resolve_path("/tmp/outside-vector-store.sqlite3", None)

    def test_check_document_format_rejects_paths_outside_project(self):
        result = check_document_format("/tmp/outside-project.md")

        self.assertIn("error", result)
        self.assertIn("outside project", result["error"])

    def test_run_command_rejects_inline_python_even_when_enabled(self):
        import os

        old_value = os.environ.get("ENABLE_RUN_COMMAND")
        os.environ["ENABLE_RUN_COMMAND"] = "true"
        try:
            result = run_command("python -c 'print(1)'")
        finally:
            if old_value is None:
                os.environ.pop("ENABLE_RUN_COMMAND", None)
            else:
                os.environ["ENABLE_RUN_COMMAND"] = old_value

        self.assertIn("inline code", result)


if __name__ == "__main__":
    unittest.main()
