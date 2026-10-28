from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .diffing import compare_attachment_text, compare_texts, is_text_content_type
from .fetcher import extract_attachment_links, fetch_attachments, fetch_page_rendered, sanitize_storage_filename
from .results_store import (
    comparison_snapshot,
    delete_legacy_snapshot,
    delete_snapshot,
    load_legacy_snapshot,
    load_snapshot,
    read_attachment_bytes,
    save_legacy_snapshot,
    save_snapshot,
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


async def _persist_snapshot(repo, url: str, snapshot: dict, fetched_attachments: list[dict], existing: dict | None):
    content = snapshot.get("content") or ""
    title = snapshot.get("title")
    if existing:
        page_id = existing["id"]
        await repo.update_page(page_id, content, title)
    else:
        page_id = await repo.insert_page(url, content, title)

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
            # Local path (relative under results/<url>/...)
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
                # Keep local storage_path if upload is unavailable.
                row["storage_path"] = row["storage_path"]
        attachments_to_insert.append(row)
    await repo.insert_attachments(snapshot_id, attachments_to_insert)
    return page_id, snapshot_id, len(attachments_to_insert)


@router.get("/check", response_model=CheckResponse)
async def check(url: str, request: Request):
    if not url:
        return JSONResponse(status_code=400, content={"error": "URL is required"})
    if not is_valid_url(url):
        return JSONResponse(status_code=400, content={"error": "Invalid URL format"})

    repo = _repo(request)
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

    if not url:
        return JSONResponse(status_code=400, content={"error": "URL is required"})
    if not is_valid_url(url):
        return JSONResponse(status_code=400, content={"error": "Invalid URL format"})

    repo = _repo(request)
    existing = await repo.get_page_by_url(url)

    browser = _browser(request)
    try:
        rendered = await fetch_page_rendered(browser, url)
        attachment_links = extract_attachment_links(rendered["html"], url)
        current_attachments = await fetch_attachments(attachment_links)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})

    snapshot = comparison_snapshot(url, rendered.get("title"), rendered.get("content"), current_attachments)
    save_snapshot(url, snapshot, downloaded_attachments=current_attachments)
    save_legacy_snapshot(url, snapshot)
    stored = load_snapshot(url)
    if stored is None:
        return JSONResponse(status_code=500, content={"error": "Failed to read saved snapshot"})

    page_id, snapshot_id, attachment_count = await _persist_snapshot(repo, url, stored, current_attachments, existing)
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
    if not url:
        return JSONResponse(status_code=400, content={"error": "URL is required"})
    if not is_valid_url(url):
        return JSONResponse(status_code=400, content={"error": "Invalid URL format"})

    repo = _repo(request)
    saved = await repo.get_page_by_url(url)
    if not saved:
        return JSONResponse(status_code=404, content={"error": "No saved version found for this URL"})

    snap_row = None
    if body.snapshotId is not None:
        candidate = await repo.get_snapshot(body.snapshotId)
        if candidate and str(candidate.get("page_id")) == str(saved["id"]):
            snap_row = candidate
        else:
            return JSONResponse(status_code=404, content={"error": "Snapshot not found"})
    else:
        snap_row = await repo.get_latest_snapshot(saved["id"])
    snapshot = None
    if snap_row and snap_row.get("local_path"):
        snapshot = load_snapshot(url, local_path=snap_row.get("local_path"))
    if snapshot is None and body.snapshotId is None:
        snapshot = load_legacy_snapshot(url)
    if snapshot is None:
        snapshot = load_snapshot(url)
    if snapshot is None and snap_row:
        # fallback to DB snapshot data (no local files)
        snapshot = {
            "url": url,
            "title": snap_row.get("title"),
            "content": snap_row.get("content") or "",
            "fetchedAt": snap_row.get("captured_at"),
            "localPath": snap_row.get("local_path"),
            "attachments": [],
        }
        try:
            db_atts = await repo.list_attachments(snap_row["id"])
            snapshot["attachments"] = db_atts
        except Exception:
            snapshot["attachments"] = []
    if snapshot is None:
        return JSONResponse(status_code=500, content={"error": "Failed to load saved snapshot"})

    browser = _browser(request)
    current = await fetch_page_rendered(browser, url)
    current_links = extract_attachment_links(current["html"], url)
    current_attachments = await fetch_attachments(current_links)

    text_diff = compare_texts(snapshot.get("content") or "", current.get("content") or "")

    saved_attachments = list(snapshot.get("attachments") or [])
    saved_map = {a.get("url"): a for a in saved_attachments if a.get("url")}
    current_map = {a.get("url"): a for a in current_attachments if a.get("url")}

    added: list[dict] = []
    removed: list[dict] = []
    modified: list[dict] = []
    unchanged: list[dict] = []

    for att_url, cur in current_map.items():
        saved_att = saved_map.get(att_url)
        ct = cur.get("content_type") or cur.get("contentType") or (saved_att.get("content_type") if saved_att else None)
        if not saved_att:
            added.append(
                {
                    "url": att_url,
                    "filename": cur.get("filename") or "unnamed",
                    "contentType": ct,
                    "size": cur.get("size"),
                }
            )
            continue

        saved_hash = (saved_att.get("hash") or "")
        cur_hash = (cur.get("hash") or "")
        if saved_hash == cur_hash and saved_hash:
            unchanged.append(
                {
                    "url": att_url,
                    "filename": cur.get("filename") or saved_att.get("filename") or "unnamed",
                    "contentType": ct,
                    "size": cur.get("size"),
                }
            )
            continue

        if is_text_content_type(ct):
            text_diff_att = compare_attachment_text(saved_att.get("text_content"), cur.get("text_content"))
            modified.append(
                {
                    "url": att_url,
                    "filename": cur.get("filename") or saved_att.get("filename") or "unnamed",
                    "contentType": ct,
                    "oldSize": saved_att.get("size"),
                    "newSize": cur.get("size"),
                    "oldHash": saved_att.get("hash"),
                    "newHash": cur.get("hash"),
                    "textDiff": text_diff_att,
                }
            )
            continue

        # Binary: compare bytes against the saved copy on disk (source of truth).
        saved_rel = saved_att.get("path") or saved_att.get("storage_path")
        saved_bytes = (
            read_attachment_bytes(url, saved_rel, local_path=snapshot.get("localPath")) if saved_rel else None
        )
        cur_bytes = cur.get("bytes") or b""
        if saved_bytes is not None and saved_bytes == cur_bytes:
            unchanged.append(
                {
                    "url": att_url,
                    "filename": cur.get("filename") or saved_att.get("filename") or "unnamed",
                    "contentType": ct,
                    "size": cur.get("size"),
                }
            )
        elif saved_bytes is None and saved_hash == cur_hash and saved_hash:
            # No saved file on disk (e.g. legacy snapshot from DB); fall back to hash equality.
            unchanged.append(
                {
                    "url": att_url,
                    "filename": cur.get("filename") or saved_att.get("filename") or "unnamed",
                    "contentType": ct,
                    "size": cur.get("size"),
                }
            )
        else:
            modified.append(
                {
                    "url": att_url,
                    "filename": cur.get("filename") or saved_att.get("filename") or "unnamed",
                    "contentType": ct,
                    "oldSize": saved_att.get("size"),
                    "newSize": cur.get("size"),
                    "oldHash": saved_att.get("hash"),
                    "newHash": cur.get("hash"),
                    "textDiff": None,
                }
            )

    for att_url, saved_att in saved_map.items():
        if att_url not in current_map:
            removed.append(
                {
                    "url": att_url,
                    "filename": saved_att.get("filename") or "unnamed",
                    "contentType": saved_att.get("content_type") or saved_att.get("contentType"),
                    "size": saved_att.get("size"),
                }
            )

    attachment_diffs = {"added": added, "removed": removed, "modified": modified, "unchanged": unchanged}

    # Do not leak bytes in the response.
    for a in current_attachments:
        a.pop("bytes", None)

    summary = {
        "textChanged": bool(text_diff.get("hasChanges")),
        "attachmentsAdded": len(attachment_diffs["added"]),
        "attachmentsRemoved": len(attachment_diffs["removed"]),
        "attachmentsModified": len(attachment_diffs["modified"]),
        "attachmentsUnchanged": len(attachment_diffs["unchanged"]),
    }

    comparison = {
        "url": url,
        "savedTitle": snapshot.get("title"),
        "currentTitle": current.get("title"),
        "savedAt": snapshot.get("fetchedAt") or saved.get("updated_at"),
        "textDiff": text_diff,
        "attachmentDiffs": attachment_diffs,
        "summary": summary,
        "explanation": None,
    }

    # Agent explanation (optional, added later by agent module)
    explain = getattr(request.app.state, "explain_delta", None)
    if explain:
        try:
            comparison["explanation"] = await explain(comparison, locale=body.locale)
        except Exception:
            comparison["explanation"] = None

    return {"success": True, "comparison": comparison}


