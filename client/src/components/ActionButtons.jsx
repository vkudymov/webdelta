import React from 'react';
import { useTranslation } from '../hooks/useTranslation';

export default function ActionButtons({ 
  onDownload, 
  onCompare, 
  onShowDelta, 
  loading, 
  loadingAction,
  hasComparison 
}) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-wrap gap-3">
      <Button 
        onClick={onDownload}
        loading={loading && loadingAction === 'download'}
        disabled={loading}
        variant="primary"
        icon={<DownloadIcon />}
      >
        {loading && loadingAction === 'download' ? t('downloading') : t('downloadOriginal')}
      </Button>
      
      <Button 
        onClick={onCompare}
        loading={loading && loadingAction === 'compare'}
        disabled={loading}
        variant="secondary"
        icon={<CompareIcon />}
      >
        {loading && loadingAction === 'compare' ? t('comparing') : t('compareWithOriginal')}
      </Button>
      
      <Button 
        onClick={onShowDelta}
        disabled={loading || !hasComparison}
        variant="accent"
        icon={<DeltaIcon />}
      >
        {t('showDelta')}
      </Button>
    </div>
  );
}

function Button({ children, onClick, disabled, loading, variant, icon }) {
  const variants = {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white shadow-blue-200',
    secondary: 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-emerald-200',
    accent: 'bg-purple-600 hover:bg-purple-700 text-white shadow-purple-200',
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`
        flex items-center gap-2 px-6 py-3 rounded-xl font-medium
        shadow-lg transition-all duration-200
        disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none
        hover:shadow-xl hover:-translate-y-0.5 active:translate-y-0
        ${variants[variant]}
      `}
    >
      {loading ? <Spinner /> : icon}
      {children}
    </button>
  );
}

function Spinner() {
  return (
    <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
    </svg>
  );
}

function CompareIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
    </svg>
  );
}

function DeltaIcon() {
  return (
    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
      <path d="M12 2L2 19h20L12 2zm0 4l6.5 11h-13L12 6z"/>
    </svg>
  );
}
