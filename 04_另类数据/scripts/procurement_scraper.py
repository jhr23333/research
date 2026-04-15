"""
招标数据爬虫 - 中国政府采购网 (ccgp.gov.cn)
追踪半导体/PCB 相关采购公告，作为国内产能扩张的领先指标

使用方式：
    python procurement_scraper.py              # 默认关键词，近30天
    python procurement_scraper.py --days 90   # 近90天
    python procurement_scraper.py --kw "光刻机"  # 自定义关键词

输出：
    04_另类数据/data/procurement.csv     — 追加写入，去重
    05_另起数据/看板/招标追踪.md         — 最新摘要，覆盖写入
"""

import sys
import csv
import time
import hashlib
import argparse
import datetime
import os
import requests
from bs4 import BeautifulSoup

# ── 配置 ──────────────────────────────────────────────
SEARCH_URL = "http://search.ccgp.gov.cn/bxsearch"

# 关键词组合：匹配半导体设备、PCB、封测相关采购
KEYWORDS = [
    "半导体设备",
    "晶圆",
    "刻蚀机",
    "薄膜沉积",
    "光刻机",
    "印制电路板",
    "PCB",
    "封装测试",
    "集成电路",
]

# 已知相关采购机构（用于过滤/标记，非强制）
# 按实际覆盖的产业链公司填写，此处仅保留通用半导体厂商
RELEVANT_BUYERS = [
    "中芯国际", "华虹", "长江存储", "长鑫", "北方华创",
    "中微", "华润微", "士兰微", "通富微电",
]

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
KANBAN_DIR = os.path.join(os.path.dirname(__file__), "..", "看板")
CSV_PATH = os.path.join(DATA_DIR, "procurement.csv")
MD_PATH = os.path.join(KANBAN_DIR, "招标追踪.md")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

CSV_FIELDS = ["id", "date", "title", "buyer", "type", "url", "keyword", "relevance"]


# ── 工具函数 ──────────────────────────────────────────
def make_id(title: str, date: str) -> str:
    return hashlib.md5(f"{title}{date}".encode()).hexdigest()[:10]


def load_existing_ids() -> set:
    if not os.path.exists(CSV_PATH):
        return set()
    with open(CSV_PATH, encoding="utf-8") as f:
        return {row["id"] for row in csv.DictReader(f)}


def mark_relevance(title: str, buyer: str) -> str:
    """简单相关性标注：高/中/低"""
    text = title + buyer
    if any(b in text for b in RELEVANT_BUYERS):
        return "高"
    high_signals = ["扩产", "新建", "产线", "fab", "FAB", "生产线"]
    if any(s in text for s in high_signals):
        return "中"
    return "低"


