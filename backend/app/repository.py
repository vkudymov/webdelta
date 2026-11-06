from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from supabase import Client, create_client
from postgrest.exceptions import APIError

from .config import settings


class StorageError(RuntimeError):
    pass


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

    async def upsert_history(
        self,
        url: str,
        last_action: str,
        last_ok: bool,
        last_error: str | None = None,
        title: str | None = None,
        page_id: Any = None,
        check_name: str | None = None,
    ) -> Any: ...

    async def list_history(self) -> list[dict]: ...

    async def get_history_by_id(self, history_id: Any) -> Optional[dict]: ...

    async def delete_history(self, history_id: Any) -> bool: ...

    async def insert_page(self, url: str, content: str, title: str | None, check_name: str | None = None) -> Any: ...

    async def update_page(self, page_id: Any, content: str, title: str | None, check_name: str | None = None) -> None: ...

    async def delete_page(self, page_id: Any) -> bool: ...

    async def insert_snapshot(self, page_id: Any, captured_at: str, content: str, title: str | None, local_path: str | None) -> Any: ...

    async def get_snapshot(self, snapshot_id: Any) -> Optional[dict]: ...

    async def list_snapshots(self, page_id: Any) -> list[dict]: ...

    async def get_latest_snapshot(self, page_id: Any) -> Optional[dict]: ...

    async def delete_snapshot(self, snapshot_id: Any) -> bool: ...

    async def delete_attachments(self, snapshot_id: Any) -> None: ...

    async def insert_attachments(self, snapshot_id: Any, attachments: list[dict]) -> None: ...

    async def list_attachments(self, snapshot_id: Any) -> list[dict]: ...

    async def store_binary_attachment(self, page_id: Any, snapshot_id: Any, att: dict) -> str: ...


