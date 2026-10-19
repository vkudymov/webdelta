"use client";

import { useState } from "react";
import Header from "../components/Header";
import UrlInput from "../components/UrlInput";
import ActionButtons from "../components/ActionButtons";
import DiffViewer from "../components/DiffViewer";
import ConfirmDialog from "../components/ConfirmDialog";
import Notification from "../components/Notification";
import SavedPages from "../components/SavedPages";
import { LocaleProvider } from "../lib/locale";
import { useTranslation } from "../hooks/useTranslation";
import { apiFetch } from "../lib/api";

function AppContent() {
  const { t, locale } = useTranslation();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingAction, setLoadingAction] = useState("");
  const [comparison, setComparison] = useState(null);
  const [showDelta, setShowDelta] = useState(false);
  const [notification, setNotification] = useState(null);
  const [confirmDialog, setConfirmDialog] = useState(null);
  const [pagesRefreshToken, setPagesRefreshToken] = useState(0);

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const validateUrl = (value) => {
    try {
      new URL(value);
      return true;
    } catch {
      return false;
    }
  };

  const handleDownload = async (overwrite = false) => {
    if (!url.trim() || !validateUrl(url)) {
      showNotification("error", t("invalidUrl"));
      return;
    }

    setLoading(true);
    setLoadingAction("download");

    try {
      const { res, data } = await apiFetch("/api/pages/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, overwrite }),
      });

      if (res.status === 409 && data.requiresConfirmation) {
        setConfirmDialog({
          title: t("overwriteTitle"),
          message: t("overwriteMessage"),
          onConfirm: () => {
            setConfirmDialog(null);
            handleDownload(true);
          },
          onCancel: () => setConfirmDialog(null),
        });
        setLoading(false);
        return;
      }

      if (!res.ok) {
        throw new Error(data.error || t("networkError"));
      }

      showNotification(
        "success",
        `${overwrite ? t("pageUpdated") : t("pageSaved")}. ${t("attachmentsFound")}: ${data.attachmentCount ?? 0}`
      );
      setComparison(null);
      setShowDelta(false);
      setPagesRefreshToken((x) => x + 1);
    } catch (error) {
      showNotification("error", error.message);
    } finally {
      setLoading(false);
      setLoadingAction("");
    }
  };

  const handleCompare = async () => {
    if (!url.trim() || !validateUrl(url)) {
      showNotification("error", t("invalidUrl"));
      return;
    }

    setLoading(true);
    setLoadingAction("compare");

    try {
      const { res, data } = await apiFetch("/api/pages/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, locale }),
      });

      if (!res.ok) {
        if (res.status === 404) throw new Error(t("noSavedVersion"));
        throw new Error(data.error || t("networkError"));
      }

      setComparison(data.comparison);
      setShowDelta(false);

      const summary = data.comparison?.summary;
      if (
        data.comparison?.textDiff?.hasChanges ||
        summary?.attachmentsAdded > 0 ||
        summary?.attachmentsRemoved > 0 ||
        summary?.attachmentsModified > 0
      ) {
        showNotification("success", t("changesFound"));
      } else {
        showNotification("success", t("noChanges"));
      }
    } catch (error) {
      showNotification("error", error.message);
    } finally {
      setLoading(false);
      setLoadingAction("");
    }
  };

  const handleShowDelta = () => {
    if (comparison) setShowDelta(true);
  };

  const handleSelectPage = (pageUrl) => {
    setUrl(pageUrl);
    setComparison(null);
    setShowDelta(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      <Header />

      <main className="max-w-6xl mx-auto px-4 py-8">
        <div className="bg-white rounded-2xl shadow-xl p-6 mb-6">
          <UrlInput url={url} onChange={setUrl} disabled={loading} />

          <ActionButtons
            onDownload={() => handleDownload(false)}
            onCompare={handleCompare}
            onShowDelta={handleShowDelta}
            loading={loading}
            loadingAction={loadingAction}
            hasComparison={!!comparison}
          />
        </div>

        {comparison && showDelta && <DiffViewer comparison={comparison} />}

        {comparison && !showDelta && <StatsPanel comparison={comparison} />}

        <SavedPages onSelectPage={handleSelectPage} refreshToken={pagesRefreshToken} />
      </main>

      {notification && (
        <Notification type={notification.type} message={notification.message} onClose={() => setNotification(null)} />
      )}

      {confirmDialog && (
        <ConfirmDialog
          title={confirmDialog.title}
          message={confirmDialog.message}
          onConfirm={confirmDialog.onConfirm}
          onCancel={confirmDialog.onCancel}
        />
      )}
    </div>
  );
}

function StatsPanel({ comparison }) {
  const { t } = useTranslation();
  const explanation = comparison.explanation;
  return (
    <div className="bg-white rounded-2xl shadow-xl p-6 mb-6">
      <h3 className="text-lg font-semibold text-gray-800 mb-4">{t("statistics")}</h3>

      {explanation && (
        <div className="mb-5 border rounded-xl overflow-hidden">
          <div className="bg-indigo-50 px-4 py-3 border-b">
            <div className="font-medium text-indigo-900">{t("explanation")}</div>
          </div>
          <div className="p-4 text-sm text-gray-800 whitespace-pre-wrap">{explanation}</div>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label={t("changedLines")} value={comparison.textDiff?.stats?.changedLines || 0} color="purple" />
        <StatCard label={t("modifications")} value={comparison.textDiff?.stats?.modifications || 0} color="yellow" />
        <StatCard label={`${t("attachmentChanges")} (+)`} value={comparison.summary?.attachmentsAdded || 0} color="green" />
        <StatCard label={`${t("attachmentChanges")} (-)`} value={comparison.summary?.attachmentsRemoved || 0} color="red" />
      </div>
      <p className="text-center mt-4 text-gray-500">{t("showDelta")} 👆</p>
    </div>
  );
}

function StatCard({ label, value, color }) {
  const colorClasses = {
    green: "bg-green-100 text-green-800",
    red: "bg-red-100 text-red-800",
    blue: "bg-blue-100 text-blue-800",
    orange: "bg-orange-100 text-orange-800",
    purple: "bg-purple-100 text-purple-800",
    yellow: "bg-yellow-100 text-yellow-800",
  };

  return (
    <div className={`rounded-xl p-4 ${colorClasses[color]}`}>
      <div className="text-3xl font-bold">{value}</div>
      <div className="text-sm opacity-75">{label}</div>
    </div>
  );
}

export default function Page() {
  return (
    <LocaleProvider>
      <AppContent />
    </LocaleProvider>
  );
}

