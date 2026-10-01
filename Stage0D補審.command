#!/bin/bash
# 雙擊啟動 Stage 0D 審片主控台（直接顯示補審清單）
cd "$(dirname "$0")/process/workspace/project-output/stage0d_master_review" || exit 1
lsof -ti tcp:8080 | xargs kill 2>/dev/null
(sleep 1.5; open "http://127.0.0.1:8080") &
exec python3 app.py
