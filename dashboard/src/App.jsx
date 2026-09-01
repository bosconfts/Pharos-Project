import { useState, useEffect } from "react";
import { fetchStats, fetchHistory, fetchLive, fetchAnalysis, ApiError } from "./api";
import ActionList from "./components/ActionList";
import ActionDetail from "./components/ActionDetail";
import "./App.css";

export default function App() {
  const [stats, setStats]       = useState(null);
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

  async function loadActions(mode) {
    setTab(mode);
    setSelected(null);
    setAnalysis(null);
    setDetail("idle");
    setList("loading");
    try {
      const data = mode === "analysed" ? await fetchHistory(50) : await fetchLive(20);
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
          <ActionList
            actions={actions}
            state={listState}
            tab={tab}
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
