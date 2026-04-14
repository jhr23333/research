#!/usr/bin/env python3
"""
方案D: 每次对话结束时检测 Clippings/ 中未处理的剪藏文件
触发: Stop
stderr 内容显示在终端给用户看
"""
import json
import os
import sys

VAULT = r"D:\research"
CLIPPINGS_DIR = os.path.join(VAULT, "Clippings")
PROCESSED_LOG = os.path.join(CLIPPINGS_DIR, ".processed.txt")
EXCLUDE = {"README.md", ".processed.txt"}
ALERT_THRESHOLD = 3  # 超过这个数量才提醒


def get_processed():
    if not os.path.exists(PROCESSED_LOG):
        return set()
    with open(PROCESSED_LOG, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def get_all_clippings():
    if not os.path.isdir(CLIPPINGS_DIR):
        return []
    return [
        f for f in os.listdir(CLIPPINGS_DIR)
        if f.endswith(".md") and f not in EXCLUDE
    ]


def main():
    data = json.load(sys.stdin)
    if data.get("hook_event_name") != "Stop":
        sys.exit(0)

    all_files = get_all_clippings()
    processed = get_processed()
    unprocessed = [f for f in all_files if f not in processed]

    if len(unprocessed) < ALERT_THRESHOLD:
        sys.exit(0)

    print(
        f"\n[Clippings] 有 {len(unprocessed)} 个未处理的剪藏，可运行 /kb-add 归档：",
        file=sys.stderr,
    )
    for f in unprocessed[:5]:
        print(f"  · {f}", file=sys.stderr)
    if len(unprocessed) > 5:
        print(f"  · ... 共 {len(unprocessed)} 个", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
