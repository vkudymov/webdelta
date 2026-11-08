"""Windows portable entry point. Frozen as WebDelta.exe; the FastAPI app stays in runtime/."""

from __future__ import annotations

import os
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


def first_free_port(start: int) -> int:
    for port in range(start, start + 20):
        if not port_busy(port):
            return port
    print(f"Нет свободного порта в диапазоне {start}–{start + 19}.", file=sys.stderr)
    sys.exit(1)


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


def start_server(root: Path, port: int) -> subprocess.Popen:
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


def wait_healthy(proc: subprocess.Popen, port: int, timeout: float = 120) -> None:
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            print("Сервер завершился до готовности. Смотрите сообщения выше.", file=sys.stderr)
            sys.exit(proc.returncode or 1)
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.3)
    print("Сервер не ответил на /health.", file=sys.stderr)
    sys.exit(1)


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
    port = first_free_port(preferred_port(root))
    print(f"Корень: {root}")
    print(f"Запуск: http://127.0.0.1:{port}/")
    proc = start_server(root, port)
    _tie_child_lifetime(proc.pid)
    try:
        wait_healthy(proc, port)
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
