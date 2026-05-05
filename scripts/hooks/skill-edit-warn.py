#!/usr/bin/env python3
"""
PostToolUse hook: SKILL.md 被编辑时，提醒检查 CLAUDE.md / README.md 是否需要同步。
触发: PostToolUse (Write, Edit)，file_path 匹配 .claude/skills/X/SKILL.md
作用: 抓"功能改了 SKILL.md 但忘了改上层索引"这一类漂移
"""
import json
import os
import re
import sys

VAULT = r"D:\research"
KEY_DOCS = ["CLAUDE.md", "README.md"]


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    norm = file_path.replace("\\", "/")

    m = re.search(r"\.claude/skills/([^/]+)/SKILL\.md", norm)
    if not m:
        sys.exit(0)

    skill = m.group(1)

    print(
        f"\n[doc-sync] /{skill} SKILL.md 已修改 — 检查以下文档是否需要同步：",
        file=sys.stderr,
    )
    for doc in KEY_DOCS:
        path = os.path.join(VAULT, doc)
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue
        if skill in content:
            print(f"  · {doc}（含 /{skill} 引用，确认一句话描述是否仍准确）", file=sys.stderr)
        else:
            print(f"  · {doc}（未引用 /{skill}，可能需要新增条目）", file=sys.stderr)
    print(
        f"  也可跑 /lint 做完整文档一致性扫描\n",
        file=sys.stderr,
    )

    sys.exit(0)


if __name__ == "__main__":
    main()
