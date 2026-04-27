# -*- coding: utf-8 -*-
"""
维度① 基本面催化扫描（v2）

v2 相比 v1 的增量：
  - 新增业绩快报净利润同比（区间字段，时间语义可靠）
  - 新增近 30 天机构调研次数（区间字段，时间语义可靠）作为关注度补充信号
  - 合同/扩产仍不接入（iwencai 时间关键词对公告类不可靠，需 search_notice，SDK 无等价物）

打分（叠加，最高 6 分）：
  业绩预告净利润同比：
    +4  > 100%
    +3  > 50%
    +2  > 30%
    +1  > 0%
  业绩快报净利润同比：
    +3  > 50%
    +2  > 30%
    +1  > 0%
  机构调研近 30 天频次（弱信号，仅在已有催化时加成）：
    +1  ≥ 10 次
    +2  ≥ 20 次

输出：out/catalysts_{YYYYMMDD}.json，取 Top 10
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    iwencai_query, get_sw_electronics_pool, filter_pool, write_output
)

TOP_N = 10


def _pick_key(keys, keyword_list):
    for k in keys:
        for kw in keyword_list:
            if kw in k:
                return k
    return None


def _to_float(v):
    try:
        if v in (None, '', '--'):
            return None
        return float(v)
    except (ValueError, TypeError):
        return None


def scan_earnings_preannouncement() -> dict[str, dict]:
    """
    业绩预告净利润同比增长率 > 0%（取宽，由打分细分）。
    Returns: {code: {'name', 'pre_growth', 'trigger'}}
    """
    q = '电子行业 业绩预告 归属母公司股东的净利润同比增长率大于0% 近30天'
    data = iwencai_query(q)
    if not data:
        return {}
    keys = list(data.keys())
    code_key = _pick_key(keys, ['股票代码'])
    name_key = _pick_key(keys, ['股票简称'])
    growth_key = _pick_key(keys, ['同比增长率', '净利润同比'])
    if not (code_key and growth_key):
        return {}
    codes = data[code_key]
    names = data.get(name_key, [''] * len(codes))
    growths = data[growth_key]
    out = {}
    for i, code in enumerate(codes):
        if not code:
            continue
        g = _to_float(growths[i] if i < len(growths) else None)
        if g is None:
            continue
        out[code] = {
            'name': names[i] if i < len(names) else '',
            'pre_growth': round(g, 1),
            'trigger': f'业绩预告净利润同比+{g:.0f}%',
        }
    return out


def scan_earnings_express() -> dict[str, dict]:
    """
    业绩快报净利润同比 > 0%（已正式披露的最新季度数据）。
    Returns: {code: {'name', 'exp_growth', 'trigger'}}
    """
    q = '电子行业 业绩快报 净利润同比增长率大于0% 近60天'
    data = iwencai_query(q)
    if not data:
        return {}
    keys = list(data.keys())
    code_key = _pick_key(keys, ['股票代码'])
    name_key = _pick_key(keys, ['股票简称'])
    growth_key = _pick_key(keys, ['同比增长率', '净利润同比'])
    if not (code_key and growth_key):
        return {}
    codes = data[code_key]
    names = data.get(name_key, [''] * len(codes))
    growths = data[growth_key]
    out = {}
    for i, code in enumerate(codes):
        if not code:
            continue
        g = _to_float(growths[i] if i < len(growths) else None)
        if g is None:
            continue
        out[code] = {
            'name': names[i] if i < len(names) else '',
            'exp_growth': round(g, 1),
            'trigger': f'业绩快报净利润同比+{g:.0f}%',
        }
    return out


def scan_institutional_visits() -> dict[str, int]:
    """
    近 30 天机构调研次数。区间字段名形如 `区间机构调研次数[20260329-20260427]`。
    Returns: {code: visit_count}
    """
    q = '近30天机构调研次数'
    data = iwencai_query(q)
    if not data:
        return {}
    keys = list(data.keys())
    code_key = _pick_key(keys, ['股票代码'])
    visit_key = next((k for k in keys if '调研次数' in k or '机构调研' in k), None)
    if not (code_key and visit_key):
        return {}
    codes = data[code_key]
    visits = data[visit_key]
    out = {}
    for i, code in enumerate(codes):
        if not code:
            continue
        try:
            n = int(float(visits[i])) if i < len(visits) and visits[i] not in (None, '', '--') else 0
        except (ValueError, TypeError):
            n = 0
        if n > 0:
            out[code] = n
    return out


def score_pre(g: float) -> int:
    if g is None: return 0
    if g > 100: return 4
    if g > 50: return 3
    if g > 30: return 2
    if g > 0: return 1
    return 0


def score_exp(g: float) -> int:
    if g is None: return 0
    if g > 50: return 3
    if g > 30: return 2
    if g > 0: return 1
    return 0


def score_visits(n: int) -> int:
    if n is None: return 0
    if n >= 20: return 2
    if n >= 10: return 1
    return 0


def main():
    print('[catalysts] 拉取业绩预告...', flush=True)
    pre_map = scan_earnings_preannouncement()
    print(f'[catalysts] 业绩预告命中 {len(pre_map)} 支', flush=True)

    print('[catalysts] 拉取业绩快报...', flush=True)
    exp_map = scan_earnings_express()
    print(f'[catalysts] 业绩快报命中 {len(exp_map)} 支', flush=True)

    print('[catalysts] 拉取机构调研频次...', flush=True)
    visit_map = scan_institutional_visits()
    print(f'[catalysts] 机构调研命中 {len(visit_map)} 支', flush=True)

    # 限定在 SW 电子池内（剔除已覆盖/ST）
    pool = get_sw_electronics_pool()
    pool_filtered = filter_pool(pool)
    pool_codes = {s['code']: s['name'] for s in pool_filtered}

    candidates = {}
    all_codes = set(pre_map) | set(exp_map)  # 调研只做加成，不独立触发
    for code in all_codes:
        if code not in pool_codes:
            continue
        pre = pre_map.get(code, {})
        exp = exp_map.get(code, {})
        visits = visit_map.get(code, 0)

        s_pre = score_pre(pre.get('pre_growth'))
        s_exp = score_exp(exp.get('exp_growth'))
        s_vis = score_visits(visits) if (s_pre or s_exp) else 0
        score = s_pre + s_exp + s_vis
        if score == 0:
            continue

        triggers = []
        if pre.get('trigger'):
            triggers.append(pre['trigger'])
        if exp.get('trigger'):
            triggers.append(exp['trigger'])
        if s_vis > 0:
            triggers.append(f'近30天机构调研 {visits} 次')

        candidates[code] = {
            'code': code,
            'name': pool_codes[code],
            'score': score,
            'pre_growth': pre.get('pre_growth'),
            'exp_growth': exp.get('exp_growth'),
            'visits_30d': visits if visits > 0 else None,
            'triggers': triggers,
        }

    ranked = sorted(
        candidates.values(),
        key=lambda x: (-x['score'], -(x.get('pre_growth') or 0), -(x.get('exp_growth') or 0))
    )[:TOP_N]
    out_file = write_output('catalysts', ranked, meta={
        'pool_size': len(pool_filtered),
        'pre_hits': len(pre_map),
        'exp_hits': len(exp_map),
        'visit_hits': len(visit_map),
    })
    print(f'[catalysts] 输出 {len(ranked)} 条到 {out_file}', flush=True)


if __name__ == '__main__':
    main()
