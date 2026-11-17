from __future__ import annotations

import json
import re
import threading
import traceback as traceback_mod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

_lock = threading.Lock()
_log_dir: Path | None = None
_LOG_FILES = ("success.log", "errors.log", "list_file.log")
_SNAPSHOT_PATH = re.compile(r"^(\d{4}-\d{2}-\d{2})/(\d{2})-(\d{2})-(\d{2})$")


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


def purge_site(*, url: str | None = None, page_id: str | None = None, check_name: str | None = None) -> None:
    """Remove JSONL rows that belong to a deleted site."""
    if not url and not page_id and not check_name:
        return
    _rewrite_logs(lambda event: _matches_site(event, url=url, page_id=page_id, check_name=check_name))


def purge_snapshot(*, url: str | None = None, snapshot_id: str | None = None) -> None:
    """Remove JSONL rows that belong to a deleted version (snapshot)."""
    sid = (snapshot_id or "").strip()
    if not sid and not url:
        return
    _rewrite_logs(lambda event: _matches_snapshot(event, url=url, snapshot_id=sid))


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


def _rewrite_logs(drop: Callable[[dict[str, Any]], bool]) -> None:
    root = _log_dir
    if root is None or not Path(root).is_dir():
        return
    try:
        with _lock:
            for day_dir in Path(root).iterdir():
                if not day_dir.is_dir():
                    continue
                for name in _LOG_FILES:
                    path = day_dir / name
                    if not path.is_file():
                        continue
                    _filter_log_file(path, drop)
                try:
                    next(day_dir.iterdir())
                except StopIteration:
                    day_dir.rmdir()
    except Exception:
        return


def _filter_log_file(path: Path, drop: Callable[[dict[str, Any]], bool]) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return
    kept: list[str] = []
    changed = False
    for line in lines:
        raw = line.strip()
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except Exception:
            kept.append(line)
            continue
        if isinstance(event, dict) and drop(event):
            changed = True
            continue
        kept.append(raw)
    if not changed:
        return
    if not kept:
        try:
            path.unlink()
        except Exception:
            pass
        return
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _norm_url(value: Any) -> str:
    return str(value or "").strip().rstrip("/").casefold()


def _matches_site(event: dict[str, Any], *, url: str | None, page_id: str | None, check_name: str | None) -> bool:
    if page_id and str(event.get("pageId") or "") == str(page_id):
        return True
    event_url = _norm_url(event.get("url"))
    if url and event_url and event_url == _norm_url(url):
        if not check_name:
            return True
        event_name = str(event.get("checkName") or "").strip()
        return not event_name or event_name == str(check_name).strip()
    if check_name and str(event.get("checkName") or "").strip() == str(check_name).strip() and not event_url:
        return True
    return False


def _matches_snapshot(event: dict[str, Any], *, url: str | None, snapshot_id: str) -> bool:
    sid = str(snapshot_id or "").strip()
    if sid and sid in {str(event.get("snapshotId") or "").strip(), str(event.get("snapshotId2") or "").strip()}:
        return True
    if not url or _norm_url(event.get("url")) != _norm_url(url):
        return False
    snap_at = _snapshot_local_time(sid)
    event_at = _parse_event_ts(event.get("ts"))
    if snap_at is None or event_at is None:
        return False
    event_at = event_at.astimezone(snap_at.tzinfo)
    return snap_at - timedelta(minutes=10) <= event_at <= snap_at + timedelta(minutes=1)


def _parse_event_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _snapshot_local_time(snapshot_id: str) -> datetime | None:
    match = _SNAPSHOT_PATH.match((snapshot_id or "").strip())
    if not match:
        return None
    try:
        naive = datetime.strptime(f"{match.group(1)} {match.group(2)}:{match.group(3)}:{match.group(4)}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return naive.replace(tzinfo=datetime.now().astimezone().tzinfo)


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
