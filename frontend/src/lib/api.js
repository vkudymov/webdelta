"use client";

// Unset: Mac/dev Next on :3000 talks to uvicorn on :8000.
// "" or "same-origin": portable UI is served by FastAPI, so requests stay on that host.
const rawApiBase = process.env.NEXT_PUBLIC_API_URL;
const API_BASE =
  rawApiBase == null
    ? "http://127.0.0.1:8000"
    : rawApiBase === "" || rawApiBase === "same-origin"
      ? ""
      : rawApiBase.replace(/\/$/, "");

let currentSource = "results";

function localApiHeaders() {
  if (typeof window === "undefined") return {};
  const token = window.__WEBDELTA_LOCAL_TOKEN__;
  return token ? { "X-WebDelta-Token": token } : {};
}

export function setApiSource(source) {
  currentSource = source === "supabase" ? "supabase" : "results";
}

export function getApiSource() {
  return currentSource;
}

export async function apiFetch(path, options = {}) {
  let url = `${API_BASE}${path}`;
  const opts = { ...options };
  if (path.startsWith("/api/pages")) {
    const joiner = path.includes("?") ? "&" : "?";
    url = `${API_BASE}${path}${joiner}source=${encodeURIComponent(currentSource)}`;
    if (typeof opts.body === "string") {
      try {
        const parsed = JSON.parse(opts.body);
        if (parsed && typeof parsed === "object" && parsed.source == null) {
          parsed.source = currentSource;
          opts.body = JSON.stringify(parsed);
        }
      } catch {
        // keep original body
      }
    }
  }
  const res = await fetch(url, {
    ...opts,
    headers: { ...localApiHeaders(), ...(opts.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  return { res, data };
}
