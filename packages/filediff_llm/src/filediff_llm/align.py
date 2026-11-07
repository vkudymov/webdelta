from __future__ import annotations

import json
import time
from difflib import SequenceMatcher

from .provider import OpenAICompatibleProvider
from .usage import UsageStore

_WINDOW = 16
_OVERLAP = 3
_BLOCK_CHARS = 1200

_SYSTEM = """You align fragments of two versions of one document.
Match a fragment to its counterpart by content and meaning, not by position.
If new text was inserted above, the original fragment still matches the same text further down.
relation must be one of:
- same: the obligation and facts are the same, even if the wording changed
- changed: a number, date, name, term, or duty differs
- left_only: this left fragment has no counterpart
- right_only: this right fragment has no counterpart
Return JSON only, no markdown:
{"pairs":[{"leftId":"L1 or null","rightId":"R1 or null","relation":"same","note":"one short sentence"}]}
Every listed left id and right id must appear exactly once. Do not output context ids."""


def split_blocks(text: str, prefix: str) -> list[dict]:
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    blocks = []
    number = 0
    for part in raw.split("\n"):
        part = part.strip()
        if not part:
            continue
        number += 1
        blocks.append(
            {
                "id": f"{prefix}{number}",
                "text": part,
                "norm": " ".join(part.casefold().split()),
            }
        )
    return blocks


def _pair(left: dict | None, right: dict | None, relation: str, note: str = "") -> dict:
    return {
        "leftId": left["id"] if left else None,
        "rightId": right["id"] if right else None,
        "left": left["text"] if left else "",
        "right": right["text"] if right else "",
        "relation": relation,
        "note": note,
    }


