from __future__ import annotations

from .config import settings
from .document_text import extract_document_text
from .filediff_prompt import FILEDIFF_SYSTEM_PROMPT
from .results_store import read_attachment_bytes

_FILE_LIMIT = 12


def _filename(att: dict) -> str:
    raw = str(att.get("filename") or "unnamed").replace("\\", "/").split("/")[-1].strip()
    return raw or "unnamed"


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


def _find(attachments: list[dict], filename: str) -> dict | None:
    target = filename.casefold()
    for att in attachments:
        if _filename(att).casefold() == target:
            return att
    return None


async def filediff_status() -> dict:
    model = (settings.filediff_model or "").strip() or None
    try:
        from filediff_llm import list_models
    except ImportError:
        return {"available": False, "models": [], "defaultModel": model, "reason": "package"}
    try:
        models = await list_models(settings.filediff_base_url, settings.filediff_api_key or "lm-studio")
    except Exception as exc:
        return {"available": False, "models": [], "defaultModel": model, "reason": str(exc)[:200]}
    default = model if model in models else (models[0] if models else None)
    return {"available": bool(models), "models": models, "defaultModel": default, "reason": None}


async def apply_semantic_compare(
    comparison: dict,
    *,
    url: str,
    left: dict,
    right: dict,
    check_name: str | None,
    model: str | None,
    locale: str,
) -> dict:
    """Replace positional file diffs with meaning alignment. Hash result stays if the model is unavailable."""
    summary = comparison.setdefault("summary", {})
    summary["compareEngine"] = "llm"
    diffs = comparison.setdefault("attachmentDiffs", {})
    modified = list(diffs.get("modified") or [])
    unchanged = list(diffs.get("unchanged") or [])

    try:
        from filediff_llm import JsonlUsageStore, OpenAICompatibleProvider, align_and_compare
    except ImportError:
        comparison["filediffError"] = "filediff-llm is not installed"
        return comparison

    chosen = (model or settings.filediff_model or "").strip()
    if not chosen:
        comparison["filediffError"] = "FILEDIFF_MODEL is empty and no model was selected"
        return comparison

    provider = OpenAICompatibleProvider(
        base_url=settings.filediff_base_url,
        api_key=settings.filediff_api_key or "lm-studio",
        model=chosen,
    )
    usage = JsonlUsageStore(settings.filediff_usage_path)
    left_path = left.get("localPath") or left.get("local_path")
    right_path = right.get("localPath") or right.get("local_path")
    left_attachments = list(left.get("attachments") or [])
    right_attachments = list(right.get("attachments") or [])

    kept: list[dict] = []
    for index, row in enumerate(modified):
        filename = row.get("filename") or "unnamed"
        if index >= _FILE_LIMIT:
            row["semanticError"] = "file limit reached; hash diff kept"
            kept.append(row)
            continue
        left_att = _find(left_attachments, filename)
        right_att = _find(right_attachments, filename)
        if left_att is None or right_att is None:
            row["semanticError"] = "file bytes were not found for both versions"
            kept.append(row)
            continue
        left_bytes = _attachment_bytes(url, left_att, left_path, check_name)
        right_bytes = _attachment_bytes(url, right_att, right_path, check_name)
        left_text, left_error = extract_document_text(left_bytes, filename)
        right_text, right_error = extract_document_text(right_bytes, filename)
        if not left_text or not right_text:
            row["semanticError"] = "; ".join(item for item in (left_error, right_error) if item) or "no text"
            kept.append(row)
            continue
        try:
            semantic = await align_and_compare(
                left_text,
                right_text,
                filename,
                provider=provider,
                usage=usage,
                locale=locale or "ru",
                system_prompt=FILEDIFF_SYSTEM_PROMPT,
            )
        except Exception as exc:
            row["semanticError"] = str(exc)[:300]
            kept.append(row)
            continue
        row["semantic"] = {
            "summary": semantic["summary"],
            "sameCount": semantic["sameCount"],
            "stats": semantic.get("stats"),
            "pairs": [
                {
                    "left": pair["left"],
                    "right": pair["right"],
                    "relation": pair["relation"],
                    "note": pair["note"],
                }
                for pair in semantic["pairs"]
            ],
        }
        row["semanticError"] = None
        if semantic["material"]:
            row["textDiff"] = None
            kept.append(row)
            continue
        unchanged.append(
            {
                "url": row.get("url") or "",
                "filename": filename,
                "contentType": row.get("contentType"),
                "fileType": row.get("fileType"),
                "size": row.get("newSize") if row.get("newSize") is not None else row.get("oldSize"),
            }
        )

    diffs["modified"] = kept
    diffs["unchanged"] = unchanged
    summary["attachmentsModified"] = len(kept)
    summary["attachmentsUnchanged"] = len(unchanged)
    return comparison
