"""Windows portable entry point. Frozen as WebDelta.exe; the FastAPI app stays in runtime/."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

DEFAULT_PORT = 8765


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    cwd = Path.cwd()
    if (cwd / "backend").is_dir():
        return cwd
    return Path(__file__).resolve().parents[2]


def ensure_env(root: Path) -> None:
    env_file = root / ".env"
    example = root / ".env.example"
    if env_file.exists() or not example.is_file():
        return
    shutil.copyfile(example, env_file)
    print(f"Создан {env_file.name} из {example.name}")


def preferred_port(root: Path) -> int:
    env_file = root / ".env"
    if not env_file.is_file():
        return DEFAULT_PORT
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() != "PORT":
            continue
        try:
            return int(value.strip())
        except ValueError:
            return DEFAULT_PORT
    return DEFAULT_PORT


def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def port_range(start: int):
    return range(start, start + 20)


_JOB_HANDLE = None


def _tie_child_lifetime(pid: int) -> None:
    """Kill the server when this process exits, including closing the console window."""
    if sys.platform != "win32":
        return

    import ctypes
    from ctypes import wintypes

    global _JOB_HANDLE

    job_object_extended_limit_information = 9
    job_object_limit_kill_on_job_close = 0x2000
    process_terminate = 0x0001
    process_set_quota = 0x0100

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", ctypes.c_uint32),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", ctypes.c_uint32),
            ("SchedulingClass", ctypes.c_uint32),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        print("Не удалось привязать сервер к окну запуска.", file=sys.stderr)
        return

    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = job_object_limit_kill_on_job_close
    if not kernel32.SetInformationJobObject(
        job,
        job_object_extended_limit_information,
        ctypes.byref(info),
        ctypes.sizeof(info),
    ):
        kernel32.CloseHandle(job)
        print("Не удалось привязать сервер к окну запуска.", file=sys.stderr)
        return

    process = kernel32.OpenProcess(process_terminate | process_set_quota, False, pid)
    if not process or not kernel32.AssignProcessToJobObject(job, process):
        if process:
            kernel32.CloseHandle(process)
        kernel32.CloseHandle(job)
        print("Не удалось привязать сервер к окну запуска.", file=sys.stderr)
        return

    kernel32.CloseHandle(process)
    _JOB_HANDLE = job


def write_portable_ui_token(root: Path, token: str) -> None:
    ui = root / "frontend" / "out"
    if not ui.is_dir():
        return
    script = ui / "_webdelta_local.js"
    script.write_text(f"window.__WEBDELTA_LOCAL_TOKEN__={json.dumps(token)};", encoding="utf-8")
    index = ui / "index.html"
    if not index.is_file():
        return
    tag = '<script src="/_webdelta_local.js"></script>'
    html = index.read_text(encoding="utf-8")
    if tag in html:
        return
    if "</head>" in html:
        html = html.replace("</head>", f"  {tag}\n</head>", 1)
    else:
        html = f"{tag}\n{html}"
    index.write_text(html, encoding="utf-8")


def start_server(root: Path, port: int, *, local_token: str) -> subprocess.Popen:
    python = root / "runtime" / "python.exe"
    backend = root / "backend"
    if not python.is_file():
        print(f"Не найден {python}. Распакуйте архив целиком и запускайте WebDelta.exe из этой папки.", file=sys.stderr)
        sys.exit(1)
    if not backend.is_dir():
        print(f"Не найден каталог {backend}.", file=sys.stderr)
        sys.exit(1)

    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(root / ".playwright-browsers")
    env["PLAYWRIGHT_CHANNEL"] = ""
    env["WEBDELTA_SERVE_UI"] = "1"
    env["HOST"] = "127.0.0.1"
    env["PORT"] = str(port)
    env["WEBDELTA_LOCAL_TOKEN"] = local_token

    return subprocess.Popen(
        [
            str(python),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(backend),
        env=env,
    )


def wait_healthy(proc: subprocess.Popen, port: int, timeout: float = 120) -> bool:
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.3)
    return False


def stop_server(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def main() -> None:
    root = app_root()
    ensure_env(root)
    local_token = secrets.token_urlsafe(32)
    write_portable_ui_token(root, local_token)
    start = preferred_port(root)
    proc = None
    port = None
    for candidate in port_range(start):
        if port_busy(candidate):
            continue
        proc = start_server(root, candidate, local_token=local_token)
        _tie_child_lifetime(proc.pid)
        if wait_healthy(proc, candidate):
            port = candidate
            break
        stop_server(proc)
        proc = None
    if proc is None or port is None:
        print(f"Не удалось запустить сервер на портах {start}–{start + 19}.", file=sys.stderr)
        sys.exit(1)
    print(f"Корень: {root}")
    print(f"Запуск: http://127.0.0.1:{port}/")
    try:
        webbrowser.open(f"http://127.0.0.1:{port}/")
        print("Закройте это окно, чтобы остановить WebDelta.")
        code = proc.wait()
        sys.exit(code)
    except KeyboardInterrupt:
        sys.exit(0)
    finally:
        stop_server(proc)


if __name__ == "__main__":
    main()
