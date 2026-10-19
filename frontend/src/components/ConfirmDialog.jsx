"use client";

import { useTranslation } from "../hooks/useTranslation";

export default function ConfirmDialog({ title, message, onConfirm, onCancel }) {
  const { t } = useTranslation();

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-3">{title}</h3>
        <p className="text-gray-600 mb-6">{message}</p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-xl font-medium text-gray-700 bg-gray-100 hover:bg-gray-200"
          >
            {t("cancel")}
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 rounded-xl font-medium text-white bg-blue-600 hover:bg-blue-700"
          >
            {t("yes")}
          </button>
        </div>
      </div>
    </div>
  );
}

