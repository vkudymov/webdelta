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

def legacy_snapshot_path(url: str) -> Path:
    """
    Legacy flat snapshot file:
      results/<safe_url>.json
    Used for backward-compatible 'single file per input' snapshots.
    """
    name = _UNSAFE_FILENAME.sub("_", url.strip()).strip(" .") or "snapshot"
    encoded = name.encode("utf-8")
    if len(encoded) > 240:
        name = encoded[:240].decode("utf-8", errors="ignore").rstrip(" .") or "snapshot"
    return Path(settings.results_dir) / f"{name}.json"


def save_legacy_snapshot(url: str, snapshot: dict[str, Any]) -> Path:
    """
    Save only fields used for compare. Does not store bytes.
    """
    out = {
        "url": snapshot.get("url") or url,
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

    path = legacy_snapshot_path(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_legacy_snapshot(url: str) -> dict[str, Any] | None:
    path = legacy_snapshot_path(url)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def delete_legacy_snapshot(url: str) -> None:
    path = legacy_snapshot_path(url)
    if path.is_file():
        try:
            path.unlink()
        except Exception:
            pass


def site_dir(url: str) -> Path:
    name = _UNSAFE_FILENAME.sub("_", url.strip())
    name = name.strip(" .") or "snapshot"
    encoded = name.encode("utf-8")
    if len(encoded) > 240:
        name = encoded[:240].decode("utf-8", errors="ignore").rstrip(" .") or "snapshot"
    return Path(settings.results_dir) / name


def _format_local_path(captured_at: datetime) -> str:
    local = captured_at.astimezone()
    return f"{local:%Y-%m-%d}/{local:%H-%M-%S}"


def snapshot_dir(url: str, *, local_path: str | None = None, captured_at: datetime | None = None) -> Path:
    """
    Dated snapshot directory:
      results/<safe_url>/<YYYY-MM-DD>/<HH-MM-SS>/

    Legacy snapshot directory (pre-dated):
      results/<safe_url>/
    """
    base = site_dir(url)
    if local_path:
        return base / local_path
    if captured_at is not None:
        return base / _format_local_path(captured_at)
    return base


def page_json_path(url: str, *, local_path: str | None = None, captured_at: datetime | None = None) -> Path:
    return snapshot_dir(url, local_path=local_path, captured_at=captured_at) / "page.json"


def files_dir(url: str, *, local_path: str | None = None, captured_at: datetime | None = None) -> Path:
    return snapshot_dir(url, local_path=local_path, captured_at=captured_at) / "files"

def attachment_path(url: str, rel_path: str, *, local_path: str | None = None, captured_at: datetime | None = None) -> Path:
    """
    Convert a relative attachment path from page.json (e.g. 'files/x.pdf') into an absolute path.
    Prevents path traversal outside of the snapshot directory.
    """
    base = snapshot_dir(url, local_path=local_path, captured_at=captured_at).resolve()
    rel = (rel_path or "").lstrip("/").strip()
    p = (base / rel).resolve()
    try:
        p.relative_to(base)
    except Exception:
        raise ValueError("Invalid attachment path")
    return p


def read_attachment_bytes(url: str, rel_path: str, *, local_path: str | None = None, captured_at: datetime | None = None) -> bytes | None:
    try:
        p = attachment_path(url, rel_path, local_path=local_path, captured_at=captured_at)
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
        "title": title,
        "content": content or "",
        "fetchedAt": fetched_at or datetime.now(timezone.utc).isoformat(),
        "attachments": stored_attachments,
    }


def save_snapshot(url: str, snapshot: dict[str, Any], downloaded_attachments: list[dict] | None = None) -> Path:
    """
    Persist a snapshot under results/<url>/page.json.

    If downloaded_attachments are provided (output of fetch_attachments), bytes are stored under
    results/<url>/files/* and snapshot attachments will include relative `path` fields.
    """
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

    base = snapshot_dir(url, local_path=local_path)
    base.mkdir(parents=True, exist_ok=True)

    if downloaded_attachments is not None:
        fdir = files_dir(url, local_path=local_path)
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
            "title": snapshot.get("title"),
            "content": snapshot.get("content") or "",
            "fetchedAt": snapshot.get("fetchedAt") or datetime.now(timezone.utc).isoformat(),
            "localPath": local_path,
            "attachments": stored_attachments,
        }

    path = page_json_path(url, local_path=local_path)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_snapshot(url: str, local_path: str | None = None) -> dict[str, Any] | None:
    # explicit version
    if local_path:
        path = page_json_path(url, local_path=local_path)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    # latest dated version (if present)
    base = site_dir(url)
    if base.is_dir():
        date_dirs = [p for p in base.iterdir() if p.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", p.name)]
        for date_dir in sorted(date_dirs, reverse=True):
            time_dirs = [p for p in date_dir.iterdir() if p.is_dir() and re.match(r"^\d{2}-\d{2}-\d{2}$", p.name)]
            for time_dir in sorted(time_dirs, reverse=True):
                pj = time_dir / "page.json"
                if pj.is_file():
                    return json.loads(pj.read_text(encoding="utf-8"))

    # legacy snapshot (pre-dated)
    legacy = page_json_path(url)
    if legacy.is_file():
        return json.loads(legacy.read_text(encoding="utf-8"))
    return None


def delete_snapshot(url: str, local_path: str | None = None) -> None:
    base = snapshot_dir(url, local_path=local_path) if local_path else site_dir(url)
    if base.is_dir():
        shutil.rmtree(base, ignore_errors=True)
