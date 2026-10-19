"use client";

import { useContext } from "react";
import { translations } from "../i18n/translations";
import { LocaleContext } from "../lib/locale";

export function useTranslation() {
  const { locale } = useContext(LocaleContext);
  const dict = translations[locale] || translations.ru;
  const t = (key) => dict[key] ?? key;
  return { t, locale };
}

