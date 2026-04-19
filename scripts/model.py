"""
财务模型计算脚本
功能：RSI/MACD/MA 技术指标、情景P&L辅助、implied假设反推

依赖：pandas, numpy（标准数据科学库，已含在 anaconda 中）
数据来源：iFind MCP（价格数据由 Claude 调用后以 JSON 传入）

使用方式（在 Claude Code 中由 /model skill 驱动）：
  python model.py --mode technical --data prices.json
  python model.py --mode implied   --mktcap 500 --metric pe --earnings 20
  python model.py --mode scenario  --help

各 mode 也可直接 import 调用（见下方函数）。
"""

import argparse
import json
import sys
import math
from typing import Optional

# ══════════════════════════════════════════════════════════════════
# 一、技术指标计算
# ══════════════════════════════════════════════════════════════════

def calc_rsi(closes: list[float], period: int = 14) -> Optional[float]:
    """
    计算 RSI(period)。
    closes: 按时间升序排列的收盘价列表（最新价在末尾）
    返回最新一期 RSI 值（0-100），数据不足返回 None。
    """
    if len(closes) < period + 1:
        return None

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0) for d in deltas]
    losses = [abs(min(d, 0)) for d in deltas]

    # 初始平均（简单平均，后续用 Wilder 平滑）
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def calc_ema(values: list[float], period: int) -> list[float]:
    """计算 EMA 序列，长度与输入相同（前 period-1 个为 None）。"""
    k = 2 / (period + 1)
    emas = [None] * len(values)
    # 用前 period 个数据的简单平均作为种子
    if len(values) < period:
        return emas
    seed = sum(values[:period]) / period
    emas[period - 1] = seed
    for i in range(period, len(values)):
        emas[i] = values[i] * k + emas[i - 1] * (1 - k)
    return emas


def calc_macd(closes: list[float],
              fast: int = 12, slow: int = 26, signal: int = 9
              ) -> dict:
    """
    计算 MACD（DIF）、信号线（DEA）、柱状图（Histogram）。
    返回最新值字典，数据不足时对应字段为 None。
    """
    ema_fast = calc_ema(closes, fast)
    ema_slow = calc_ema(closes, slow)

    dif = []
    for f, s in zip(ema_fast, ema_slow):
        if f is None or s is None:
            dif.append(None)
        else:
            dif.append(f - s)

    valid_dif = [v for v in dif if v is not None]
    if len(valid_dif) < signal:
        return {"macd": None, "signal_line": None, "histogram": None,
                "crossover": None}

    dea_series = calc_ema(valid_dif, signal)
    latest_dif = valid_dif[-1]
    latest_dea = dea_series[-1]

    if latest_dea is None:
        return {"macd": None, "signal_line": None, "histogram": None,
                "crossover": None}

    histogram = (latest_dif - latest_dea) * 2  # 习惯乘2放大显示
    # 金叉/死叉：检测最近两期 MACD 与信号线的位置关系
    prev_dif = valid_dif[-2] if len(valid_dif) >= 2 else None
    prev_dea = dea_series[-2] if len(dea_series) >= 2 and dea_series[-2] is not None else None
    crossover = None
    if prev_dif is not None and prev_dea is not None:
        if prev_dif < prev_dea and latest_dif >= latest_dea:
            crossover = "金叉"
        elif prev_dif > prev_dea and latest_dif <= latest_dea:
            crossover = "死叉"
        elif latest_dif > latest_dea:
            crossover = "多头（MACD在信号线上方）"
        else:
            crossover = "空头（MACD在信号线下方）"

    return {
        "macd": round(latest_dif, 4),
        "signal_line": round(latest_dea, 4),
        "histogram": round(histogram, 4),
        "crossover": crossover,
    }


