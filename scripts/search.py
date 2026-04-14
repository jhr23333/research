"""
research库全文搜索工具
用法：
  python search.py "关键词"               # 全库搜索
  python search.py "关键词" --dir 01_公司  # 限定目录
  python search.py "关键词" --type 假设   # 只搜特定文件名
  python search.py "关键词" --context 3   # 显示前后3行（默认2行）

输出：文件路径 + 行号 + 匹配行 + 上下文
"""

import sys
import os
import re
import argparse

VAULT = r"D:\research"
EXCLUDE_DIRS = {".obsidian", ".claude", "scripts", ".git", "inbox", "Clippings"}
EXCLUDE_FILES = {"README.md", "_index.md"}


def search(query, search_dir=None, filename_filter=None, context_lines=2):
    root = os.path.join(VAULT, search_dir) if search_dir else VAULT
    pattern = re.compile(query, re.IGNORECASE)
    results = []

    for dirpath, dirnames, filenames in os.walk(root):
        # 跳过排除目录
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]

        for filename in filenames:
            if not filename.endswith(".md"):
                continue
            if filename in EXCLUDE_FILES:
                continue
            if filename_filter and filename_filter not in filename:
                continue

            filepath = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(filepath, VAULT)

            try:
                with open(filepath, encoding="utf-8") as f:
                    lines = f.readlines()
            except Exception:
                continue

            for i, line in enumerate(lines):
                if pattern.search(line):
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    ctx = lines[start:end]
                    results.append({
                        "file": rel_path,
                        "line": i + 1,
                        "match": line.rstrip(),
                        "context": ctx,
                        "context_start": start + 1,
                    })

    return results


def format_results(results, query):
    if not results:
        print(f"未找到匹配「{query}」的内容")
        return

    print(f"找到 {len(results)} 处匹配「{query}」\n")
    current_file = None

    for r in results:
        if r["file"] != current_file:
            current_file = r["file"]
            print(f"\n📄 {current_file}")
            print("─" * 60)

        print(f"  第{r['line']}行：{r['match']}")
        for j, ctx_line in enumerate(r["context"]):
            lineno = r["context_start"] + j
            marker = "→ " if lineno == r["line"] else "  "
            print(f"  {marker}{lineno:3d} │ {ctx_line.rstrip()}")
        print()


def main():
    parser = argparse.ArgumentParser(description="research库全文搜索")
    parser.add_argument("query", help="搜索关键词（支持正则）")
    parser.add_argument("--dir", help="限定搜索目录（相对于库根目录）", default=None)
    parser.add_argument("--type", help="文件名包含的关键词", default=None)
    parser.add_argument("--context", type=int, help="上下文行数", default=2)
    args = parser.parse_args()

    results = search(args.query, args.dir, args.type, args.context)
    format_results(results, args.query)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
