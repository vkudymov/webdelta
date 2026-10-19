#!/usr/bin/env bash
# Запуск разработки WebDelta (Python/FastAPI + Playwright + Next.js).
# Первый запуск ставит зависимости, затем открывает backend и frontend
# в отдельных окнах Terminal.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Нужна команда: $1"
    exit 1
  fi
}

require_cmd node
require_cmd npm
require_cmd python3
require_cmd lsof
require_cmd osascript

port_busy() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

hash_file() {
  shasum -a 256 "$1" | awk '{print $1}'
}

ensure_venv() {
  if [[ ! -d "$ROOT/.venv" ]]; then
    echo "Создаю venv..."
    (cd "$ROOT" && python3 -m venv .venv)
  fi
}

ensure_backend_deps() {
  ensure_venv
  local req="$ROOT/backend/requirements.txt"
  local stamp="$ROOT/.venv/.webdelta_backend_reqs.sha256"
  local current_hash
  current_hash="$(hash_file "$req")"

  if [[ -f "$stamp" ]] && [[ "$(cat "$stamp")" == "$current_hash" ]]; then
    echo "Python-зависимости уже установлены."
    return
  fi

  echo "Устанавливаю Python-зависимости..."
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
  python -m pip install -U pip
  pip install -r "$req"
  echo "$current_hash" >"$stamp"
}

ensure_playwright() {
  ensure_venv
  local stamp="$ROOT/.venv/.webdelta_playwright.ok"
  if [[ -f "$stamp" ]] && [[ -d "$ROOT/.playwright-browsers" ]] && ls "$ROOT/.playwright-browsers" >/dev/null 2>&1; then
    echo "Playwright Chromium уже установлен."
    return
  fi

  echo "Устанавливаю Chromium для Playwright..."
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
  export PLAYWRIGHT_BROWSERS_PATH="$ROOT/.playwright-browsers"
  python -m playwright install chromium
  touch "$stamp"
}

ensure_frontend_deps() {
  local dir="$ROOT/frontend"
  if [[ -d "$dir/node_modules" ]] && (cd "$dir" && npm ls --depth=0 >/dev/null 2>&1); then
    echo "Frontend-зависимости уже установлены."
    return
  fi

  echo "Устанавливаю frontend-зависимости..."
  rm -rf "$dir/node_modules"
  (cd "$dir" && npm install)
}

open_terminal() {
  local dir="$1"
  local title="$2"
  local cmd="$3"

  local full_cmd
  full_cmd="cd \"${dir}\" && ${cmd}"

  osascript \
    -e 'on run argv' \
    -e 'tell application "Terminal"' \
    -e 'activate' \
    -e 'do script (item 1 of argv)' \
    -e 'end tell' \
    -e 'end run' \
    -- "$full_cmd" >/dev/null
}

ensure_backend_deps
ensure_playwright
ensure_frontend_deps

echo "Открываю backend и frontend в отдельных окнах Terminal..."

if port_busy 8000; then
  echo "Порт 8000 уже занят — backend не запускаю."
else
  open_terminal "$ROOT/backend" "WebDelta backend" "export PLAYWRIGHT_BROWSERS_PATH=\"$ROOT/.playwright-browsers\" && ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
  echo "Backend: http://127.0.0.1:8000"
fi

if port_busy 3000; then
  echo "Порт 3000 уже занят — frontend не запускаю."
else
  open_terminal "$ROOT/frontend" "WebDelta frontend" "export NEXT_PUBLIC_API_URL=\${NEXT_PUBLIC_API_URL:-http://127.0.0.1:8000} && npm run dev"
  echo "Frontend: http://localhost:3000"
fi
