---
name: kb-add
description: 将外部文件（PDF/Word/PPT/Excel）或Clippings网页剪藏转换为Markdown并归入研究知识库。支持单文件和批量处理。转换后自动生成摘要，按公司/行业归档。触发词：/kb-add、加入知识库、转换研报、归档文件、处理PDF、导入资料、处理剪藏、Clippings、处理inbox。
---

# KB-Add 知识库入库工作流

**适用场景**：将研报PDF、管理层PPT、财报Word等外部文件转换并归入本地知识库。

Python路径：`/d/anaconda3/python.exe`（Git Bash环境）
文件投入口：`D:\research\inbox\`
网页剪藏收件箱：`D:\research\Clippings\`
提炼后归档目录：公司专属资料 → `D:\research\01_公司\{公司名}\`，行业级资料 → `D:\research\03_主题\`

---

## 支持格式

| 格式 | 转换工具 | 备注 |
|------|---------|------|
| PDF | marker-pdf | 保留表格结构，适合研报/财报 |
| Word (.docx) | markitdown | 快速，适合纪要/报告 |
| PPT (.pptx) | markitdown | 提取文字内容 |
| Excel (.xlsx) | markitdown | 转为Markdown表格 |

---

## 执行步骤

### Step 1：确认来源类型

**情况A：处理 inbox/ 文件夹**（用户说"处理inbox"或不指定文件）
- 列出 `D:\research\inbox\` 下所有文件
- 如果为空，告知用户"inbox 为空"
- 逐个处理，每个文件处理完后从 inbox/ 删除

**情况B：处理 Clippings 文件夹**（用户说"处理剪藏"或路径含Clippings）
- 列出 `D:\research\Clippings\` 下所有 .md 文件（排除 README.md、.processed.txt）
- 逐个读取，判断是公司资料还是行业资料
- 批量提取摘要并归档，处理完将文件名追加到 `Clippings\.processed.txt`

**情况C：处理指定文件**
- 直接处理用户提供的路径

### Step 2：转换为Markdown

**PDF转换**（使用marker-pdf，保留表格）：
```bash
/d/anaconda3/python.exe -c "
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

converter = PdfConverter(artifact_dict=create_model_dict())
rendered = converter('$FILEPATH')
text, _, _ = text_from_rendered(rendered)
print(text)
" 2>&1 | cat
```

**Word/PPT/Excel转换**（使用markitdown）：
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

### Step 3：生成结构化摘要

转换完成后，读取内容，生成摘要（归档路径见 Step 4）：

```markdown
---
source: {原始文件名}
date: {文件日期或今日}
type: 研报/财报/管理层交流/行业数据
company: {公司名，如适用}
converted: {今日日期}
---

## 核心观点
{3条以内，每条一句话，含具体数字}

## 关键数据
| 指标 | 数值 | 时间 |
|------|------|------|

## 管理层关键原话
{如有，保留原文引用，不要改写}

## 与现有假设的关联
{对照该公司假设.md，标注哪些假设有新证据}

## 原文参考位置
{重要数据在原文的位置，方便回溯}
```

### Step 4：归档提炼后的 md

根据资料类型选择归档位置：

| 类型 | 归档路径 | 说明 |
|------|---------|------|
| 卖方研报（已覆盖公司） | `01_公司\{公司名}\研报\{日期}_{机构}_{标题}.md` | cross-check/kb-research 从这里读取 |
| 年报（已覆盖公司） | `01_公司\{公司名}\年报\{日期}_{类型}.md` | |
| 公告/监管文件（已覆盖公司） | `01_公司\{公司名}\公告\{日期}_{类型}.md` | |
| 行业性资料/跨公司新闻 | `03_主题\{日期}_{标题}.md` | 无法归属单一公司时放这里 |

### Step 5：处理原始文件

归档完成后：
1. 告知用户 md 已存入路径
2. **从 inbox/ 删除原始文件**（原始文件价值已提炼到 md，无需保留）
3. 如果是已覆盖公司的资料，询问是否同时更新该公司的 `假设.md`

> 例外：如果用户明确说要保留原始文件（如官方公告、监管文件），则移动到
> `01_公司\{公司名}\公告\原始\` 而不是删除；跨公司文件移动到 `03_主题\原始\`。

---

## 注意事项
- PDF用marker-pdf（首次运行会下载模型，需要等待）；Word/PPT/Excel用markitdown
- 摘要只保留与研究假设相关的数据，不需要把原文全部复述
- 管理层原话保留原文，不要改写或总结
- 如果文件识别失败，告知用户并提示手动粘贴文本内容
