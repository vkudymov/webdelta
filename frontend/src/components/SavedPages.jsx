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

export default function SavedPages({ onSelectPage, refreshToken, currentUrl }) {
  const { t } = useTranslation();
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

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
            return (
              <div
                key={page.id}
                className={`border rounded-xl p-3 transition-all group ${
                  active ? "border-blue-400 bg-blue-50" : "hover:border-blue-300 hover:bg-blue-50/50"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelectPage(page.url)}
                  className="w-full text-left"
                >
                  <div className="font-medium text-gray-800 truncate text-sm">{page.title || page.url}</div>
                  <div className="text-xs text-blue-600 truncate">{page.url}</div>
                </button>
                <div className="flex items-center justify-between gap-2 mt-2">
                  <span className={`text-[11px] px-2 py-0.5 rounded-full ${statusClass(page)}`}>
                    {statusLabel(page, t)}
                  </span>
                  <button
                    onClick={() => setDeleteConfirm(page.id)}
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
