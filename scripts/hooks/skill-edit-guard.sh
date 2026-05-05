#!/usr/bin/env bash
# 轻量守卫：只在写入 .claude/skills/X/SKILL.md 时才启动 Python 检查脚本
data=$(cat)
if [[ "$data" == *"SKILL.md"* ]] && [[ "$data" == *".claude"* ]]; then
    printf '%s' "$data" | /d/anaconda3/python.exe D:/research/scripts/hooks/skill-edit-warn.py
fi
