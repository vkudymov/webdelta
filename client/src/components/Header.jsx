import React, { useContext } from 'react';
import { LocaleContext } from '../App';
import { useTranslation } from '../hooks/useTranslation';

export default function Header() {
  const { locale, setLocale } = useContext(LocaleContext);
  const { t } = useTranslation();

  return (
    <header className="bg-gradient-to-r from-blue-600 to-indigo-700 text-white shadow-lg">
      <div className="max-w-6xl mx-auto px-4 py-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center">
            <svg viewBox="0 0 24 24" className="w-6 h-6" fill="currentColor">
              <path d="M12 2L2 19h20L12 2zm0 4l6.5 11h-13L12 6z"/>
            </svg>
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{t('appTitle')}</h1>
            <p className="text-blue-100 text-sm">{t('appSubtitle')}</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={() => setLocale('ru')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
              locale === 'ru' 
                ? 'bg-white text-blue-700' 
                : 'bg-white/10 hover:bg-white/20'
            }`}
          >
            RU
          </button>
          <button
            onClick={() => setLocale('en')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
              locale === 'en' 
                ? 'bg-white text-blue-700' 
                : 'bg-white/10 hover:bg-white/20'
            }`}
          >
            EN
          </button>
        </div>
      </div>
    </header>
  );
}
