#!/usr/bin/env python3
"""
Skills 完整性檢查腳本

確認每個 skill 目錄下都有 SKILL.md，且 SKILL.md 包含必要的欄位。
用於 pre-commit hook。
"""

import sys
from pathlib import Path

SKILLS_DIR = Path(".claude/skills")
REQUIRED_SECTIONS = ["觸發", "流程", "輸出"]  # 至少提到其中之一
REQUIRED_FILES = ["SKILL.md"]

# Windows console 可能不支援 emoji，改用 ASCII 替代
ICON_FAIL = "[FAIL]"
ICON_WARN = "[WARN]"
ICON_OK = "[OK]"


def check_skills() -> list[str]:
    """檢查所有 skills 的完整性。"""
    errors: list[str] = []

    if not SKILLS_DIR.exists():
        errors.append(f"{ICON_FAIL} Skills directory not found: {SKILLS_DIR}")
        return errors

    skill_dirs = [d for d in SKILLS_DIR.iterdir() if d.is_dir()]

    if not skill_dirs:
        errors.append(f"{ICON_WARN} No skill directories found: {SKILLS_DIR}")
        return errors

    for skill_dir in sorted(skill_dirs):
        skill_name = skill_dir.name

        # 檢查 SKILL.md 存在
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            errors.append(f"{ICON_FAIL} {skill_name}: 缺少 SKILL.md")
            continue

        # 檢查 SKILL.md 非空且有基本內容
        content = skill_md.read_text(encoding="utf-8")
        if len(content.strip()) < 50:
            errors.append(f"{ICON_WARN} {skill_name}: SKILL.md 內容過短 ({len(content)} chars)")

        # 檢查是否有標題（支援 YAML frontmatter 格式）
        has_heading = content.startswith("#") or content.startswith("---")
        if not has_heading:
            errors.append(f"{ICON_WARN} {skill_name}: SKILL.md 應以 # 標題或 --- frontmatter 開頭")

    return errors


def main() -> int:
    """主程式。"""
    errors = check_skills()

    if errors:
        print("Skills check found issues:")
        for err in errors:
            print(f"  {err}")
        # 只有 ❌ 才算失敗
        critical = [e for e in errors if e.startswith(ICON_FAIL)]
        if critical:
            return 1

    skill_count = len(list(SKILLS_DIR.iterdir())) if SKILLS_DIR.exists() else 0
    print(f"{ICON_OK} Skills check passed ({skill_count} skills)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
