from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "django_rclone"
ALLOWED_POPEN_PATHS = {
    SRC_ROOT / "rclone.py",
    SRC_ROOT / "db" / "mongodb.py",
    SRC_ROOT / "db" / "mysql.py",
    SRC_ROOT / "db" / "postgresql.py",
    SRC_ROOT / "db" / "sqlite.py",
}


def _source_files() -> list[Path]:
    return sorted(path for path in SRC_ROOT.rglob("*.py") if path.is_file())


def _is_popen_call(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr == "Popen"
    if isinstance(node.func, ast.Name):
        return node.func.id == "Popen"
    return False


def test_no_wait_calls_in_runtime_code():
    offenders: list[str] = []
    for path in _source_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "wait":
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    assert not offenders, "Use process_utils.finish_process()/communicate() instead of wait():\n" + "\n".join(offenders)


def test_popen_calls_are_limited_to_wrapper_modules():
    offenders: list[str] = []
    for path in _source_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_popen_call(node) and path not in ALLOWED_POPEN_PATHS:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    assert not offenders, "Create subprocesses only in rclone/db wrappers:\n" + "\n".join(offenders)
