from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error: str


class CheckResponse(BaseModel):
    exists: bool
    page: dict[str, Any] | None = None


class DownloadRequest(BaseModel):
    url: str
    overwrite: bool = False


class CompareRequest(BaseModel):
    url: str
    locale: Literal["ru", "en"] = "ru"
    snapshotId: int | str | None = None


class DownloadResponse(BaseModel):
    success: bool = True
    message: str
    pageId: int | str
    snapshotId: int | str | None = None
    attachmentCount: int = 0


class TextDiffChange(BaseModel):
    type: Literal["added", "removed", "modified"]
    lineNumber: int
    original: str | None
    current: str | None


class TextDiffStats(BaseModel):
    additions: int = 0
    deletions: int = 0
    modifications: int = 0
    totalLines: int = 0
    changedLines: int = 0


class TextDiff(BaseModel):
    hasChanges: bool
    changes: list[TextDiffChange]
    stats: TextDiffStats


class AttachmentSummary(BaseModel):
    url: str
    filename: str
    contentType: str | None = None
    size: int | None = None


class AttachmentModified(BaseModel):
    url: str
    filename: str
    contentType: str | None = None
    oldSize: int | None = None
    newSize: int | None = None
    oldHash: str | None = None
    newHash: str | None = None
    textDiff: TextDiff | None = None


class AttachmentDiffs(BaseModel):
    added: list[AttachmentSummary] = Field(default_factory=list)
    removed: list[AttachmentSummary] = Field(default_factory=list)
    modified: list[AttachmentModified] = Field(default_factory=list)
    unchanged: list[AttachmentSummary] = Field(default_factory=list)


class ComparisonSummary(BaseModel):
    textChanged: bool
    attachmentsAdded: int = 0
    attachmentsRemoved: int = 0
    attachmentsModified: int = 0
    attachmentsUnchanged: int = 0


class ComparisonPayload(BaseModel):
    url: str
    savedTitle: str | None = None
    currentTitle: str | None = None
    savedAt: datetime | str | None = None
    textDiff: TextDiff
    attachmentDiffs: AttachmentDiffs
    summary: ComparisonSummary
    explanation: str | None = None


class CompareResponse(BaseModel):
    success: bool = True
    comparison: ComparisonPayload


class PageListItem(BaseModel):
    id: int | str
    url: str
    title: str | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None
    attachment_count: int = 0


class ListResponse(BaseModel):
    pages: list[PageListItem]


class SnapshotListItem(BaseModel):
    id: int | str
    capturedAt: datetime | str | None = None
    title: str | None = None
    attachmentCount: int = 0


class SnapshotsResponse(BaseModel):
    url: str
    snapshots: list[SnapshotListItem] = Field(default_factory=list)

