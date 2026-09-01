import { useState, useEffect } from "react";
import { fetchStats, fetchHistory, fetchLive, fetchAnalysis, ApiError } from "./api";
import ActionList from "./components/ActionList";
import ActionDetail from "./components/ActionDetail";
import StatsBar from "./components/StatsBar";
import "./App.css";

export default function App() {
  const [stats, setStats]       = useState(null);
  const [actions, setActions]   = useState([]);
  const [listState, setList]    = useState("loading"); // loading | ok | offline
  const [selected, setSelected] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [detail, setDetail]     = useState("idle"); // idle | loading | ok | pending | offline
  const [tab, setTab]           = useState("history");

  useEffect(() => {
    fetchStats().then(setStats).catch(() => setStats(null));
    loadActions("history");
  }, []);

  async function loadActions(mode) {
    setTab(mode);
    setSelected(null);
    setAnalysis(null);
    setDetail("idle");
    setList("loading");
    try {
      const data = mode === "history" ? await fetchHistory(50) : await fetchLive(20);
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
      // 404 é o caso normal para uma action que o worker ainda não alcançou.
      setDetail(e instanceof ApiError && e.status === 404 ? "pending" : "offline");
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-pill">PIL</span>
            <span className="logo-text">Proposal Intelligence Layer</span>
          </div>
          <div className="header-meta">
            <span className="network-badge">mainnet</span>
            {stats && <span className="stat-badge">{stats.total_analyzed} analyzed</span>}
          </div>
        </div>
      </header>

      {stats && <StatsBar stats={stats} />}

      <main className="main">
        <section className="sidebar">
          <div className="tab-bar">
            <button className={tab === "history" ? "tab active" : "tab"}
                    onClick={() => loadActions("history")}>
              PIL History
            </button>
            <button className={tab === "live" ? "tab active" : "tab"}
                    onClick={() => loadActions("live")}>
              Live
            </button>
          </div>
          <ActionList
            actions={actions}
            state={listState}
            tab={tab}
            selected={selected}
            onSelect={selectAction}
          />
        </section>

        <section className="detail">
          {detail === "loading" && (
            <div className="loading">
              <div className="spinner" />
              <p>Loading analysis…</p>
            </div>
          )}

          {detail === "pending" && (
            <div className="empty">
              <p className="empty-title">Analysis not available yet</p>
              <p>
                This governance action is on-chain but the PIL worker hasn’t
                processed it yet. Analyses are generated in batches every few hours.
              </p>
              <code className="empty-id">{selected}</code>
            </div>
          )}

          {detail === "offline" && (
            <div className="empty">
              <p className="empty-title">Can’t reach the PIL API</p>
              <p>The analysis service is unavailable. Please try again shortly.</p>
            </div>
          )}

          {detail === "ok" && analysis && <ActionDetail analysis={analysis} />}

          {detail === "idle" && (
            <div className="empty">
              <p>Select a governance action to view the PIL analysis</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
