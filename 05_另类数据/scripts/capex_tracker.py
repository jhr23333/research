"""
资本开支追踪器 - 基于 iFind search_notice
追踪半导体产业链关键公司的资本开支指引、产能规划公告

覆盖范围：
  晶圆代工：台积电(TSM)、中芯国际、华虹半导体、三星、英特尔
  设备商：  ASML、应用材料(AMAT)、泛林(LRCX)、北方华创、中微公司
  封测：    日月光、长电科技
  AI基础设施：Amazon/AWS、微软Azure、谷歌、Meta、字节、腾讯、阿里

使用方式：
  python capex_tracker.py              # 拉取近90天公告
  python capex_tracker.py --days 180   # 拉取近180天

输出：
  05_另类数据/data/capex_log.csv       — 追加，去重
  05_另类数据/看板/资本开支追踪.md     — 覆盖写入，Obsidian看板
"""

# ════════════════════════════════════════════
# 注意：此脚本依赖 iFind MCP 工具 (search_notice)
# 在 Claude Code 中通过 /alt-data 触发，由 AI 调用 MCP
# 本文件仅记录追踪逻辑和配置，实际调用由 SKILL.md 驱动
# ════════════════════════════════════════════

# ── 监控列表配置说明 ──────────────────────────────────
# link 字段格式："{覆盖公司缩写}H{假设编号}"，按实际覆盖公司填写
# 示例：{"signal": "资本开支 产能扩张", "link": "公司AH2 公司BH1"}
# ────────────────────────────────────────────────────

CAPEX_WATCHLIST = {
    # 晶圆代工 → 影响设备商订单 + 封测需求
    "foundry": {
        "中芯国际":   {"signal": "资本开支 产能扩张 月产能",   "link": ""},
        "华虹半导体": {"signal": "资本开支 无锡产线 新增产能", "link": ""},
        "台积电":     {"signal": "资本开支 CoWoS 先进封装",   "link": ""},
    },

    # 设备商 → 比晶圆厂资本开支领先0-2季度的早期信号
    "equipment": {
        "北方华创":   {"signal": "订单 出货 资本开支",         "link": "行业景气"},
        "中微公司":   {"signal": "订单 新签 刻蚀设备",         "link": "行业景气"},
        "ASML":       {"signal": "光刻机订单 出货",            "link": "行业景气"},
    },

    # AI基础设施 → 服务器需求
    "ai_infra": {
        "Amazon AWS":  {"signal": "资本支出 数据中心 服务器",    "link": ""},
        "微软 Azure":  {"signal": "资本支出 数据中心 AI基础设施", "link": ""},
        "谷歌 Google": {"signal": "资本支出 数据中心 TPU",       "link": ""},
        "Meta":        {"signal": "资本支出 数据中心 AI服务器",  "link": ""},
        "字节跳动":    {"signal": "数据中心 服务器采购 算力",    "link": ""},
    },

    # 封测 → PCB/基板需求的另一个观测点
    "packaging": {
        "日月光":      {"signal": "资本开支 先进封装 CoWoS",   "link": ""},
        "长电科技":    {"signal": "资本开支 产能",              "link": ""},
    },
}

# ── 信号关键词（出现即标记为高价值公告）──────────────
HIGH_VALUE_KEYWORDS = [
    "资本开支", "capex", "CapEx",
    "产能扩张", "新建产线", "新增产能",
    "月产能增加", "在建工程",
    "设备订单", "新签订单",
    "数据中心投资", "AI基础设施",
]

# ── 使用说明 ─────────────────────────────────────────
USAGE = """
调用方式（在 Claude Code 中）：
  /alt-data 资本开支

执行逻辑（由 alt-data SKILL 驱动）：
  1. 读取上方 CAPEX_WATCHLIST
  2. 对每家公司调用 iFind search_notice，时间范围=近90天，size=5
  3. 扫描公告片段中是否含 HIGH_VALUE_KEYWORDS
  4. 含关键词的公告 → 标记为信号，提取数值，写入 capex_log.csv
  5. 生成 Obsidian 看板笔记（资本开支追踪.md）
  6. 信号触发时（资本开支指引上调/下调 >10%）→ 追加至对应公司 假设.md

输出格式（capex_log.csv）：
  date, company, category, signal_type, value, unit, source_title, link_to_hypothesis
"""

if __name__ == "__main__":
    print(USAGE)
    print("\n当前监控列表：")
    for cat, companies in CAPEX_WATCHLIST.items():
        print(f"\n[{cat}]")
        for name, cfg in companies.items():
            print(f"  {name} → {cfg['link']}")
