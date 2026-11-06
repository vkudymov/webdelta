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


def list_local_snapshots(url: str, check_name: str | None = None) -> list[dict[str, Any]]:
    """Read dated snapshot folders: results/<site>/<YYYY-MM-DD>/<HH-MM-SS>/page.json."""
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    name = normalize_check_name(check_name)
    bases = [site_dir(url, name)]
    if name:
        bases.append(site_dir(url))
    for base in bases:
        if not base.is_dir():
            continue
        date_dirs = [p for p in base.iterdir() if p.is_dir() and _DATE_DIR.match(p.name)]
        for date_dir in sorted(date_dirs, reverse=True):
            time_dirs = [p for p in date_dir.iterdir() if p.is_dir() and _TIME_DIR.match(p.name)]
            for time_dir in sorted(time_dirs, reverse=True):
                page_json = time_dir / "page.json"
                if not page_json.is_file():
                    continue
                local_path = f"{date_dir.name}/{time_dir.name}"
                if local_path in seen:
                    continue
                seen.add(local_path)
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


def delete_snapshot(url: str, local_path: str | None = None, check_name: str | None = None) -> None:
    name = normalize_check_name(check_name)
    bases = [snapshot_dir(url, local_path=local_path, check_name=name) if local_path else site_dir(url, name)]
    if name:
        bases.append(snapshot_dir(url, local_path=local_path) if local_path else site_dir(url))
    for base in bases:
        if base.is_dir():
            shutil.rmtree(base, ignore_errors=True)
