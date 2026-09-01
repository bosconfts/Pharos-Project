const BASE = import.meta.env.VITE_API_URL ?? "/api";

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

// A API é read-only e serve o que o worker persistiu. Um 404 em /analysis
// significa "ainda não processada", não "erro" — a UI precisa distinguir isso
// de uma falha de rede, senão toda tela vazia parece um bug.
async function get(path) {
  let r;
  try {
    r = await fetch(`${BASE}${path}`);
  } catch (e) {
    throw new ApiError(0, "API unreachable");
  }
  if (!r.ok) {
    let detail = r.statusText;
    try {
      detail = (await r.json()).detail ?? detail;
    } catch {
      /* resposta sem corpo JSON */
    }
    throw new ApiError(r.status, detail);
  }
  return r.json();
}

export const fetchStats = () => get("/stats");

export const fetchHistory = (limit = 50, offset = 0) =>
  get(`/governance/history?limit=${limit}&offset=${offset}`);

export const fetchLive = (limit = 20) =>
  get(`/governance/actions?count=${limit}`);

export const fetchAnalysis = (govActionId) =>
  get(`/analysis/${encodeURIComponent(govActionId)}`);
