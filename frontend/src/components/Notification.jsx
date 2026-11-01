"use client";

import { useTranslation } from "../hooks/useTranslation";

export default function Notification({ type, message, onClose }) {
  const { t } = useTranslation();
  const styles = {
    success: "bg-green-600",
    error: "bg-red-600",
  };

  return (
    <div className="fixed top-4 right-4 z-50 max-w-md w-[calc(100vw-2rem)]">
      <div className={`rounded-xl shadow-2xl text-white p-4 ${styles[type] || "bg-gray-700"}`}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="font-semibold">{type === "success" ? t("success") : t("error")}</div>
            <div className="text-sm opacity-95 mt-1 whitespace-pre-wrap">{message}</div>
          </div>
          <button onClick={onClose} className="text-white/80 hover:text-white">
            ✕
          </button>
        </div>
      </div>
    </div>
  );
}

