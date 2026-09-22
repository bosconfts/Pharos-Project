import { useState, useEffect, useMemo } from "react";
import { fetchStats, fetchHistory, fetchLive, fetchAnalysis, ApiError } from "./api";
import ActionList from "./components/ActionList";
import ActionDetail from "./components/ActionDetail";
import "./App.css";

// Sem acento e sem caixa: "decisao" acha "Decisão", "eternl" acha "Eternl".
const norm = (s) =>
  (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

// Cada palavra da busca precisa aparecer em algum campo: "eternl 2026" acha a
// proposta da Eternl de 2026, não qualquer uma que cite só um dos dois termos.
function matches(action, query) {
  const terms = norm(query).split(/\s+/).filter(Boolean);
  if (!terms.length) return true;
  const haystack = norm(
    [action.title, action.one_liner, action.gov_action_id, action.action_type].join(" ")
  );
  return terms.every((t) => haystack.includes(t));
}

export default function App() {
  const [stats, setStats]       = useState(null);
  const [query, setQuery]       = useState("");
  const [actions, setActions]   = useState([]);
  const [listState, setList]    = useState("loading");
  const [selected, setSelected] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [detail, setDetail]     = useState("idle");
  const [tab, setTab]           = useState("analysed");

  useEffect(() => {
    fetchStats().then(setStats).catch(() => setStats(null));
    loadActions("analysed");
  }, []);

  const visible = useMemo(
    () => actions.filter((a) => matches(a, query)),
    [actions, query]
  );

  async function loadActions(mode) {
    setTab(mode);
    setQuery("");
    setSelected(null);
    setAnalysis(null);
    setDetail("idle");
    setList("loading");
    try {
      // A lista inteira, não as 50 mais recentes: a busca só acha o que foi
      // carregado, e com 50 de 155 metade do registro ficava inalcançável.
      // 200 é o teto da API; passando disso, a busca precisa ir para o servidor.
      const data = mode === "analysed" ? await fetchHistory(200) : await fetchLive(20);
      setActions(data.actions || []);
      setList("ok");
    } catch {
      setActions([]);
      setList("offline");
    }
  }

  async function selectAction(id) {
    setSelected(id);
    setAnalysis(null);
    setDetail("loading");
    try {
      setAnalysis(await fetchAnalysis(id));
      setDetail("ok");
    } catch (e) {
      setDetail(e instanceof ApiError && e.status === 404 ? "pending" : "offline");
    }
  }

  return (
    <div className="app">
      <header className="masthead">
        <div className="masthead-inner">
          <div className="brand">
            <h1 className="brand-mark">Pharos</h1>
            <p className="brand-sub">Proposal Intelligence Layer</p>
          </div>

          <p className="masthead-lede">
            Every governance action on Cardano, read closely: what it asks for, who
            stands to receive it, and how it compares with the proposals that came
            before. The analysis is public, reproducible, and anchored on-chain.
          </p>

          <dl className="masthead-meta">
            <div>
              <dt>Proposals analysed</dt>
              <dd className="num">{stats ? stats.total_analyzed : "—"}</dd>
            </div>
            <div>
              <dt>Network</dt>
              <dd>{stats ? stats.network : "mainnet"}</dd>
            </div>
            <div>
              <dt>Method</dt>
              <dd>Open pipeline · anchored record</dd>
            </div>
          </dl>
        </div>
      </header>

      <main className="main">
        <aside className="index-pane">
          <div className="pane-head">
            <h2>Index</h2>
            <div className="tabs">
              <button
                className={tab === "analysed" ? "tab active" : "tab"}
                onClick={() => loadActions("analysed")}
              >
                Analysed
              </button>
              <button
                className={tab === "chain" ? "tab active" : "tab"}
                onClick={() => loadActions("chain")}
              >
                On chain
              </button>
            </div>
          </div>

          {listState === "ok" && actions.length > 0 && (
            <div className="search">
              <input
                type="search"
                className="search-input"
                placeholder={tab === "analysed" ? "Search proposals" : "Search by id or type"}
                aria-label="Search the index"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Escape" && setQuery("")}
              />
              {query.trim() && (
                <p className="search-count" aria-live="polite">
                  {visible.length} of {actions.length}
                </p>
              )}
            </div>
          )}

          <ActionList
            actions={visible}
            state={listState}
            tab={tab}
            query={query}
            selected={selected}
            onSelect={selectAction}
          />
        </aside>

        <section className="record-pane">
          {detail === "loading" && (
            <div className="loading">
              <span className="loading-bar" aria-hidden="true" />
              <span>Retrieving record</span>
            </div>
          )}

          {detail === "pending" && (
            <div className="state">
              <h2 className="state-title">Not analysed yet</h2>
              <p>
                This action is on chain, but the analysis pipeline hasn’t reached it.
                Records are produced in batches every few hours — check back shortly.
              </p>
              <span className="mono">{selected}</span>
            </div>
          )}

          {detail === "offline" && (
            <div className="state">
              <h2 className="state-title">The record service is unreachable</h2>
              <p>
                Analyses are served from a public API that isn’t responding right now.
                Reload in a moment; nothing on your side needs fixing.
              </p>
            </div>
          )}

          {detail === "ok" && analysis && <ActionDetail analysis={analysis} />}

          {detail === "idle" && (
            <div className="state">
              <h2 className="state-title">Choose a proposal</h2>
              <p>
                Select an entry from the index to read its analysis — a plain-language
                summary first, then the evidence behind the score.
              </p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
