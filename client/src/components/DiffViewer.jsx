import React from 'react';
import { useTranslation } from '../hooks/useTranslation';

export default function DiffViewer({ comparison }) {
  const { t } = useTranslation();

  const { textDiff, attachmentDiffs, savedAt } = comparison;

  return (
    <div className="bg-white rounded-2xl shadow-xl overflow-hidden mb-6">
      <div className="bg-gradient-to-r from-gray-50 to-gray-100 px-6 py-4 border-b">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">{t('showDelta')}</h2>
          <p className="text-sm text-gray-500">
            {t('savedAt')}: {new Date(savedAt).toLocaleString()}
          </p>
        </div>
      </div>

      <div className="p-6">
        <div className="mb-6">
          <h3 className="text-lg font-medium text-gray-700 mb-3 flex items-center gap-2">
            <TextIcon />
            {t('changedLines')}
            <span className="text-sm font-normal text-gray-500">
              ({textDiff.stats.changedLines} {t('lines')})
            </span>
          </h3>

          <LineDeltaTable changes={textDiff.changes} t={t} />
        </div>

        {attachmentDiffs.modified.length > 0 && (
          <div>
            <h3 className="text-lg font-medium text-gray-700 mb-3 flex items-center gap-2">
              <AttachmentIcon />
              {t('attachmentChanges')}
            </h3>
            <AttachmentDiffs diffs={attachmentDiffs} t={t} />
          </div>
        )}

        {(attachmentDiffs.added.length > 0 || attachmentDiffs.removed.length > 0) && (
          <div className="mt-4">
            <AttachmentAddedRemoved diffs={attachmentDiffs} t={t} />
          </div>
        )}
      </div>
    </div>
  );
}

function LineDeltaTable({ changes, t }) {
  if (changes.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 bg-gray-50 rounded-xl">
        {t('noChangedLines')}
      </div>
    );
  }

  return (
    <div className="border rounded-xl overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-100 text-gray-600">
            <th className="px-4 py-3 text-left font-medium w-20">{t('lineNumber')}</th>
            <th className="px-4 py-3 text-left font-medium">{t('originalLine')}</th>
            <th className="px-4 py-3 text-left font-medium">{t('currentLine')}</th>
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
    added: t('lineAdded'),
    removed: t('lineRemoved'),
    modified: t('lineModified'),
  };

  const typeStyles = {
    added: 'bg-green-50',
    removed: 'bg-red-50',
    modified: 'bg-yellow-50',
  };

  const badgeStyles = {
    added: 'bg-green-100 text-green-700',
    removed: 'bg-red-100 text-red-700',
    modified: 'bg-yellow-100 text-yellow-700',
  };

  return (
    <tr className={typeStyles[change.type]}>
      <td className="px-4 py-3 font-mono text-gray-600 align-top">
        <div className="flex flex-col gap-1">
          <span className="font-semibold">{change.lineNumber}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded ${badgeStyles[change.type]}`}>
            {typeLabels[change.type]}
          </span>
        </div>
      </td>
      <td className="px-4 py-3 font-mono align-top">
        {change.original !== null ? (
          <div className="bg-red-100 text-red-800 px-2 py-1 rounded whitespace-pre-wrap break-all">
            {change.original || <span className="text-gray-400 italic">(пустая строка)</span>}
          </div>
        ) : (
          <span className="text-gray-400 italic">—</span>
        )}
      </td>
      <td className="px-4 py-3 font-mono align-top">
        {change.current !== null ? (
          <div className="bg-green-100 text-green-800 px-2 py-1 rounded whitespace-pre-wrap break-all">
            {change.current || <span className="text-gray-400 italic">(пустая строка)</span>}
          </div>
        ) : (
          <span className="text-gray-400 italic">—</span>
        )}
      </td>
    </tr>
  );
}

function AttachmentDiffs({ diffs, t }) {
  return (
    <div className="space-y-4">
      {diffs.modified.map((att, idx) => (
        <div key={idx} className="border rounded-xl overflow-hidden">
          <div className="bg-yellow-50 px-4 py-3 border-b flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-xs font-medium bg-yellow-200 text-yellow-800">
                {t('modified')}
              </span>
              <span className="font-medium text-gray-700">{att.filename}</span>
            </div>
            <span className="text-sm text-gray-500">
              {formatSize(att.oldSize)} → {formatSize(att.newSize)}
            </span>
          </div>
          
          {att.textDiff && att.textDiff.changes && att.textDiff.changes.length > 0 && (
            <div className="p-4">
              <h4 className="text-sm font-medium text-gray-600 mb-2">{t('attachmentTextChanges')}:</h4>
              <LineDeltaTable changes={att.textDiff.changes} t={t} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function AttachmentAddedRemoved({ diffs, t }) {
  return (
    <div className="space-y-2">
      {diffs.added.map((att, idx) => (
        <div key={`added-${idx}`} className="p-3 rounded-lg border bg-green-50 border-green-200">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-xs font-medium bg-green-200 text-green-800">
              {t('added')}
            </span>
            <span className="font-medium text-gray-700">{att.filename}</span>
            <span className="text-sm text-gray-500">({formatSize(att.size)})</span>
          </div>
        </div>
      ))}
      {diffs.removed.map((att, idx) => (
        <div key={`removed-${idx}`} className="p-3 rounded-lg border bg-red-50 border-red-200">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-xs font-medium bg-red-200 text-red-800">
              {t('removed')}
            </span>
            <span className="font-medium text-gray-700">{att.filename}</span>
            <span className="text-sm text-gray-500">({formatSize(att.size)})</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function TextIcon() {
  return (
    <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  );
}

function AttachmentIcon() {
  return (
    <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
    </svg>
  );
}
