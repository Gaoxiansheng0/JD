#!/usr/bin/env bash
# 本地开发启动器：同时拉起后端 API 和前端 Vite。
# 不包含任何 API Key，也不写死用户数据路径。
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_dir="$repo_root/backend"
frontend_dir="$repo_root/frontend"
venv_dir="$backend_dir/.venv"

backend_host="${RESUMEFIT_HOST:-127.0.0.1}"
backend_port="${RESUMEFIT_PORT:-8000}"

if [[ ! -x "$venv_dir/bin/python" ]]; then
  echo "==> 创建后端虚拟环境"
  python3 -m venv "$venv_dir"
fi

echo "==> 同步后端依赖"
"$venv_dir/bin/pip" install --quiet --upgrade pip
"$venv_dir/bin/pip" install --quiet -e "$backend_dir[dev]"

if [[ ! -d "$frontend_dir/node_modules" ]]; then
  echo "==> 安装前端依赖"
  npm --prefix "$frontend_dir" install
fi

pids=()
cleanup() {
  for pid in "${pids[@]:-}"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT INT TERM

echo "==> 启动后端 http://$backend_host:$backend_port"
(
  cd "$backend_dir"
  exec "$venv_dir/bin/uvicorn" resumefit.app:create_app \
    --factory --host "$backend_host" --port "$backend_port" --reload
) &
pids+=($!)

echo "==> 启动前端 http://127.0.0.1:5173"
npm --prefix "$frontend_dir" run dev &
pids+=($!)

# macOS 自带 bash 3.2，没有 `wait -n`；轮询直到任一子进程退出，再由 trap 收尾。
while true; do
  for pid in "${pids[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "==> 子进程 $pid 已退出，停止开发服务"
      exit 1
    fi
  done
  sleep 1
done
