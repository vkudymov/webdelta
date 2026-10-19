import React, { useState, useEffect } from 'react';
import { useTranslation } from '../hooks/useTranslation';

export default function SavedPages({ onSelectPage }) {
  const { t } = useTranslation();
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const fetchPages = async () => {
    try {
      const response = await fetch('/api/pages/list');
      const data = await response.json();
      setPages(data.pages || []);
    } catch (error) {
      console.error('Failed to fetch pages:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPages();
  }, []);

  const handleDelete = async (id) => {
    try {
      await fetch(`/api/pages/${id}`, { method: 'DELETE' });
      setPages(pages.filter(p => p.id !== id));
      setDeleteConfirm(null);
    } catch (error) {
      console.error('Failed to delete page:', error);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-2xl shadow-xl p-6">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">{t('savedPages')}</h2>
        <div className="flex justify-center py-8">
          <div className="loading-spinner" />
        </div>
      </div>
    );
  }

  if (pages.length === 0) {
    return (
      <div className="bg-white rounded-2xl shadow-xl p-6">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">{t('savedPages')}</h2>
        <p className="text-center text-gray-500 py-8">{t('noDataYet')}</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl shadow-xl p-6">
      <h2 className="text-xl font-semibold text-gray-800 mb-4">{t('savedPages')}</h2>
      
      <div className="space-y-3">
        {pages.map((page) => (
          <div 
            key={page.id}
            className="border rounded-xl p-4 hover:border-blue-300 hover:bg-blue-50/50 transition-all group"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <h3 className="font-medium text-gray-800 truncate">{page.title}</h3>
                <p 
                  className="text-sm text-blue-600 truncate cursor-pointer hover:underline"
                  onClick={() => onSelectPage(page.url)}
                >
                  {page.url}
                </p>
                <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                  <span>
                    {t('savedAt')}: {new Date(page.updated_at).toLocaleString()}
                  </span>
                  <span className="flex items-center gap-1">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                    </svg>
                    {page.attachment_count} {t('attachmentsFound').toLowerCase()}
                  </span>
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                <button
                  onClick={() => onSelectPage(page.url)}
                  className="px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-100 rounded-lg hover:bg-blue-200 transition-colors"
                >
                  {t('compareWithOriginal')}
                </button>
                <button
                  onClick={() => setDeleteConfirm(page.id)}
                  className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full p-6">
            <h3 className="text-lg font-semibold text-gray-800 mb-3">{t('confirmDelete')}</h3>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 rounded-xl font-medium text-gray-700 bg-gray-100 hover:bg-gray-200"
              >
                {t('cancel')}
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                className="px-4 py-2 rounded-xl font-medium text-white bg-red-600 hover:bg-red-700"
              >
                {t('delete')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
