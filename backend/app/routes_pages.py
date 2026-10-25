from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .diffing import compare_attachments, compare_texts, is_text_content_type
from .fetcher import extract_attachment_links, fetch_attachments, fetch_page_rendered, sanitize_storage_filename
from .results_store import comparison_snapshot, delete_snapshot, load_snapshot, save_snapshot
from .schemas import (
    CheckResponse,
    CompareRequest,
    CompareResponse,
    DownloadRequest,
    DownloadResponse,
    ListResponse,
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

    await repo.delete_attachments(page_id)
    by_url = {att.get("url"): att for att in fetched_attachments}
    attachments_to_insert: list[dict] = []
    for att in snapshot.get("attachments") or []:
        row = {
            "url": att.get("url"),
            "filename": att.get("filename") or "unnamed",
            "content_type": att.get("content_type"),
            "size": att.get("size"),
            "hash": att.get("hash"),
            "text_content": att.get("text_content"),
            "storage_path": None,
        }
        if not is_text_content_type(row["content_type"]):
            raw = dict(by_url.get(row["url"]) or {})
            raw["filename"] = sanitize_storage_filename(row["filename"] or "file")
            raw["bytes"] = raw.get("bytes") or b""
            raw["content_type"] = row["content_type"]
            raw["hash"] = row["hash"]
            row["storage_path"] = await repo.store_binary_attachment(page_id, raw)
        attachments_to_insert.append(row)
    await repo.insert_attachments(page_id, attachments_to_insert)
    return page_id, len(attachments_to_insert)


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
    overwrite = bool(body.overwrite)

    if not url:
        return JSONResponse(status_code=400, content={"error": "URL is required"})
    if not is_valid_url(url):
        return JSONResponse(status_code=400, content={"error": "Invalid URL format"})

    repo = _repo(request)
    existing = await repo.get_page_by_url(url)

    if existing and not overwrite:
        return JSONResponse(
            status_code=409,
            content={"error": "Page already exists", "requiresConfirmation": True},
        )

    browser = _browser(request)
    try:
        rendered = await fetch_page_rendered(browser, url)
        attachment_links = extract_attachment_links(rendered["html"], url)
        current_attachments = await fetch_attachments(attachment_links)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})

    snapshot = comparison_snapshot(url, rendered.get("title"), rendered.get("content"), current_attachments)
    save_snapshot(url, snapshot)
    stored = load_snapshot(url)
    if stored is None:
        return JSONResponse(status_code=500, content={"error": "Failed to read saved snapshot"})

    page_id, attachment_count = await _persist_snapshot(repo, url, stored, current_attachments, existing)
    return {
        "success": True,
        "message": "Page updated" if existing else "Page saved",
        "pageId": page_id,
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

    snapshot = load_snapshot(url)
    if snapshot is None:
        saved_attachments = await repo.list_attachments(saved["id"])
        snapshot = comparison_snapshot(
            url,
            saved.get("title"),
            saved.get("content"),
            saved_attachments,
            fetched_at=saved.get("updated_at"),
        )
        save_snapshot(url, snapshot)
        snapshot = load_snapshot(url)
        if snapshot is None:
            return JSONResponse(status_code=500, content={"error": "Failed to read saved snapshot"})

    browser = _browser(request)
    current = await fetch_page_rendered(browser, url)
    current_links = extract_attachment_links(current["html"], url)
    current_attachments = await fetch_attachments(current_links)
    for a in current_attachments:
        a.pop("bytes", None)

    text_diff = compare_texts(snapshot.get("content") or "", current.get("content") or "")
    attachment_diffs = compare_attachments(snapshot.get("attachments") or [], current_attachments)

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
    await repo.delete_attachments(page_id)
    ok = await repo.delete_page(page_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "Page not found"})
    return {"success": True, "message": "Page deleted"}

