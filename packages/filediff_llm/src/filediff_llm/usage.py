from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol


class UsageStore(Protocol):
    def record(self, event: dict) -> None: ...


class JsonlUsageStore:
    """Append-only usage ledger. Swap this for a paid billing store later."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def record(self, event: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
