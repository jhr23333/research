# -*- coding: utf-8 -*-
"""
Discover 工作流公共模块

功能：
- 申万电子一级成分股池（801080.SL，~479 支）
- 已覆盖公司池（从 _index.md 解析）
- iFind SDK 薄封装（DataPool / BasicData / iwencai）
- JSON 输出统一格式
"""
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.expanduser('~/.ifind'))
from ifind_helper import _ensure_login  # noqa: E402

# ══════════════════════════════════════════════════════════════════
# 路径常量
# ══════════════════════════════════════════════════════════════════

RESEARCH_ROOT = Path(r'D:\research')
INDEX_MD = RESEARCH_ROOT / '_index.md'
SUPPLY_CHAIN_DIR = RESEARCH_ROOT / '02_产业链节点'
ALT_DATA_README = RESEARCH_ROOT / '04_另类数据' / 'README.md'
OUT_DIR = Path(__file__).parent / 'out'
CACHE_DIR = Path(__file__).parent / 'cache'

SW_ELECTRONICS_CODE = '801080.SL'  # 申万电子一级

OUT_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)


# ══════════════════════════════════════════════════════════════════
# iFind 封装
# ══════════════════════════════════════════════════════════════════

def _sdk():
    """登录并返回 iFindPy 模块。"""
    _ensure_login()
    import iFinDPy
    return iFinDPy


def get_sw_electronics_pool(date: str = None, use_cache: bool = True) -> list[dict]:
    """
    获取申万电子一级成分股。默认使用缓存（7 天过期）。
    Returns: [{'code': '688521.SH', 'name': '芯原股份'}, ...]
    """
    if date is None:
        date = datetime.today().strftime('%Y-%m-%d')

    cache_file = CACHE_DIR / 'sw_electronics_pool.json'
    if use_cache and cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < 7 * 86400:
            return json.loads(cache_file.read_text(encoding='utf-8'))

    sdk = _sdk()
    raw = sdk.THS_DataPool(
        'index',
        f'{date};{SW_ELECTRONICS_CODE}',
        'date:Y,thscode:Y,security_name:Y'
    )
    df = sdk.THS_Trans2DataFrame(raw)
    if df is None or len(df) == 0:
        raise RuntimeError(f'申万电子成分为空（date={date}）')

    pool = [
        {'code': row['THSCODE'], 'name': row['SECURITY_NAME']}
        for _, row in df.iterrows()
    ]
    cache_file.write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding='utf-8')
    return pool


def get_basic_data(codes: list[str], indicators: list[tuple[str, str]]) -> dict:
    """
    批量拉基础数据。indicators 为 [(指标名, 参数), ...] 的列表。
    iFindPy 的 THS_BasicData 支持多代码多指标，但参数字符串需与指标按序对齐。
    Returns: {code: {indicator_name: value, ...}}
    """
    if not codes:
        return {}
    sdk = _sdk()
    codes_str = ','.join(codes)
    ind_str = ';'.join(name for name, _ in indicators)
    param_str = ';'.join(p for _, p in indicators)
    raw = sdk.THS_BasicData(codes_str, ind_str, param_str)
    df = sdk.THS_Trans2DataFrame(raw)
    result = {c: {} for c in codes}
    if df is None or len(df) == 0:
        return result
    for _, row in df.iterrows():
        code = row.get('thscode')
        if code not in result:
            continue
        for name, _ in indicators:
            if name in row:
                result[code][name] = row[name]
    return result


def iwencai_query(query: str, domain: str = 'stock') -> dict:
    """
    i 问财自然语言查询。
    Returns: {字段名: [列数据]}，若失败返回 {}。
    """
    sdk = _sdk()
    d = sdk.THS_iwencai(query, domain)
    if not isinstance(d, dict) or d.get('errorcode') != 0:
        return {}
    tables = d.get('tables') or []
    if not tables:
        return {}
    table = tables[0].get('table', {})
    return dict(table)


# ══════════════════════════════════════════════════════════════════
# 覆盖池解析
# ══════════════════════════════════════════════════════════════════

def get_covered_companies() -> list[dict]:
    """
    解析 _index.md 拿已覆盖公司清单。
    Returns: [{'name': '芯原股份', 'code': '688521'}, ...]
    """
    if not INDEX_MD.exists():
        return []
    text = INDEX_MD.read_text(encoding='utf-8')
    result = []
    # 匹配 | [[公司名]] | 代码 | 格式
    pattern = re.compile(r'\|\s*\[\[([^\]]+)\]\]\s*\|\s*(\d{6})\s*\|')
    for m in pattern.finditer(text):
        name = m.group(1).strip()
        code6 = m.group(2)
        result.append({'name': name, 'code6': code6})
    # 去重（_index.md 多个表可能重复）
    seen = set()
    unique = []
    for c in result:
        if c['code6'] not in seen:
            seen.add(c['code6'])
            unique.append(c)
    return unique


def covered_code6_set() -> set[str]:
    """返回已覆盖公司的 6 位代码集合（不带交易所后缀）。"""
    return {c['code6'] for c in get_covered_companies()}


# ══════════════════════════════════════════════════════════════════
# 股票池过滤
# ══════════════════════════════════════════════════════════════════

def filter_pool(pool: list[dict], *,
                exclude_covered: bool = True,
                exclude_st: bool = True) -> list[dict]:
    """
    股票池标准过滤：
    - 剔除已覆盖（匹配 6 位代码）
    - 剔除 ST/*ST（名称前缀）
    """
    covered = covered_code6_set() if exclude_covered else set()
    out = []
    for s in pool:
        code6 = s['code'].split('.')[0]
        name = s['name']
        if exclude_covered and code6 in covered:
            continue
        if exclude_st and (name.startswith('ST') or name.startswith('*ST')):
            continue
        out.append(s)
    return out


# ══════════════════════════════════════════════════════════════════
# JSON 输出
# ══════════════════════════════════════════════════════════════════

def write_output(dimension: str, items: list[dict], meta: dict = None) -> Path:
    """
    统一 JSON 输出格式。
    dimension: catalysts / valuation / coverage / supply_chain / alt_mapping
    items: [{'code': ..., 'name': ..., 'score': ..., 'triggers': [...], ...}]
    Returns: 输出文件路径
    """
    today = datetime.today().strftime('%Y%m%d')
    out_file = OUT_DIR / f'{dimension}_{today}.json'
    payload = {
        'dimension': dimension,
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'count': len(items),
        'meta': meta or {},
        'items': items,
    }
    out_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    return out_file


# ══════════════════════════════════════════════════════════════════
# 自检
# ══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print('=== 覆盖池 ===')
    covered = get_covered_companies()
    for c in covered:
        print(f'  {c["name"]} ({c["code6"]})')

    print()
    print('=== 申万电子池（前 5）===')
    pool = get_sw_electronics_pool()
    for s in pool[:5]:
        print(f'  {s["code"]} {s["name"]}')
    print(f'  ...共 {len(pool)} 支')

    print()
    print('=== 过滤后 ===')
    filtered = filter_pool(pool)
    print(f'  过滤后 {len(filtered)} 支（原 {len(pool)}，剔除 {len(pool) - len(filtered)}）')
