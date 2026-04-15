# 研究库元规则

1. 直接行动，减少中间步骤
2. 用列表点反馈和总结
3. 先规划再执行

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
