"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "../hooks/useTranslation";
import { apiFetch } from "../lib/api";

function statusLabel(page, t) {
  if (!page.lastOk) return t("statusError");
  if (page.lastAction === "compare") return t("statusCompared");
  return t("statusSaved");
}

function statusClass(page) {
  if (!page.lastOk) return "bg-red-100 text-red-700";
  if (page.lastAction === "compare") return "bg-indigo-100 text-indigo-700";
  return "bg-green-100 text-green-700";
}

function sameId(a, b) {
  return a != null && b != null && String(a) === String(b);
}

function snapshotStamp(snap) {
  const localPath = String(snap?.localPath || "");
  const fromPath = localPath.match(/^(\d{4}-\d{2}-\d{2})\/(\d{2})-(\d{2})-(\d{2})$/);
  if (fromPath) {
    return { date: fromPath[1], time: `${fromPath[2]}:${fromPath[3]}:${fromPath[4]}` };
  }
  if (snap?.capturedAt) {
    const captured = new Date(snap.capturedAt);
    if (!Number.isNaN(captured.getTime())) {
      const date = [
        captured.getFullYear(),
        String(captured.getMonth() + 1).padStart(2, "0"),
        String(captured.getDate()).padStart(2, "0"),
      ].join("-");
      const time = [
        String(captured.getHours()).padStart(2, "0"),
        String(captured.getMinutes()).padStart(2, "0"),
        String(captured.getSeconds()).padStart(2, "0"),
      ].join(":");
      return { date, time };
    }
  }
  return { date: "—", time: String(snap?.id ?? "") };
}

function groupSnapshotsByDate(snapshots) {
  const groups = [];
  const byDate = new Map();
  for (const snap of snapshots || []) {
    const stamp = snapshotStamp(snap);
    if (!byDate.has(stamp.date)) {
      const group = { date: stamp.date, items: [] };
      byDate.set(stamp.date, group);
      groups.push(group);
    }
    byDate.get(stamp.date).items.push({ ...snap, timeLabel: stamp.time });
  }
  return groups;
}

function siteTitle(page) {
  return page.checkName || page.title || page.url;
}

function VersionCheck({ checked, title, disabled, slot, onChange }) {
  return (
    <label
      className={`flex items-center gap-1 select-none ${disabled ? "cursor-not-allowed opacity-40" : "cursor-pointer"}`}
      title={title}
    >
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        aria-label={title}
        className="h-4 w-4 cursor-pointer rounded border-gray-300 accent-blue-600 disabled:cursor-not-allowed"
      />
      {slot ? <span className="text-[11px] font-semibold text-gray-600">{slot}</span> : null}
    </label>
  );
}

