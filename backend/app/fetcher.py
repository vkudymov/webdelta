from __future__ import annotations

import asyncio
import hashlib
import os
import re
import tempfile
import time
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Browser, Page

from . import applog
from .config import settings
from .diffing import is_text_content_type


# Documents and archives only. Images, media, and tracking pixels are not saved.
DOCUMENT_ATTACHMENT_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".txt",
    ".rtf",
    ".odt",
    ".ods",
    ".odp",
    ".csv",
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
)

_FILENAME_RE = re.compile(r"""filename\*?=(?:UTF-8''|utf-8'')?["']?([^"';]+)""", re.IGNORECASE)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _strip_non_content(soup: BeautifulSoup) -> None:
    for tag in soup.select(
        "script, style, noscript, iframe, nav, footer, [role='navigation'], [role='banner'], [role='contentinfo']"
    ):
        tag.decompose()


def _extract_text_content(soup: BeautifulSoup) -> str:
    main = soup.select_one("main, article, [role='main'], .content, #content, .main, #main")
    root = main if main is not None else soup.body
    if root is None:
        return ""

    lines: list[str] = []
    for el in root.select("h1,h2,h3,h4,h5,h6,p,li,td,th,blockquote,pre,dd,dt"):
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        tag = (el.name or "").lower()
        if tag.startswith("h"):
            lines.append(f"\n## {text}\n")
        elif tag == "li":
            lines.append(f"• {text}")
        else:
            lines.append(text)

    if not lines:
        text = root.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return ""
        parts = [p.strip() for p in re.split(r"\.\s+", text) if p.strip()]
        return ".\n".join(parts)

    joined = "\n".join(lines)
    joined = re.sub(r"\n{3,}", "\n\n", joined).strip()
    return joined


def _log_page_file_list(page_url: str, title: str, attachments: list[dict], links: list[str]) -> None:
    names: list[str] = []
    seen: set[str] = set()
    for row in attachments:
        name = (row.get("filename") or "").strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    for href in links:
        name = _filename_from_url(href)
        if name and name != "unnamed" and name not in seen:
            seen.add(name)
            names.append(name)
    applog.list_files(url=page_url, title=title, files=names, count=len(names))


async def fetch_page_rendered(browser: Browser, url: str) -> dict:
    ctx = await browser.new_context(user_agent=USER_AGENT, locale="ru-RU", ignore_https_errors=True)
    page: Page = await ctx.new_page()
    try:
        try:
            await page.goto(url, wait_until="load", timeout=settings.page_timeout_ms)
        except Exception as exc:
            if type(exc).__name__ == "TimeoutError":
                raise TimeoutError("Сайт не ответил за 30 секунд. Страница с этого компьютера не открывается.") from exc
            raise
        html = await page.content()
        title = (await page.title()) or "Untitled"
        cookies = await ctx.cookies()
        attachment_links = extract_attachment_links(html, url)
        attachments = await _fetch_attachments_playwright(page, attachment_links, page_url=url)
        _log_page_file_list(url, title, attachments, attachment_links)
    finally:
        await ctx.close()

    soup = BeautifulSoup(html, "lxml")
    _strip_non_content(soup)
    extracted_title = (soup.title.get_text(strip=True) if soup.title else "").strip()
    if extracted_title:
        title = extracted_title
    content = _extract_text_content(soup)

    return {
        "content": content,
        "title": title,
        "html": html,
        "cookies": cookies,
        "attachments": attachments,
        "attachment_links": attachment_links,
    }


def _path_is_document(raw: str) -> bool:
    path = urlparse(raw).path.lower()
    return any(path.endswith(ext) for ext in DOCUMENT_ATTACHMENT_EXTENSIONS)


def _href_is_document(raw: str) -> bool:
    parsed = urlparse(raw)
    path = (parsed.path or "").lower()
    query = (parsed.query or "").lower()
    if any(path.endswith(ext) for ext in DOCUMENT_ATTACHMENT_EXTENSIONS):
        return True
    if any(ext.strip(".") in query.split("&") or ext in query for ext in DOCUMENT_ATTACHMENT_EXTENSIONS):
        return True
    if "action=download" in query:
        return True
    stripped = path.rstrip("/")
    if stripped.endswith("/download") or "/download/" in path:
        return True
    return False


def _keep_downloaded_file(content_type: str | None, filename: str) -> bool:
    ct = (content_type or "").lower().split(";")[0].strip()
    if ct.startswith("text/html"):
        return False
    name = (filename or "").lower()
    if any(name.endswith(ext) for ext in DOCUMENT_ATTACHMENT_EXTENSIONS):
        return True
    prefixes = (
        "application/pdf",
        "application/msword",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument",
        "application/vnd.oasis.opendocument",
        "application/zip",
        "application/x-zip",
        "application/x-rar",
        "application/x-7z-compressed",
        "application/gzip",
        "application/octet-stream",
        "application/rtf",
        "text/csv",
        "text/plain",
        "text/rtf",
    )
    return any(ct == p or ct.startswith(p) for p in prefixes)


