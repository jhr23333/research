#!/usr/bin/env python3
"""
方案A: 假设.md / memo.md 更新后自动重建 _index.md
触发: PostToolUse (Write, Edit)
"""
import json
import os
import re
import sys
from datetime import datetime

VAULT = r"D:\research"
COMPANIES_DIR = os.path.join(VAULT, "01_公司")
INDEX_FILE = os.path.join(VAULT, "_index.md")
NODES_DIR = os.path.join(VAULT, "02_产业链节点")


def should_trigger(data):
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "").replace("\\", "/")
    return "假设.md" in file_path or "memo.md" in file_path


def read_file(filepath):
    try:
        with open(filepath, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def parse_company(company_dir):
    result = {
        "ticker": "",
        "conviction": "",
        "verified": 0,
        "uncertain": 0,
        "pending": 0,
        "refuted": 0,
        "pending_questions": 0,
    }

    # ticker 从 基本面.md 读（支持 code: 000001 或 ticker: 000001.SZ 两种格式）
    basic = read_file(os.path.join(company_dir, "基本面.md"))
    ticker_m = re.search(r"(?:ticker|code)[:\s]+(\d{6}(?:\.[A-Z]{2})?)", basic, re.IGNORECASE)
    if ticker_m:
        result["ticker"] = ticker_m.group(1)

    # conviction 从 memo.md 读 rating 字段
    memo = read_file(os.path.join(company_dir, "memo.md"))
    rating_m = re.search(r"rating[:\s]+(.+)", memo)
    conv_map = {"非常高": "⭐⭐⭐⭐⭐", "较高": "⭐⭐⭐⭐", "中等": "⭐⭐⭐",
                "较低": "⭐⭐", "低": "⭐", "跟踪中": "⭐⭐⭐"}
    if rating_m:
        rating_val = rating_m.group(1).strip()
        result["conviction"] = conv_map.get(rating_val, rating_val)

    # 假设状态从 假设.md 的"核心假设"表格里数（避免把"状态说明"里的符号也计入）
    hyp = read_file(os.path.join(company_dir, "假设.md"))
    table_m = re.search(r"## 核心假设\n(.*?)(?=\n##|\Z)", hyp, re.DOTALL)
    table = table_m.group(1) if table_m else ""
    result["verified"] = len(re.findall(r"✅", table))
    result["uncertain"] = len(re.findall(r"⚠️", table))
    result["pending"] = len(re.findall(r"🔲", table))
    result["refuted"] = len(re.findall(r"❌", table))

    # 待核实问题：数"待核实问题"section下的bullet条数
    pending_section = re.search(r"## 待核实问题\n(.*?)(?=\n##|\Z)", hyp, re.DOTALL)
    if pending_section:
        bullets = re.findall(r"^\s*-\s+.+", pending_section.group(1), re.MULTILINE)
        result["pending_questions"] = len(bullets)

    return result


def get_latest_note_date(company_dir):
    note_dir = os.path.join(company_dir, "纪要")
    if not os.path.isdir(note_dir):
        return "-"
    dates = []
    for f in os.listdir(note_dir):
        if not f.endswith(".md"):
            continue
        m = re.match(r"(\d{4}-\d{2}-\d{2})", f)
        if m:
            dates.append(m.group(1))
    return max(dates) if dates else "-"


def build_index():
    if not os.path.isdir(COMPANIES_DIR):
        return

    companies = []
    for company_name in sorted(os.listdir(COMPANIES_DIR)):
        company_dir = os.path.join(COMPANIES_DIR, company_name)
        if not os.path.isdir(company_dir) or company_name.startswith("."):
            continue
        if not os.path.exists(os.path.join(company_dir, "假设.md")):
            continue

        info = parse_company(company_dir)
        latest_date = get_latest_note_date(company_dir)

        # 假设状态摘要
        parts = []
        if info["verified"]:
            parts.append(f"✅×{info['verified']}")
        if info["uncertain"]:
            parts.append(f"⚠️×{info['uncertain']}")
        if info["pending"]:
            parts.append(f"🔲×{info['pending']}")
        if info["refuted"]:
            parts.append(f"❌×{info['refuted']}")
        status_str = " ".join(parts) if parts else "-"

        companies.append({
            "name": company_name,
            "ticker": info["ticker"],
            "conviction": info["conviction"] or "⭐⭐⭐",
            "status": status_str,
            "latest_date": latest_date,
            "pending_questions": info["pending_questions"],
            "uncertain": info["uncertain"],
            "pending": info["pending"],
        })

    # 产业链节点
    all_nodes = {}
    if os.path.isdir(NODES_DIR):
        for f in os.listdir(NODES_DIR):
            if not f.endswith(".md") or f.startswith("_"):
                continue
            node_name = f.replace(".md", "")
            filepath = os.path.join(NODES_DIR, f)
            mtime = os.path.getmtime(filepath)
            mdate = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
            content = read_file(filepath)
            related = [c["name"] for c in companies if c["name"] in content]
            all_nodes[node_name] = {"date": mdate, "companies": related}

    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "# 覆盖公司总览",
        "",
        f"> 由脚本自动维护。最后更新：{today}",
        "",
        "## 覆盖公司状态",
        "",
        "| 公司 | 代码 | Conviction | 假设状态 | 最近纪要 | 待核实问题数 |",
        "|------|------|-----------|---------|---------|------------|",
    ]
    for c in companies:
        lines.append(
            f"| [[{c['name']}]] | {c['ticker']} | {c['conviction']} "
            f"| {c['status']} | {c['latest_date']} | {c['pending_questions']} |"
        )

    lines += [
        "",
        "## Conviction说明",
        "- ⭐⭐⭐⭐⭐ 非常高：核心假设全部验证，逻辑闭环",
        "- ⭐⭐⭐⭐ 较高：主要假设验证，少量待确认",
        "- ⭐⭐⭐ 中等：有支撑但存在重要存疑假设",
        "- ⭐⭐ 较低：假设矛盾较多，需要更多调研",
        "- ⭐ 低：逻辑尚未闭环",
        "",
        "## 假设状态汇总（存疑/待确认）",
        "",
        "| 公司 | 存疑假设数 | 待确认假设数 |",
        "|------|-----------|------------|",
    ]
    for c in companies:
        if c["uncertain"] > 0 or c["pending"] > 0:
            lines.append(f"| [[{c['name']}]] | {c['uncertain']} | {c['pending']} |")

    if all_nodes:
        lines += [
            "",
            "## 产业链节点索引",
            "",
            "| 节点 | 关联公司 | 最后更新 |",
            "|------|---------|---------|",
        ]
        for node_name, node_info in sorted(all_nodes.items()):
            related_str = "、".join(node_info["companies"]) if node_info["companies"] else "-"
            lines.append(f"| [[{node_name}]] | {related_str} | {node_info['date']} |")

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    # 支持两种模式：hook模式（stdin读JSON）和直接运行模式
    if not sys.stdin.isatty():
        try:
            data = json.load(sys.stdin)
            if not should_trigger(data):
                sys.exit(0)
        except Exception:
            pass  # stdin解析失败时直接运行

    try:
        build_index()
        print("[research] _index.md 已自动同步", file=sys.stderr)
    except Exception as e:
        print(f"[research] _index.md 同步失败: {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