def calc_ma(closes: list[float], periods: list[int] = None) -> dict:
    """计算多条移动均线，返回最新值。"""
    if periods is None:
        periods = [20, 60, 250]
    result = {}
    latest = closes[-1] if closes else None
    for p in periods:
        if len(closes) >= p:
            ma_val = round(sum(closes[-p:]) / p, 3)
            result[f"MA{p}"] = ma_val
            if latest:
                result[f"vs_MA{p}"] = "上方" if latest > ma_val else "下方"
        else:
            result[f"MA{p}"] = None
            result[f"vs_MA{p}"] = "数据不足"
    return result


def calc_volume_signal(volumes: list[float], closes: list[float]) -> dict:
    """
    量价关系分析：
    - 5日均量 vs 20日均量（放量/缩量）
    - 最近5日价格趋势 vs 最近5日成交量趋势（健康/背离）
    """
    result = {}
    if len(volumes) >= 20:
        avg5 = sum(volumes[-5:]) / 5
        avg20 = sum(volumes[-20:]) / 20
        ratio = avg5 / avg20
        result["vol_5d_vs_20d"] = round(ratio, 2)
        result["vol_status"] = "放量" if ratio > 1.2 else ("缩量" if ratio < 0.8 else "正常")
    else:
        result["vol_5d_vs_20d"] = None
        result["vol_status"] = "数据不足"

    if len(closes) >= 5 and len(volumes) >= 5:
        price_trend = closes[-1] - closes[-5]   # 正=价格上涨
        vol_trend = volumes[-1] - volumes[-5]   # 正=成交量上升
        if price_trend > 0 and vol_trend > 0:
            result["pv_relation"] = "健康（价涨量增）"
        elif price_trend > 0 and vol_trend < 0:
            result["pv_relation"] = "背离⚠️（价涨量缩，上涨可持续性存疑）"
        elif price_trend < 0 and vol_trend > 0:
            result["pv_relation"] = "恐慌放量（价跌量增，可能近底部）"
        else:
            result["pv_relation"] = "弱势缩量（价跌量缩，缺乏承接）"
    else:
        result["pv_relation"] = "数据不足"

    return result


def rsi_signal(rsi: Optional[float]) -> str:
    if rsi is None:
        return "N/A"
    if rsi < 30:
        return f"🟢 超卖({rsi})"
    if rsi > 70:
        return f"🔴 超买({rsi})"
    return f"🟡 中性({rsi})"


def run_technical(data: dict) -> dict:
    """
    主入口：接收价格/成交量数据，输出完整技术面信号。
    data 格式：{"closes": [...], "volumes": [...], "dates": [...]}
    """
    closes = data.get("closes", [])
    volumes = data.get("volumes", [])

    rsi = calc_rsi(closes)
    macd = calc_macd(closes)
    ma = calc_ma(closes)
    vol = calc_volume_signal(volumes, closes)

    return {
        "rsi": rsi_signal(rsi),
        "rsi_raw": rsi,
        "macd_crossover": macd["crossover"],
        "macd_histogram": macd["histogram"],
        "macd_above_signal": (macd["macd"] or 0) > (macd["signal_line"] or 0),
        **ma,
        **vol,
    }


# ══════════════════════════════════════════════════════════════════
# 二、当前定价反推（What's Priced In）
# ══════════════════════════════════════════════════════════════════

def implied_growth(current_mktcap: float,
                   base_metric: float,
                   multiple: float,
                   historical_metric: float) -> dict:
    """
    反推市场隐含增速。
    current_mktcap: 当前市值（亿元）
    base_metric: 用于定价的基础指标（如历史净利润或营收，亿元）
    multiple: 目标倍数（如 PE=25）
    historical_metric: 上一年实际值，用于计算隐含增速

    返回：隐含指标值、隐含增速
    """
    implied_metric = current_mktcap / multiple
    if historical_metric and historical_metric != 0:
        implied_growth_rate = (implied_metric - historical_metric) / abs(historical_metric)
    else:
        implied_growth_rate = None

    return {
        "implied_metric_bn": round(implied_metric, 2),
        "implied_growth_pct": round(implied_growth_rate * 100, 1) if implied_growth_rate is not None else None,
    }


