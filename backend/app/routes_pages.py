from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .diffing import compare_attachments, compare_texts, is_text_content_type
from .fetcher import extract_attachment_links, fetch_attachments, fetch_page_rendered, sanitize_storage_filename
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
    rendered = await fetch_page_rendered(browser, url)
    attachment_links = extract_attachment_links(rendered["html"], url)
    current_attachments = await fetch_attachments(attachment_links)

    if existing:
        page_id = existing["id"]
        await repo.update_page(page_id, rendered["content"], rendered["title"])
        await repo.delete_attachments(page_id)
        attachments_to_insert: list[dict] = []
        for att in current_attachments:
            ct = att.get("content_type")
            if is_text_content_type(ct):
                att["storage_path"] = None
            else:
                att["filename"] = sanitize_storage_filename(att.get("filename") or "file")
                att["storage_path"] = await repo.store_binary_attachment(page_id, att)
            att.pop("bytes", None)
            attachments_to_insert.append(att)
        await repo.insert_attachments(page_id, attachments_to_insert)
        return {
            "success": True,
            "message": "Page updated",
            "pageId": page_id,
            "attachmentCount": len(attachments_to_insert),
        }

    page_id = await repo.insert_page(url, rendered["content"], rendered["title"])
    await repo.delete_attachments(page_id)
    attachments_to_insert = []
    for att in current_attachments:
        ct = att.get("content_type")
        if is_text_content_type(ct):
            att["storage_path"] = None
        else:
            att["filename"] = sanitize_storage_filename(att.get("filename") or "file")
            att["storage_path"] = await repo.store_binary_attachment(page_id, att)
        att.pop("bytes", None)
        attachments_to_insert.append(att)
    await repo.insert_attachments(page_id, attachments_to_insert)
    return {
        "success": True,
        "message": "Page saved",
        "pageId": page_id,
        "attachmentCount": len(attachments_to_insert),
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

    saved_attachments = await repo.list_attachments(saved["id"])

    browser = _browser(request)
    current = await fetch_page_rendered(browser, url)
    current_links = extract_attachment_links(current["html"], url)
    current_attachments = await fetch_attachments(current_links)
    for a in current_attachments:
        a.pop("bytes", None)

    text_diff = compare_texts(saved.get("content") or "", current.get("content") or "")
    attachment_diffs = compare_attachments(saved_attachments, current_attachments)

    summary = {
        "textChanged": bool(text_diff.get("hasChanges")),
        "attachmentsAdded": len(attachment_diffs["added"]),
        "attachmentsRemoved": len(attachment_diffs["removed"]),
        "attachmentsModified": len(attachment_diffs["modified"]),
        "attachmentsUnchanged": len(attachment_diffs["unchanged"]),
    }

    comparison = {
        "url": url,
        "savedTitle": saved.get("title"),
        "currentTitle": current.get("title"),
        "savedAt": saved.get("updated_at"),
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
    await repo.delete_attachments(page_id)
    ok = await repo.delete_page(page_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "Page not found"})
    return {"success": True, "message": "Page deleted"}

