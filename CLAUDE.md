# 研究库元规则

1. 直接行动，减少中间步骤
2. 用列表点反馈和总结
3. 先规划再执行
4. **工作流变更必须同步文档**：新增目录、修改skill、改变设计原则、调整数据源规则时，同步更新 CLAUDE.md、相关 SKILL.md 及对应 README.md，不等用户提醒

## 可用工具

- **iFind MCP**：stock / news / edb / fund
- **research-memo**（项目skill）：新建覆盖 / 整理纪要 / 更新memo
- **/kb-research**（项目skill）：基于知识库深度研究
- **/reflect**（项目skill）：反方挑战投资假设
- **/kb-add**（项目skill）：PDF/Word/PPT转Markdown并归档知识库；处理Clippings网页剪藏
- **/compare**（项目skill）：跨公司横向对比，生成差异化分析和相对投资价值判断
- **/lint**（项目skill）：知识库健康检查，找出僵尸假设、孤岛节点、数据矛盾
- **/cross-check**（项目skill）：纪要交叉验证，检查历史待跟进问题是否已回答、陈述是否出现矛盾
- **search.py**：全文搜索工具，`/d/anaconda3/python.exe D:/research/scripts/search.py "关键词"`
- **iFind EDB**：宏观高频数据（韩国半导体出口前10/20日、台湾PCB月营收等），用 `search_edb` 查指标名，`get_edb_data` 取数
- **/alt-data**（项目skill）：拉取 04_另类数据 登记的 iFind EDB 指标 + search_notice 资本开支公告，检查信号阈值；**仅负向/异常信号**写入假设.md，正向趋势只记录在看板
- **/model**（项目skill）：财务模型与定价分析——从纪要提取驱动假设、构建三情景P&L、可比公司估值、反推市场隐含假设（What's Priced In）、叠加RSI/MACD技术面信号；模型结果写入 `01_公司/{公司名}/模型.md`
- **/discover**（项目skill）：覆盖池外候选发现。串行跑五个维度脚本（基本面催化/估值/覆盖稀疏/产业链溢出/另类数据映射）扫描申万电子一级~479支，自动合并为单一摘要 md；Python 侧完成全部打分与交集计算，LLM 只读 `summary_YYYYMMDD.md`（~3-5K token，27-36s 完成扫描）

## 目录结构

```
01_公司\          ← 公司研究（memo / 基本面 / 假设 / 模型 / 纪要 / 研报 / 年报 / 公告）
02_产业链节点\    ← 技术、供应商、工艺节点（双向链接）
03_主题\          ← 跨公司主题研究 + explorations/ + 行业级原始资料
04_另类数据\      ← 高频另类数据（scripts / data / 看板）
```

**04_另类数据 设计原则**：每条数据序列必须关联到具体公司的具体假设（H#），孤立数据不入库。**仅负向/异常信号**自动追加到对应公司的 `假设.md` 待核实问题；正向信号只记录在看板，由研究员手动判断是否追加。

## 覆盖总览

见 `_index.md`（每次更新假设.md或memo.md后自动同步）

## 知识结晶层

- `rules.md` — 经3次以上验证的投资规律
- `false-beliefs.md` — 被推翻的传统智慧，反思时必读
- `03_主题/explorations/` — 有价值的研究讨论沉淀

## Session管理

- 当对话接近上下文限制时（内容明显变多、或用户提示），主动说："建议现在做session收尾，把未完成事项写入文件。"
- 收尾动作：未完成问题→`假设.md`待核实、新结论→`假设.md`/`rules.md`/`false-beliefs.md`、有价值讨论→`explorations/`
- 用户说"收尾"或"结束session"时，立即执行上述动作，列出写入了哪些文件

## 环境说明

- 本目录同时是 **Obsidian vault**，所有 .md 文件在 Obsidian 中实时可见
- 跨文件引用使用 `[[文件名]]` 格式（Obsidian 双向链接）
- 网页剪藏通过 Obsidian Web Clipper 保存到 `Clippings\`

## 详细配置

见 `research-config.md`
