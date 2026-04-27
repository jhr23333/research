# -*- coding: utf-8 -*-
"""
维度② 估值被动便宜（v2）

v2 相比 v1 的增量：
  - 新增 ROE（`ths_roe_ttm_stock`，参数仅需 '{date}'），用 ROE TTM 剔除亏损/负 ROE
  - 新增 3 年周频 PE_TTM / PB 历史分位（THS_DateSerial 多代码批量），当前值相对自身历史分布的百分位
  - 板块横截面分位仍保留，与自身历史分位交叉更稳健

打分：
  +3  PE 板块分位 < 30% 且 PB 板块分位 < 40%（横向便宜）
  +2  PE 自身 3 年历史分位 < 20%（纵向便宜）
  +2  ROE TTM > 行业中位数 且 ROE TTM > 5%（便宜但不是垃圾）
  +1  市值 ∈ [30, 300] 亿
  剔除  PE ≤ 0 / PB 缺失 / ROE TTM < 0

⚠ 本维度单独不可决策。单维度②命中的标的需与①③④维度交叉后才有信号价值。

输出：out/valuation_{YYYYMMDD}.json，取 Top 10
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import get_sw_electronics_pool, filter_pool, _sdk, write_output, CACHE_DIR

TOP_N = 10
BATCH_SIZE = 100
HIST_BATCH_SIZE = 50  # DateSerial 批量稍小，避免超时


def _to_float(v):
    try:
        if v is None or v == '':
            return None
        return float(v)
    except (ValueError, TypeError):
        return None


def _safe_div(v, denom):
    return round(v / denom, 2) if v is not None else None


def fetch_snapshot(codes: list[str], date: str) -> list[dict]:
    """抓当前 PE_TTM / PB / 市值 / ROE_TTM。"""
    sdk = _sdk()
    rows = []
    indicators = 'ths_pe_ttm_stock;ths_pb_stock;ths_market_value_stock;ths_roe_ttm_stock'
    # PE_TTM 要 101，PB 要 100，市值/ROE 只需 date
    params = f'{date},101;{date},100;{date};{date}'

    for i in range(0, len(codes), BATCH_SIZE):
        chunk = codes[i:i + BATCH_SIZE]
        raw = sdk.THS_BasicData(','.join(chunk), indicators, params)
        df = sdk.THS_Trans2DataFrame(raw)
        if df is None or len(df) == 0:
            continue
        for _, row in df.iterrows():
            rows.append({
                'code': row.get('thscode'),
                'pe_ttm': _to_float(row.get('ths_pe_ttm_stock')),
                'pb': _to_float(row.get('ths_pb_stock')),
                'mktcap_bn': _safe_div(_to_float(row.get('ths_market_value_stock')), 1e8),
                'roe_ttm': _to_float(row.get('ths_roe_ttm_stock')),
            })
    return rows


def _hist_cache_path(indicator: str, year: int, week: int) -> Path:
    """周缓存文件路径，按 ISO 年-周编号命名，自然过期。"""
    return CACHE_DIR / f'hist_{indicator}_{year}W{week:02d}.json'


def _fetch_history_raw(codes: list[str], indicator: str, option: str,
                       start: str, end: str) -> dict[str, list[float]]:
    """从 SDK 拉历史序列，返回 {code: [val_w1, ...]}。"""
    sdk = _sdk()
    result = {}
    conditions = 'Days:Tradedays,Fill:Previous,Interval:W'
    for i in range(0, len(codes), HIST_BATCH_SIZE):
        chunk = codes[i:i + HIST_BATCH_SIZE]
        raw = sdk.THS_DateSerial(','.join(chunk), indicator, option, conditions, start, end)
        if raw.get('errorcode') != 0:
            continue
        for tbl in raw.get('tables', []) or []:
            code = tbl.get('thscode')
            t = tbl.get('table', {})
            vals = t.get(indicator, []) if isinstance(t, dict) else []
            clean = [_to_float(v) for v in vals]
            clean = [v for v in clean if v is not None and v > 0]
            if clean:
                result[code] = clean
    return result


def _purge_stale_caches(indicator: str, keep: Path) -> None:
    """删除 keep 之外的所有 hist_{indicator}_*.json，避免跨周累积。"""
    for old in CACHE_DIR.glob(f'hist_{indicator}_*.json'):
        if old != keep:
            try:
                old.unlink()
            except OSError:
                pass


def get_history_series(codes: list[str], indicator: str, option: str,
                       start: str, end: str, today: datetime) -> dict[str, list[float]]:
    """
    带缓存的历史序列获取。同 ISO 周内复用缓存，跨周自动失效。
    缓存覆盖整个 SW 电子池的历史，新池子标的（如新上市）自动按需补抓。
    """
    iso_year, iso_week, _ = today.isocalendar()
    cache_file = _hist_cache_path(indicator, iso_year, iso_week)

    # 每次调用都清理旧周缓存（不依赖"有缺失"分支才触发）
    _purge_stale_caches(indicator, cache_file)

    cached: dict[str, list[float]] = {}
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            cached = {}

    missing = [c for c in codes if c not in cached]
    if missing:
        print(f'[valuation]   缓存命中 {len(codes) - len(missing)}/{len(codes)}，'
              f'增量拉 {len(missing)} 支...', flush=True)
        new_data = _fetch_history_raw(missing, indicator, option, start, end)
        cached.update(new_data)
        cache_file.write_text(json.dumps(cached, ensure_ascii=False), encoding='utf-8')
    else:
        print(f'[valuation]   全量缓存命中 ({len(codes)} 支)', flush=True)

    return {c: cached[c] for c in codes if c in cached}


def fetch_history_percentile(codes: list[str], indicator: str, option: str,
                             start: str, end: str, current: dict[str, float],
                             today: datetime) -> dict[str, float]:
    """带缓存的历史分位计算。"""
    series = get_history_series(codes, indicator, option, start, end, today)
    result = {}
    for code, hist in series.items():
        cur = current.get(code)
        if not hist or cur is None or cur <= 0:
            continue
        lower = sum(1 for x in hist if x < cur)
        result[code] = round(lower / len(hist), 3)
    return result


def percentile_rank(values: list[float], v: float) -> float:
    clean = sorted([x for x in values if x is not None])
    if not clean or v is None:
        return None
    lower = sum(1 for x in clean if x < v)
    return round(lower / len(clean), 3)


def score_valuation(row: dict, pe_sec_pct: float, pb_sec_pct: float,
                    pe_hist_pct: float, roe_median: float) -> tuple[int, list[str]]:
    score = 0
    triggers = []
    pe, pb, roe, mcap = row['pe_ttm'], row['pb'], row['roe_ttm'], row['mktcap_bn']

    if pe is None or pe <= 0 or pb is None:
        return 0, []
    if roe is not None and roe < 0:
        return 0, []  # 剔除亏损

    if pe_sec_pct is not None and pb_sec_pct is not None and pe_sec_pct < 0.30 and pb_sec_pct < 0.40:
        score += 3
        triggers.append(f'板块PE分位{pe_sec_pct:.0%}/PB分位{pb_sec_pct:.0%}')
    if pe_hist_pct is not None and pe_hist_pct < 0.20:
        score += 2
        triggers.append(f'自身3年PE历史分位{pe_hist_pct:.0%}')
    if roe is not None and roe_median is not None and roe > roe_median and roe > 5:
        score += 2
        triggers.append(f'ROE {roe:.1f}% >行业中位')
    if mcap is not None and 30 <= mcap <= 300:
        score += 1
        triggers.append(f'市值{mcap:.0f}亿')

    return score, triggers


def main():
    today = datetime.today()
    date = today.strftime('%Y-%m-%d')
    hist_start = (today - timedelta(days=365 * 3)).strftime('%Y-%m-%d')

    pool = get_sw_electronics_pool()
    pool_filtered = filter_pool(pool)
    codes = [s['code'] for s in pool_filtered]
    name_map = {s['code']: s['name'] for s in pool_filtered}

    print(f'[valuation] 拉取当前估值快照（{len(codes)} 支）...', flush=True)
    rows = fetch_snapshot(codes, date)
    print(f'[valuation] 返回 {len(rows)} 支有效数据', flush=True)

    # 板块横截面分位
    pe_vals = [r['pe_ttm'] for r in rows if r['pe_ttm'] is not None and r['pe_ttm'] > 0]
    pb_vals = [r['pb'] for r in rows if r['pb'] is not None]
    roe_vals = sorted([r['roe_ttm'] for r in rows if r['roe_ttm'] is not None])
    roe_median = roe_vals[len(roe_vals) // 2] if roe_vals else None

    # 先粗筛：板块 PE 分位 < 50% 的标的才值得拉历史（节省 DateSerial 调用）
    pe_pct_map = {}
    pb_pct_map = {}
    cur_pe_map = {}
    for r in rows:
        pe_pct_map[r['code']] = percentile_rank(pe_vals, r['pe_ttm']) if r['pe_ttm'] and r['pe_ttm'] > 0 else None
        pb_pct_map[r['code']] = percentile_rank(pb_vals, r['pb']) if r['pb'] else None
        cur_pe_map[r['code']] = r['pe_ttm']

    hist_candidates = [c for c, p in pe_pct_map.items() if p is not None and p < 0.50]
    print(f'[valuation] 算 {len(hist_candidates)} 支 3 年周频 PE 历史分位（板块分位 < 50%）...', flush=True)
    pe_hist_pct_map = fetch_history_percentile(
        hist_candidates, 'ths_pe_ttm_stock', '101', hist_start, date, cur_pe_map, today
    )
    print(f'[valuation] 历史分位算出 {len(pe_hist_pct_map)} 支', flush=True)

    candidates = []
    for row in rows:
        code = row['code']
        pe_sec = pe_pct_map.get(code)
        pb_sec = pb_pct_map.get(code)
        pe_hist = pe_hist_pct_map.get(code)
        score, triggers = score_valuation(row, pe_sec, pb_sec, pe_hist, roe_median)
        if score < 3:
            continue
        candidates.append({
            'code': code,
            'name': name_map.get(code, ''),
            'score': score,
            'pe_ttm': round(row['pe_ttm'], 1) if row['pe_ttm'] else None,
            'pb': round(row['pb'], 2) if row['pb'] else None,
            'mktcap_bn': row['mktcap_bn'],
            'roe_ttm': round(row['roe_ttm'], 1) if row['roe_ttm'] is not None else None,
            'pe_sector_pctile': pe_sec,
            'pb_sector_pctile': pb_sec,
            'pe_hist_pctile': pe_hist,
            'triggers': triggers,
        })

    ranked = sorted(candidates, key=lambda x: (-x['score'], x['pe_sector_pctile'] or 1))[:TOP_N]
    out_file = write_output('valuation', ranked, meta={
        'pool_size': len(pool_filtered),
        'valid_rows': len(rows),
        'hist_covered': len(pe_hist_pct_map),
        'roe_median_ttm': roe_median,
        'warning': '单维度命中不可独立决策，需与①③④交叉',
    })
    print(f'[valuation] 输出 {len(ranked)} 条到 {out_file}', flush=True)


if __name__ == '__main__':
    main()