export default function SavedPages({
  onSelectPage,
  onSelectVersion,
  refreshToken,
  currentUrl,
  selectedSiteUrl,
  versionAId,
  versionBId,
}) {
  const { t } = useTranslation();
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [collapsed, setCollapsed] = useState({});

  const fetchPages = async () => {
    try {
      const { data } = await apiFetch("/api/pages/list");
      setPages(data.pages || []);
    } catch (error) {
      console.error("Failed to fetch pages:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPages();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshToken]);

  const handleDelete = async (id) => {
    try {
      await apiFetch(`/api/pages/${id}`, { method: "DELETE" });
      setPages((prev) => prev.filter((p) => p.id !== id));
      setDeleteConfirm(null);
    } catch (error) {
      console.error("Failed to delete page:", error);
    }
  };

  const toggleSite = (id) => {
    setCollapsed((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <aside className="bg-white rounded-2xl shadow-xl p-4 h-fit sticky top-4 max-h-[calc(100vh-6rem)] overflow-y-auto">
      <h2 className="text-lg font-semibold text-gray-800 mb-3">{t("siteList")}</h2>

      {loading && (
        <div className="flex justify-center py-8">
          <div className="loading-spinner" />
        </div>
      )}

      {!loading && pages.length === 0 && (
        <p className="text-sm text-center text-gray-500 py-6">{t("siteListEmpty")}</p>
      )}

      {!loading && pages.length > 0 && (
        <div className="space-y-2">
          {pages.map((page) => {
            const active = currentUrl && currentUrl.trim() === page.url;
            const snapshots = page.snapshots || [];
            const dateGroups = groupSnapshotsByDate(snapshots);
            const isCollapsed = Boolean(collapsed[page.id]);
            return (
              <div
                key={page.id}
                role="button"
                tabIndex={0}
                onClick={() => onSelectPage(page)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelectPage(page);
                  }
                }}
                className={`border rounded-xl p-3 transition-all cursor-pointer ${
                  active ? "border-blue-400 bg-blue-50" : "hover:border-blue-300 hover:bg-blue-50/40"
                }`}
              >
                <div className="flex items-start gap-2">
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      toggleSite(page.id);
                    }}
                    className="mt-0.5 p-1 text-gray-500 hover:text-gray-800 rounded"
                    aria-label={isCollapsed ? t("expandSite") : t("collapseSite")}
                  >
                    <svg
                      className={`w-3.5 h-3.5 transition-transform ${isCollapsed ? "" : "rotate-90"}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </button>
                  <div className="min-w-0 flex-1 text-left">
                    <div className="font-medium text-gray-800 truncate text-sm">{siteTitle(page)}</div>
                    <div className="text-xs text-blue-600 truncate">{page.url}</div>
                  </div>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      setDeleteConfirm(page.id);
                    }}
                    className="p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    aria-label={t("delete")}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                      />
                    </svg>
                  </button>
                </div>

                <div className="flex items-center justify-between gap-2 mt-2 pl-6">
                  <span className={`text-[11px] px-2 py-0.5 rounded-full ${statusClass(page)}`}>
                    {statusLabel(page, t)}
                  </span>
                  <span className="text-[11px] text-gray-500">
                    {snapshots.length} {t("snapshotCount")}
                  </span>
                </div>

                {!isCollapsed && (
                  <div className="mt-3 pl-6 space-y-2">
                    {dateGroups.length === 0 && (
                      <p className="text-xs text-gray-400">{t("noSnapshots")}</p>
                    )}
                    {dateGroups.map((group) => (
                      <div key={group.date}>
                        <div className="text-[11px] font-semibold text-gray-500 mb-1">{group.date}</div>
                        <div className="space-y-1">
                          {group.items.map((snap) => {
                            const snapKey = snap.localPath || snap.id;
                            const sameSite = !selectedSiteUrl || selectedSiteUrl === page.url;
                            const isA = sameSite && sameId(versionAId, snapKey);
                            const isB = sameSite && sameId(versionBId, snapKey);
                            const selected = isA || isB;
                            const twoSelected = Boolean(versionAId && versionBId);
                            return (
                              <div
                                key={snap.id}
                                className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs ${
                                  selected ? "bg-white border border-blue-200" : "bg-slate-50"
                                }`}
                              >
                                <span className="flex-1 font-mono text-gray-700">{snap.timeLabel}</span>
                                <div
                                  onClick={(event) => event.stopPropagation()}
                                  onKeyDown={(event) => event.stopPropagation()}
                                >
                                  <VersionCheck
                                    checked={selected}
                                    slot={isA ? "1" : isB ? "2" : ""}
                                    title={isA ? t("versionOne") : isB ? t("versionTwo") : t("selectSnapshot")}
                                    disabled={!selected && twoSelected && sameSite}
                                    onChange={(checked) => onSelectVersion(page, snap, checked)}
                                  />
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full p-6">
            <h3 className="text-lg font-semibold text-gray-800 mb-3">{t("confirmDelete")}</h3>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 rounded-xl font-medium text-gray-700 bg-gray-100 hover:bg-gray-200"
              >
                {t("cancel")}
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                className="px-4 py-2 rounded-xl font-medium text-white bg-red-600 hover:bg-red-700"
              >
                {t("delete")}
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