@router.get("/list", response_model=ListResponse)
async def list_pages(request: Request):
    repo = _repo(request)
    pages = await repo.list_pages()
    return {"pages": pages}

@router.get("/snapshots", response_model=SnapshotsResponse)
async def list_snapshots(url: str, request: Request):
    if not url:
        return JSONResponse(status_code=400, content={"error": "URL is required"})
    if not is_valid_url(url):
        return JSONResponse(status_code=400, content={"error": "Invalid URL format"})

    repo = _repo(request)
    page = await repo.get_page_by_url(url)
    if not page:
        return {"url": url, "snapshots": []}

    snapshots = await repo.list_snapshots(page["id"])
    items = []
    for s in snapshots:
        items.append(
            {
                "id": s.get("id"),
                "capturedAt": s.get("captured_at") or s.get("capturedAt"),
                "title": s.get("title"),
                "attachmentCount": int(s.get("attachment_count") or s.get("attachmentCount") or 0),
            }
        )
    return {"url": url, "snapshots": items}


@router.get("", response_model=ListResponse)
async def list_pages_alias(request: Request):
    return await list_pages(request)


@router.delete("/{page_id}")
async def delete(page_id: str, request: Request):
    repo = _repo(request)
    page = await repo.get_page_by_id(page_id)
    if not page:
        return JSONResponse(status_code=404, content={"error": "Page not found"})
    delete_snapshot(page["url"])
    delete_legacy_snapshot(page["url"])
    ok = await repo.delete_page(page_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "Page not found"})
    return {"success": True, "message": "Page deleted"}

