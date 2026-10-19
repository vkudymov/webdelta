from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Browser, Page

from .config import settings
from .diffing import is_text_content_type


ATTACHMENT_EXTENSIONS = [
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
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".svg",
    ".webp",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    ".csv",
    ".json",
    ".xml",
]

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


async def fetch_page_rendered(browser: Browser, url: str) -> dict:
    ctx = await browser.new_context(user_agent=USER_AGENT, locale="ru-RU")
    page: Page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=settings.page_timeout_ms)
        html = await page.content()
        title = (await page.title()) or "Untitled"
    finally:
        await ctx.close()

    soup = BeautifulSoup(html, "lxml")
    _strip_non_content(soup)
    extracted_title = (soup.title.get_text(strip=True) if soup.title else "").strip()
    if extracted_title:
        title = extracted_title
    content = _extract_text_content(soup)

    return {"content": content, "title": title, "html": html}


def extract_attachment_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links: set[str] = set()

    def add_abs(raw: str) -> None:
        try:
            abs_url = urljoin(base_url, raw)
            links.add(abs_url)
        except Exception:
            return

    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        lower = href.lower()
        if any(lower.endswith(ext) for ext in ATTACHMENT_EXTENSIONS):
            add_abs(href)

    for img in soup.select("img[src]"):
        src = (img.get("src") or "").strip()
        if not src or src.startswith("data:"):
            continue
        add_abs(src)

    return list(links)


def _filename_from_url(url: str) -> str:
    try:
        path = urlparse(url).path
        name = path.split("/")[-1] or "unnamed"
        return name
    except Exception:
        return "unnamed"


async def fetch_attachments(urls: Iterable[str]) -> list[dict]:
    attachments: list[dict] = []
    timeout = httpx.Timeout(timeout=settings.attachment_timeout_ms / 1000.0)
    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for url in urls:
            try:
                r = await client.get(url)
                if r.status_code < 200 or r.status_code >= 300:
                    continue
                content = r.content
                md5 = hashlib.md5(content).hexdigest()
                content_type = r.headers.get("content-type") or "application/octet-stream"
                filename = _filename_from_url(url)

                text_content: Optional[str] = None
                if is_text_content_type(content_type):
                    try:
                        text_content = content.decode("utf-8")
                    except Exception:
                        text_content = content.decode("utf-8", errors="ignore")

                attachments.append(
                    {
                        "url": url,
                        "filename": filename,
                        "content_type": content_type,
                        "size": len(content),
                        "hash": md5,
                        "bytes": content,
                        "text_content": text_content,
                    }
                )
            except Exception:
                continue
    return attachments


def sanitize_storage_filename(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("_")
    return name or "file"

