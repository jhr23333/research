---
name: quick-memo
description: 临时资料库一次性memo生成。读取 D:\research\_临时\ 下全部资料（PDF/Word/PPT/Excel/md/txt），按用户当次具体要求生成一份 memo，存入 _临时\，然后删除所有原始资料。触发词：/quick-memo、临时memo、临时库、生成memo后删掉、单次资料。
---

# Quick-Memo 临时资料一次性memo工作流

**适用场景**：用户看过一批一次性资料（券商日报、临时纪要、零散研报），只需要一份当下的 memo，不进入正式知识库，用完即删。

**与 /kb-add 的区别**：
- `/kb-add` → 长期归档进 `01_公司\` / `03_主题\`，资料保留价值
- `/quick-memo` → 一次性消耗，memo 生成完原始资料全部删除

Python：`/d/anaconda3/python.exe`
临时库：`D:\research\_临时\`

---

## 执行步骤

### Step 1：盘点资料

列出 `D:\research\_临时\` 下所有文件（递归子目录），**排除** `README.md` 和已存在的 `memo_*.md`。

```bash
/d/anaconda3/python.exe -c "
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
root = r'D:\research\_临时'
for dp, _, fs in os.walk(root):
    for f in fs:
        if f == 'README.md' or f.startswith('memo_'):
            continue
        print(os.path.join(dp, f))
"
```

如果为空，告知用户"临时库为空，没有资料可处理"，结束。

确认用户的"当次具体要求"（生成什么角度的 memo），如果用户在 `/quick-memo` 后没说要求，**主动问一句**："这批资料想要什么角度的 memo？（例如：聚焦XX公司基本面 / 横向对比XX赛道 / 提炼XX主题催化剂）"

### Step 2：转换全部资料为文本（双路径）

#### Step 2.0：长 PDF 必须先做相关性预筛（**强制**）

**触发条件**（满足任一即必须先预筛）：
- 任一 PDF 页数 > 30 页
- 整批 PDF 总页数 > 80 页
- 整批文件数 ≥ 3 份且包含至少一份券商研报（文件名含 `bernstein` / `jefferies` / `hsbc` / `morgan` / `goldman` / `ubs` / `citi` 等）

**为什么强制**：券商研报后 30%-50% 是 disclosures、ratings definitions、各国分发条款等纯噪声；多份长 PDF 全量塞进 context 会浪费大量 token（实测 4 份长研报全量 extract = ~150-200K token，其中可用内容仅 30-40K）。

**预筛流程**：

```bash
/d/anaconda3/python.exe -c "
import sys, fitz, os
sys.stdout.reconfigure(encoding='utf-8')
files = [r'PATH1', r'PATH2', ...]  # 替换为实际文件列表
out = r'D:\research\_临时\_preview.md'
with open(out, 'w', encoding='utf-8') as fp:
    for f in files:
        doc = fitz.open(f)
        n = len(doc)
        fp.write(f'\n\n# {os.path.basename(f)} ({n} pages)\n')
        # 首 3 页（标题 / 摘要 / 目录通常在这）
        for i in range(min(3, n)):
            fp.write(f'\n## Page {i+1}\n\n')
            fp.write(doc[i].get_text())
        # 末 2 页（看正文哪页截止、disclosure 起点）
        if n > 5:
            fp.write(f'\n\n## ... (skipped pages 4-{n-2}) ...\n')
            for i in range(max(3, n-2), n):
                fp.write(f'\n## Page {i+1}\n\n')
                fp.write(doc[i].get_text())
        doc.close()
