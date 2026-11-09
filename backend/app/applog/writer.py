from __future__ import annotations

import json
import threading
import traceback as traceback_mod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_log_dir: Path | None = None


def configure(log_dir: Path | str) -> None:
    global _log_dir
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)
    _log_dir = path


def success(action: str, **fields: Any) -> None:
    _write("success.log", "success", action, fields)


def error(action: str, **fields: Any) -> None:
    _write("errors.log", "error", action, fields)


def list_files(**fields: Any) -> None:
    _write("list_file.log", "list_file", "list_file", fields)


def _write(filename: str, level: str, action: str, fields: dict[str, Any]) -> None:
    try:
        root = _log_dir
        if root is None:
            return
        event = _build_event(level, action, fields)
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        folder = root / day
        folder.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False, default=str) + "\n"
        with _lock:
            with (folder / filename).open("a", encoding="utf-8") as handle:
                handle.write(line)
    except Exception:
        return


def _build_event(level: str, action: str, fields: dict[str, Any]) -> dict[str, Any]:
    event: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "level": level,
        "action": action,
    }
    exc = fields.pop("exc", None)
    if exc is not None and isinstance(exc, BaseException):
        event["errorType"] = type(exc).__name__
        event["error"] = str(exc).strip() or type(exc).__name__
        event["traceback"] = "".join(traceback_mod.format_exception(type(exc), exc, exc.__traceback__))
    for key, value in fields.items():
        if value is None or key == "bytes":
            continue
        event[key] = _jsonable(value)
    return event


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items() if key != "bytes" and item is not None}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return str(value)
