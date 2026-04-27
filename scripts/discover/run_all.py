# -*- coding: utf-8 -*-
"""
Discover 工作流调度器

顺序执行五个维度扫描脚本，输出统一 JSON 到 out/。
维度③④ 依赖维度① 的输出（交集加分），所以串行执行而非并行。
若顺序不敏感（单维度调试），直接运行对应 scan_*.py 即可。

用法：
    python run_all.py           # 跑全部五维度
    python run_all.py --only catalysts  # 只跑指定维度
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

# Windows 默认 cp936 控制台无法打印 ✓✗ 等 unicode 字符；
# 在主进程层强制 UTF-8，省掉外部 PYTHONIOENCODING 环境变量。
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

HERE = Path(__file__).parent

# 执行顺序：① 先，③ ④ 依赖 ①，② ⑤ 独立
DIMENSIONS = [
    ('catalysts', '① 基本面催化'),
    ('valuation', '② 估值被动便宜'),
    ('coverage', '③ 覆盖稀疏度'),
    ('supply_chain', '④ 产业链溢出'),
    ('alt_mapping', '⑤ 另类数据反向映射'),
]


def run_dimension(key: str, label: str) -> tuple[bool, float]:
    script = HERE / f'scan_{key}.py'
    if not script.exists():
        print(f'  ✗ {label}: 脚本不存在 {script}', flush=True)
        return False, 0
    t0 = time.time()
    try:
        r = subprocess.run(
            [sys.executable, '-X', 'utf8', str(script)],
            cwd=str(HERE),
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=300,
        )
        dt = time.time() - t0
        if r.returncode != 0:
            print(f'  ✗ {label} 失败（{dt:.1f}s）', flush=True)
            print(f'    stderr: {r.stderr.strip()[:500]}', flush=True)
            return False, dt
        # 打印子进程最后一行摘要
        last_line = (r.stdout.strip().split('\n') or [''])[-1]
        print(f'  ✓ {label}（{dt:.1f}s）: {last_line[:120]}', flush=True)
        return True, dt
    except subprocess.TimeoutExpired:
        print(f'  ✗ {label} 超时', flush=True)
        return False, time.time() - t0
    except Exception as e:
        print(f'  ✗ {label} 异常: {e}', flush=True)
        return False, time.time() - t0


def main():
    parser = argparse.ArgumentParser(description='Discover 覆盖池外候选发现')
    parser.add_argument('--only', choices=[k for k, _ in DIMENSIONS],
                        help='只跑指定维度')
    args = parser.parse_args()

    dims = DIMENSIONS if not args.only else [(k, l) for k, l in DIMENSIONS if k == args.only]

    print(f'=== Discover 扫描开始（{len(dims)} 个维度）===\n')
    results = []
    total_start = time.time()
    for k, l in dims:
        ok, dt = run_dimension(k, l)
        results.append((k, l, ok, dt))
    total = time.time() - total_start

    print(f'\n=== 完成，总耗时 {total:.1f}s ===')
    for k, l, ok, dt in results:
        mark = '✓' if ok else '✗'
        print(f'  {mark} {l}  {dt:.1f}s')

    # 生成单一摘要 md（即便部分维度失败也跑，能合并多少合并多少）
    print()
    try:
        sys.path.insert(0, str(HERE))
        from summarize import main as summarize_main
        out_md = summarize_main()
        print(f'\n下一步：LLM 读 {out_md} 即可（无需读 5 个 JSON），交叉判断后写入 03_主题/候选池/')
    except Exception as e:
        print(f'  ✗ summarize 失败: {e}')
        print('  fallback: 直接读 out/*.json')


if __name__ == '__main__':
    main()
