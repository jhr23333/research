#!/usr/bin/env bash
# 轻量守卫：只在写入假设.md或memo.md时才启动Python同步脚本
data=$(cat)
if [[ "$data" == *"假设.md"* ]] || [[ "$data" == *"memo.md"* ]]; then
    printf '%s' "$data" | /d/anaconda3/python.exe D:/research/scripts/hooks/sync-index.py
fi