def _exact_jobs(left_blocks: list[dict], right_blocks: list[dict]) -> tuple[int, list[tuple[list[dict], list[dict]]]]:
    """Pair identical paragraphs regardless of position. Return jobs that still need the model."""
    matcher = SequenceMatcher(
        a=[block["norm"] for block in left_blocks],
        b=[block["norm"] for block in right_blocks],
        autojunk=False,
    )
    exact = 0
    pending: list[tuple[str, list[dict], list[dict]]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            exact += i2 - i1
            continue
        pending.append((tag, left_blocks[i1:i2], right_blocks[j1:j2]))

    jobs: list[tuple[list[dict], list[dict]]] = []
    left_buf: list[dict] = []
    right_buf: list[dict] = []
    for _tag, left_part, right_part in pending:
        left_buf.extend(left_part)
        right_buf.extend(right_part)
        if left_buf and right_buf:
            jobs.append((left_buf, right_buf))
            left_buf = []
            right_buf = []
    if left_buf or right_buf:
        jobs.append((left_buf, right_buf))
    return exact, jobs


def _windows(blocks: list[dict]) -> list[tuple[list[dict], set[str]]]:
    if len(blocks) <= _WINDOW:
        return [(blocks, {block["id"] for block in blocks})]
    spans = []
    start = 0
    while start < len(blocks):
        end = min(len(blocks), start + _WINDOW)
        core_from = start if start == 0 else start + _OVERLAP
        core = {block["id"] for block in blocks[core_from:end]}
        spans.append((blocks[start:end], core))
        if end == len(blocks):
            break
        start = end - _OVERLAP
    return spans


def _clip(text: str) -> str:
    if len(text) <= _BLOCK_CHARS:
        return text
    return text[: _BLOCK_CHARS - 1] + "…"


def _prompt(filename: str, left_blocks: list[dict], right_blocks: list[dict], locale: str) -> str:
    lang = "Russian" if locale == "ru" else "English"

    def lines(blocks: list[dict]) -> str:
        if not blocks:
            return "(none)"
        return "\n".join(f"{block['id']}: {_clip(block['text'])}" for block in blocks)

    return (
        f"Write notes in {lang}. File: {filename}\n\n"
        f"LEFT\n{lines(left_blocks)}\n\nRIGHT\n{lines(right_blocks)}"
    )


def _parse_pairs(raw: str) -> list[dict]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("model did not return JSON")
    payload = json.loads(text[start : end + 1])
    pairs = payload.get("pairs")
    if not isinstance(pairs, list):
        raise ValueError("model JSON has no pairs")
    return pairs


def _accepted(pair: dict, left_ids: set[str], right_ids: set[str]) -> dict | None:
    relation = str(pair.get("relation") or "").strip().lower()
    if relation not in {"same", "changed", "left_only", "right_only"}:
        return None
    left_id = pair.get("leftId") or None
    right_id = pair.get("rightId") or None
    if left_id is not None and left_id not in left_ids:
        left_id = None
    if right_id is not None and right_id not in right_ids:
        right_id = None
    if relation == "left_only":
        right_id = None
    elif relation == "right_only":
        left_id = None
    elif relation in {"same", "changed"} and (not left_id or not right_id):
        return None
    if not left_id and not right_id:
        return None
    note = str(pair.get("note") or "").strip()
    return {"leftId": left_id, "rightId": right_id, "relation": relation, "note": note[:300]}


async def _ask_window(
    provider: OpenAICompatibleProvider,
    filename: str,
    left_blocks: list[dict],
    right_blocks: list[dict],
    locale: str,
    usage: UsageStore | None,
) -> list[dict]:
    started = time.perf_counter()
    error = None
    stats = {"promptTokens": 0, "completionTokens": 0}
    parsed: list[dict] = []
    try:
        raw, stats = await provider.complete_json(
            _SYSTEM,
            _prompt(filename, left_blocks, right_blocks, locale),
        )
        parsed = _parse_pairs(raw)
    except Exception as exc:
        error = str(exc)[:300]
        raise
    finally:
        if usage is not None:
            usage.record(
                {
                    "timestamp": int(time.time() * 1000),
                    "provider": "openai-compatible",
                    "baseUrl": provider.base_url,
                    "model": provider.model,
                    "filename": filename,
                    "promptTokens": stats["promptTokens"],
                    "completionTokens": stats["completionTokens"],
                    "latencyMs": int((time.perf_counter() - started) * 1000),
                    "ok": error is None,
                    "error": error,
                }
            )
    return parsed


async def align_and_compare(
    left_text: str,
    right_text: str,
    filename: str,
    *,
    provider: OpenAICompatibleProvider,
    usage: UsageStore | None = None,
    locale: str = "ru",
) -> dict:
    """Return pairs aligned by content. Identical paragraphs are not sent to the model."""
    left_blocks = split_blocks(left_text, "L")
    right_blocks = split_blocks(right_text, "R")
    by_left = {block["id"]: block for block in left_blocks}
    by_right = {block["id"]: block for block in right_blocks}
    exact_count, jobs = _exact_jobs(left_blocks, right_blocks)

    resolved: dict[str, dict] = {}
    for left_part, right_part in jobs:
        if not left_part:
            for block in right_part:
                resolved[f"R:{block['id']}"] = _pair(None, block, "right_only")
            continue
        if not right_part:
            for block in left_part:
                resolved[f"L:{block['id']}"] = _pair(block, None, "left_only")
            continue

        left_windows = _windows(left_part)
        right_windows = _windows(right_part)
        total = max(len(left_windows), len(right_windows))
        for index in range(total):
            left_window, left_core = left_windows[min(index, len(left_windows) - 1)]
            right_window, right_core = right_windows[min(index, len(right_windows) - 1)]
            if index >= len(left_windows):
                left_core = set()
            if index >= len(right_windows):
                right_core = set()
            raw_pairs = await _ask_window(provider, filename, left_window, right_window, locale, usage)
            accepted = []
            for item in raw_pairs:
                pair = _accepted(item, {block["id"] for block in left_window}, {block["id"] for block in right_window})
                if pair is None:
                    continue
                if pair["leftId"] and pair["leftId"] not in left_core and pair["relation"] != "right_only":
                    continue
                if pair["rightId"] and pair["rightId"] not in right_core and pair["relation"] != "left_only":
                    continue
                accepted.append(pair)
            seen_left = {pair["leftId"] for pair in accepted if pair["leftId"]}
            seen_right = {pair["rightId"] for pair in accepted if pair["rightId"]}
            for pair in accepted:
                key = f"L:{pair['leftId']}" if pair["leftId"] else f"R:{pair['rightId']}"
                resolved[key] = _pair(
                    by_left.get(pair["leftId"]) if pair["leftId"] else None,
                    by_right.get(pair["rightId"]) if pair["rightId"] else None,
                    pair["relation"],
                    pair["note"],
                )
            for block in left_window:
                if block["id"] in left_core and block["id"] not in seen_left:
                    resolved[f"L:{block['id']}"] = _pair(block, None, "left_only")
            for block in right_window:
                if block["id"] in right_core and block["id"] not in seen_right:
                    resolved[f"R:{block['id']}"] = _pair(None, block, "right_only")

    pairs = list(resolved.values())
    same_meaning = sum(1 for pair in pairs if pair["relation"] == "same")
    material = [pair for pair in pairs if pair["relation"] != "same"]
    same_total = exact_count + same_meaning
    changed = sum(1 for pair in material if pair["relation"] == "changed")
    left_only = sum(1 for pair in material if pair["relation"] == "left_only")
    right_only = sum(1 for pair in material if pair["relation"] == "right_only")
    return {
        "summary": _summary(same_total, material, locale),
        "sameCount": same_total,
        "stats": {
            "sameCount": same_total,
            "changedCount": changed,
            "leftOnlyCount": left_only,
            "rightOnlyCount": right_only,
        },
        "pairs": material + [pair for pair in pairs if pair["relation"] == "same"],
        "material": bool(material),
    }


def _summary(same_count: int, material: list[dict], locale: str) -> str:
    changed = sum(1 for pair in material if pair["relation"] == "changed")
    left_only = sum(1 for pair in material if pair["relation"] == "left_only")
    right_only = sum(1 for pair in material if pair["relation"] == "right_only")
    if locale == "ru":
        if not material:
            return f"Смысл фрагментов совпадает ({same_count})."
        return (
            f"Тот же смысл: {same_count}. Изменён смысл: {changed}. "
            f"Только слева: {left_only}. Только справа: {right_only}."
        )
    if not material:
        return f"Fragment meaning matches ({same_count})."
    return (
        f"Same meaning: {same_count}. Meaning changed: {changed}. "
        f"Left only: {left_only}. Right only: {right_only}."
    )