def scenario_comparison(current_mktcap: float, scenarios: dict) -> list[dict]:
    """
    将当前市值与三情景目标市值对比，输出上下行空间。
    scenarios: {"Bull": target_mktcap, "Base": target_mktcap, "Bear": target_mktcap}
    """
    result = []
    for name, target in scenarios.items():
        upside = (target - current_mktcap) / current_mktcap * 100
        result.append({
            "scenario": name,
            "target_mktcap_bn": target,
            "upside_pct": round(upside, 1),
        })
    return result


# ══════════════════════════════════════════════════════════════════
# 三、情景 P&L 辅助计算
# ══════════════════════════════════════════════════════════════════

def build_scenario_pnl(revenue_base: float,
                       revenue_growth: float,
                       gross_margin: float,
                       opex_rate: float,
                       tax_rate: float = 0.15,
                       years: int = 3) -> list[dict]:
    """
    简单线性情景 P&L（单一增速假设）。
    revenue_base: 基准年营收（亿元）
    revenue_growth: 年化营收增速（小数，如 0.4 = 40%）
    gross_margin: 毛利率（小数）
    opex_rate: 费用率（研发+销管，小数）
    tax_rate: 有效税率
    years: 预测年数

    实际建模时 Claude 直接在 模型.md 填数，此函数作验算用。
    """
    rows = []
    rev = revenue_base
    for y in range(1, years + 1):
        rev = rev * (1 + revenue_growth)
        gross = rev * gross_margin
        ebit = gross - rev * opex_rate
        net = ebit * (1 - tax_rate)
        rows.append({
            "year": f"FY+{y}",
            "revenue_bn": round(rev, 2),
            "gross_profit_bn": round(gross, 2),
            "ebit_bn": round(ebit, 2),
            "net_profit_bn": round(net, 2),
            "net_margin_pct": round(net / rev * 100, 1),
        })
    return rows


# ══════════════════════════════════════════════════════════════════
# 四、CLI 入口
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="财务模型计算工具（由 /model skill 驱动）"
    )
    parser.add_argument("--mode", choices=["technical", "implied", "scenario"],
                        required=True, help="运行模式")
    parser.add_argument("--data", help="JSON文件路径（technical模式，含closes/volumes）")
    parser.add_argument("--mktcap", type=float, help="当前市值（亿元，implied模式）")
    parser.add_argument("--multiple", type=float, help="估值倍数（PE/PS等，implied模式）")
    parser.add_argument("--metric", type=float, help="基础指标值（亿元，implied模式）")
    parser.add_argument("--hist-metric", type=float, help="历史基础指标（亿元，implied模式）")
    parser.add_argument("--rev-base", type=float, help="基准年营收（亿元，scenario模式）")
    parser.add_argument("--growth", type=float, help="年化增速（如0.4，scenario模式）")
    parser.add_argument("--gm", type=float, help="毛利率（如0.35，scenario模式）")
    parser.add_argument("--opex", type=float, help="费用率（如0.25，scenario模式）")
    args = parser.parse_args()

    if args.mode == "technical":
        if not args.data:
            print("ERROR: --data 参数必须指定JSON文件路径", file=sys.stderr)
            sys.exit(1)
        with open(args.data, encoding="utf-8") as f:
            data = json.load(f)
        result = run_technical(data)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.mode == "implied":
        if not all([args.mktcap, args.multiple, args.metric]):
            print("ERROR: implied模式需要 --mktcap --multiple --metric", file=sys.stderr)
            sys.exit(1)
        result = implied_growth(args.mktcap, args.metric, args.multiple,
                                args.hist_metric or args.metric)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.mode == "scenario":
        if not all([args.rev_base, args.growth, args.gm, args.opex]):
            print("ERROR: scenario模式需要 --rev-base --growth --gm --opex", file=sys.stderr)
            sys.exit(1)
        result = build_scenario_pnl(args.rev_base, args.growth, args.gm, args.opex)
        for row in result:
            print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