print('preview written:', os.path.getsize(out))
"
```

**读 `_preview.md` 后必须做的判断**（每份 PDF 单独标注）：
- **相关性**：与用户当次要求的相关度（高 / 中 / 低 / 跳过）
- **正文页范围**：disclosure 起点之前的页数（例如"23 页 PDF，正文 p1-p13，p14-p23 全是合规披露"）
- **重点页**：摘要/结论/关键表格在哪几页（例如"Exhibit 13 在 p11"）

**根据预筛结果决定全量提取范围**：
- 相关度"低 / 跳过"的 PDF → **不再 extract**，memo 不引用
- 相关度"高 / 中"的 PDF → 用下面 pymupdf 流程，但**只抽正文页范围**（用 `doc[i] for i in range(start, end)`），跳过 disclosure
- 多份 PDF 信息高度重叠时（例如同一公司的多家研报） → 选最详细的 1 份全量、其他只抽摘要

**例外（可跳过预筛）**：
- 全部 PDF < 30 页且总页数 < 80 → 直接走下面的批量 extract
- 用户明确说"全文都要看"

---

按格式选工具：

| 格式 | 默认工具 | 何时切换 |
|------|---------|---------|
| PDF (.pdf) | **pymupdf** (~0.3s/30页) | 见下方"PDF 双路径决策" |
| Word (.docx/.doc) | markitdown | - |
| PPT (.pptx) | markitdown | - |
| Excel (.xlsx/.xls) | markitdown | - |
| Markdown (.md) | 直接 Read | - |
| Text (.txt) | 直接 Read | - |

#### PDF 双路径决策

**两条路径**：

| 路径 | 速度 | 优势 | 短板 |
|------|------|------|------|
| pymupdf（默认） | 30页 ~0.3s | 文字 100% 不丢、行序基本对 | 表格被按列优先打散成一行一格，单元格对应关系丢失 |
| marker-pdf（升级） | 30页 60-180s | 表格还原为真正的 markdown table、阅读顺序最好 | 慢、首次加载模型 30-90s |

**何时切 marker-pdf**（满足任一即切，**单文件级别**切换，不要整批切）：

1. **用户当次要求包含表格/数字密集类关键词**：表格、财务模型、估值表、对比表、league table、复算、横向对比数字、PE/PS、毛利率拆解 → 直接全量上 marker-pdf
2. **pymupdf 抽完后自检**：某文件出现连续 ≥15 行单字段（单数字 / 1-3 个字 / 单百分比）的密集块 → 该文件切 marker-pdf 重抽，其他文件保留 pymupdf 结果
3. **memo 生成后用户反馈**："某某表格不对/缺了/数字串了" → 用户手动指定文件重抽

**pymupdf 转换（默认，批量；支持页范围）**：

`files` 是 `(path, page_start, page_end)` 三元组列表。`page_start=None, page_end=None` 表示全量；预筛后用具体页号截掉 disclosure。页号 1-based、闭区间（与 `## Page N` 标头一致），便于后续引用。

```bash
/d/anaconda3/python.exe -c "
import sys, fitz, os
sys.stdout.reconfigure(encoding='utf-8')
files = [
    (r'PATH1', None, None),     # 全量
    (r'PATH2', 1, 13),          # 只抽 p1-p13（正文，跳过 disclosure）
    # ...
]
out = r'D:\research\_临时\_extracted.md'
with open(out, 'w', encoding='utf-8') as fp:
    for path, ps, pe in files:
        doc = fitz.open(path)
        n = len(doc)
        s = (ps - 1) if ps else 0
        e = pe if pe else n
        fp.write(f'\n\n# {os.path.basename(path)}\n')
        fp.write(f'> Pages extracted: {s+1}-{e} of {n}\n\n')
        for i in range(s, e):
            fp.write(f'\n## Page {i+1}\n\n')
            fp.write(doc[i].get_text())
        doc.close()
print('written:', os.path.getsize(out))
"
```

**marker-pdf 转换（升级路径，单文件）**：

```bash
/d/anaconda3/python.exe -c "
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
converter = PdfConverter(artifact_dict=create_model_dict())
rendered = converter(r'$FILEPATH')
text, _, _ = text_from_rendered(rendered)
fname = os.path.splitext(os.path.basename(r'$FILEPATH'))[0]
out = rf'D:\research\_临时\_marker_{fname}.md'
with open(out, 'w', encoding='utf-8') as fp:
    fp.write(text)
print('written:', out)
"
```

