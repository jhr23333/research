# -*- coding: utf-8 -*-
"""
维度③ 覆盖稀疏度扫描

用 iwencai 查电子板块近 6 个月研报数量，筛选 1-5 家覆盖的标的。
核心原则：低覆盖 + 有催化 = 目标区域；低覆盖 + 无催化 = 忽略。

打分规则：
  +2  研报数 ∈ [1, 5]（有覆盖但稀疏；0 通常是垃圾股）
  +3  同时命中维度① 催化榜（交集）
  +1  市值 ∈ [30, 80]（小市值大概率被机构忽略）
  剔除  研报数 = 0 或 > 10

输出：out/coverage_{YYYYMMDD}.json，取 Top 10
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    iwencai_query, get_sw_electronics_pool, filter_pool,
    _sdk, write_output, OUT_DIR
)

TOP_N = 10


def fetch_report_counts() -> dict[str, int]:
    """
    用 iwencai 拿电子板块近 6 个月研报数量。
    Returns: {code: count}
    """
    q = '申万电子行业 近6个月研究报告数量'
    data = iwencai_query(q)
    if not data:
        return {}

    keys = list(data.keys())
    code_key = next((k for k in keys if '股票代码' in k), None)
    count_key = next((k for k in keys if '研究报告数量' in k or '研报数' in k), None)
    if not (code_key and count_key):
        return {}

    codes = data[code_key]
    counts = data[count_key]
    result = {}
    for i, code in enumerate(codes):
        if not code:
            continue
        raw = counts[i] if i < len(counts) else None
        try:
            c = int(raw) if raw not in (None, '', '--') else 0
        except (ValueError, TypeError):
            c = 0
        result[code] = c
    return result


def fetch_mktcap(codes: list[str], date: str) -> dict[str, float]:
    """快速拉市值，单位亿。"""
    sdk = _sdk()
    result = {}
    BATCH = 100
    for i in range(0, len(codes), BATCH):
        chunk = codes[i:i + BATCH]
        raw = sdk.THS_BasicData(','.join(chunk), 'ths_market_value_stock', date)
        df = sdk.THS_Trans2DataFrame(raw)
        if df is None or len(df) == 0:
            continue
        for _, row in df.iterrows():
            code = row.get('thscode')
            v = row.get('ths_market_value_stock')
            try:
                result[code] = round(float(v) / 1e8, 2) if v else None
            except (ValueError, TypeError):
                result[code] = None
    return result


def load_catalysts_today() -> set[str]:
    """
    从当日维度① 输出读取 code 集合，用于交集加分。
    若维度① 尚未跑则返回空 set。
    """
    today = datetime.today().strftime('%Y%m%d')
    f = OUT_DIR / f'catalysts_{today}.json'
    if not f.exists():
        return set()
    try:
        d = json.loads(f.read_text(encoding='utf-8'))
        return {x['code'] for x in d.get('items', [])}
    except Exception:
        return set()


def main():
    date = datetime.today().strftime('%Y-%m-%d')
    pool = filter_pool(get_sw_electronics_pool())
    pool_codes = {s['code']: s['name'] for s in pool}

    print('[coverage] 拉研报数量...', flush=True)
    reports = fetch_report_counts()
    print(f'[coverage] 研报覆盖数据 {len(reports)} 支', flush=True)

    print('[coverage] 拉市值...', flush=True)
    mcaps = fetch_mktcap(list(pool_codes.keys()), date)

    catalyst_codes = load_catalysts_today()

    candidates = []
    for code, name in pool_codes.items():
        rc = reports.get(code, 0)
        mcap = mcaps.get(code)
        if rc == 0 or rc > 10:
            continue
        if mcap is None:
            continue

        score = 0
        triggers = []
        if 1 <= rc <= 5:
            score += 2
            triggers.append(f'研报数 {rc}（稀疏覆盖）')
        if code in catalyst_codes:
            score += 3
            triggers.append('同时命中催化榜')
        if 30 <= mcap <= 80:
            score += 1
            triggers.append(f'市值{mcap:.0f}亿（被忽略区）')

        if score < 2:
            continue
        candidates.append({
            'code': code,
            'name': name,
            'score': score,
            'report_count': rc,
            'mktcap_bn': mcap,
            'triggers': triggers,
        })

    ranked = sorted(candidates, key=lambda x: (-x['score'], x['report_count']))[:TOP_N]
    # 真实交集：今日催化榜 ∩ 本榜筛出（候选阈值 score≥2）的标的
    real_intersect = sum(1 for c in candidates if c['code'] in catalyst_codes)
    out_file = write_output('coverage', ranked, meta={
        'pool_size': len(pool_codes),
        'report_data_size': len(reports),
        'catalysts_loaded': len(catalyst_codes),
        'catalyst_intersect': real_intersect,
    })
    print(f'[coverage] 输出 {len(ranked)} 条到 {out_file}', flush=True)


if __name__ == '__main__':
    main()
