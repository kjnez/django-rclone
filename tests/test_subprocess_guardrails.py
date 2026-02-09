from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "django_rclone"
ALLOWED_SUBPROCESS_CALL_PATHS = {
    SRC_ROOT / "rclone.py",
    SRC_ROOT / "db" / "mongodb.py",
    SRC_ROOT / "db" / "mysql.py",
    SRC_ROOT / "db" / "postgresql.py",
    SRC_ROOT / "db" / "sqlite.py",
}


def _source_files() -> list[Path]:
    return sorted(path for path in SRC_ROOT.rglob("*.py") if path.is_file())


def _collect_subprocess_aliases(tree: ast.AST) -> tuple[set[str], set[str]]:
    module_aliases = {"subprocess"}
    direct_call_aliases: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess":
                    module_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            for alias in node.names:
                if alias.name in {"Popen", "run"}:
                    direct_call_aliases.add(alias.asname or alias.name)

    return module_aliases, direct_call_aliases


def _is_subprocess_call(node: ast.Call, module_aliases: set[str], direct_call_aliases: set[str]) -> bool:
    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
        return node.func.value.id in module_aliases and node.func.attr in {"Popen", "run"}
    if isinstance(node.func, ast.Name):
        return node.func.id in direct_call_aliases
    return False


def test_no_wait_calls_in_runtime_code():
    offenders: list[str] = []
    for path in _source_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "wait":
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    assert not offenders, "Use process_utils.finish_process()/communicate() instead of wait():\n" + "\n".join(offenders)


def test_subprocess_calls_are_limited_to_wrapper_modules():
    offenders: list[str] = []
    for path in _source_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        module_aliases, direct_call_aliases = _collect_subprocess_aliases(tree)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and _is_subprocess_call(node, module_aliases, direct_call_aliases)
                and path not in ALLOWED_SUBPROCESS_CALL_PATHS
            ):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    assert not offenders, "Call subprocess.run/Popen only in rclone/db wrappers:\n" + "\n".join(offenders)
