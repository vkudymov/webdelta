import { useContext } from 'react';
import { LocaleContext } from '../App';
import { translations } from '../i18n/translations';

export function useTranslation() {
  const { locale } = useContext(LocaleContext);
  
  const t = (key) => {
    return translations[locale]?.[key] || translations.ru[key] || key;
  };

  return { t, locale };
}
