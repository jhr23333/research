# 临时资料库

**用途**：单次使用资料的暂存口。投入 PDF / Word / PPT / Excel / md / txt，调用 `/quick-memo` 后会：

1. 提取全部文件文本（PDF 用 marker-pdf，保留表格）
2. 按你当次的"具体要求"生成一份 memo
3. memo 存为 `_临时\memo_YYYYMMDDHHMM.md`
4. **删除全部原始资料**（包括子目录），只留 memo 和本 README

**注意**：
- 这里不是知识库，资料一次性消耗，不进入 `01_公司\` / `03_主题\`
- 想长期归档请走 `/kb-add` 而不是这里
- memo 生成后你自行决定是否搬走 / 删除
