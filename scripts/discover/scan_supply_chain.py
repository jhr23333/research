# -*- coding: utf-8 -*-
"""
维度④ 产业链溢出扫描

核心逻辑：工作区 02_产业链节点/ 下每个节点 md 记录了主要厂商/供应商/客户，
这些是研究员在研究已覆盖公司时已经思考过但尚未覆盖的标的。

v1 启发式提取：
1. 扫描节点 md 正文中的中文公司名候选
2. 用 iwencai 解析为 A 股代码
3. 交集 SW 电子池
4. 剔除已覆盖

打分：
  +3  节点 md 中被明确列为供应商/客户/厂商
  +2  该标的同时命中维度① 催化榜
  +1  该标的同时命中维度③ 稀疏覆盖榜

输出：out/supply_chain_{YYYYMMDD}.json，取 Top 10
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    iwencai_query, get_sw_electronics_pool, filter_pool,
    covered_code6_set, write_output, SUPPLY_CHAIN_DIR, OUT_DIR
)

TOP_N = 10

# 已知的中国 A 股电子行业常见公司名（启发式白名单，v1 增强覆盖率）
KNOWN_CANDIDATES = [
    '沪电股份', '深南电路', '胜宏科技', '生益科技', '景旺电子', '广合科技',
    '大族激光', '三安光电', '北方华创', '中微公司', '澜起科技', '兆易创新',
    '圣邦股份', '韦尔股份', '紫光国微', '纳芯微', '长川科技', '华海清科',
    '拓荆科技', '精测电子', '至纯科技', '华峰测控', '盛美上海', '华兴源创',
    '江丰电子', '安集科技', '雅克科技', '中环股份', 'TCL科技', '京东方',
    '立讯精密', '工业富联', '歌尔股份', '传音控股', '蓝思科技', '欣旺达',
    '德赛电池', '光大同创', '裕同科技', '华勤技术', '铜冠铜箔', '诺德股份',
    '金安国纪', '华正新材', '南亚新材', '斯瑞新材',
]

# 过滤明显不是公司名的高频词
STOPWORDS = {
    '主要', '产品', '客户', '供应商', '厂商', '设备', '材料', '环节', '行业',
    '技术', '工艺', '模块', '方案', '服务', '数据', '信息', '系统', '中国',
    '美国', '日本', '韩国', '台湾', '全球', '市场', '国内', '海外', '公司',
}


def extract_candidate_names(text: str) -> set[str]:
    """
    启发式：从 md 正文中提取可能的中文公司名。
    - 匹配带"股份/电子/科技/光电/微电子/芯片/半导体/新材"等后缀的 2-8 字词
    - 加上已知白名单做补充
    """
    # A 股公司常见命名模式
    patterns = [
        r'[\u4e00-\u9fa5]{2,6}(?:股份|电子|科技|光电|微电子|半导体|新材|芯片|集成|材料|设备|通讯|通信)',
    ]
    names = set()
    for p in patterns:
        for m in re.finditer(p, text):
            name = m.group(0)
            if name not in STOPWORDS:
                names.add(name)
    # 补充白名单匹配（直接搜索）
    for known in KNOWN_CANDIDATES:
        if known in text:
            names.add(known)
    return names


def resolve_name_to_code(name: str) -> tuple[str, str] | None:
    """用 iwencai 查公司名 → 代码。返回 (code, 精确名) 或 None。"""
    d = iwencai_query(f'{name} 股票代码', 'stock')
    if not d:
        return None
    codes = d.get('股票代码', [])
    names = d.get('股票简称', [])
    if not codes:
        return None
    # 只取第一个，且简称必须与查询名包含关系
    for i, code in enumerate(codes[:3]):
        short = names[i] if i < len(names) else ''
        # 精确匹配或包含匹配
        if short == name or name in short or short in name:
            return (code, short)
    return None


def scan_supply_chain_nodes() -> dict[str, dict]:
    """
    扫描所有节点 md，返回 {code: {'name': ..., 'nodes': [node_name, ...]}}
    """
    result: dict[str, dict] = {}
    if not SUPPLY_CHAIN_DIR.exists():
        return result

    for md_file in SUPPLY_CHAIN_DIR.glob('*.md'):
        text = md_file.read_text(encoding='utf-8')
        node_name = md_file.stem
        candidates = extract_candidate_names(text)
        for cand in candidates:
            resolved = resolve_name_to_code(cand)
            if not resolved:
                continue
            code, short = resolved
            if code not in result:
                result[code] = {'name': short, 'nodes': []}
            if node_name not in result[code]['nodes']:
                result[code]['nodes'].append(node_name)
    return result


def load_sibling_hits(filename: str) -> set[str]:
    today = datetime.today().strftime('%Y%m%d')
    f = OUT_DIR / f'{filename}_{today}.json'
    if not f.exists():
        return set()
    try:
        d = json.loads(f.read_text(encoding='utf-8'))
        return {x['code'] for x in d.get('items', [])}
    except Exception:
        return set()


def main():
    pool = filter_pool(get_sw_electronics_pool())
    pool_codes = {s['code']: s['name'] for s in pool}
    covered = covered_code6_set()

    print('[supply_chain] 扫描节点 md...', flush=True)
    mentions = scan_supply_chain_nodes()
    print(f'[supply_chain] 节点提及命中 {len(mentions)} 支', flush=True)

    catalyst_hits = load_sibling_hits('catalysts')
    coverage_hits = load_sibling_hits('coverage')

    candidates = []
    for code, info in mentions.items():
        # 必须在电子池、未覆盖、非 ST
        if code not in pool_codes:
            continue
        code6 = code.split('.')[0]
        if code6 in covered:
            continue

        score = 3  # 基础分：被节点 md 列出
        triggers = [f'产业链节点: {", ".join(info["nodes"])}']
        if code in catalyst_hits:
            score += 2
            triggers.append('同时命中催化榜')
        if code in coverage_hits:
            score += 1
            triggers.append('同时命中稀疏榜')

        candidates.append({
            'code': code,
            'name': pool_codes[code],
            'score': score,
            'nodes': info['nodes'],
            'triggers': triggers,
        })

    ranked = sorted(candidates, key=lambda x: -x['score'])[:TOP_N]
    out_file = write_output('supply_chain', ranked, meta={
        'pool_size': len(pool_codes),
        'node_files': len(list(SUPPLY_CHAIN_DIR.glob('*.md'))) if SUPPLY_CHAIN_DIR.exists() else 0,
        'mentions_resolved': len(mentions),
    })
    print(f'[supply_chain] 输出 {len(ranked)} 条到 {out_file}', flush=True)


if __name__ == '__main__':
    main()
