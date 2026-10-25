from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings
from .diffing import is_text_content_type


# `/` и символы, недопустимые в имени файла, иначе строка из input разрежется на каталоги.
_UNSAFE_FILENAME = re.compile(r'[/\\:*?"<>|\x00-\x1f]')


def snapshot_path(url: str) -> Path:
    name = _UNSAFE_FILENAME.sub("_", url.strip())
    name = name.strip(" .") or "snapshot"
    encoded = name.encode("utf-8")
    if len(encoded) > 240:
        name = encoded[:240].decode("utf-8", errors="ignore").rstrip(" .") or "snapshot"
    return Path(settings.results_dir) / f"{name}.json"


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
            }
        )
    return {
        "url": url,
        "title": title,
        "content": content or "",
        "fetchedAt": fetched_at or datetime.now(timezone.utc).isoformat(),
        "attachments": stored_attachments,
    }


def save_snapshot(url: str, snapshot: dict[str, Any]) -> Path:
    path = snapshot_path(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_snapshot(url: str) -> dict[str, Any] | None:
    path = snapshot_path(url)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def delete_snapshot(url: str) -> None:
    path = snapshot_path(url)
    if path.is_file():
        path.unlink()
