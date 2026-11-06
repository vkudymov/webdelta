"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { apiFetch, setApiSource } from "./api";

export const StorageContext = createContext({
  source: "results",
  setSource: () => {},
  supabaseConfigured: false,
});

function readSavedSource() {
  if (typeof window === "undefined") return "results";
  const saved = window.localStorage.getItem("webdelta.source");
  return saved === "supabase" ? "supabase" : "results";
}

export function StorageProvider({ children }) {
  const [source, setSourceState] = useState(() => {
    const saved = readSavedSource();
    setApiSource(saved);
    return saved;
  });
  const [supabaseConfigured, setSupabaseConfigured] = useState(false);

  useEffect(() => {
    const saved = readSavedSource();
    setSourceState(saved);
    setApiSource(saved);
    let cancelled = false;
    (async () => {
      try {
        const { data } = await apiFetch("/api/storage");
        if (cancelled) return;
        const configured = Boolean(data.supabaseConfigured);
        setSupabaseConfigured(configured);
        if (!configured && saved === "supabase") {
          setSourceState("results");
          setApiSource("results");
          window.localStorage.setItem("webdelta.source", "results");
        }
      } catch {
        if (!cancelled) setSupabaseConfigured(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const setSource = (next) => {
    if (next === "supabase" && !supabaseConfigured) return;
    const value = next === "supabase" ? "supabase" : "results";
    setSourceState(value);
    setApiSource(value);
    window.localStorage.setItem("webdelta.source", value);
  };

  return (
    <StorageContext.Provider value={{ source, setSource, supabaseConfigured }}>
      {children}
    </StorageContext.Provider>
  );
}

export function useStorageSource() {
  return useContext(StorageContext);
}
