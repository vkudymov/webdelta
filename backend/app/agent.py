from __future__ import annotations

import json
from typing import Any, Dict, Optional

from openai import AsyncOpenAI

from .config import settings


def _truncate(s: str, max_len: int) -> str:
    s = s or ""
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _compact_comparison(comparison: Dict[str, Any]) -> Dict[str, Any]:
    text_diff = comparison.get("textDiff") or {}
    changes = list(text_diff.get("changes") or [])

    compact_changes = []
    for c in changes[:80]:
        compact_changes.append(
            {
                "type": c.get("type"),
                "lineNumber": c.get("lineNumber"),
                "original": _truncate(c.get("original") or "", 200) if c.get("original") is not None else None,
                "current": _truncate(c.get("current") or "", 200) if c.get("current") is not None else None,
            }
        )

    attachment_diffs = comparison.get("attachmentDiffs") or {}
    def _compact_list(key: str, limit: int = 15):
        items = list(attachment_diffs.get(key) or [])
        return [
            {"url": _truncate(i.get("url") or "", 200), "filename": _truncate(i.get("filename") or "", 120)}
            for i in items[:limit]
        ]

    return {
        "url": comparison.get("url"),
        "savedTitle": _truncate(comparison.get("savedTitle") or "", 200) or None,
        "currentTitle": _truncate(comparison.get("currentTitle") or "", 200) or None,
        "savedAt": comparison.get("savedAt"),
        "summary": comparison.get("summary") or {},
        "textChangesSample": compact_changes,
        "attachments": {
            "added": _compact_list("added"),
            "removed": _compact_list("removed"),
            "modified": _compact_list("modified"),
        },
        "note": "textChangesSample is truncated to first 80 changes; attachments lists truncated to first 15 items each.",
    }


def build_explainer() -> Optional[callable]:
    if not settings.openai_api_key:
        return None

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def explain_delta(comparison: Dict[str, Any], locale: str = "ru") -> Optional[str]:
        compact = _compact_comparison(comparison)
        lang = "Russian" if locale == "ru" else "English"

        system = (
            f"You are a concise assistant. Write in {lang}. "
            "Explain the changes between the saved and current versions of the webpage. "
            "Be factual, short, and avoid speculation. "
            "Use 3-7 bullet points. If there are no changes, say so in one short sentence."
        )

        user = "Here is the diff payload (JSON):\n" + json.dumps(compact, ensure_ascii=False)

        resp = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=250,
        )
        text = (resp.choices[0].message.content or "").strip()
        return text or None

    return explain_delta

