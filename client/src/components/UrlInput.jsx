import React from 'react';
import { useTranslation } from '../hooks/useTranslation';

export default function UrlInput({ url, onChange, disabled }) {
  const { t } = useTranslation();

  return (
    <div className="mb-6">
      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
          <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
          </svg>
        </div>
        <input
          type="url"
          value={url}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          placeholder={t('urlPlaceholder')}
          className="w-full pl-12 pr-4 py-4 text-lg border-2 border-gray-200 rounded-xl 
                     focus:border-blue-500 focus:ring-4 focus:ring-blue-100 
                     transition-all outline-none disabled:bg-gray-50 disabled:cursor-not-allowed"
        />
      </div>
    </div>
  );
}
