from __future__ import annotations

import io
from pathlib import Path


def extract_document_text(data: bytes | None, filename: str) -> tuple[str | None, str | None]:
    """Return (text, error).

    text is None and error is None when the type has no text extractor (compare by hash only).
    """
    if data is None:
        return None, "file not found"
    ext = Path(filename or "").suffix.lower()
    try:
        if ext in {".txt", ".csv", ".rtf"}:
            return data.decode("utf-8", errors="replace"), None
        if ext == ".docx":
            return _docx_text(data), None
        if ext == ".xlsx":
            return _xlsx_text(data), None
        if ext == ".pdf":
            return _pdf_text(data), None
    except Exception as exc:
        return None, str(exc)[:300]
    return None, None


def _docx_text(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    lines: list[str] = []
    for paragraph in doc.paragraphs:
        text = (paragraph.text or "").strip()
        if text:
            lines.append(text)
    for table in doc.tables:
        for row in table.rows:
            cells = [(cell.text or "").strip() for cell in row.cells]
            if any(cells):
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def _xlsx_text(data: bytes) -> str:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    try:
        lines: list[str] = []
        for sheet in workbook.worksheets:
            lines.append(f"# {sheet.title}")
            for row in sheet.iter_rows(values_only=True):
                values = ["" if value is None else str(value) for value in row]
                if any(value.strip() for value in values):
                    lines.append("\t".join(values))
        return "\n".join(lines)
    finally:
        workbook.close()


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n".join(part for part in parts if part)
