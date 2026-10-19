from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

from supabase import Client, create_client

from .config import settings


class StorageError(RuntimeError):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_supabase() -> Optional[Client]:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


class Repo:
    async def init(self) -> None: ...

    async def get_page_by_url(self, url: str) -> Optional[dict]: ...

    async def get_page_by_id(self, page_id: Any) -> Optional[dict]: ...

    async def count_attachments(self, page_id: Any) -> int: ...

    async def list_pages(self) -> list[dict]: ...

    async def insert_page(self, url: str, content: str, title: str | None) -> Any: ...

    async def update_page(self, page_id: Any, content: str, title: str | None) -> None: ...

    async def delete_page(self, page_id: Any) -> bool: ...

    async def delete_attachments(self, page_id: Any) -> None: ...

    async def insert_attachments(self, page_id: Any, attachments: list[dict]) -> None: ...

    async def list_attachments(self, page_id: Any) -> list[dict]: ...

    async def store_binary_attachment(self, page_id: Any, att: dict) -> str: ...


class SqliteRepo(Repo):
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    async def init(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pages (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  url TEXT UNIQUE NOT NULL,
                  content TEXT NOT NULL,
                  title TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS attachments (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  page_id INTEGER NOT NULL,
                  url TEXT NOT NULL,
                  filename TEXT NOT NULL,
                  content_type TEXT,
                  size INTEGER,
                  hash TEXT,
                  text_content TEXT,
                  storage_path TEXT,
                  created_at TEXT NOT NULL,
                  UNIQUE(page_id, url)
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_attachments_page_id ON attachments(page_id);")

    async def get_page_by_url(self, url: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM pages WHERE url = ?", (url,)).fetchone()
            return dict(row) if row else None

    async def get_page_by_id(self, page_id: Any) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
            return dict(row) if row else None

    async def count_attachments(self, page_id: Any) -> int:
        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM attachments WHERE page_id = ?", (page_id,)).fetchone()
            return int(row["c"]) if row else 0

    async def list_pages(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT p.*,
                       (SELECT COUNT(*) FROM attachments a WHERE a.page_id = p.id) AS attachment_count
                FROM pages p
                ORDER BY updated_at DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    async def insert_page(self, url: str, content: str, title: str | None) -> Any:
        now = _utc_now_iso()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO pages(url, content, title, created_at, updated_at) VALUES(?,?,?,?,?)",
                (url, content, title, now, now),
            )
            return cur.lastrowid

    async def update_page(self, page_id: Any, content: str, title: str | None) -> None:
        now = _utc_now_iso()
        with self._conn() as conn:
            conn.execute(
                "UPDATE pages SET content = ?, title = ?, updated_at = ? WHERE id = ?",
                (content, title, now, page_id),
            )

    async def delete_page(self, page_id: Any) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM pages WHERE id = ?", (page_id,))
            return cur.rowcount > 0

    async def delete_attachments(self, page_id: Any) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM attachments WHERE page_id = ?", (page_id,))

    async def insert_attachments(self, page_id: Any, attachments: list[dict]) -> None:
        now = _utc_now_iso()
        with self._conn() as conn:
            for a in attachments:
                conn.execute(
                    """
                    INSERT INTO attachments(page_id, url, filename, content_type, size, hash, text_content, storage_path, created_at)
                    VALUES(?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        page_id,
                        a.get("url"),
                        a.get("filename"),
                        a.get("content_type"),
                        a.get("size"),
                        a.get("hash"),
                        a.get("text_content"),
                        a.get("storage_path"),
                        now,
                    ),
                )

    async def list_attachments(self, page_id: Any) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM attachments WHERE page_id = ?", (page_id,)).fetchall()
            return [dict(r) for r in rows]

    async def store_binary_attachment(self, page_id: Any, att: dict) -> str:
        # For sqlite dev mode we don't persist bytes; keep only metadata.
        return att.get("storage_path") or ""


class SupabaseRepo(Repo):
    def __init__(self, client: Client):
        self.client = client

    async def init(self) -> None:
        # Supabase schema is managed separately (schema.sql).
        return None

    async def get_page_by_url(self, url: str) -> Optional[dict]:
        res = self.client.table("pages").select("*").eq("url", url).limit(1).execute()
        data = getattr(res, "data", None) or []
        return data[0] if data else None

    async def get_page_by_id(self, page_id: Any) -> Optional[dict]:
        res = self.client.table("pages").select("*").eq("id", page_id).limit(1).execute()
        data = getattr(res, "data", None) or []
        return data[0] if data else None

    async def count_attachments(self, page_id: Any) -> int:
        res = self.client.table("attachments").select("id", count="exact").eq("page_id", page_id).execute()
        count = getattr(res, "count", None)
        return int(count or 0)

    async def list_pages(self) -> list[dict]:
        res = self.client.table("pages").select("*").order("updated_at", desc=True).execute()
        pages = getattr(res, "data", None) or []
        # Attachment counts: keep simple (N+1); still ok for small datasets.
        for p in pages:
            p["attachment_count"] = await self.count_attachments(p["id"])
        return pages

    async def insert_page(self, url: str, content: str, title: str | None) -> Any:
        payload = {"url": url, "content": content, "title": title}
        res = self.client.table("pages").insert(payload).execute()
        data = getattr(res, "data", None) or []
        if not data:
            raise StorageError("Failed to insert page")
        return data[0]["id"]

    async def update_page(self, page_id: Any, content: str, title: str | None) -> None:
        payload = {"content": content, "title": title, "updated_at": datetime.now(timezone.utc).isoformat()}
        self.client.table("pages").update(payload).eq("id", page_id).execute()

    async def delete_page(self, page_id: Any) -> bool:
        res = self.client.table("pages").delete().eq("id", page_id).execute()
        data = getattr(res, "data", None)
        return bool(data)

    async def delete_attachments(self, page_id: Any) -> None:
        self.client.table("attachments").delete().eq("page_id", page_id).execute()

    async def insert_attachments(self, page_id: Any, attachments: list[dict]) -> None:
        if not attachments:
            return
        payload = []
        for a in attachments:
            payload.append(
                {
                    "page_id": page_id,
                    "url": a.get("url"),
                    "filename": a.get("filename"),
                    "content_type": a.get("content_type"),
                    "size": a.get("size"),
                    "hash": a.get("hash"),
                    "text_content": a.get("text_content"),
                    "storage_path": a.get("storage_path"),
                }
            )
        self.client.table("attachments").insert(payload).execute()

    async def list_attachments(self, page_id: Any) -> list[dict]:
        res = self.client.table("attachments").select("*").eq("page_id", page_id).execute()
        return getattr(res, "data", None) or []

    async def store_binary_attachment(self, page_id: Any, att: dict) -> str:
        bucket = self.client.storage.from_(settings.supabase_attachments_bucket)
        filename = att.get("filename") or "file"
        h = att.get("hash") or "hash"
        # avoid collisions
        path = f"{page_id}/{h}_{filename}"
        content_type = att.get("content_type") or "application/octet-stream"
        data = att.get("bytes") or b""
        # supabase-py accepts bytes directly
        bucket.upload(path, data, file_options={"content-type": content_type, "upsert": "true"})
        return path


async def get_repo() -> Repo:
    if settings.storage_backend.lower() == "sqlite":
        repo: Repo = SqliteRepo(settings.sqlite_path)
        await repo.init()
        return repo

    sb = create_supabase()
    if sb is None:
        # Dev-friendly fallback if keys are not provided.
        repo = SqliteRepo(settings.sqlite_path)
        await repo.init()
        return repo
    repo = SupabaseRepo(sb)
    await repo.init()
    return repo

