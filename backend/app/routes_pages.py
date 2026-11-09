from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from . import applog
from .diffing import compare_texts, is_text_content_type
from .document_text import extract_document_text
from .filediff_bridge import apply_semantic_compare
from .fetcher import fetch_page_rendered, sanitize_storage_filename
from .results_store import (
    comparison_snapshot,
    count_snapshot_disk_files,
    delete_legacy_snapshot,
    delete_site_dir,
    delete_site_snapshot,
    delete_snapshot,
    files_dir,
    is_local_snapshot_path,
    list_local_snapshots,
    list_sites,
    load_latest_error,
    load_legacy_snapshot,
    load_snapshot,
    normalize_check_name,
    read_attachment_bytes,
    save_error,
    save_legacy_snapshot,
    save_snapshot,
    site_dir,
)
from .schemas import (
    CheckResponse,
    CompareRequest,
    CompareResponse,
    DownloadRequest,
    DownloadResponse,
    ListResponse,
    SnapshotsResponse,
)
from .utils import is_valid_url


router = APIRouter(prefix="/api/pages", tags=["pages"])


def _repo(request: Request):
    return request.app.state.repo


def _browser(request: Request):
    return request.app.state.browser


def _parse_source(request: Request, body_source: str | None = None) -> str:
    raw = (body_source or request.query_params.get("source") or "results").strip().lower()
    if raw not in ("results", "supabase"):
        return "results"
    return raw


def _supabase_unavailable(source: str, repo) -> JSONResponse | None:
    if source != "supabase":
        return None
    if repo is None:
        return JSONResponse(status_code=400, content={"error": "Supabase is not configured"})
    return None


async def _persist_snapshot(
    repo,
    url: str,
    snapshot: dict,
    fetched_attachments: list[dict],
    existing: dict | None,
    check_name: str | None = None,
):
    content = snapshot.get("content") or ""
    title = snapshot.get("title")
    name = normalize_check_name(check_name) or normalize_check_name(snapshot.get("checkName"))
    local_count = len(snapshot.get("attachments") or fetched_attachments or [])
    if repo is None:
        return None, None, local_count
    try:
        if existing:
            page_id = existing["id"]
            await repo.update_page(page_id, content, title, check_name=name)
        else:
            page_id = await repo.insert_page(url, content, title, check_name=name)

        captured_at = snapshot.get("fetchedAt")
        local_path = snapshot.get("localPath")
        snapshot_id = await repo.insert_snapshot(page_id, captured_at, content, title, local_path)

        by_url = {a.get("url"): a for a in fetched_attachments if a.get("url")}
        attachments_to_insert: list[dict] = []
        for att in snapshot.get("attachments") or []:
            ct = att.get("content_type")
            row = {
                "url": att.get("url"),
                "filename": att.get("filename") or "unnamed",
                "content_type": ct,
                "size": att.get("size"),
                "hash": att.get("hash"),
                "text_content": att.get("text_content"),
                "storage_path": att.get("path") or att.get("storage_path"),
            }
            if is_text_content_type(ct):
                row["storage_path"] = None
            else:
                if local_path and row["storage_path"]:
                    row["storage_path"] = f"{local_path}/{row['storage_path']}"

                raw = dict(by_url.get(row["url"]) or {})
                raw["filename"] = sanitize_storage_filename(row["filename"] or "file")
                raw["bytes"] = raw.get("bytes") or b""
                raw["content_type"] = ct
                raw["hash"] = row["hash"]
                try:
                    stored_path = await repo.store_binary_attachment(page_id, snapshot_id, raw)
                    row["storage_path"] = stored_path or row["storage_path"]
                except Exception:
                    row["storage_path"] = row["storage_path"]
            attachments_to_insert.append(row)
        await repo.insert_attachments(snapshot_id, attachments_to_insert)
        return page_id, snapshot_id, len(attachments_to_insert)
    except Exception:
        return None, None, local_count


async def _mark_history(
    repo,
    url: str,
    action: str,
    ok: bool,
    error: str | None = None,
    title: str | None = None,
    page_id=None,
    check_name: str | None = None,
):
    if not ok and error:
        try:
            save_error(url, error, action=action, check_name=check_name)
        except Exception:
            pass
    if repo is None:
        return
    try:
        await repo.upsert_history(
            url,
            last_action=action,
            last_ok=ok,
            last_error=(error[:500] if error else None),
            title=title,
            page_id=page_id,
            check_name=check_name,
        )
    except Exception:
        return


def _compare_log_error(url: str, check_name: str | None, error: str, *, started: float, exc: BaseException | None = None, **extra):
    applog.error(
        "compare",
        url=url,
        checkName=check_name,
        error=error if exc is None else None,
        exc=exc,
        durationMs=int((time.perf_counter() - started) * 1000),
        **extra,
    )


