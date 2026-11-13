#!/usr/bin/env bash
# 一键启动（macOS / Linux）
#
# 做四件事：准备 .env → 拉起 Postgres → 播种演示数据 → 开后端 + 前端
#
# 用法：
#   ./scripts/start.sh              # 完整启动
#   ./scripts/start.sh --no-seed    # 不播种
#   ./scripts/start.sh --no-front   # 只起后端

set -euo pipefail

NO_SEED=0
NO_FRONT=0
PORT=${PORT:-8001}
WEB_PORT=${WEB_PORT:-9999}

for arg in "$@"; do
  case "$arg" in
    --no-seed) NO_SEED=1 ;;
    --no-front) NO_FRONT=1 ;;
    *) echo "未知参数：$arg"; exit 1 ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB="$(dirname "$ROOT")/agent-lab-web"

echo "== agent-lab 一键启动 =="

# ---- 1. .env ----
if [ ! -f "$ROOT/.env" ]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "  · 已生成 .env（记得填 LLM_API_KEY）"
fi

PG_DSN=$(grep -E '^PG_DSN=' "$ROOT/.env" | head -1 | cut -d= -f2- || true)
PG_DSN=${PG_DSN:-postgresql://agent_lab:agent_lab@127.0.0.1:5433/agent_lab}
PG_PORT=$(echo "$PG_DSN" | sed -n 's/.*:\([0-9]\{2,\}\)\/.*/\1/p')
PG_PORT=${PG_PORT:-5433}

# ---- 2. Postgres ----
port_open() {
  if command -v nc >/dev/null 2>&1; then nc -z 127.0.0.1 "$1" 2>/dev/null; else (echo > "/dev/tcp/127.0.0.1/$1") 2>/dev/null; fi
}

if ! port_open "$PG_PORT"; then
  echo "  · Postgres 未监听 $PG_PORT，尝试 docker compose up -d pg"
  (cd "$(dirname "$ROOT")" && docker compose up -d pg) || echo "    docker 不可用，请手动启动 Postgres"
  for _ in $(seq 1 20); do
    port_open "$PG_PORT" && break
    sleep 1
  done
else
  echo "  · Postgres 已在 $PG_PORT"
fi

# ---- 3. 依赖 + 播种 ----
cd "$ROOT"
echo "  · 同步依赖"
uv sync

if [ "$NO_SEED" -eq 0 ]; then
  echo "  · 播种演示数据"
  uv run python scripts/seed.py
fi

# ---- 4. 起服务 ----
echo "  · 后端 http://127.0.0.1:$PORT"
uv run python -m uvicorn agent_lab.app.main:app --host 127.0.0.1 --port "$PORT" --reload &
BACKEND_PID=$!

cleanup() {
  echo ""
  echo "停止中…"
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

if [ "$NO_FRONT" -eq 0 ] && [ -d "$WEB" ]; then
  echo "  · 前端 http://127.0.0.1:$WEB_PORT"
  cd "$WEB"
  [ -d node_modules ] || npm install
  npm run dev -- --port "$WEB_PORT"
else
  wait "$BACKEND_PID"
fi