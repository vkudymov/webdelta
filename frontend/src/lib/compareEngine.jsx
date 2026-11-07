"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { apiFetch } from "./api";

const CompareEngineContext = createContext({
  engine: "hash",
  setEngine: () => {},
  model: "",
  setModel: () => {},
  models: [],
  available: false,
});

export function CompareEngineProvider({ children }) {
  const [engine, setEngineState] = useState("hash");
  const [model, setModelState] = useState("");
  const [models, setModels] = useState([]);
  const [available, setAvailable] = useState(false);

  useEffect(() => {
    const savedEngine = window.localStorage.getItem("webdelta.compareEngine");
    const savedModel = window.localStorage.getItem("webdelta.compareModel") || "";
    if (savedEngine === "llm" || savedEngine === "hash") setEngineState(savedEngine);
    setModelState(savedModel);
    let cancelled = false;
    (async () => {
      try {
        const { data } = await apiFetch("/api/filediff");
        if (cancelled) return;
        const list = Array.isArray(data.models) ? data.models : [];
        setModels(list);
        setAvailable(Boolean(data.available));
        const next = list.includes(savedModel) ? savedModel : data.defaultModel || list[0] || "";
        setModelState(next);
        if (!data.available && savedEngine === "llm") setEngineState("hash");
      } catch {
        if (!cancelled) {
          setAvailable(false);
          setEngineState("hash");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const setEngine = (next) => {
    if (next === "llm" && !available) return;
    const value = next === "llm" ? "llm" : "hash";
    setEngineState(value);
    window.localStorage.setItem("webdelta.compareEngine", value);
  };

  const setModel = (next) => {
    setModelState(next);
    window.localStorage.setItem("webdelta.compareModel", next);
  };

  return (
    <CompareEngineContext.Provider value={{ engine, setEngine, model, setModel, models, available }}>
      {children}
    </CompareEngineContext.Provider>
  );
}

export function useCompareEngine() {
  return useContext(CompareEngineContext);
}
