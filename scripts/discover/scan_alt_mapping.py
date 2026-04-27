# -*- coding: utf-8 -*-
"""
维度⑤ 另类数据反向映射（简化版）

v1 逻辑：
  读 alt_signals_config.json，找到 latest_yoy > threshold 的景气信号
  → 用 iwencai 查该环节对应电子股票
  → 剔除已覆盖 / 已在配置的 known_covered_names
  → 输出未覆盖的候选

v1 依赖研究员每月运行 /alt-data 后手动更新 alt_signals_config.json 的 latest_yoy 字段。
v2 计划：脚本自动调 THS_EDB 拉数，无需人工维护。

打分：
  +3  对应景气信号 yoy > threshold + 10pp（强景气）
  +2  对应景气信号 yoy > threshold（一般景气）
  +1  命中多个景气信号

输出：out/alt_mapping_{YYYYMMDD}.json，取 Top 10
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    iwencai_query, get_sw_electronics_pool, filter_pool,
    covered_code6_set, write_output
)

TOP_N = 10
CONFIG_FILE = Path(__file__).parent / 'alt_signals_config.json'


def load_active_signals() -> list[dict]:
    """读配置，筛出 latest_yoy > threshold 的信号。"""
    if not CONFIG_FILE.exists():
        return []
    configs = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    active = []
    for c in configs:
        yoy = c.get('latest_yoy')
        th = c.get('yoy_threshold', 20)
        if yoy is None:
            continue
        if yoy >= th:
            active.append(c)
    return active


def query_sector_stocks(keyword: str, pool_codes: dict[str, str]) -> list[tuple[str, str]]:
    """
    用 iwencai 查该关键词对应的电子股票。
    Returns: [(code, name), ...] 且仅限 pool_codes 内的标的
    """
    q = f'申万电子行业 {keyword} 概念股'
    data = iwencai_query(q)
    if not data:
        return []
    codes = data.get('股票代码', [])
    names = data.get('股票简称', [])
    result = []
    for i, code in enumerate(codes):
        if code in pool_codes:
            short = names[i] if i < len(names) else pool_codes[code]
            result.append((code, short))
    return result


def main():
    pool = filter_pool(get_sw_electronics_pool())
    pool_codes = {s['code']: s['name'] for s in pool}
    covered = covered_code6_set()

    print('[alt_mapping] 读取配置...', flush=True)
    signals = load_active_signals()
    print(f'[alt_mapping] 激活信号 {len(signals)} 个', flush=True)

    if not signals:
        print('[alt_mapping] 无激活信号（latest_yoy 均未填或未超阈值），跳过', flush=True)
        write_output('alt_mapping', [], meta={
            'active_signals': 0,
            'note': 'v1 依赖研究员维护 alt_signals_config.json 的 latest_yoy',
        })
        return

    # 收集候选：code → {name, signals, score}
    candidates: dict[str, dict] = {}
    for sig in signals:
        kw = sig.get('iwencai_keyword', '')
        known = set(sig.get('known_covered_names', []))
        strong = sig['latest_yoy'] >= sig['yoy_threshold'] + 10

        hits = query_sector_stocks(kw, pool_codes)
        for code, name in hits:
            code6 = code.split('.')[0]
            if code6 in covered:
                continue
            if name in known:
                continue

            if code not in candidates:
                candidates[code] = {
                    'code': code,
                    'name': name,
                    'score': 0,
                    'signals': [],
                    'triggers': [],
                }
            entry = candidates[code]
            add = 3 if strong else 2
            entry['score'] += add
            entry['signals'].append(sig['signal_name'])
            entry['triggers'].append(
                f'{sig["signal_name"]} YoY+{sig["latest_yoy"]:.0f}%（阈值{sig["yoy_threshold"]}）'
            )

    # 多信号命中奖励
    for entry in candidates.values():
        if len(entry['signals']) > 1:
            entry['score'] += 1
            entry['triggers'].append(f'命中 {len(entry["signals"])} 个景气信号')

    ranked = sorted(candidates.values(), key=lambda x: -x['score'])[:TOP_N]
    out_file = write_output('alt_mapping', ranked, meta={
        'active_signals': len(signals),
        'signal_names': [s['signal_name'] for s in signals],
    })
    print(f'[alt_mapping] 输出 {len(ranked)} 条到 {out_file}', flush=True)


if __name__ == '__main__':
    main()