# ── 爬取函数 ──────────────────────────────────────────
def fetch_page(keyword: str, page: int, days: int) -> list[dict]:
    """抓取单页结果，返回公告列表"""
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days)

    params = {
        "searchtype": "1",
        "kw": keyword,
        "start_time": start.strftime("%Y:%m:%d"),
        "end_time": end.strftime("%Y:%m:%d"),
        "timeType": "6",
        "dbselect": "bidx",
        "bidType": "0",
        "page_index": str(page),
    }

    try:
        resp = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = "utf-8"
    except requests.RequestException as e:
        print(f"  ⚠️  请求失败（{keyword} 第{page}页）: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = []

    for li in soup.select("ul.vT-srch-result-list-bid li"):
        try:
            a_tag = li.select_one("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            url = a_tag.get("href", "")

            spans = li.select("span")
            buyer = spans[0].get_text(strip=True) if len(spans) > 0 else ""
            ann_type = spans[1].get_text(strip=True) if len(spans) > 1 else ""
            date_str = spans[-1].get_text(strip=True) if spans else ""

            items.append({
                "id": make_id(title, date_str),
                "date": date_str,
                "title": title,
                "buyer": buyer,
                "type": ann_type,
                "url": url,
                "keyword": keyword,
                "relevance": mark_relevance(title, buyer),
            })
        except Exception:
            continue

    return items


def scrape(keywords: list[str], days: int) -> list[dict]:
    """遍历关键词，每个关键词抓前2页"""
    existing = load_existing_ids()
    new_items = []

    for kw in keywords:
        print(f"🔍 搜索：{kw}")
        for page in range(1, 3):
            items = fetch_page(kw, page, days)
            if not items:
                break
            for item in items:
                if item["id"] not in existing:
                    new_items.append(item)
                    existing.add(item["id"])
            time.sleep(1.5)  # 礼貌性延迟

    return new_items


# ── 写入函数 ──────────────────────────────────────────
def append_csv(items: list[dict]):
    os.makedirs(DATA_DIR, exist_ok=True)
    write_header = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerows(items)


def write_kanban(items: list[dict], days: int):
    """生成 Obsidian 看板笔记"""
    os.makedirs(KANBAN_DIR, exist_ok=True)
    today = datetime.date.today().isoformat()

    # 按相关性排序
    high = [i for i in items if i["relevance"] == "高"]
    mid  = [i for i in items if i["relevance"] == "中"]
    low  = [i for i in items if i["relevance"] == "低"]

    lines = [
        f"# 招标追踪：半导体/PCB 采购公告",
        f"> 数据来源：中国政府采购网 ccgp.gov.cn | 更新：{today} | 搜索范围：近{days}天",
        f"> 新增公告：{len(items)} 条（高相关 {len(high)} / 中 {len(mid)} / 低 {len(low)}）",
        "",
        "## 关联公司映射",
        "<!-- 按 04_另类数据/README.md 中登记的覆盖公司填写 -->",
        "",
    ]

    def fmt_section(title, data):
        if not data:
            return []
        result = [f"## {title}（{len(data)} 条）", ""]
        for i in data[:20]:  # 每类最多显示20条
            result.append(f"- **{i['date']}** [{i['type']}] {i['buyer']}")
            result.append(f"  {i['title']}")
            if i["url"]:
                result.append(f"  [原文链接]({i['url']})")
            result.append("")
        return result

    lines += fmt_section("⭐ 高相关（已知企业 / 明确扩产）", high)
    lines += fmt_section("🔶 中相关（含产线/扩产关键词）", mid)

    if low:
        lines.append(f"## 低相关（{len(low)} 条，已折叠）")
        lines.append(f"> 含关键词但相关性低，查看 procurement.csv 获取完整列表")
        lines.append("")

    lines += [
        "## 信号判断指引",
        "- 同一采购方短期内多条采购 → 扩产信号",
        "- 出现新采购方（非常规企业）→ 新建产线信号",
        "- PCB/基板设备采购量增加 → 潜在利好，参考 04_另类数据/README.md 中的假设映射",
        "",
        f"[[04_另类数据]]",
    ]

    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ── 主函数 ────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="政府采购网半导体招标爬虫")
    parser.add_argument("--days", type=int, default=30, help="搜索近N天（默认30）")
    parser.add_argument("--kw", type=str, default=None, help="自定义关键词（覆盖默认列表）")
    args = parser.parse_args()

    keywords = [args.kw] if args.kw else KEYWORDS

    print(f"📡 开始抓取，关键词 {len(keywords)} 个，范围：近{args.days}天")
    items = scrape(keywords, args.days)

    if items:
        append_csv(items)
        write_kanban(items, args.days)
        print(f"\n✅ 新增 {len(items)} 条公告")
        print(f"   CSV  → {CSV_PATH}")
        print(f"   看板 → {MD_PATH}")

        # 打印高相关条目
        high = [i for i in items if i["relevance"] == "高"]
        if high:
            print(f"\n⭐ 高相关公告（{len(high)} 条）：")
            for i in high[:5]:
                print(f"   {i['date']} | {i['buyer']} | {i['title'][:40]}")
    else:
        print("ℹ️  无新增公告（数据已是最新，或网络问题）")
        # 仍然更新看板时间戳
        write_kanban([], args.days)


if __name__ == "__main__":
    main()
