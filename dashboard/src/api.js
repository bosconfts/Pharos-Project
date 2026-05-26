const BASE = import.meta.env.VITE_API_URL ?? "/api";

export async function fetchStats() {
  const r = await fetch(`${BASE}/stats`);
  return r.json();
}

export async function fetchHistory(limit = 50, offset = 0) {
  const r = await fetch(`${BASE}/governance/history?limit=${limit}&offset=${offset}`);
  return r.json();
}

export async function fetchLive(limit = 20) {
  const r = await fetch(`${BASE}/governance/actions?count=${limit}`);
  return r.json();
}

export async function fetchAnalysis(govActionId) {
  const r = await fetch(`${BASE}/analysis/${encodeURIComponent(govActionId)}`);
  return r.json();
}
