#!/usr/bin/env python3
"""Start frontend and backend from VS Code: Run Python File."""

from __future__ import annotations

import hashlib
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
PLAYWRIGHT_BROWSERS = ROOT / ".playwright-browsers"

PROCESSES: list[subprocess.Popen] = []


def require_cmd(name: str) -> str:
    path = shutil.which(name)
    if not path:
        print(f"Нужна команда: {name}", file=sys.stderr)
        sys.exit(1)
    return path


def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def pids_on_port(port: int) -> list[int]:
    result = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
    )
    pids: list[int] = []
    for line in result.stdout.split():
        try:
            pid = int(line)
        except ValueError:
            continue
        if pid not in pids and pid != os.getpid():
            pids.append(pid)
    return pids


def free_port(port: int) -> None:
    if not port_busy(port):
        return

    pids = pids_on_port(port)
    if not pids:
        print(f"Порт {port} занят, но процесс не найден.", file=sys.stderr)
        sys.exit(1)

    print(f"Порт {port} занят — закрываю процессы: {', '.join(map(str, pids))}")
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue

    deadline = time.time() + 5
    while time.time() < deadline and port_busy(port):
        time.sleep(0.2)

    if port_busy(port):
        for pid in pids_on_port(port):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                continue
        time.sleep(0.3)

    if port_busy(port):
        print(f"Не удалось освободить порт {port}.", file=sys.stderr)
        sys.exit(1)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_checked(args: list[str], **kwargs) -> None:
    result = subprocess.run(args, **kwargs)
    if result.returncode != 0:
        sys.exit(result.returncode)


def ensure_venv() -> None:
    if VENV_PYTHON.exists():
        return
    print("Создаю venv...")
    run_checked([sys.executable, "-m", "venv", str(ROOT / ".venv")])


def ensure_backend_deps() -> None:
    ensure_venv()
    req = BACKEND_DIR / "requirements.txt"
    stamp = ROOT / ".venv" / ".webdelta_backend_reqs.sha256"
    current = file_hash(req)
    if stamp.exists() and stamp.read_text().strip() == current:
        return
    print("Устанавливаю Python-зависимости...")
    run_checked([str(VENV_PYTHON), "-m", "pip", "install", "-U", "pip"])
    run_checked([str(VENV_PYTHON), "-m", "pip", "install", "-r", str(req)])
    stamp.write_text(current)


def ensure_playwright() -> None:
    stamp = ROOT / ".venv" / ".webdelta_playwright.ok"
    if stamp.exists() and PLAYWRIGHT_BROWSERS.exists():
        return
    print("Устанавливаю Chromium для Playwright...")
    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(PLAYWRIGHT_BROWSERS)
    run_checked([str(VENV_PYTHON), "-m", "playwright", "install", "chromium"], env=env)
    stamp.write_text("ok\n")


def ensure_frontend_deps() -> None:
    if (FRONTEND_DIR / "node_modules").exists():
        return
    print("Устанавливаю frontend-зависимости...")
    run_checked(["npm", "install"], cwd=FRONTEND_DIR)


def start(
    args: list[str], cwd: Path, env: dict[str, str] | None = None
) -> subprocess.Popen:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    proc = subprocess.Popen(args, cwd=cwd, env=merged, start_new_session=True)
    PROCESSES.append(proc)
    return proc


def stop_all(*_args) -> None:
    for proc in PROCESSES:
        if proc.poll() is not None:
            continue
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
    for proc in PROCESSES:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def main() -> None:
    require_cmd("node")
    require_cmd("npm")
    require_cmd("lsof")
    ensure_backend_deps()
    ensure_playwright()
    ensure_frontend_deps()

    print("Backend: http://127.0.0.1:8000")
    print("Frontend: http://localhost:3000")
    print("Stop в VS Code / Ctrl+C останавливает оба процесса.")

    free_port(8000)
    free_port(3000)

    start(
        [
            str(VENV_PYTHON),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=BACKEND_DIR,
        env={"PLAYWRIGHT_BROWSERS_PATH": str(PLAYWRIGHT_BROWSERS)},
    )
    start(
        ["npm", "run", "dev"],
        cwd=FRONTEND_DIR,
        env={
            "NEXT_PUBLIC_API_URL": os.environ.get(
                "NEXT_PUBLIC_API_URL", "http://127.0.0.1:8000"
            )
        },
    )

    signal.signal(signal.SIGINT, stop_all)
    signal.signal(signal.SIGTERM, stop_all)

    exit_code = 0
    try:
        for proc in PROCESSES:
            code = proc.wait()
            if code not in (0, None, -signal.SIGTERM):
                exit_code = code or 1
            stop_all()
    finally:
        stop_all()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
