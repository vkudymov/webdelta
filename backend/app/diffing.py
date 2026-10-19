from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


def compare_texts(old_text: str, new_text: str) -> Dict[str, Any]:
    old_lines = old_text.split("\n")
    new_lines = new_text.split("\n")
    max_lines = max(len(old_lines), len(new_lines))

    changes: List[Dict[str, Any]] = []

    for i in range(max_lines):
        line_num = i + 1
        old_line = old_lines[i] if i < len(old_lines) else ""
        new_line = new_lines[i] if i < len(new_lines) else ""

        if old_line != new_line:
            if i >= len(old_lines):
                changes.append({"type": "added", "lineNumber": line_num, "original": None, "current": new_line})
            elif i >= len(new_lines):
                changes.append({"type": "removed", "lineNumber": line_num, "original": old_line, "current": None})
            else:
                changes.append({"type": "modified", "lineNumber": line_num, "original": old_line, "current": new_line})

    stats = {
        "additions": sum(1 for c in changes if c["type"] == "added"),
        "deletions": sum(1 for c in changes if c["type"] == "removed"),
        "modifications": sum(1 for c in changes if c["type"] == "modified"),
        "totalLines": max_lines,
        "changedLines": len(changes),
    }

    return {"hasChanges": len(changes) > 0, "changes": changes, "stats": stats}


def is_text_content_type(content_type: Optional[str]) -> bool:
    if not content_type:
        return False
    ct = content_type.lower()
    text_types = [
        "text/",
        "application/json",
        "application/xml",
        "application/javascript",
        "application/csv",
    ]
    return any(t in ct for t in text_types)


def compare_attachment_text(old_text: Optional[str], new_text: Optional[str]) -> Optional[Dict[str, Any]]:
    if not old_text or not new_text:
        return {"hasChanges": True, "changes": [], "stats": {"error": "missing content"}}
    return compare_texts(old_text, new_text)


def compare_attachments(saved_attachments: list[dict], current_attachments: list[dict]) -> Dict[str, Any]:
    saved_map = {a["url"]: a for a in saved_attachments}
    current_map = {a["url"]: a for a in current_attachments}

    added: list[dict] = []
    removed: list[dict] = []
    modified: list[dict] = []
    unchanged: list[dict] = []

    for url, current in current_map.items():
        saved = saved_map.get(url)
        if not saved:
            added.append(
                {
                    "url": url,
                    "filename": current.get("filename") or "unnamed",
                    "contentType": current.get("content_type") or current.get("contentType"),
                    "size": current.get("size"),
                }
            )
        elif (saved.get("hash") or "") != (current.get("hash") or ""):
            ct = current.get("content_type") or current.get("contentType")
            text_diff = None
            if is_text_content_type(ct):
                text_diff = compare_attachment_text(saved.get("text_content"), current.get("text_content"))
            modified.append(
                {
                    "url": url,
                    "filename": current.get("filename") or "unnamed",
                    "contentType": ct,
                    "oldSize": saved.get("size"),
                    "newSize": current.get("size"),
                    "oldHash": saved.get("hash"),
                    "newHash": current.get("hash"),
                    "textDiff": text_diff,
                }
            )
        else:
            unchanged.append(
                {
                    "url": url,
                    "filename": current.get("filename") or "unnamed",
                    "contentType": current.get("content_type") or current.get("contentType"),
                    "size": current.get("size"),
                }
            )

    for url, saved in saved_map.items():
        if url not in current_map:
            removed.append(
                {
                    "url": url,
                    "filename": saved.get("filename") or "unnamed",
                    "contentType": saved.get("content_type") or saved.get("contentType"),
                    "size": saved.get("size"),
                }
            )

    return {"added": added, "removed": removed, "modified": modified, "unchanged": unchanged}

