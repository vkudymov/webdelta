"use client";

import { useEffect, useState } from "react";
import Header from "../components/Header";
import UrlInput from "../components/UrlInput";
import ActionButtons from "../components/ActionButtons";
import DiffViewer from "../components/DiffViewer";
import ConfirmDialog from "../components/ConfirmDialog";
import Notification from "../components/Notification";
import SavedPages from "../components/SavedPages";
import { LocaleProvider } from "../lib/locale";
import { StorageProvider, useStorageSource } from "../lib/storage";
import { useTranslation } from "../hooks/useTranslation";
import { apiFetch } from "../lib/api";
import { formatSnapshotLabel } from "../lib/snapshotLabel";

function AppContent() {
  const { t, locale } = useTranslation();
  const { source } = useStorageSource();
  const [url, setUrl] = useState("");
  const [checkName, setCheckName] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingAction, setLoadingAction] = useState("");
  const [comparison, setComparison] = useState(null);
  const [showDelta, setShowDelta] = useState(false);
  const [notification, setNotification] = useState(null);
  const [confirmDialog, setConfirmDialog] = useState(null);
  const [pagesRefreshToken, setPagesRefreshToken] = useState(0);
  const [versionA, setVersionA] = useState(null);
  const [versionB, setVersionB] = useState(null);

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

  useEffect(() => {
    setPagesRefreshToken((x) => x + 1);
    setVersionA(null);
    setVersionB(null);
    setComparison(null);
    setShowDelta(false);
  }, [source]);

  const sameSnapshot = (left, right) =>
    left != null && right != null && String(left) === String(right);

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
        body: JSON.stringify({ url, overwrite, checkName: checkName.trim() || null }),
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
        setPagesRefreshToken((x) => x + 1);
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
      setPagesRefreshToken((x) => x + 1);
      showNotification("error", error.message);
    } finally {
      setLoading(false);
      setLoadingAction("");
    }
  };

  const handleShowDelta = async () => {
    const hasTwoVersions = Boolean(versionA?.snapshotId != null && versionB?.snapshotId != null);
    if (!hasTwoVersions) {
      showNotification("error", t("selectTwoVersions"));
      return;
    }
    if (!url.trim() || !validateUrl(url)) {
      showNotification("error", t("invalidUrl"));
      return;
    }

    setLoading(true);
    setLoadingAction("delta");

    try {
      const { res, data } = await apiFetch("/api/pages/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: versionA.url || url,
          locale,
          snapshotId: versionA.snapshotId,
          snapshotId2: versionB.snapshotId,
          checkName: (versionA.checkName || checkName).trim() || null,
        }),
      });

      if (!res.ok) {
        setPagesRefreshToken((x) => x + 1);
        if (res.status === 404) throw new Error(t("noSavedVersion"));
        throw new Error(data.error || t("networkError"));
      }

      setComparison(data.comparison);
      setShowDelta(true);
      setPagesRefreshToken((x) => x + 1);

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
      setPagesRefreshToken((x) => x + 1);
      showNotification("error", error.message);
    } finally {
      setLoading(false);
      setLoadingAction("");
    }
  };

  const fillSiteFields = (page) => {
    setUrl(page?.url || "");
    setCheckName(page?.checkName || page?.title || "");
  };

  const handleSelectPage = (page) => {
    fillSiteFields(page);
    setComparison(null);
    setShowDelta(false);
  };

  const handleVersionDeleted = (page, snap) => {
    const snapId = snap?.localPath || snap?.id;
    if (versionA && versionA.url === page.url && sameSnapshot(versionA.snapshotId, snapId)) {
      setVersionA(versionB);
      setVersionB(null);
      setComparison(null);
      setShowDelta(false);
    } else if (versionB && versionB.url === page.url && sameSnapshot(versionB.snapshotId, snapId)) {
      setVersionB(null);
      setComparison(null);
      setShowDelta(false);
    }
  };

  const handleSelectVersion = (page, snap, checked) => {
    const next = {
      url: page.url,
      checkName: page.checkName || page.title || "",
      snapshotId: snap.localPath || snap.id,
    };
    const isA = versionA && versionA.url === page.url && sameSnapshot(versionA.snapshotId, next.snapshotId);
    const isB = versionB && versionB.url === page.url && sameSnapshot(versionB.snapshotId, next.snapshotId);

    fillSiteFields(page);
    setComparison(null);
    setShowDelta(false);

    if (!checked) {
      if (isA) {
        setVersionA(versionB);
        setVersionB(null);
      } else if (isB) {
        setVersionB(null);
      }
      return;
    }

    if (versionA && versionA.url !== page.url) {
      setVersionA(next);
      setVersionB(null);
      return;
    }
    if (!versionA) {
      setVersionA(next);
      return;
    }
    if (!versionB && !sameSnapshot(versionA.snapshotId, next.snapshotId)) {
      setVersionB(next);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      <Header />

      <main className="max-w-7xl mx-auto px-4 py-8 grid grid-cols-1 md:grid-cols-[320px_minmax(0,1fr)] gap-6 items-start">
        <SavedPages
          onSelectPage={handleSelectPage}
          onSelectVersion={handleSelectVersion}
          onVersionDeleted={handleVersionDeleted}
          refreshToken={pagesRefreshToken}
          currentUrl={url}
          selectedSiteUrl={versionA?.url || versionB?.url}
          versionAId={versionA?.snapshotId}
          versionBId={versionB?.snapshotId}
        />

        <div>
          <div className="bg-white rounded-2xl shadow-xl p-6 mb-6">
            <UrlInput
              url={url}
              onUrlChange={setUrl}
              checkName={checkName}
              onCheckNameChange={setCheckName}
              disabled={loading}
            />

            <ActionButtons
              onDownload={() => handleDownload(false)}
              onShowDelta={handleShowDelta}
              loading={loading}
              loadingAction={loadingAction}
              hasComparison={!!comparison}
              hasTwoVersions={Boolean(versionA?.snapshotId != null && versionB?.snapshotId != null)}
            />
          </div>

          {comparison && showDelta && (
            <DiffViewer
              comparison={comparison}
              versionLeftLabel={formatSnapshotLabel(versionA?.snapshotId)}
              versionRightLabel={formatSnapshotLabel(versionB?.snapshotId)}
            />
          )}
        </div>
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

export default function Page() {
  return (
    <LocaleProvider>
      <StorageProvider>
        <AppContent />
      </StorageProvider>
    </LocaleProvider>
  );
}

