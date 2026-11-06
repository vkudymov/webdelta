"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "../hooks/useTranslation";

/** added = only in right (absent from left); removed = only in left (absent from right); content: modified */
const DEFAULT_FILE_FILTERS = { missingInLeft: true, missingInRight: true, contentDiff: true };

export default function DiffViewer({ comparison, versionLeftLabel, versionRightLabel }) {
  const { t } = useTranslation();
  const [fileFilters, setFileFilters] = useState(DEFAULT_FILE_FILTERS);

  useEffect(() => {
    setFileFilters(DEFAULT_FILE_FILTERS);
  }, [comparison]);

  const colLeft = versionLeftLabel || t("versionOne");
  const colRight = versionRightLabel || t("versionTwo");

  const textDiff = comparison.textDiff || { hasChanges: false, changes: [], stats: {} };
  const attachmentDiffs = comparison.attachmentDiffs || { added: [], removed: [], modified: [], unchanged: [] };
  const summary = comparison.summary || {};
  const missingInLeftCount = summary.attachmentsAdded || 0;
  const missingInRightCount = summary.attachmentsRemoved || 0;
  const contentDiffCount = summary.attachmentsModified || 0;

  const fileRows = useMemo(
    () => [
      ...(attachmentDiffs.modified || []).map((item) => ({ ...item, status: "modified" })),
      ...(attachmentDiffs.added || []).map((item) => ({ ...item, status: "added" })),
      ...(attachmentDiffs.removed || []).map((item) => ({ ...item, status: "removed" })),
      ...(attachmentDiffs.unchanged || []).map((item) => ({ ...item, status: "unchanged" })),
    ],
    [attachmentDiffs]
  );

  const filteredFileRows = useMemo(() => {
    return fileRows.filter((row) => {
      if (row.status === "added") {
        return fileFilters.missingInLeft;
      }
      if (row.status === "removed") {
        return fileFilters.missingInRight;
      }
      if (row.status === "modified") {
        return fileFilters.contentDiff;
      }
      return false;
    });
  }, [fileRows, fileFilters]);

  const toggleFileFilter = (key) => {
    setFileFilters((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="bg-white rounded-2xl shadow-xl overflow-hidden mb-6">
      <div className="bg-gradient-to-r from-gray-50 to-gray-100 px-6 py-4 border-b">
        <h2 className="text-xl font-semibold text-gray-800">{t("showDelta")}</h2>
        <p className="text-sm text-gray-500 mt-1">
          <span className="font-medium text-gray-700">{colLeft}</span>
          <span className="mx-2 text-gray-400">↔</span>
          <span className="font-medium text-gray-700">{colRight}</span>
        </p>
        <p className="text-sm text-gray-500 mt-1">
          {t("savedAt")}: {comparison.savedAt ? new Date(comparison.savedAt).toLocaleString() : "—"}
        </p>
      </div>

      <div className="p-6 space-y-8">
        {comparison.explanation && (
          <div className="border rounded-xl overflow-hidden">
            <div className="bg-indigo-50 px-4 py-3 border-b">
              <div className="font-medium text-indigo-900">{t("explanation")}</div>
            </div>
            <div className="p-4 text-sm text-gray-800 whitespace-pre-wrap">{comparison.explanation}</div>
          </div>
        )}

        {!comparison.explanation && comparison.explanationError && (
          <div className="border rounded-xl overflow-hidden">
            <div className="bg-red-50 px-4 py-3 border-b">
              <div className="font-medium text-red-900">{t("explanation")}</div>
            </div>
            <div className="p-4 text-sm text-red-800 whitespace-pre-wrap">{comparison.explanationError}</div>
          </div>
        )}

        <section>
          <h3 className="text-lg font-medium text-gray-700 mb-3 flex items-center gap-2">
            <TextIcon />
            {t("pageChanges")}
          </h3>
          <p className={`mb-3 text-sm font-medium ${textDiff.hasChanges ? "text-yellow-800" : "text-green-700"}`}>
            {textDiff.hasChanges ? t("pageChanged") : t("pageUnchanged")}
            {textDiff.hasChanges ? ` · ${textDiff.stats?.changedLines || 0} ${t("lines")}` : ""}
          </p>
          <LineDeltaTable changes={textDiff.changes || []} t={t} columnLeftLabel={colLeft} columnRightLabel={colRight} />
        </section>

        <section>
          <h3 className="text-lg font-medium text-gray-700 mb-3 flex items-center gap-2">
            <AttachmentIcon />
            {t("fileCounts")}
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
            <CountCard label={`${colLeft}: ${summary.filesLeft || 0} ${t("filesInVersion")}`} />
            <CountCard label={`${colRight}: ${summary.filesRight || 0} ${t("filesInVersion")}`} />
            <FilterCountToggle
              filterKey="missingInLeft"
              active={fileFilters.missingInLeft}
              label={`${t("filterAbsentFrom")} ${colLeft}: ${missingInLeftCount}`}
              variant="emerald"
              title={t("fileFilterToggle")}
              onToggle={toggleFileFilter}
            />
            <FilterCountToggle
              filterKey="missingInRight"
              active={fileFilters.missingInRight}
              label={`${t("filterAbsentFrom")} ${colRight}: ${missingInRightCount}`}
              variant="rose"
              title={t("fileFilterToggle")}
              onToggle={toggleFileFilter}
            />
            <FilterCountToggle
              filterKey="contentDiff"
              active={fileFilters.contentDiff}
              label={`${t("filterByContent")}: ${contentDiffCount}`}
              variant="amber"
              title={t("fileFilterToggle")}
              onToggle={toggleFileFilter}
            />
          </div>
          {(summary.attachmentsUnchanged || 0) > 0 && (
            <p className="mt-3 text-xs text-gray-500">
              {t("unchangedFilesNote").replace("{count}", String(summary.attachmentsUnchanged))}
            </p>
          )}
        </section>

        <section>
          <h3 className="text-lg font-medium text-gray-700 mb-3">{t("eachFile")}</h3>
          {fileRows.length === 0 ? (
            <div className="text-center py-8 text-gray-500 bg-gray-50 rounded-xl">{t("noFiles")}</div>
          ) : !Object.values(fileFilters).some(Boolean) ? (
            <div className="text-center py-8 text-amber-800 bg-amber-50 border border-amber-200 rounded-xl text-sm">
              {t("fileFilterNone")}
            </div>
          ) : filteredFileRows.length === 0 ? (
            <div className="text-center py-8 text-gray-500 bg-gray-50 rounded-xl">{t("noFilesAfterFilter")}</div>
          ) : (
            <div className="space-y-3">
              {filteredFileRows.map((file, index) => (
                <FileRow
                  key={`${file.status}-${file.filename}-${index}`}
                  file={file}
                  t={t}
                  columnLeftLabel={colLeft}
                  columnRightLabel={colRight}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function CountCard({ label }) {
  return <div className="rounded-xl bg-slate-50 border border-slate-200 px-3 py-2 text-gray-700">{label}</div>;
}

const FILTER_VARIANTS = {
  emerald: {
    on: "bg-emerald-100 border-emerald-400 text-emerald-900 ring-2 ring-emerald-300",
    off: "bg-slate-50 border-slate-200 text-gray-400 line-through",
  },
  rose: {
    on: "bg-rose-100 border-rose-400 text-rose-900 ring-2 ring-rose-300",
    off: "bg-slate-50 border-slate-200 text-gray-400 line-through",
  },
  amber: {
    on: "bg-amber-100 border-amber-400 text-amber-900 ring-2 ring-amber-300",
    off: "bg-slate-50 border-slate-200 text-gray-400 line-through",
  },
};

function FilterCountToggle({ filterKey, active, label, variant, title, onToggle }) {
  const classes = FILTER_VARIANTS[variant];
  return (
    <button
      type="button"
      onClick={() => onToggle(filterKey)}
      title={title}
      aria-pressed={active}
      className={`rounded-xl border px-3 py-2 text-left text-sm font-medium transition-all ${active ? classes.on : classes.off}`}
    >
      {label}
    </button>
  );
}

function FileRow({ file, t, columnLeftLabel, columnRightLabel }) {
  const styles = {
    added: "bg-green-50 border-green-200",
    removed: "bg-red-50 border-red-200",
    modified: "bg-yellow-50 border-yellow-200",
    unchanged: "bg-slate-50 border-slate-200",
  };
  const badges = {
    added: "bg-green-200 text-green-800",
    removed: "bg-red-200 text-red-800",
    modified: "bg-yellow-200 text-yellow-800",
    unchanged: "bg-slate-200 text-slate-700",
  };
  const labels = {
    added: t("added"),
    removed: t("removed"),
    modified: t("modified"),
    unchanged: t("unchanged"),
  };
  const sizeLabel =
    file.status === "modified"
      ? `${formatSize(file.oldSize)} → ${formatSize(file.newSize)}`
      : formatSize(file.size);

  return (
    <div className={`border rounded-xl overflow-hidden ${styles[file.status]}`}>
      <div className="px-4 py-3 flex flex-wrap items-center gap-2 justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${badges[file.status]}`}>{labels[file.status]}</span>
          <span className="font-medium text-gray-800 break-all">{file.filename}</span>
        </div>
        <div className="text-sm text-gray-500 flex gap-3">
          <span>
            {t("fileType")}: {file.fileType || "—"}
          </span>
          <span>{sizeLabel}</span>
        </div>
      </div>
      {file.readError && <div className="px-4 pb-3 text-sm text-red-700">{file.readError}</div>}
      {file.textDiff?.changes?.length > 0 && (
        <div className="p-4 bg-white border-t">
          <h4 className="text-sm font-medium text-gray-600 mb-2">{t("attachmentTextChanges")}</h4>
          <LineDeltaTable
            changes={file.textDiff.changes}
            t={t}
            columnLeftLabel={columnLeftLabel}
            columnRightLabel={columnRightLabel}
          />
        </div>
      )}
    </div>
  );
}

function LineDeltaTable({ changes, t, columnLeftLabel, columnRightLabel }) {
  if (changes.length === 0) {
    return <div className="text-center py-8 text-gray-500 bg-gray-50 rounded-xl">{t("noChangedLines")}</div>;
  }

  return (
    <div className="border rounded-xl overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-100 text-gray-600">
            <th className="px-4 py-3 text-left font-medium w-20">{t("lineNumber")}</th>
            <th className="px-4 py-3 text-left font-medium min-w-[8rem]">{columnLeftLabel}</th>
            <th className="px-4 py-3 text-left font-medium min-w-[8rem]">{columnRightLabel}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {changes.map((change, idx) => (
            <DeltaRow key={idx} change={change} t={t} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DeltaRow({ change, t }) {
  const typeLabels = {
    added: t("lineAdded"),
    removed: t("lineRemoved"),
    modified: t("lineModified"),
  };
  const typeStyles = {
    added: "bg-green-50",
    removed: "bg-red-50",
    modified: "bg-yellow-50",
  };
  const badgeStyles = {
    added: "bg-green-100 text-green-700",
    removed: "bg-red-100 text-red-700",
    modified: "bg-yellow-100 text-yellow-700",
  };

  return (
    <tr className={typeStyles[change.type]}>
      <td className="px-4 py-3 font-mono text-gray-600 align-top">
        <div className="flex flex-col gap-1">
          <span className="font-semibold">{change.lineNumber}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded ${badgeStyles[change.type]}`}>{typeLabels[change.type]}</span>
        </div>
      </td>
      <td className="px-4 py-3 font-mono align-top">
        {change.original !== null ? (
          <div className="bg-red-100 text-red-800 px-2 py-1 rounded whitespace-pre-wrap break-all">
            {change.original || <span className="text-gray-400 italic">(empty)</span>}
          </div>
        ) : (
          <span className="text-gray-400 italic">—</span>
        )}
      </td>
      <td className="px-4 py-3 font-mono align-top">
        {change.current !== null ? (
          <div className="bg-green-100 text-green-800 px-2 py-1 rounded whitespace-pre-wrap break-all">
            {change.current || <span className="text-gray-400 italic">(empty)</span>}
          </div>
        ) : (
          <span className="text-gray-400 italic">—</span>
        )}
      </td>
    </tr>
  );
}

function formatSize(bytes) {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function TextIcon() {
  return (
    <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
      />
    </svg>
  );
}

function AttachmentIcon() {
  return (
    <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
      />
    </svg>
  );
}