class SupabaseRepo(Repo):
    def __init__(self, client: Client):
        self.client = client

    async def init(self) -> None:
        return None

    def _missing_history_table(self, exc: Exception) -> bool:
        text = str(exc)
        return "url_history" in text and ("PGRST205" in text or "schema cache" in text)

    def _missing_column_key(self, exc: Exception, payload: dict) -> str | None:
        text = str(exc)
        if "PGRST204" not in text:
            return None
        for key in payload:
            if f"'{key}' column" in text:
                return key
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
        snap = await self.get_latest_snapshot(page_id)
        if not snap:
            return 0
        res = self.client.table("attachments").select("id", count="exact").eq("snapshot_id", snap["id"]).execute()
        count = getattr(res, "count", None)
        return int(count or 0)

    async def list_pages(self) -> list[dict]:
        res = self.client.table("pages").select("*").order("updated_at", desc=True).execute()
        pages = getattr(res, "data", None) or []
        for p in pages:
            p["attachment_count"] = await self.count_attachments(p["id"])
        return pages

    async def upsert_history(
        self,
        url: str,
        last_action: str,
        last_ok: bool,
        last_error: str | None = None,
        title: str | None = None,
        page_id: Any = None,
        check_name: str | None = None,
    ) -> Any:
        now = datetime.now(timezone.utc).isoformat()
        try:
            existing = self.client.table("url_history").select("*").eq("url", url).limit(1).execute()
        except APIError as exc:
            if self._missing_history_table(exc):
                return None
            raise
        rows = getattr(existing, "data", None) or []
        if rows:
            current = rows[0]
            payload = {
                "last_action": last_action,
                "last_ok": last_ok,
                "last_error": last_error,
                "title": title if title is not None else current.get("title"),
                "page_id": page_id if page_id is not None else current.get("page_id"),
                "check_name": check_name if check_name is not None else current.get("check_name"),
                "updated_at": now,
            }
            try:
                res = self.client.table("url_history").update(payload).eq("url", url).execute()
            except APIError as exc:
                missing = self._missing_column_key(exc, payload)
                if not missing:
                    raise
                payload.pop(missing, None)
                res = self.client.table("url_history").update(payload).eq("url", url).execute()
            data = getattr(res, "data", None) or []
            return data[0]["id"] if data else current.get("id")
        payload = {
            "url": url,
            "title": title,
            "check_name": check_name,
            "last_action": last_action,
            "last_ok": last_ok,
            "last_error": last_error,
            "page_id": page_id,
            "created_at": now,
            "updated_at": now,
        }
        try:
            res = self.client.table("url_history").insert(payload).execute()
        except APIError as exc:
            missing = self._missing_column_key(exc, payload)
            if not missing:
                raise
            payload.pop(missing, None)
            res = self.client.table("url_history").insert(payload).execute()
        data = getattr(res, "data", None) or []
        if not data:
            raise StorageError("Failed to insert url_history")
        return data[0]["id"]

    async def list_history(self) -> list[dict]:
        try:
            res = self.client.table("url_history").select("*").order("updated_at", desc=True).execute()
        except APIError as exc:
            if self._missing_history_table(exc):
                return []
            raise
        rows = getattr(res, "data", None) or []
        for row in rows:
            page_id = row.get("page_id")
            row["attachment_count"] = await self.count_attachments(page_id) if page_id else 0
        return rows

    async def get_history_by_id(self, history_id: Any) -> Optional[dict]:
        try:
            res = self.client.table("url_history").select("*").eq("id", history_id).limit(1).execute()
        except APIError as exc:
            if self._missing_history_table(exc):
                return None
            raise
        data = getattr(res, "data", None) or []
        return data[0] if data else None

    async def delete_history(self, history_id: Any) -> bool:
        try:
            res = self.client.table("url_history").delete().eq("id", history_id).execute()
        except APIError as exc:
            if self._missing_history_table(exc):
                return False
            raise
        data = getattr(res, "data", None)
        return bool(data)

    async def insert_page(self, url: str, content: str, title: str | None, check_name: str | None = None) -> Any:
        payload = {"url": url, "content": content, "title": title}
        if check_name is not None:
            payload["check_name"] = check_name
        try:
            res = self.client.table("pages").insert(payload).execute()
        except APIError as exc:
            missing = self._missing_column_key(exc, payload)
            if not missing:
                raise
            payload.pop(missing, None)
            res = self.client.table("pages").insert(payload).execute()
        data = getattr(res, "data", None) or []
        if not data:
            raise StorageError("Failed to insert page")
        return data[0]["id"]

    async def update_page(self, page_id: Any, content: str, title: str | None, check_name: str | None = None) -> None:
        payload = {"content": content, "title": title, "updated_at": datetime.now(timezone.utc).isoformat()}
        if check_name is not None:
            payload["check_name"] = check_name
        try:
            self.client.table("pages").update(payload).eq("id", page_id).execute()
        except APIError as exc:
            missing = self._missing_column_key(exc, payload)
            if not missing:
                raise
            payload.pop(missing, None)
            self.client.table("pages").update(payload).eq("id", page_id).execute()

    async def delete_page(self, page_id: Any) -> bool:
        try:
            self.client.table("url_history").update({"page_id": None}).eq("page_id", page_id).execute()
        except APIError as exc:
            if not self._missing_history_table(exc):
                raise
        res = self.client.table("pages").delete().eq("id", page_id).execute()
        data = getattr(res, "data", None)
        return bool(data)

    async def insert_snapshot(self, page_id: Any, captured_at: str, content: str, title: str | None, local_path: str | None) -> Any:
        payload = {
            "page_id": page_id,
            "captured_at": captured_at,
            "content": content,
            "title": title,
            "local_path": local_path,
        }
        res = self.client.table("snapshots").insert(payload).execute()
        data = getattr(res, "data", None) or []
        if not data:
            raise StorageError("Failed to insert snapshot")
        return data[0]["id"]

    async def get_snapshot(self, snapshot_id: Any) -> Optional[dict]:
        res = self.client.table("snapshots").select("*").eq("id", snapshot_id).limit(1).execute()
        data = getattr(res, "data", None) or []
        return data[0] if data else None

    async def list_snapshots(self, page_id: Any) -> list[dict]:
        res = self.client.table("snapshots").select("*").eq("page_id", page_id).order("captured_at", desc=True).execute()
        snaps = getattr(res, "data", None) or []
        for s in snaps:
            a = self.client.table("attachments").select("id", count="exact").eq("snapshot_id", s["id"]).execute()
            s["attachment_count"] = int(getattr(a, "count", None) or 0)
        return snaps

    async def get_latest_snapshot(self, page_id: Any) -> Optional[dict]:
        res = (
            self.client.table("snapshots")
            .select("*")
            .eq("page_id", page_id)
            .order("captured_at", desc=True)
            .limit(1)
            .execute()
        )
        data = getattr(res, "data", None) or []
        return data[0] if data else None

    async def delete_snapshot(self, snapshot_id: Any) -> bool:
        await self.delete_attachments(snapshot_id)
        res = self.client.table("snapshots").delete().eq("id", snapshot_id).execute()
        return bool(getattr(res, "data", None))

    async def delete_attachments(self, snapshot_id: Any) -> None:
        self.client.table("attachments").delete().eq("snapshot_id", snapshot_id).execute()

    async def insert_attachments(self, snapshot_id: Any, attachments: list[dict]) -> None:
        if not attachments:
            return
        payload = []
        for a in attachments:
            payload.append(
                {
                    "snapshot_id": snapshot_id,
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

    async def list_attachments(self, snapshot_id: Any) -> list[dict]:
        res = self.client.table("attachments").select("*").eq("snapshot_id", snapshot_id).execute()
        return getattr(res, "data", None) or []

    async def store_binary_attachment(self, page_id: Any, snapshot_id: Any, att: dict) -> str:
        bucket = self.client.storage.from_(settings.supabase_attachments_bucket)
        filename = att.get("filename") or "file"
        h = att.get("hash") or "hash"
        path = f"{page_id}/{snapshot_id}/{h}_{filename}"
        content_type = att.get("content_type") or "application/octet-stream"
        data = att.get("bytes") or b""
        bucket.upload(path, data, file_options={"content-type": content_type, "upsert": "true"})
        return path


async def get_repo() -> Optional[Repo]:
    sb = create_supabase()
    if sb is None:
        return None
    try:
        sb.table("snapshots").select("id").limit(1).execute()
    except Exception:
        return None
    repo = SupabaseRepo(sb)
    await repo.init()
    return repo