**自检"表格被打散"的具体方法**：抽完后用 grep 数一下连续短行：
```bash
/d/anaconda3/python.exe -c "
import re, sys
sys.stdout.reconfigure(encoding='utf-8')
text = open(r'D:\research\_临时\_extracted.md', encoding='utf-8').read()
lines = text.split('\n')
# 单数字、单百分比、1-3字短词
short = lambda l: bool(re.match(r'^\s*([-\d.,%\$]+|\S{1,3})\s*\$', l))
runs, cur = [], 0
for l in lines:
    if short(l): cur += 1
    else:
        if cur >= 15: runs.append(cur)
        cur = 0
if runs: print('表格疑似被打散，最长连续单字段块:', runs)
else: print('未检出表格被打散，pymupdf 输出可用')
"
```

**Word/PPT/Excel 转换（markitdown）**：
```bash
/d/anaconda3/python.exe -c "
import sys
sys.stdout.reconfigure(encoding='utf-8')
from markitdown import MarkItDown
md = MarkItDown()
result = md.convert(r'$FILEPATH')
print(result.text_content)
" 2>&1 | cat
```

> 多个 PDF 时 pymupdf 一次批量处理（毫秒级），marker-pdf 必须**串行**逐个处理（避免一次启动多个模型实例）。
> 如果转换失败（编码 / 模型加载错误），告知用户跳过该文件，**不删该文件**。
> 中间文件 `_extracted.md` / `_marker_*.md` 不算 memo，会在 Step 5 一并清理。

### Step 3：按用户要求生成 memo

读取所有提取的文本 + 用户当次要求 → 生成 memo。

memo 模板（根据用户要求灵活裁剪，不必字段全填）：

```markdown
---
created: {YYYY-MM-DD HH:MM}
sources: {逐条列出原始文件名}
要求: {用户当次提的具体要求原话}
---

# {memo标题，自拟，体现当次要求角度}

## 核心结论
{3条以内，每条一句话，必须含具体数字/事件/对比}

## 关键证据
{按用户要求展开，可用小标题分块。重要数据务必带来源标注，例如 "（来源：xx研报p3）"}

## 数据/对比表
{如有横向对比或多家数据，用表格}

## 待跟进
{若资料留下未解问题，列在这里。注意：这是一次性 memo，待跟进不会自动写入任何公司假设.md}
```

**关键纪律**：
- 不引用资料外的内容（这是临时memo，不串联其他知识库内容，除非用户要求）
- 数字带来源（哪份资料 / 哪页 / 哪段）
- 如果用户要求里提到某个覆盖公司，可以**只读**该公司的 `假设.md` 做对照（不写入），让 memo 更有针对性

### Step 4：保存 memo

存到 `D:\research\_临时\memo_YYYYMMDDHHMM.md`（用当前时间戳），告知用户路径。

### Step 5：删除全部原始资料

**直接执行，不要二次确认**（用户已授权 "memo放在临时，你自己删"）：

```bash
/d/anaconda3/python.exe -c "
import os, sys, shutil
sys.stdout.reconfigure(encoding='utf-8')
root = r'D:\research\_临时'
removed = []
for dp, dns, fs in os.walk(root, topdown=False):
    for f in fs:
        if f == 'README.md' or f.startswith('memo_'):
            continue
        p = os.path.join(dp, f)
        os.remove(p)
        removed.append(p)
    # 清理空子目录（保留 _临时 根目录）
    if dp != root and not os.listdir(dp):
        os.rmdir(dp)
for r in removed:
    print('removed:', r)
"
```

转换过程中如果某个文件**转换失败**（Step 2 中跳过的），同样**不删**，让用户人工处理。

### Step 6：汇报

输出 3 行：
1. memo 路径
2. 处理的资料数 / 删除数
3. 跳过的资料（如有）和原因
