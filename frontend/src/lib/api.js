"use client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

let currentSource = "results";

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
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  return { res, data };
}
