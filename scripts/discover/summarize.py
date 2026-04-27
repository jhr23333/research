# -*- coding: utf-8 -*-
"""
合并五维度 JSON 输出为单一 markdown 摘要，供 LLM 消费。

设计：
  LLM 触发 /discover 后只读这一个文件（~3-5K token），不再读 5 个独立 JSON。
  保留交集分析、元信息、单维度 Top 摘要。

输入：out/{dimension}_{YYYYMMDD}.json × 5
输出：out/summary_{YYYYMMDD}.md
"""
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
OUT_DIR = HERE / 'out'

DIMENSIONS = [
    ('catalysts', '① 催化', ['pre_growth', 'exp_growth', 'visits_30d']),
    ('valuation', '② 估值', ['pe_ttm', 'pb', 'roe_ttm', 'pe_sector_pctile', 'pe_hist_pctile']),
    ('coverage', '③ 稀疏', ['report_count', 'mktcap_bn']),
    ('supply_chain', '④ 产业链', ['nodes']),
    ('alt_mapping', '⑤ 另类', ['signals']),
]


def load(dim: str, today: str) -> dict | None:
    f = OUT_DIR / f'{dim}_{today}.json'
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return None


def fmt_signals(item: dict, fields: list[str]) -> str:
    """提取每条候选的关键字段为单行字符串。"""
    parts = []
    for f in fields:
        v = item.get(f)
        if v is None:
            continue
        if isinstance(v, float):
            parts.append(f'{f}={v:.2f}')
        elif isinstance(v, list):
            if v:
                parts.append(f'{f}={"/".join(map(str, v[:3]))}')
        else:
            parts.append(f'{f}={v}')
    triggers = item.get('triggers', [])
    if triggers:
        parts.append('｜'.join(triggers[:3]))
    return ' '.join(parts)


def build_intersect(payloads: dict[str, dict]) -> list[dict]:
    """计算多维度命中的强候选。"""
    by_code = defaultdict(lambda: {'name': '', 'dims': [], 'total_score': 0, 'details': []})
    for dim_key, payload in payloads.items():
        if not payload:
            continue
        for item in payload.get('items', []):
            code = item.get('code')
            if not code:
                continue
            entry = by_code[code]
            entry['name'] = item.get('name') or entry['name']
            entry['dims'].append(dim_key)
            entry['total_score'] += item.get('score', 0)
            entry['details'].append((dim_key, item.get('triggers', [])))

    strong = [
        {'code': c, **v}
        for c, v in by_code.items()
        if len(v['dims']) >= 2
    ]
    strong.sort(key=lambda x: (-len(x['dims']), -x['total_score']))
    return strong


def render_dim_table(payload: dict, fields: list[str]) -> str:
    if not payload or not payload.get('items'):
        meta = payload.get('meta', {}) if payload else {}
        note = meta.get('note', '无候选')
        return f'_无候选_（{note}）\n'
    lines = ['| 代码 | 名称 | 分 | 关键信号 |', '|------|------|----|---------|']
    for item in payload['items']:
        code = item.get('code', '')
        name = item.get('name', '')
        score = item.get('score', '')
        sig = fmt_signals(item, fields).replace('|', '/')
        lines.append(f'| {code} | {name} | {score} | {sig} |')
    return '\n'.join(lines) + '\n'


def render_intersect(strong: list[dict]) -> str:
    if not strong:
        return '_本期无 ≥2 维度命中的强候选。_\n'
    lines = ['| 代码 | 名称 | 命中维度 | 综合分 | 细节 |',
             '|------|------|---------|--------|------|']
    for s in strong[:15]:
        dims = ', '.join(s['dims'])
        details = '；'.join(
            f'{d}:{",".join(t[:2])}' for d, t in s['details'][:3]
        ).replace('|', '/')
        lines.append(f'| {s["code"]} | {s["name"]} | {dims} | {s["total_score"]} | {details} |')
    return '\n'.join(lines) + '\n'


def render_meta(payloads: dict[str, dict]) -> str:
    lines = []
    for dim_key, label, _ in DIMENSIONS:
        p = payloads.get(dim_key)
        if not p:
            lines.append(f'- {label}: 未运行或失败')
            continue
        meta = p.get('meta', {})
        cnt = p.get('count', 0)
        meta_str = ', '.join(f'{k}={v}' for k, v in meta.items() if k not in ('warning', 'note'))
        lines.append(f'- {label}: 候选 {cnt} 条；{meta_str}')
    return '\n'.join(lines)


def main():
    today = datetime.today().strftime('%Y%m%d')
    today_iso = datetime.today().strftime('%Y-%m-%d')
    iso_year, iso_week, _ = datetime.today().isocalendar()

    payloads = {dim: load(dim, today) for dim, _, _ in DIMENSIONS}
    strong = build_intersect(payloads)

    out_lines = [
        f'# Discover 摘要 — {today_iso}（{iso_year}年第{iso_week}周）',
        '',
        '> LLM 消费入口。读这一个文件即可完成交叉判断与候选池写入，',
        '> 无需再读 `out/*_{YYYYMMDD}.json`。',
        '',
        '## 强候选（≥2 维度命中）',
        '',
        render_intersect(strong),
        '## 单维度 Top',
        '',
    ]
    for dim_key, label, fields in DIMENSIONS:
        out_lines.append(f'### {label}')
        out_lines.append('')
        out_lines.append(render_dim_table(payloads.get(dim_key) or {}, fields))
        out_lines.append('')

    out_lines.extend([
        '## 元信息',
        '',
        render_meta(payloads),
        '',
        '---',
        '_生成于_ ' + datetime.now().isoformat(timespec='seconds'),
    ])

    out_file = OUT_DIR / f'summary_{today}.md'
    out_file.write_text('\n'.join(out_lines), encoding='utf-8')
    print(f'[summarize] 摘要写入 {out_file}', flush=True)
    return out_file


if __name__ == '__main__':
    main()
