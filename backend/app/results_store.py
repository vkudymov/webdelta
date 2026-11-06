from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings
from .diffing import is_text_content_type
from .fetcher import sanitize_storage_filename


# `/` и символы, недопустимые в имени файла, иначе строка из input разрежется на каталоги.
_UNSAFE_FILENAME = re.compile(r'[/\\:*?"<>|\x00-\x1f]')


def normalize_check_name(check_name: str | None) -> str | None:
    name = (check_name or "").strip()
    return name or None


def _folder_name(url: str, check_name: str | None = None) -> str:
    raw = normalize_check_name(check_name) or (url or "").strip()
    name = _UNSAFE_FILENAME.sub("_", raw).strip(" .") or "snapshot"
    encoded = name.encode("utf-8")
    if len(encoded) > 240:
        name = encoded[:240].decode("utf-8", errors="ignore").rstrip(" .") or "snapshot"
    return name


def legacy_snapshot_path(url: str, check_name: str | None = None) -> Path:
    """
    Legacy flat snapshot file:
      results/<safe_url>.json
    Used for backward-compatible 'single file per input' snapshots.
    """
    return Path(settings.results_dir) / f"{_folder_name(url, check_name)}.json"


def save_legacy_snapshot(url: str, snapshot: dict[str, Any], check_name: str | None = None) -> Path:
    """
    Save only fields used for compare. Does not store bytes.
    """
    name = normalize_check_name(check_name) or normalize_check_name(snapshot.get("checkName"))
    out = {
        "url": snapshot.get("url") or url,
        "checkName": name,
        "title": snapshot.get("title"),
        "content": snapshot.get("content") or "",
        "fetchedAt": snapshot.get("fetchedAt") or datetime.now(timezone.utc).isoformat(),
        "attachments": [],
    }
    for att in snapshot.get("attachments") or []:
        ct = att.get("content_type") or att.get("contentType")
        out["attachments"].append(
            {
                "url": att.get("url"),
                "filename": att.get("filename") or "unnamed",
                "content_type": ct,
                "size": att.get("size"),
                "hash": att.get("hash"),
                "text_content": att.get("text_content") if is_text_content_type(ct) else None,
            }
        )

    path = legacy_snapshot_path(url, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_legacy_snapshot(url: str, check_name: str | None = None) -> dict[str, Any] | None:
    path = legacy_snapshot_path(url, check_name)
    if not path.is_file() and check_name:
        path = legacy_snapshot_path(url)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def delete_legacy_snapshot(url: str, check_name: str | None = None) -> None:
    for path in {legacy_snapshot_path(url, check_name), legacy_snapshot_path(url)}:
        if path.is_file():
            try:
                path.unlink()
            except Exception:
                pass


def site_dir(url: str, check_name: str | None = None) -> Path:
    return Path(settings.results_dir) / _folder_name(url, check_name)


def _format_local_path(captured_at: datetime) -> str:
    local = captured_at.astimezone()
    return f"{local:%Y-%m-%d}/{local:%H-%M-%S}"


def snapshot_dir(
    url: str,
    *,
    local_path: str | None = None,
    captured_at: datetime | None = None,
    check_name: str | None = None,
) -> Path:
    """
    Dated snapshot directory:
      results/<safe_check_name_or_url>/<YYYY-MM-DD>/<HH-MM-SS>/

    Legacy snapshot directory (pre-dated):
      results/<safe_check_name_or_url>/
    """
    base = site_dir(url, check_name)
    if local_path:
        return base / local_path
    if captured_at is not None:
        return base / _format_local_path(captured_at)
    return base


def page_json_path(
    url: str,
    *,
    local_path: str | None = None,
    captured_at: datetime | None = None,
    check_name: str | None = None,
) -> Path:
    return snapshot_dir(url, local_path=local_path, captured_at=captured_at, check_name=check_name) / "page.json"


def files_dir(
    url: str,
    *,
    local_path: str | None = None,
    captured_at: datetime | None = None,
    check_name: str | None = None,
) -> Path:
    return snapshot_dir(url, local_path=local_path, captured_at=captured_at, check_name=check_name) / "files"

def attachment_path(
    url: str,
    rel_path: str,
    *,
    local_path: str | None = None,
    captured_at: datetime | None = None,
    check_name: str | None = None,
) -> Path:
    """
    Convert a relative attachment path from page.json (e.g. 'files/x.pdf') into an absolute path.
    Prevents path traversal outside of the snapshot directory.
    """
    base = snapshot_dir(url, local_path=local_path, captured_at=captured_at, check_name=check_name).resolve()
    rel = (rel_path or "").lstrip("/").strip()
    p = (base / rel).resolve()
    try:
        p.relative_to(base)
    except Exception:
        raise ValueError("Invalid attachment path")
    return p


def read_attachment_bytes(
    url: str,
    rel_path: str,
    *,
    local_path: str | None = None,
    captured_at: datetime | None = None,
    check_name: str | None = None,
) -> bytes | None:
    try:
        p = attachment_path(url, rel_path, local_path=local_path, captured_at=captured_at, check_name=check_name)
    except Exception:
        return None
    if not p.is_file():
        return None
    try:
        return p.read_bytes()
    except Exception:
        return None


def comparison_snapshot(
    url: str,
    title: str | None,
    content: str | None,
    attachments: list[dict],
    fetched_at: str | None = None,
    check_name: str | None = None,
) -> dict[str, Any]:
    stored_attachments: list[dict[str, Any]] = []
    for att in attachments:
        content_type = att.get("content_type")
        stored_attachments.append(
            {
                "url": att.get("url"),
                "filename": att.get("filename") or "unnamed",
                "content_type": content_type,
                "size": att.get("size"),
                "hash": att.get("hash"),
                "text_content": att.get("text_content") if is_text_content_type(content_type) else None,
                "path": att.get("path") or att.get("storage_path"),
            }
        )
    return {
        "url": url,
        "checkName": normalize_check_name(check_name),
        "title": title,
        "content": content or "",
        "fetchedAt": fetched_at or datetime.now(timezone.utc).isoformat(),
        "attachments": stored_attachments,
    }


def save_snapshot(
    url: str,
    snapshot: dict[str, Any],
    downloaded_attachments: list[dict] | None = None,
    check_name: str | None = None,
) -> Path:
    """
    Persist a snapshot under results/<check_name_or_url>/page.json.

    If downloaded_attachments are provided (output of fetch_attachments), bytes are stored under
    results/<check_name_or_url>/files/* and snapshot attachments will include relative `path` fields.
    """
    name = normalize_check_name(check_name) or normalize_check_name(snapshot.get("checkName"))
    snapshot["checkName"] = name
    snapshot["url"] = snapshot.get("url") or url
    fetched_at_raw = snapshot.get("fetchedAt")
    captured_at: datetime
    if isinstance(fetched_at_raw, str):
        try:
            captured_at = datetime.fromisoformat(fetched_at_raw.replace("Z", "+00:00"))
        except Exception:
            captured_at = datetime.now(timezone.utc)
    elif isinstance(fetched_at_raw, datetime):
        captured_at = fetched_at_raw
    else:
        captured_at = datetime.now(timezone.utc)

    local_path = _format_local_path(captured_at)
    snapshot["localPath"] = local_path

    base = snapshot_dir(url, local_path=local_path, check_name=name)
    base.mkdir(parents=True, exist_ok=True)

    if downloaded_attachments is not None:
        fdir = files_dir(url, local_path=local_path, check_name=name)
        fdir.mkdir(parents=True, exist_ok=True)

        used_names: set[str] = set()
        stored_attachments: list[dict[str, Any]] = []
        for att in downloaded_attachments:
            raw_name = att.get("filename") or "file"
            safe_name = sanitize_storage_filename(raw_name)
            h = (att.get("hash") or "hash")[:8]
            candidate = safe_name
            if candidate in used_names:
                candidate = f"{h}_{candidate}"
            if candidate in used_names:
                i = 2
                while True:
                    candidate2 = f"{h}_{i}_{safe_name}"
                    if candidate2 not in used_names:
                        candidate = candidate2
                        break
                    i += 1
            used_names.add(candidate)

            data = att.get("bytes") or b""
            (fdir / candidate).write_bytes(data)

            content_type = att.get("content_type")
            stored_attachments.append(
                {
                    "url": att.get("url"),
                    "filename": safe_name or "file",
                    "content_type": content_type,
                    "size": att.get("size") if att.get("size") is not None else len(data),
                    "hash": att.get("hash"),
                    "text_content": att.get("text_content") if is_text_content_type(content_type) else None,
                    "path": f"files/{candidate}",
                }
            )
        snapshot = {
            "url": snapshot.get("url") or url,
            "checkName": name,
            "title": snapshot.get("title"),
            "content": snapshot.get("content") or "",
            "fetchedAt": snapshot.get("fetchedAt") or datetime.now(timezone.utc).isoformat(),
            "localPath": local_path,
            "attachments": stored_attachments,
        }

    path = page_json_path(url, local_path=local_path, check_name=name)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _latest_page_json(base: Path) -> dict[str, Any] | None:
    if not base.is_dir():
        return None
    date_dirs = [p for p in base.iterdir() if p.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", p.name)]
    for date_dir in sorted(date_dirs, reverse=True):
        time_dirs = [p for p in date_dir.iterdir() if p.is_dir() and re.match(r"^\d{2}-\d{2}-\d{2}$", p.name)]
        for time_dir in sorted(time_dirs, reverse=True):
            pj = time_dir / "page.json"
            if pj.is_file():
                return json.loads(pj.read_text(encoding="utf-8"))
    legacy = base / "page.json"
    if legacy.is_file():
        return json.loads(legacy.read_text(encoding="utf-8"))
    return None


_DATE_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_DIR = re.compile(r"^\d{2}-\d{2}-\d{2}$")
LOCAL_PATH_RE = re.compile(r"^\d{4}-\d{2}-\d{2}/\d{2}-\d{2}-\d{2}$")


def is_local_snapshot_path(value: str | None) -> bool:
    return bool(value and LOCAL_PATH_RE.match(str(value).strip()))


def _list_snapshots_from_base(base: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not base.is_dir():
        return items
    date_dirs = [p for p in base.iterdir() if p.is_dir() and _DATE_DIR.match(p.name)]
    for date_dir in sorted(date_dirs, reverse=True):
        time_dirs = [p for p in date_dir.iterdir() if p.is_dir() and _TIME_DIR.match(p.name)]
        for time_dir in sorted(time_dirs, reverse=True):
            page_json = time_dir / "page.json"
            if not page_json.is_file():
                continue
            local_path = f"{date_dir.name}/{time_dir.name}"
            try:
                data = json.loads(page_json.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            fetched = data.get("fetchedAt")
            if not fetched:
                try:
                    fetched = datetime.strptime(f"{date_dir.name} {time_dir.name}", "%Y-%m-%d %H-%M-%S").isoformat()
                except Exception:
                    fetched = None
            items.append(
                {
                    "id": local_path,
                    "localPath": local_path,
                    "capturedAt": fetched,
                    "title": data.get("title"),
                    "attachmentCount": len(data.get("attachments") or []),
                }
            )
    return items


def list_local_snapshots(url: str, check_name: str | None = None) -> list[dict[str, Any]]:
    """Read dated snapshot folders: results/<site>/<YYYY-MM-DD>/<HH-MM-SS>/page.json."""
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    name = normalize_check_name(check_name)
    bases = [site_dir(url, name)]
    if name:
        bases.append(site_dir(url))
    for base in bases:
        for item in _list_snapshots_from_base(base):
            path = str(item.get("localPath") or "")
            if path in seen:
                continue
            seen.add(path)
            items.append(item)
    return items


def _latest_error_from_base(base: Path) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    latest_key = ""
    if not base.is_dir():
        return None
    date_dirs = [p for p in base.iterdir() if p.is_dir() and _DATE_DIR.match(p.name)]
    for date_dir in date_dirs:
        time_dirs = [p for p in date_dir.iterdir() if p.is_dir() and _TIME_DIR.match(p.name)]
        for time_dir in time_dirs:
            error_json = time_dir / "error.json"
            if not error_json.is_file():
                continue
            local_path = f"{date_dir.name}/{time_dir.name}"
            try:
                data = json.loads(error_json.read_text(encoding="utf-8"))
            except Exception:
                data = {"error": None, "localPath": local_path}
            key = str(data.get("failedAt") or local_path)
            if key >= latest_key:
                latest_key = key
                latest = data
    return latest


def list_sites() -> list[dict[str, Any]]:
    """Build the left-list payload from results/<site>/ dated folders."""
    root = Path(settings.results_dir)
    if not root.is_dir():
        return []
    sites: list[dict[str, Any]] = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        latest = _latest_page_json(entry)
        latest_err = _latest_error_from_base(entry)
        url = (latest or {}).get("url") or (latest_err or {}).get("url")
        if not url:
            continue
        snapshots = _list_snapshots_from_base(entry)
        last_ok = True
        last_action = "download"
        last_error = None
        if latest_err:
            err_key = str(latest_err.get("failedAt") or latest_err.get("localPath") or "")
            snap_key = str((latest or {}).get("fetchedAt") or (latest or {}).get("localPath") or "")
            if not latest or err_key >= snap_key:
                last_ok = False
                last_action = latest_err.get("action") or "download"
                last_error = latest_err.get("error")
        sites.append(
            {
                "id": entry.name,
                "url": url,
                "title": (latest or {}).get("title"),
                "checkName": normalize_check_name(
                    (latest or {}).get("checkName") or (latest_err or {}).get("checkName")
                ),
                "created_at": None,
                "updated_at": (latest or {}).get("fetchedAt") or (latest_err or {}).get("failedAt"),
                "attachment_count": snapshots[0]["attachmentCount"] if snapshots else 0,
                "lastAction": last_action,
                "lastOk": last_ok,
                "lastError": last_error,
                "pageId": None,
                "snapshots": snapshots,
            }
        )
    sites.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    return sites


def delete_site_dir(folder_name: str) -> bool:
    root = Path(settings.results_dir).resolve()
    base = (Path(settings.results_dir) / folder_name).resolve()
    try:
        base.relative_to(root)
    except Exception:
        return False
    if not base.is_dir() or base == root:
        return False
    shutil.rmtree(base, ignore_errors=True)
    return True


def save_error(url: str, error: str, *, action: str, check_name: str | None = None) -> Path:
    """Write results/<site>/<YYYY-MM-DD>/<HH-MM-SS>/error.json for a failed read."""
    name = normalize_check_name(check_name)
    captured_at = datetime.now(timezone.utc)
    local_path = _format_local_path(captured_at)
    folder = snapshot_dir(url, local_path=local_path, check_name=name)
    folder.mkdir(parents=True, exist_ok=True)
    payload = {
        "url": url,
        "checkName": name,
        "action": action,
        "error": str(error),
        "failedAt": captured_at.astimezone().isoformat(),
        "localPath": local_path,
    }
    path = folder / "error.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_latest_error(url: str, check_name: str | None = None) -> dict[str, Any] | None:
    """Return the newest error.json under the site folder, or None."""
    name = normalize_check_name(check_name)
    bases = [site_dir(url, name)]
    if name:
        bases.append(site_dir(url))
    latest: dict[str, Any] | None = None
    latest_key = ""
    for base in bases:
        found = _latest_error_from_base(base)
        if not found:
            continue
        key = str(found.get("failedAt") or found.get("localPath") or "")
        if key >= latest_key:
            latest_key = key
            latest = found
    return latest


def load_snapshot(url: str, local_path: str | None = None, check_name: str | None = None) -> dict[str, Any] | None:
    name = normalize_check_name(check_name)
    if local_path:
        path = page_json_path(url, local_path=local_path, check_name=name)
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        if name:
            path = page_json_path(url, local_path=local_path)
            if path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))
        return None

    found = _latest_page_json(site_dir(url, name))
    if found is None and name:
        found = _latest_page_json(site_dir(url))
    return found


def _prune_empty_parents(folder: Path) -> None:
    root = Path(settings.results_dir).resolve()
    current = folder
    for _ in range(2):
        parent = current.parent
        try:
            parent.resolve().relative_to(root)
        except Exception:
            return
        if parent == root or not parent.is_dir():
            return
        try:
            next(parent.iterdir())
        except StopIteration:
            parent.rmdir()
            current = parent
            continue
        return


def delete_site_snapshot(folder_name: str, local_path: str) -> bool:
    if not is_local_snapshot_path(local_path):
        return False
    if not folder_name or folder_name in {".", ".."} or "/" in folder_name or "\\" in folder_name:
        return False
    root = Path(settings.results_dir).resolve()
    base = (Path(settings.results_dir) / folder_name / local_path).resolve()
    try:
        base.relative_to(root)
    except Exception:
        return False
    if not base.is_dir() or base == root:
        return False
    shutil.rmtree(base, ignore_errors=True)
    _prune_empty_parents(base)
    return True


def delete_snapshot(url: str, local_path: str | None = None, check_name: str | None = None) -> None:
    name = normalize_check_name(check_name)
    bases = [snapshot_dir(url, local_path=local_path, check_name=name) if local_path else site_dir(url, name)]
    if name:
        bases.append(snapshot_dir(url, local_path=local_path) if local_path else site_dir(url))
    for base in bases:
        if base.is_dir():
            shutil.rmtree(base, ignore_errors=True)
            if local_path:
                _prune_empty_parents(base)