def _history_item(row: dict) -> dict:
    last_ok = row.get("last_ok")
    if last_ok is None:
        last_ok = row.get("lastOk")
    if isinstance(last_ok, int):
        last_ok = bool(last_ok)
    return {
        "id": row.get("id"),
        "url": row.get("url"),
        "title": row.get("title"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "attachment_count": int(row.get("attachment_count") or 0),
        "lastAction": row.get("last_action") or row.get("lastAction"),
        "lastOk": last_ok,
        "lastError": row.get("last_error") or row.get("lastError"),
        "pageId": row.get("page_id") if row.get("page_id") is not None else row.get("pageId"),
        "checkName": row.get("check_name") or row.get("checkName"),
    }


def _resolve_check_name(raw: str | None, existing: dict | None = None) -> str | None:
    name = normalize_check_name(raw)
    if name:
        return name
    if not existing:
        return None
    return normalize_check_name(existing.get("check_name") or existing.get("checkName"))


def _snapshot_files_on_disk(url: str, local_path: str | None, check_name: str | None) -> int | None:
    if not local_path or not is_local_snapshot_path(str(local_path)):
        return None
    try:
        return count_snapshot_disk_files(url, local_path=str(local_path).strip(), check_name=check_name)
    except Exception:
        return None


def _snapshot_item(row: dict) -> dict:
    local_path = row.get("local_path") or row.get("localPath")
    return {
        "id": row.get("id") if row.get("id") is not None else local_path,
        "capturedAt": row.get("captured_at") or row.get("capturedAt"),
        "title": row.get("title"),
        "attachmentCount": int(row.get("attachment_count") or row.get("attachmentCount") or 0),
        "localPath": local_path,
    }


def _merge_snapshots(db_rows: list[dict], file_items: list[dict]) -> list[dict]:
    # Date/time list comes from results/<site>/<date>/<time>/page.json.
    # DB rows only enrich matching folders so a wrong page_id cannot leak another site.
    by_path: dict[str, dict] = {}
    for row in db_rows:
        item = _snapshot_item(row)
        path = item.get("localPath")
        if path:
            by_path[str(path)] = item

    merged: list[dict] = []
    for item in file_items:
        path = str(item.get("localPath") or "")
        db_item = by_path.get(path) if path else None
        disk_count = int(item.get("attachmentCount") or 0)
        merged.append(
            {
                "id": (db_item or {}).get("id") if db_item and db_item.get("id") is not None else (item.get("id") or path),
                "capturedAt": item.get("capturedAt") or (db_item or {}).get("capturedAt"),
                "title": item.get("title") or (db_item or {}).get("title"),
                "attachmentCount": disk_count if disk_count > 0 else int((db_item or {}).get("attachmentCount") or 0),
                "localPath": path or None,
            }
        )

    if not merged:
        merged = [_snapshot_item(row) for row in db_rows]

    def _sort_key(item: dict) -> str:
        return str(item.get("capturedAt") or item.get("localPath") or "")

    merged.sort(key=_sort_key, reverse=True)
    return merged


async def _load_saved_snapshot(repo, url: str, snap_row: dict | None, check_name: str | None, *, allow_legacy: bool) -> dict | None:
    snapshot = None
    local_path = (snap_row or {}).get("local_path") or (snap_row or {}).get("localPath")
    if snap_row and local_path:
        snapshot = load_snapshot(url, local_path=local_path, check_name=check_name)
    if snapshot is None and allow_legacy:
        snapshot = load_legacy_snapshot(url, check_name=check_name)
    if snapshot is None:
        snapshot = load_snapshot(url, check_name=check_name)
    if snapshot is not None and local_path:
        snapshot.setdefault("localPath", local_path)
    if snapshot is None and snap_row:
        snapshot = {
            "url": url,
            "checkName": check_name,
            "title": snap_row.get("title"),
            "content": snap_row.get("content") or "",
            "fetchedAt": snap_row.get("captured_at"),
            "localPath": snap_row.get("local_path"),
            "attachments": [],
        }
        try:
            snapshot["attachments"] = await repo.list_attachments(snap_row["id"])
        except Exception:
            snapshot["attachments"] = []
    return snapshot


def _attachment_bytes(url: str, att: dict, local_path: str | None, check_name: str | None) -> bytes | None:
    data = att.get("bytes")
    if data:
        return data
    rel = att.get("path") or att.get("storage_path")
    if not rel:
        return None
    found = read_attachment_bytes(url, rel, local_path=local_path, check_name=check_name)
    if found is not None:
        return found
    if local_path and rel.startswith(f"{local_path}/"):
        stripped = rel[len(local_path) + 1 :]
        found = read_attachment_bytes(url, stripped, local_path=local_path, check_name=check_name)
        if found is not None:
            return found
    return read_attachment_bytes(url, rel, check_name=check_name)


def _attachment_name(att: dict) -> str:
    raw = str(att.get("filename") or "unnamed").replace("\\", "/").split("/")[-1].strip()
    return raw or "unnamed"


def _attachment_type(att: dict) -> str:
    ext = Path(_attachment_name(att)).suffix.lower()
    if ext:
        return ext
    return str(att.get("content_type") or att.get("contentType") or "")


def _attachment_match_key(att: dict) -> str:
    name = _attachment_name(att)
    stem, dot, ext = name.rpartition(".")
    if not stem:
        return name.casefold()
    return f"{stem.casefold()}.{ext.casefold()}"


def _content_hash(data: bytes | None, att: dict) -> str:
    if data is not None:
        return hashlib.md5(data).hexdigest()
    return str(att.get("hash") or "")


def _summary_row(att: dict) -> dict:
    return {
        "url": att.get("url") or "",
        "filename": _attachment_name(att),
        "contentType": att.get("content_type") or att.get("contentType"),
        "fileType": _attachment_type(att) or None,
        "size": att.get("size"),
    }


def _row_match_key(row: dict) -> str:
    return _attachment_match_key({"filename": row.get("filename") or "unnamed"})


def _scan_files_subdir_keys(
    url: str, local_path: str | None, check_name: str | None
) -> tuple[set[str], dict[str, str]]:
    """
    Filenames in snapshot .../files/ (flat), keyed by the same match rule as attachments.
    Returns (set of keys, key -> display filename).
    """
    keys: set[str] = set()
    key_to_name: dict[str, str] = {}
    if not local_path or not is_local_snapshot_path(str(local_path).strip()):
        return keys, key_to_name
    try:
        d = files_dir(url, local_path=str(local_path).strip(), check_name=check_name)
    except Exception:
        return keys, key_to_name
    if not d.is_dir():
        return keys, key_to_name
    for p in d.iterdir():
        if not p.is_file() or p.name == ".DS_Store":
            continue
        key = _attachment_match_key({"filename": p.name})
        keys.add(key)
        key_to_name.setdefault(key, p.name)
    return keys, key_to_name


def _synthetic_summary_from_disk_file(
    url: str, local_path: str, check_name: str | None, filename: str
) -> dict:
    att = {"url": "", "filename": filename, "content_type": None, "contentType": None}
    try:
        p = files_dir(url, local_path=local_path, check_name=check_name) / filename
        if p.is_file():
            att["size"] = p.stat().st_size
    except Exception:
        pass
    return _summary_row(att)


def _merge_disk_filename_only_diff(
    url: str,
    left_path: str | None,
    right_path: str | None,
    check_name: str | None,
    added: list[dict],
    removed: list[dict],
    modified: list[dict],
    unchanged: list[dict],
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """
    When page.json attachments disagree with saved files under files/, list files present only
    on one side's disk so UI filters (only left / only right) match Finder counts.
    """
    if (
        not left_path
        or not right_path
        or not is_local_snapshot_path(str(left_path).strip())
        or not is_local_snapshot_path(str(right_path).strip())
    ):
        return added, removed, modified, unchanged

    lp = str(left_path).strip()
    rp = str(right_path).strip()
    left_keys, left_names = _scan_files_subdir_keys(url, lp, check_name)
    right_keys, right_names = _scan_files_subdir_keys(url, rp, check_name)
    only_on_right = right_keys - left_keys
    only_on_left = left_keys - right_keys
    if not only_on_right and not only_on_left:
        return added, removed, modified, unchanged

    def keys_in(rows: list[dict]) -> set[str]:
        return {_row_match_key(r) for r in rows}

    added_keys = keys_in(added)
    removed_keys = keys_in(removed)

    def move_to_added(row: dict) -> None:
        k = _row_match_key(row)
        if k in added_keys:
            return
        added.append(row)
        added_keys.add(k)

    def move_to_removed(row: dict) -> None:
        k = _row_match_key(row)
        if k in removed_keys:
            return
        removed.append(row)
        removed_keys.add(k)

    new_modified: list[dict] = []
    for row in modified:
        k = _row_match_key(row)
        if k in only_on_right:
            move_to_added(row)
        elif k in only_on_left:
            move_to_removed(row)
        else:
            new_modified.append(row)

    new_unchanged: list[dict] = []
    for row in unchanged:
        k = _row_match_key(row)
        if k in only_on_right:
            move_to_added(row)
        elif k in only_on_left:
            move_to_removed(row)
        else:
            new_unchanged.append(row)

    for k in only_on_right:
        if k not in added_keys:
            fn = right_names.get(k) or ""
            if fn:
                added.append(_synthetic_summary_from_disk_file(url, rp, check_name, fn))
                added_keys.add(k)

    for k in only_on_left:
        if k not in removed_keys:
            fn = left_names.get(k) or ""
            if fn:
                removed.append(_synthetic_summary_from_disk_file(url, lp, check_name, fn))
                removed_keys.add(k)

    return added, removed, new_modified, new_unchanged


def _pair_attachments(left_items: list[dict], right_items: list[dict]) -> list[tuple[str, dict | None, dict | None]]:
    grouped_left: dict[str, list[dict]] = defaultdict(list)
    grouped_right: dict[str, list[dict]] = defaultdict(list)
    for att in left_items:
        grouped_left[_attachment_match_key(att)].append(att)
    for att in right_items:
        grouped_right[_attachment_match_key(att)].append(att)

    pairs: list[tuple[str, dict | None, dict | None]] = []
    seen: set[str] = set()
    for att in left_items + right_items:
        key = _attachment_match_key(att)
        if key in seen:
            continue
        seen.add(key)
        left_group = grouped_left.get(key) or []
        right_group = grouped_right.get(key) or []
        shared = min(len(left_group), len(right_group))
        for index in range(shared):
            pairs.append(("both", left_group[index], right_group[index]))
        for att in left_group[shared:]:
            pairs.append(("removed", att, None))
        for att in right_group[shared:]:
            pairs.append(("added", None, att))
    return pairs


def _file_text_diff(left_bytes: bytes | None, right_bytes: bytes | None, filename: str) -> tuple[dict | None, str | None]:
    left_text, left_error = extract_document_text(left_bytes, filename)
    right_text, right_error = extract_document_text(right_bytes, filename)
    errors = [item for item in (left_error, right_error) if item and item != "file not found"]
    if left_bytes is None or right_bytes is None:
        missing = []
        if left_bytes is None:
            missing.append("version 1")
        if right_bytes is None:
            missing.append("version 2")
        errors.append("file not found: " + ", ".join(missing))
    if left_text is None or right_text is None:
        return None, "; ".join(errors) or None
    diff = compare_texts(left_text, right_text)
    if len(diff["changes"]) > 400:
        diff["changes"] = diff["changes"][:400]
    return diff, "; ".join(errors) or None


def _diff_snapshots(url: str, left: dict, right: dict, check_name: str | None) -> dict:
    text_diff = compare_texts(left.get("content") or "", right.get("content") or "")
    saved_attachments = list(left.get("attachments") or [])
    current_attachments = list(right.get("attachments") or [])
    left_path = left.get("localPath") or left.get("local_path")
    right_path = right.get("localPath") or right.get("local_path")
    name = check_name or left.get("checkName") or right.get("checkName")

    added: list[dict] = []
    removed: list[dict] = []
    modified: list[dict] = []
    unchanged: list[dict] = []

    for kind, saved_att, cur in _pair_attachments(saved_attachments, current_attachments):
        if kind == "added" and cur is not None:
            added.append(_summary_row(cur))
            continue
        if kind == "removed" and saved_att is not None:
            removed.append(_summary_row(saved_att))
            continue
        if saved_att is None or cur is None:
            continue

        saved_bytes = _attachment_bytes(url, saved_att, left_path, name)
        cur_bytes = _attachment_bytes(url, cur, right_path, name)
        saved_hash = _content_hash(saved_bytes, saved_att)
        cur_hash = _content_hash(cur_bytes, cur)
        filename = _attachment_name(cur) if _attachment_name(cur) != "unnamed" else _attachment_name(saved_att)
        row_type = _attachment_type(cur) or _attachment_type(saved_att) or None
        content_type = cur.get("content_type") or cur.get("contentType") or saved_att.get("content_type")
        if saved_hash and saved_hash == cur_hash:
            unchanged.append(
                {
                    "url": cur.get("url") or saved_att.get("url") or "",
                    "filename": filename,
                    "contentType": content_type,
                    "fileType": row_type,
                    "size": cur.get("size") if cur.get("size") is not None else saved_att.get("size"),
                }
            )
            continue

        file_diff, read_error = _file_text_diff(saved_bytes, cur_bytes, filename)
        modified.append(
            {
                "url": cur.get("url") or saved_att.get("url") or "",
                "filename": filename,
                "contentType": content_type,
                "fileType": row_type,
                "oldSize": saved_att.get("size") if saved_att.get("size") is not None else (len(saved_bytes) if saved_bytes is not None else None),
                "newSize": cur.get("size") if cur.get("size") is not None else (len(cur_bytes) if cur_bytes is not None else None),
                "oldHash": saved_hash or None,
                "newHash": cur_hash or None,
                "textDiff": file_diff,
                "readError": read_error,
            }
        )

    for att in saved_attachments + current_attachments:
        att.pop("bytes", None)

    added, removed, modified, unchanged = _merge_disk_filename_only_diff(
        url,
        left_path if isinstance(left_path, str) else None,
        right_path if isinstance(right_path, str) else None,
        name,
        added,
        removed,
        modified,
        unchanged,
    )

    attachment_diffs = {"added": added, "removed": removed, "modified": modified, "unchanged": unchanged}

    _files_left_disk = _snapshot_files_on_disk(url, left_path if isinstance(left_path, str) else None, name)
    _files_right_disk = _snapshot_files_on_disk(url, right_path if isinstance(right_path, str) else None, name)
    _summary_files_left = _files_left_disk if _files_left_disk is not None else len(saved_attachments)
    _summary_files_right = _files_right_disk if _files_right_disk is not None else len(current_attachments)

    return {
        "url": url,
        "savedTitle": left.get("title"),
        "currentTitle": right.get("title"),
        "savedAt": left.get("fetchedAt") or left.get("captured_at"),
        "textDiff": text_diff,
        "attachmentDiffs": attachment_diffs,
        "summary": {
            "textChanged": bool(text_diff.get("hasChanges")),
            "filesLeft": _summary_files_left,
            "filesRight": _summary_files_right,
            "attachmentsAdded": len(added),
            "attachmentsRemoved": len(removed),
            "attachmentsModified": len(modified),
            "attachmentsUnchanged": len(unchanged),
        },
        "explanation": None,
    }


@router.get("/check", response_model=CheckResponse)
async def check(url: str, request: Request):
    if not url:
        return JSONResponse(status_code=400, content={"error": "URL is required"})
    if not is_valid_url(url):
        return JSONResponse(status_code=400, content={"error": "Invalid URL format"})

    repo = _repo(request)
    source = _parse_source(request)
    blocked = _supabase_unavailable(source, repo)
    if blocked:
        return blocked
    if source == "results":
        stored = load_snapshot(url) or load_legacy_snapshot(url)
        if not stored:
            return {"exists": False}
        return {
            "exists": True,
            "page": {
                "id": site_dir(url, stored.get("checkName")).name,
                "url": stored.get("url") or url,
                "title": stored.get("title"),
                "created_at": stored.get("fetchedAt"),
                "updated_at": stored.get("fetchedAt"),
                "attachmentCount": len(stored.get("attachments") or []),
            },
        }

    if repo is None:
        return {"exists": False}
    page = await repo.get_page_by_url(url)
    if not page:
        return {"exists": False}

    attachment_count = await repo.count_attachments(page["id"])
    # keep shape close to the old backend
    page_payload = {
        "id": page["id"],
        "url": page["url"],
        "title": page.get("title"),
        "created_at": page.get("created_at"),
        "updated_at": page.get("updated_at"),
        "attachmentCount": attachment_count,
    }
    return {"exists": True, "page": page_payload}


@router.post("/download", response_model=DownloadResponse)
async def download(body: DownloadRequest, request: Request):
    url = body.url.strip()
    started = time.perf_counter()

    if not url:
        applog.error("page_download", error="URL is required")
        return JSONResponse(status_code=400, content={"error": "URL is required"})
    if not is_valid_url(url):
        applog.error("page_download", url=url, error="Invalid URL format")
        return JSONResponse(status_code=400, content={"error": "Invalid URL format"})

    repo = _repo(request)
    source = _parse_source(request, body.source)
    blocked = _supabase_unavailable(source, repo)
    if blocked:
        applog.error("page_download", url=url, error="Supabase is not configured", source=source)
        return blocked
    existing = await repo.get_page_by_url(url) if repo else None
    existing_id = existing["id"] if existing else None
    check_name = _resolve_check_name(body.checkName, existing)
    await _mark_history(repo, url, "download", False, page_id=existing_id, check_name=check_name)

    browser = _browser(request)
    try:
        rendered = await fetch_page_rendered(browser, url)
        current_attachments = list(rendered.get("attachments") or [])
    except Exception as exc:
        await _mark_history(repo, url, "download", False, error=str(exc), page_id=existing_id, check_name=check_name)
        applog.error(
            "page_download",
            url=url,
            checkName=check_name,
            source=source,
            durationMs=int((time.perf_counter() - started) * 1000),
            exc=exc,
        )
        return JSONResponse(status_code=500, content={"error": str(exc)})

    snapshot = comparison_snapshot(
        url, rendered.get("title"), rendered.get("content"), current_attachments, check_name=check_name
    )
    save_snapshot(url, snapshot, downloaded_attachments=current_attachments, check_name=check_name)
    save_legacy_snapshot(url, snapshot, check_name=check_name)
    stored = load_snapshot(url, check_name=check_name)
    if stored is None:
        await _mark_history(
            repo, url, "download", False, error="Failed to read saved snapshot", page_id=existing_id, check_name=check_name
        )
        applog.error(
            "page_download",
            url=url,
            checkName=check_name,
            source=source,
            durationMs=int((time.perf_counter() - started) * 1000),
            error="Failed to read saved snapshot",
        )
        return JSONResponse(status_code=500, content={"error": "Failed to read saved snapshot"})

    page_id, snapshot_id, attachment_count = await _persist_snapshot(
        repo, url, stored, current_attachments, existing, check_name=check_name
    )
    if page_id is None:
        page_id = site_dir(url, check_name).name
        snapshot_id = stored.get("localPath")
        attachment_count = len(stored.get("attachments") or current_attachments or [])
    await _mark_history(repo, url, "download", True, title=stored.get("title"), page_id=page_id, check_name=check_name)
    applog.success(
        "page_download",
        url=url,
        checkName=check_name,
        source=source,
        title=stored.get("title"),
        pageId=page_id,
        snapshotId=snapshot_id,
        attachmentCount=attachment_count,
        durationMs=int((time.perf_counter() - started) * 1000),
    )
    return {
        "success": True,
        "message": "Page saved",
        "pageId": page_id,
        "snapshotId": snapshot_id,
        "attachmentCount": attachment_count,
    }


@router.post("/compare", response_model=CompareResponse)
async def compare(body: CompareRequest, request: Request):
    url = body.url.strip()
    started = time.perf_counter()
    if not url:
        applog.error("compare", error="URL is required")
        return JSONResponse(status_code=400, content={"error": "URL is required"})
    if not is_valid_url(url):
        applog.error("compare", url=url, error="Invalid URL format")
        return JSONResponse(status_code=400, content={"error": "Invalid URL format"})

    repo = _repo(request)
    source = _parse_source(request, body.source)
    blocked = _supabase_unavailable(source, repo)
    if blocked:
        applog.error("compare", url=url, error="Supabase is not configured", source=source)
        return blocked
    saved = await repo.get_page_by_url(url) if repo and source == "supabase" else None
    saved_id = saved["id"] if saved else None
    check_name = _resolve_check_name(body.checkName, saved)
    await _mark_history(repo, url, "compare", False, page_id=saved_id, check_name=check_name)

    two_saved = body.snapshotId is not None and body.snapshotId2 is not None
    file_snapshot = load_snapshot(url, check_name=check_name) or load_legacy_snapshot(url, check_name=check_name)
    if source == "results":
        if not file_snapshot and not two_saved:
            await _mark_history(
                repo, url, "compare", False, error="No saved version found for this URL", check_name=check_name
            )
            _compare_log_error(url, check_name, "No saved version found for this URL", started=started, source=source)
            return JSONResponse(status_code=404, content={"error": "No saved version found for this URL"})
    elif not saved and not two_saved:
        await _mark_history(repo, url, "compare", False, error="No saved version found for this URL", check_name=check_name)
        _compare_log_error(url, check_name, "No saved version found for this URL", started=started, source=source)
        return JSONResponse(status_code=404, content={"error": "No saved version found for this URL"})

    async def _snap_for(snapshot_id, *, allow_legacy: bool):
        if snapshot_id is not None:
            sid = str(snapshot_id).strip()
            if is_local_snapshot_path(sid) or source == "results":
                payload = load_snapshot(url, local_path=sid if is_local_snapshot_path(sid) else None, check_name=check_name)
                if payload is None and is_local_snapshot_path(sid):
                    return None, JSONResponse(status_code=404, content={"error": "Snapshot not found"})
                if payload is not None:
                    if is_local_snapshot_path(sid):
                        payload.setdefault("localPath", sid)
                    return payload, None
            if not saved or repo is None:
                payload = load_snapshot(url, local_path=sid if is_local_snapshot_path(sid) else None, check_name=check_name)
                if payload is None:
                    return None, JSONResponse(status_code=404, content={"error": "Snapshot not found"})
                return payload, None
            candidate = await repo.get_snapshot(snapshot_id)
            if not candidate or str(candidate.get("page_id")) != str(saved["id"]):
                payload = load_snapshot(url, local_path=sid, check_name=check_name)
                if payload is None:
                    return None, JSONResponse(status_code=404, content={"error": "Snapshot not found"})
                return payload, None
            payload = await _load_saved_snapshot(repo, url, candidate, check_name, allow_legacy=False)
            return payload, None
        if not saved or repo is None or source == "results":
            payload = load_snapshot(url, check_name=check_name)
            if payload is None and allow_legacy:
                payload = load_legacy_snapshot(url, check_name=check_name)
            return payload, None
        row = await repo.get_latest_snapshot(saved["id"])
        payload = await _load_saved_snapshot(repo, url, row, check_name, allow_legacy=allow_legacy)
        return payload, None

    if body.snapshotId2 is not None:
        if body.snapshotId is None:
            await _mark_history(
                repo, url, "compare", False, error="Both snapshot versions are required", page_id=saved_id, check_name=check_name
            )
            _compare_log_error(url, check_name, "Both snapshot versions are required", started=started)
            return JSONResponse(status_code=400, content={"error": "Both snapshot versions are required"})
        left, err = await _snap_for(body.snapshotId, allow_legacy=False)
        if err:
            await _mark_history(
                repo, url, "compare", False, error="Snapshot not found", page_id=saved_id, check_name=check_name
            )
            _compare_log_error(url, check_name, "Snapshot not found", started=started, snapshotId=body.snapshotId)
            return err
        right, err = await _snap_for(body.snapshotId2, allow_legacy=False)
        if err:
            await _mark_history(
                repo, url, "compare", False, error="Snapshot not found", page_id=saved_id, check_name=check_name
            )
            _compare_log_error(url, check_name, "Snapshot not found", started=started, snapshotId=body.snapshotId2)
            return err
        if left is None or right is None:
            await _mark_history(
                repo, url, "compare", False, error="Failed to load saved snapshot", page_id=saved_id, check_name=check_name
            )
            _compare_log_error(url, check_name, "Failed to load saved snapshot", started=started)
            return JSONResponse(status_code=500, content={"error": "Failed to load saved snapshot"})
        comparison = _diff_snapshots(url, left, right, check_name)
        semantic_left, semantic_right = left, right
    else:
        if source != "results" and not saved:
            await _mark_history(
                repo, url, "compare", False, error="No saved version found for this URL", check_name=check_name
            )
            _compare_log_error(url, check_name, "No saved version found for this URL", started=started, source=source)
            return JSONResponse(status_code=404, content={"error": "No saved version found for this URL"})
        snapshot, err = await _snap_for(body.snapshotId, allow_legacy=body.snapshotId is None)
        if err:
            await _mark_history(
                repo, url, "compare", False, error="Snapshot not found", page_id=saved_id, check_name=check_name
            )
            _compare_log_error(url, check_name, "Snapshot not found", started=started, snapshotId=body.snapshotId)
            return err
        if snapshot is None:
            await _mark_history(
                repo, url, "compare", False, error="Failed to load saved snapshot", page_id=saved_id, check_name=check_name
            )
            _compare_log_error(url, check_name, "Failed to load saved snapshot", started=started)
            return JSONResponse(status_code=500, content={"error": "Failed to load saved snapshot"})

        browser = _browser(request)
        try:
            current = await fetch_page_rendered(browser, url)
            current_attachments = list(current.get("attachments") or [])
        except Exception as exc:
            await _mark_history(repo, url, "compare", False, error=str(exc), page_id=saved_id, check_name=check_name)
            _compare_log_error(url, check_name, str(exc), started=started, exc=exc)
            return JSONResponse(status_code=500, content={"error": str(exc)})

        right = {
            "url": url,
            "checkName": check_name,
            "title": current.get("title"),
            "content": current.get("content") or "",
            "fetchedAt": current.get("fetchedAt"),
            "attachments": current_attachments,
        }
        comparison = _diff_snapshots(url, snapshot, right, check_name)
        semantic_left, semantic_right = snapshot, right

    if body.compareEngine == "llm":
        comparison = await apply_semantic_compare(
            comparison,
            url=url,
            left=semantic_left,
            right=semantic_right,
            check_name=check_name,
            model=body.compareModel,
            locale=body.locale,
        )

    # Agent explanation (optional, added later by agent module)
    explain = getattr(request.app.state, "explain_delta", None)
    if explain:
        try:
            comparison["explanation"] = await explain(comparison, locale=body.locale)
        except Exception as exc:
            comparison["explanation"] = None
            msg = str(exc).strip() or type(exc).__name__
            comparison["explanationError"] = msg[:500]
            applog.error(
                "compare",
                url=url,
                checkName=check_name,
                stage="explanation",
                durationMs=int((time.perf_counter() - started) * 1000),
                exc=exc,
            )

    await _mark_history(
        repo,
        url,
        "compare",
        True,
        title=comparison.get("currentTitle") or comparison.get("savedTitle"),
        page_id=saved_id,
        check_name=check_name,
    )
    applog.success(
        "compare",
        url=url,
        checkName=check_name,
        source=source,
        compareEngine=body.compareEngine,
        durationMs=int((time.perf_counter() - started) * 1000),
    )
    return {"success": True, "comparison": comparison}


@router.get("/list", response_model=ListResponse)
async def list_pages(request: Request):
    repo = _repo(request)
    source = _parse_source(request)
    blocked = _supabase_unavailable(source, repo)
    if blocked:
        return blocked
    if source == "results":
        return {"pages": list_sites()}
    if repo is None:
        return {"pages": []}
    rows = await repo.list_history()
    pages = []
    for row in rows:
        item = _history_item(row)
        page_id = item.get("pageId")
        db_rows: list[dict] = []
        if page_id is not None:
            try:
                db_rows = await repo.list_snapshots(page_id)
            except Exception:
                db_rows = []
        file_items = list_local_snapshots(item.get("url") or "", item.get("checkName"))
        item["snapshots"] = _merge_snapshots(db_rows, file_items)
        if not item.get("lastError"):
            stored = load_latest_error(item.get("url") or "", item.get("checkName"))
            if stored and stored.get("error"):
                item["lastError"] = stored.get("error")
        pages.append(item)
    return {"pages": pages}

@router.get("/snapshots", response_model=SnapshotsResponse)
async def list_snapshots(url: str, request: Request):
    if not url:
        return JSONResponse(status_code=400, content={"error": "URL is required"})
    if not is_valid_url(url):
        return JSONResponse(status_code=400, content={"error": "Invalid URL format"})

    repo = _repo(request)
    source = _parse_source(request)
    blocked = _supabase_unavailable(source, repo)
    if blocked:
        return blocked
    db_rows: list[dict] = []
    check_name = None
    if source == "supabase" and repo:
        page = await repo.get_page_by_url(url)
        if page:
            check_name = _resolve_check_name(None, page)
            try:
                db_rows = await repo.list_snapshots(page["id"])
            except Exception:
                db_rows = []
    file_items = list_local_snapshots(url, check_name)
    if source == "results":
        return {"url": url, "snapshots": file_items}
    return {"url": url, "snapshots": _merge_snapshots(db_rows, file_items)}


@router.get("", response_model=ListResponse)
async def list_pages_alias(request: Request):
    return await list_pages(request)


@router.delete("/{page_id}/snapshots")
async def delete_page_snapshot(page_id: str, request: Request, snapshotId: str):
    repo = _repo(request)
    source = _parse_source(request)
    blocked = _supabase_unavailable(source, repo)
    if blocked:
        return blocked
    sid = (snapshotId or "").strip()
    if not sid:
        return JSONResponse(status_code=400, content={"error": "snapshotId is required"})

    if source == "results":
        if delete_site_snapshot(page_id, sid):
            return {"success": True, "message": "Snapshot deleted"}
        return JSONResponse(status_code=404, content={"error": "Snapshot not found"})

    if repo is None:
        return JSONResponse(status_code=400, content={"error": "Supabase is not configured"})

    hist = await repo.get_history_by_id(page_id)
    page = None
    if hist and hist.get("page_id") is not None:
        page = await repo.get_page_by_id(hist.get("page_id"))
    if page is None:
        page = await repo.get_page_by_id(page_id)

    snap_row = await repo.get_snapshot(sid)
    local_path = None
    if snap_row:
        local_path = snap_row.get("local_path") or snap_row.get("localPath")
        await repo.delete_snapshot(snap_row["id"])
    elif is_local_snapshot_path(sid):
        local_path = sid
        if page:
            try:
                for row in await repo.list_snapshots(page["id"]):
                    path = row.get("local_path") or row.get("localPath")
                    if path == sid:
                        await repo.delete_snapshot(row["id"])
                        break
            except Exception:
                pass
    else:
        return JSONResponse(status_code=404, content={"error": "Snapshot not found"})

    url = (page or {}).get("url")
    check_name = _resolve_check_name((hist or {}).get("check_name") if hist else None, page)
    if url and local_path:
        delete_snapshot(url, local_path=local_path, check_name=check_name)
    if is_local_snapshot_path(sid):
        delete_site_snapshot(page_id, sid)
    return {"success": True, "message": "Snapshot deleted"}


@router.delete("/{page_id}")
async def delete(page_id: str, request: Request):
    repo = _repo(request)
    source = _parse_source(request)
    blocked = _supabase_unavailable(source, repo)
    if blocked:
        return blocked
    if source == "results":
        if delete_site_dir(page_id):
            return {"success": True, "message": "Page deleted"}
        return JSONResponse(status_code=404, content={"error": "Page not found"})

    if repo is None:
        return JSONResponse(status_code=400, content={"error": "Supabase is not configured"})
    hist = await repo.get_history_by_id(page_id)
    if hist:
        page = await repo.get_page_by_id(hist.get("page_id")) if hist.get("page_id") is not None else None
        if page:
            check_name = _resolve_check_name(hist.get("check_name") or hist.get("checkName"), page)
            delete_snapshot(page["url"], check_name=check_name)
            delete_legacy_snapshot(page["url"], check_name=check_name)
            await repo.delete_page(page["id"])
        await repo.delete_history(hist["id"])
        return {"success": True, "message": "Page deleted"}

    page = await repo.get_page_by_id(page_id)
    if not page:
        return JSONResponse(status_code=404, content={"error": "Page not found"})
    check_name = _resolve_check_name(None, page)
    delete_snapshot(page["url"], check_name=check_name)
    delete_legacy_snapshot(page["url"], check_name=check_name)
    ok = await repo.delete_page(page_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "Page not found"})
    return {"success": True, "message": "Page deleted"}

