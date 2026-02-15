#!/usr/bin/env python3
"""
DDD 架構依賴方向檢查

正確方向: Presentation → Application → Domain ← Infrastructure
禁止:
  - Domain 不能 import Infrastructure / Application / Presentation
  - Application 不能 import Infrastructure (直接)
  - Infrastructure 不能 import Presentation

用於 pre-commit hook。
"""

import ast
import sys
from pathlib import Path

SRC_DIR = Path("src/hyperhierarchical_rag")

# 定義禁止的 import 規則
# key = 來源層, value = 禁止 import 的層
FORBIDDEN_IMPORTS: dict[str, list[str]] = {
    "Domain": ["Infrastructure", "Application", "Presentation"],
    "Application": ["Presentation"],
    "Infrastructure": ["Presentation"],
}


def get_layer(file_path: Path) -> str | None:
    """從檔案路徑識別所在的 DDD 層。"""
    parts = file_path.parts
    for layer in ["Domain", "Application", "Infrastructure", "Presentation"]:
        if layer in parts:
            return layer
    return None


def get_module_level_imports(file_path: Path) -> list[tuple[str, int]]:
    """解析 Python 檔案中的模組級 import 語句（忽略函數內的 lazy import）。"""
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    imports: list[tuple[str, int]] = []
    for node in ast.iter_child_nodes(tree):
        # 只看 top-level statements
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append((node.module, node.lineno))
        # 也檢查 class body 的 top-level imports
        elif isinstance(node, ast.ClassDef | ast.If | ast.Try):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.Import):
                    for alias in child.names:
                        imports.append((alias.name, child.lineno))
                elif isinstance(child, ast.ImportFrom) and child.module:
                    imports.append((child.module, child.lineno))
    return imports


def check_ddd_dependencies() -> list[str]:
    """檢查所有 Python 檔案的 DDD 依賴方向。"""
    errors: list[str] = []

    if not SRC_DIR.exists():
        errors.append(f"[FAIL] Source dir not found: {SRC_DIR}")
        return errors

    python_files = list(SRC_DIR.rglob("*.py"))

    for py_file in python_files:
        source_layer = get_layer(py_file)
        if source_layer is None:
            continue

        forbidden = FORBIDDEN_IMPORTS.get(source_layer, [])
        if not forbidden:
            continue

        imports = get_module_level_imports(py_file)
        rel_path = py_file.relative_to(Path("."))

        for imp, lineno in imports:
            for forbidden_layer in forbidden:
                # 檢查 import 路徑是否包含禁止層
                if f".{forbidden_layer}." in imp or imp.endswith(f".{forbidden_layer}"):
                    errors.append(
                        f"[FAIL] {rel_path}:{lineno}: "
                        f"{source_layer} should not import {forbidden_layer} "
                        f"(found: {imp})"
                    )

    return errors


def main() -> int:
    """主程式。"""
    errors = check_ddd_dependencies()

    if errors:
        print("DDD dependency violations found:")
        for err in errors:
            print(f"  {err}")
        return 1

    file_count = len(list(SRC_DIR.rglob("*.py"))) if SRC_DIR.exists() else 0
    print(f"[OK] DDD dependency check passed ({file_count} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
