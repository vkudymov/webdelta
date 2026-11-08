"use client";

import { useContext } from "react";
import { LocaleContext } from "../lib/locale";
import { useStorageSource } from "../lib/storage";
import { useCompareEngine } from "../lib/compareEngine";
import { useTranslation } from "../hooks/useTranslation";

export default function Header() {
  const { locale, setLocale } = useContext(LocaleContext);
  const { source, setSource, supabaseConfigured } = useStorageSource();
  const { engine, setEngine, model, setModel, models, available } = useCompareEngine();
  const { t } = useTranslation();

  return (
    <header className="bg-gradient-to-r from-blue-600 to-indigo-700 text-white shadow-lg">
      <div className="max-w-6xl mx-auto px-4 py-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center">
            <svg viewBox="0 0 24 24" className="w-6 h-6" fill="currentColor">
              <path d="M12 2L2 19h20L12 2zm0 4l6.5 11h-13L12 6z" />
            </svg>
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{t("appTitle")}</h1>
            <p className="text-blue-100 text-sm">{t("appSubtitle")}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap justify-end">
          <button
            type="button"
            onClick={() => setSource("results")}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
              source === "results" ? "bg-white text-blue-700" : "bg-white/10 hover:bg-white/20"
            }`}
          >
            {t("sourceFiles")}
          </button>
          <button
            type="button"
            onClick={() => setSource("supabase")}
            disabled={!supabaseConfigured}
            title={supabaseConfigured ? t("sourceSupabase") : t("sourceUnavailable")}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
              source === "supabase" ? "bg-white text-blue-700" : "bg-white/10 hover:bg-white/20"
            } disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-white/10`}
          >
            {t("sourceSupabase")}
          </button>
          <button
            type="button"
            onClick={() => setEngine("hash")}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
              engine === "hash" ? "bg-white text-blue-700" : "bg-white/10 hover:bg-white/20"
            }`}
          >
            {t("engineHash")}
          </button>
          <button
            type="button"
            onClick={() => setEngine("llm")}
            disabled={!available}
            title={available ? t("engineModel") : t("engineUnavailable")}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
              engine === "llm" ? "bg-white text-blue-700" : "bg-white/10 hover:bg-white/20"
            } disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-white/10`}
          >
            {t("engineModel")}
          </button>
          {engine === "llm" && models.length > 0 && (
            <select
              value={model}
              onChange={(event) => setModel(event.target.value)}
              aria-label={t("engineModel")}
              className="max-w-[14rem] rounded-lg bg-white px-2 py-1.5 text-sm font-medium text-blue-800"
            >
              {models.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          )}
          <button
            onClick={() => setLocale("ru")}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
              locale === "ru" ? "bg-white text-blue-700" : "bg-white/10 hover:bg-white/20"
            }`}
          >
            RU
          </button>
          <button
            onClick={() => setLocale("en")}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
              locale === "en" ? "bg-white text-blue-700" : "bg-white/10 hover:bg-white/20"
            }`}
          >
            EN
          </button>
        </div>
      </div>
    </header>
  );
}

