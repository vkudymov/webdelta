"use client";

import { createContext, useState } from "react";

export const LocaleContext = createContext({ locale: "ru", setLocale: () => {} });

export function LocaleProvider({ children }) {
  const [locale, setLocale] = useState("ru");
  return <LocaleContext.Provider value={{ locale, setLocale }}>{children}</LocaleContext.Provider>;
}