def extract_attachment_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    seen: set[str] = set()

    preferred = soup.select("a.display-files__link[href]")
    anchors = preferred or soup.select("a[href]")
    for a in anchors:
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        if not _href_is_document(href):
            continue
        try:
            abs_url = urljoin(base_url, href)
        except Exception:
            continue
        if abs_url in seen:
            continue
        seen.add(abs_url)
        links.append(abs_url)

    return links


def _guess_content_type(filename: str) -> str:
    lower = (filename or "").lower()
    mapping = (
        (".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        (".doc", "application/msword"),
        (".pdf", "application/pdf"),
        (".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        (".xls", "application/vnd.ms-excel"),
        (".pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        (".ppt", "application/vnd.ms-powerpoint"),
        (".zip", "application/zip"),
        (".csv", "text/csv"),
        (".txt", "text/plain"),
        (".rtf", "application/rtf"),
    )
    for ext, content_type in mapping:
        if lower.endswith(ext):
            return content_type
    return "application/octet-stream"


async def _locator_for_url(page: Page, target: str):
    parsed = urlparse(target)
    candidates = [target]
    path = parsed.path or ""
    if parsed.query:
        candidates.append(f"{path}?{parsed.query}")
    if path:
        candidates.append(path)
    for href in candidates:
        loc = page.locator(f'a[href="{href}"]').first
        if await loc.count():
            return loc
    leaf = path.rstrip("/").split("/")[-1]
    if leaf:
        loc = page.locator(f'a[href*="{leaf}"]').first
        if await loc.count():
            return loc
    return None


def _preview_text(content: bytes, content_type: str | None, limit: int = 200) -> str | None:
    ct = (content_type or "").lower()
    if not content:
        return ""
    if any(token in ct for token in ("octet-stream", "zip", "pdf", "image/", "audio/", "video/", "msword", "officedocument")):
        return None
    if not (ct.startswith("text/") or "json" in ct or "xml" in ct or "html" in ct or not ct):
        return None
    try:
        text = content[: limit * 4].decode("utf-8", errors="replace")
    except Exception:
        return None
    return text[:limit]


def _file_error(
    *,
    page_url: str,
    file_url: str | None,
    filename: str | None,
    stage: str,
    exc: BaseException | None = None,
    error: str | None = None,
    duration_ms: int | None = None,
    **extra,
) -> None:
    applog.error(
        "file_download",
        url=page_url,
        fileUrl=file_url,
        filename=filename,
        stage=stage,
        timeoutMs=settings.attachment_timeout_ms,
        durationMs=duration_ms,
        exc=exc,
        error=error if exc is None else None,
        **extra,
    )


async def _click_download_one(page: Page, loc, fallback_url: str, *, page_url: str) -> dict | None:
    started = time.perf_counter()
    stage = "resolve_href"
    link_title = ""
    link_ext = ""
    target = fallback_url
    filename = _filename_from_url(fallback_url) if fallback_url else None
    try:
        try:
            link_title = (await loc.locator("p").first.inner_text()).strip()
        except Exception:
            pass
        try:
            link_ext = (await loc.locator("span.uppercase").first.inner_text()).strip().lower()
        except Exception:
            pass
        href = (await loc.get_attribute("href")) or fallback_url
        try:
            target = urljoin(page.url, href) if href else fallback_url
        except Exception:
            target = fallback_url or href
        filename = _filename_from_url(target) if target else filename

        stage = "scroll"
        await loc.scroll_into_view_if_needed()
        stage = "click"
        async with page.expect_download(timeout=settings.attachment_timeout_ms) as pending:
            stage = "expect_download"
            await loc.click()
        download = await pending.value
        suggested = download.suggested_filename or _filename_from_url(target)
        filename = suggested
        if link_title:
            suffix = (link_ext or Path(suggested).suffix.lstrip(".") or "bin").lstrip(".")
            filename = f"{link_title}.{suffix}"
        fd, tmp_name = tempfile.mkstemp()
        os.close(fd)
        tmp = Path(tmp_name)
        stage = "save_as"
        await download.save_as(str(tmp))
        stage = "read"
        body = tmp.read_bytes()
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        content_type = _guess_content_type(filename)
        duration_ms = int((time.perf_counter() - started) * 1000)
        if not _keep_downloaded_file(content_type, filename):
            return None
        applog.success(
            "file_download",
            url=page_url,
            fileUrl=target,
            filename=filename,
            contentType=content_type,
            size=len(body),
            durationMs=duration_ms,
            stage="done",
        )
        return {
            "url": target,
            "filename": filename,
            "content_type": content_type,
            "size": len(body),
            "hash": hashlib.md5(body).hexdigest(),
            "bytes": body,
            "text_content": None,
        }
    except Exception as exc:
        _file_error(
            page_url=page_url,
            file_url=target,
            filename=filename,
            stage=stage,
            exc=exc,
            duration_ms=int((time.perf_counter() - started) * 1000),
            pageUrlAtClick=page.url,
        )
        return None


async def _fetch_attachments_playwright(page: Page, urls: list[str], *, page_url: str) -> list[dict]:
    locators = page.locator("a.display-files__link")
    count = await locators.count()
    if count == 0:
        locators = page.locator('a[href*="action=download"]')
        count = await locators.count()

    results: list[dict] = []
    seen: set[str] = set()

    if count > 0:
        for i in range(count):
            fallback = urls[i] if i < len(urls) else ""
            row = await _click_download_one(page, locators.nth(i), fallback, page_url=page_url)
            if not row or row["url"] in seen:
                continue
            seen.add(row["url"])
            results.append(row)
        return results

    for target in list(dict.fromkeys(urls)):
        loc = await _locator_for_url(page, target)
        if loc is None:
            _file_error(
                page_url=page_url,
                file_url=target,
                filename=_filename_from_url(target),
                stage="locator",
                error="No clickable link found for attachment URL",
            )
            continue
        row = await _click_download_one(page, loc, target, page_url=page_url)
        if not row or row["url"] in seen:
            continue
        seen.add(row["url"])
        results.append(row)
    return results


def _filename_from_url(url: str) -> str:
    try:
        path = urlparse(url).path
        name = unquote(path.split("/")[-1] or "") or "unnamed"
        return name
    except Exception:
        return "unnamed"


def _filename_from_response(url: str, headers) -> str:
    raw = headers.get("content-disposition") if headers is not None else None
    if raw:
        msg = EmailMessage()
        msg["content-disposition"] = raw
        name = msg.get_filename()
        if name:
            return name
        match = _FILENAME_RE.search(raw)
        if match:
            return unquote(match.group(1).strip())
    return _filename_from_url(url)


async def fetch_attachments(
    urls: Iterable[str],
    *,
    cookies: list[dict] | None = None,
    referer: str | None = None,
) -> list[dict]:
    url_list = list(dict.fromkeys(urls))
    page_url = referer or ""
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    if cookies:
        headers["Cookie"] = "; ".join(
            f"{c.get('name')}={c.get('value')}" for c in cookies if c.get("name")
        )
    timeout = httpx.Timeout(timeout=min(20.0, settings.attachment_timeout_ms / 1000.0))
    sem = asyncio.Semaphore(6)

    async def _one(client: httpx.AsyncClient, url: str) -> dict | None:
        async with sem:
            started = time.perf_counter()
            stage = "http_get"
            filename = _filename_from_url(url)
            content_type: str | None = None
            http_status: int | None = None
            try:
                r = await client.get(url)
                http_status = r.status_code
                content_type = r.headers.get("content-type") or "application/octet-stream"
                filename = _filename_from_response(url, r.headers)
                duration_ms = int((time.perf_counter() - started) * 1000)
                extra = {
                    "httpStatus": http_status,
                    "contentType": content_type,
                    "contentDisposition": r.headers.get("content-disposition"),
                    "finalUrl": str(r.url),
                    "size": len(r.content) if r.content is not None else 0,
                    "bodyPreview": _preview_text(r.content or b"", content_type),
                }
                if r.status_code < 200 or r.status_code >= 300:
                    _file_error(
                        page_url=page_url,
                        file_url=url,
                        filename=filename,
                        stage="status",
                        error=f"HTTP {r.status_code}",
                        duration_ms=duration_ms,
                        **extra,
                    )
                    return None
                if not _keep_downloaded_file(content_type, filename):
                    return None
                content = r.content
                text_content: Optional[str] = None
                if is_text_content_type(content_type):
                    try:
                        text_content = content.decode("utf-8")
                    except Exception:
                        text_content = content.decode("utf-8", errors="ignore")
                applog.success(
                    "file_download",
                    url=page_url,
                    fileUrl=url,
                    filename=filename,
                    contentType=content_type,
                    httpStatus=http_status,
                    size=len(content),
                    durationMs=duration_ms,
                    stage="done",
                )
                return {
                    "url": url,
                    "filename": filename,
                    "content_type": content_type,
                    "size": len(content),
                    "hash": hashlib.md5(content).hexdigest(),
                    "bytes": content,
                    "text_content": text_content,
                }
            except Exception as exc:
                _file_error(
                    page_url=page_url,
                    file_url=url,
                    filename=filename,
                    stage=stage,
                    exc=exc,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    httpStatus=http_status,
                    contentType=content_type,
                )
                return None

    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
        rows = await asyncio.gather(*[_one(client, u) for u in url_list])
    return [row for row in rows if row]


def sanitize_storage_filename(name: str) -> str:
    name = (name or "").replace("\n", " ").replace("\r", " ").strip()
    name = re.sub(r'[/\\:*?"<>|\x00-\x1f]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    encoded = name.encode("utf-8")
    if len(encoded) > 180:
        stem, dot, ext = name.rpartition(".")
        if not stem:
            stem, ext, dot = name, "", ""
        while stem and len(f"{stem}{dot}{ext}".encode("utf-8")) > 180:
            stem = stem[:-1]
        name = f"{stem}{dot}{ext}".strip(" .")
    return name or "file"

