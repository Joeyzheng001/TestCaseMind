#!/usr/bin/env python3
"""Prepare precision-testing artifacts for a Java REST service."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is an existing project dependency.
    yaml = None


HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
ANNOTATION_METHODS = {
    "GetMapping": "get",
    "PostMapping": "post",
    "PutMapping": "put",
    "PatchMapping": "patch",
    "DeleteMapping": "delete",
}


@dataclass
class ChangedFile:
    path: str
    status: str
    lines: set[int]


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def parse_name_status(text: str) -> dict[str, str]:
    files: dict[str, str] = {}
    for raw in text.splitlines():
        parts = raw.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        path = parts[-1]
        files[path] = status
    return files


def parse_changed_lines(diff_text: str) -> dict[str, set[int]]:
    changed: dict[str, set[int]] = {}
    current = ""
    for line in diff_text.splitlines():
        if line == "+++ /dev/null":
            current = ""
            continue
        if line.startswith("+++ b/"):
            current = line[6:]
            changed.setdefault(current, set())
            continue
        if not current or not line.startswith("@@"):
            continue
        match = re.search(r"\+(\d+)(?:,(\d+))?", line)
        if not match:
            continue
        start = int(match.group(1))
        count = int(match.group(2) or "1")
        changed[current].update(range(start, start + count))
    return changed


def collect_changed_files(repo: Path, base_ref: str, target_ref: str) -> list[ChangedFile]:
    refs = [base_ref] if target_ref == "WORKTREE" else [base_ref, target_ref]
    name_status = parse_name_status(run_git(repo, "diff", "--name-status", *refs))
    diff = run_git(repo, "diff", "--unified=0", "--no-color", *refs, "--", "*.java")
    line_map = parse_changed_lines(diff)
    paths = sorted(set(name_status) | set(line_map))
    return [
        ChangedFile(path=path, status=name_status.get(path, "M"), lines=line_map.get(path, set()))
        for path in paths
    ]


def normalize_path(*parts: str) -> str:
    path = "".join(part for part in parts if part)
    path = re.sub(r"/+", "/", path)
    if not path.startswith("/"):
        path = "/" + path
    return path if path == "/" else path.rstrip("/")


def annotation_path(annotation_args: str) -> str:
    match = re.search(r'"([^"]*)"', annotation_args)
    return match.group(1) if match else ""


def extract_controller_apis(source: str, file_path: str) -> list[dict[str, str]]:
    class_pos = source.find(" class ")
    prefix_source = source[:class_pos] if class_pos >= 0 else source
    class_paths = re.findall(r"@RequestMapping\s*\(([^)]*)\)", prefix_source)
    class_path = annotation_path(class_paths[-1]) if class_paths else ""
    apis: list[dict[str, str]] = []

    mapping_pattern = re.compile(
        r"@(?P<annotation>GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping|RequestMapping)"
        r"\s*(?:\((?P<args>[^)]*)\))?"
    )
    for match in mapping_pattern.finditer(source):
        if match.start() < len(prefix_source) and match.group("annotation") == "RequestMapping":
            continue
        annotation = match.group("annotation")
        args = match.group("args") or ""
        method = ANNOTATION_METHODS.get(annotation)
        if not method:
            method_match = re.search(r"RequestMethod\.([A-Z]+)", args)
            method = method_match.group(1).lower() if method_match else "any"
        apis.append(
            {
                "method": method,
                "path": normalize_path(class_path, annotation_path(args)),
                "source_file": file_path,
            }
        )
    return apis


def load_document(location: str) -> dict[str, Any]:
    if re.match(r"https?://", location):
        with urllib.request.urlopen(location, timeout=15) as response:
            text = response.read().decode("utf-8")
    else:
        text = Path(location).read_text(encoding="utf-8")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        if yaml is None:
            raise RuntimeError("YAML OpenAPI document requires PyYAML")
        value = yaml.safe_load(text)
    if not isinstance(value, dict):
        raise ValueError(f"OpenAPI document must be an object: {location}")
    return value


def operation_signature(operation: dict[str, Any]) -> dict[str, Any]:
    parameters = operation.get("parameters") or []
    return {
        "parameters": sorted(
            (
                item.get("in", ""),
                item.get("name", ""),
                bool(item.get("required", False)),
                json.dumps(item.get("schema", {}), ensure_ascii=False, sort_keys=True),
            )
            for item in parameters
            if isinstance(item, dict)
        ),
        "requestBody": operation.get("requestBody", {}),
        "responses": operation.get("responses", {}),
    }


def openapi_operations(document: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for path, path_item in (document.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() in HTTP_METHODS and isinstance(operation, dict):
                result[(method.upper(), path)] = operation
    return result


def compare_openapi(base: dict[str, Any], current: dict[str, Any]) -> list[dict[str, str]]:
    old = openapi_operations(base)
    new = openapi_operations(current)
    changes: list[dict[str, str]] = []
    for key in sorted(set(old) | set(new)):
        method, path = key
        if key not in old:
            kind = "added"
        elif key not in new:
            kind = "removed"
        elif operation_signature(old[key]) != operation_signature(new[key]):
            kind = "modified"
        else:
            continue
        changes.append({"kind": kind, "method": method, "path": path})
    return changes


def jacoco_lines(xml_path: Path) -> dict[str, dict[int, dict[str, int]]]:
    root = ET.parse(xml_path).getroot()
    coverage: dict[str, dict[int, dict[str, int]]] = {}
    for package in root.findall(".//package"):
        package_name = package.attrib.get("name", "")
        for source in package.findall("./sourcefile"):
            file_name = source.attrib["name"]
            source_path = f"{package_name}/{file_name}".lstrip("/")
            lines: dict[int, dict[str, int]] = {}
            for line in source.findall("./line"):
                lines[int(line.attrib["nr"])] = {
                    key: int(line.attrib.get(key, "0"))
                    for key in ("mi", "ci", "mb", "cb")
                }
            coverage[source_path] = lines
    return coverage


def match_source_file(java_path: str, coverage_paths: set[str]) -> str | None:
    normalized = java_path.replace("\\", "/")
    matches = [path for path in coverage_paths if normalized.endswith(path)]
    return max(matches, key=len) if matches else None


def calculate_diff_coverage(
    changed_files: list[ChangedFile], coverage: dict[str, dict[int, dict[str, int]]]
) -> dict[str, Any]:
    file_results = []
    total = covered = 0
    coverage_paths = set(coverage)
    for changed in changed_files:
        if not changed.path.endswith(".java") or not changed.lines:
            continue
        source_path = match_source_file(changed.path, coverage_paths)
        line_data = coverage.get(source_path or "", {})
        executable = sorted(line for line in changed.lines if line in line_data)
        covered_lines = sorted(line for line in executable if line_data[line]["ci"] > 0)
        missed_lines = sorted(set(executable) - set(covered_lines))
        total += len(executable)
        covered += len(covered_lines)
        file_results.append(
            {
                "file": changed.path,
                "jacoco_source": source_path,
                "changed_lines": sorted(changed.lines),
                "executable_lines": executable,
                "covered_lines": covered_lines,
                "missed_lines": missed_lines,
            }
        )
    percent = round(covered * 100 / total, 2) if total else None
    return {
        "executable_changed_lines": total,
        "covered_changed_lines": covered,
        "missed_changed_lines": total - covered,
        "diff_line_coverage_percent": percent,
        "files": file_results,
    }


def karate_feature(apis: list[dict[str, str]]) -> str:
    lines = [
        "Feature: Generated skeleton for impacted APIs",
        "",
        "  Background:",
        "    * url baseUrl",
        "",
    ]
    seen: set[tuple[str, str]] = set()
    for api in apis:
        key = (api["method"].lower(), api["path"])
        if key in seen or key[0] == "any":
            continue
        seen.add(key)
        lines.extend(
            [
                f"  @todo",
                f"  Scenario: {key[0].upper()} {key[1]} - fill request data and assertions",
                f"    Given path '{key[1]}'",
                f"    When method {key[0]}",
                "    Then status 200",
                "",
            ]
        )
    if not seen:
        lines.extend(["  # No impacted API could be inferred. Add scenarios after review.", ""])
    return "\n".join(lines)


def markdown_report(
    changed_files: list[ChangedFile],
    controller_apis: list[dict[str, str]],
    openapi_changes: list[dict[str, str]],
    diff_coverage: dict[str, Any] | None,
) -> str:
    lines = [
        "# Java 精准测试分析报告",
        "",
        "## 摘要",
        "",
        f"- 变更文件：{len(changed_files)}",
        f"- Controller 推断接口：{len(controller_apis)}",
        f"- OpenAPI 变更：{len(openapi_changes)}",
    ]
    if diff_coverage:
        value = diff_coverage["diff_line_coverage_percent"]
        shown = "N/A" if value is None else f"{value}%"
        lines.append(f"- 新增代码行覆盖率：{shown}")
    lines.extend(["", "## 变更文件", ""])
    lines.extend(
        f"- `{item.path}`：{item.status}，新增或修改行 {len(item.lines)}"
        for item in changed_files
    )
    lines.extend(["", "## 受影响接口", ""])
    apis = {(item["method"].upper(), item["path"]) for item in controller_apis}
    apis |= {(item["method"], item["path"]) for item in openapi_changes}
    lines.extend(f"- `{method} {path}`" for method, path in sorted(apis))
    if not apis:
        lines.append("- 未自动识别，请人工确认 Service 变更对应的入口接口。")
    lines.extend(["", "## OpenAPI 变化", ""])
    lines.extend(
        f"- `{item['kind']}`：`{item['method']} {item['path']}`" for item in openapi_changes
    )
    if not openapi_changes:
        lines.append("- 未提供 OpenAPI 基线与当前文档，或契约无变化。")
    if diff_coverage:
        lines.extend(["", "## 未覆盖新增代码行", ""])
        missed = [
            f"- `{item['file']}`：{', '.join(map(str, item['missed_lines']))}"
            for item in diff_coverage["files"]
            if item["missed_lines"]
        ]
        lines.extend(missed or ["- 无。"])
    lines.extend(
        [
            "",
            "## 下一步",
            "",
            "- 基于 `review-context.json` 结合需求文档执行测试视角 Code Review。",
            "- 人工确认受影响接口，补全 `generated-tests/karate/impacted-apis.feature`。",
            "- 执行接口用例并重新导出 JaCoCo XML，复查新增代码覆盖率。",
            "",
        ]
    )
    return "\n".join(lines)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Java B/S 项目精准测试分析器")
    parser.add_argument("--repo", required=True, help="Java Git 仓库路径")
    parser.add_argument("--base-ref", required=True, help="对比基线，如 origin/main 或 HEAD~1")
    parser.add_argument("--target-ref", default="HEAD", help="目标引用；使用 WORKTREE 分析未提交代码")
    parser.add_argument("--output", required=True, help="分析产物输出目录")
    parser.add_argument("--openapi-base", help="基线 OpenAPI JSON/YAML 文件或 URL")
    parser.add_argument("--openapi-current", help="当前 OpenAPI JSON/YAML 文件或 URL")
    parser.add_argument("--jacoco-xml", help="JaCoCo XML 报告路径")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    output = Path(args.output).resolve()
    if not (repo / ".git").exists():
        parser.error(f"不是 Git 仓库: {repo}")
    output.mkdir(parents=True, exist_ok=True)

    changed_files = collect_changed_files(repo, args.base_ref, args.target_ref)
    controller_apis: list[dict[str, str]] = []
    for changed in changed_files:
        source_path = repo / changed.path
        if changed.path.endswith(".java") and source_path.exists():
            controller_apis.extend(
                extract_controller_apis(source_path.read_text(encoding="utf-8"), changed.path)
            )

    openapi_changes: list[dict[str, str]] = []
    if args.openapi_base and args.openapi_current:
        openapi_changes = compare_openapi(
            load_document(args.openapi_base), load_document(args.openapi_current)
        )
    elif args.openapi_base or args.openapi_current:
        parser.error("--openapi-base 和 --openapi-current 必须同时提供")

    diff_coverage = None
    if args.jacoco_xml:
        diff_coverage = calculate_diff_coverage(
            changed_files, jacoco_lines(Path(args.jacoco_xml))
        )

    review_context = {
        "schema_version": "1.0",
        "repository": str(repo),
        "base_ref": args.base_ref,
        "target_ref": args.target_ref,
        "changed_files": [
            {"path": item.path, "status": item.status, "changed_lines": sorted(item.lines)}
            for item in changed_files
        ],
        "controller_apis": controller_apis,
        "openapi_changes": openapi_changes,
        "diff_coverage": diff_coverage,
    }
    write_json(output / "review-context.json", review_context)
    write_json(output / "openapi-diff.json", {"changes": openapi_changes})
    write_json(output / "impacted-apis.json", {"controller_apis": controller_apis})
    if diff_coverage:
        write_json(output / "coverage" / "diff-coverage.json", diff_coverage)
    feature_path = output / "generated-tests" / "karate" / "impacted-apis.feature"
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    feature_path.write_text(karate_feature(controller_apis + openapi_changes), encoding="utf-8")
    (output / "report.md").write_text(
        markdown_report(changed_files, controller_apis, openapi_changes, diff_coverage),
        encoding="utf-8",
    )
    print(json.dumps({"status": "done", "output_dir": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
