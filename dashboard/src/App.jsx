import { useState, useEffect } from "react";
import { fetchStats, fetchHistory, fetchLive, fetchAnalysis } from "./api";
import ActionList from "./components/ActionList";
import ActionDetail from "./components/ActionDetail";
import StatsBar from "./components/StatsBar";
import "./App.css";

export default function App() {
  const [stats, setStats]         = useState(null);
  const [actions, setActions]     = useState([]);
  const [selected, setSelected]   = useState(null);
  const [analysis, setAnalysis]   = useState(null);
  const [loading, setLoading]     = useState(false);
  const [tab, setTab]             = useState("history"); // "history" | "live"

  useEffect(() => {
    fetchStats().then(setStats).catch(() => {});
    loadActions("history");
  }, []);

  async function loadActions(mode) {
    setTab(mode);
    setSelected(null);
    setAnalysis(null);
    if (mode === "history") {
      const data = await fetchHistory(50).catch(() => ({ actions: [] }));
      setActions(data.actions || []);
    } else {
      const data = await fetchLive(20).catch(() => ({ actions: [] }));
      setActions(data.actions || []);
    }
  }

  async function selectAction(id) {
    setSelected(id);
    setAnalysis(null);
    setLoading(true);
    try {
      const data = await fetchAnalysis(id);
      setAnalysis(data);
    } catch (e) {
      setAnalysis({ error: String(e) });
    } finally {
      setLoading(false);
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
            {stats && (
              <span className="stat-badge">{stats.total_analyzed} analyzed</span>
            )}
          </div>
        </div>
      </header>

      {stats && <StatsBar stats={stats} />}

      <main className="main">
        <section className="sidebar">
          <div className="tab-bar">
            <button
              className={tab === "history" ? "tab active" : "tab"}
              onClick={() => loadActions("history")}
            >
              PIL History
            </button>
            <button
              className={tab === "live" ? "tab active" : "tab"}
              onClick={() => loadActions("live")}
            >
              Live
            </button>
          </div>
          <ActionList
            actions={actions}
            selected={selected}
            onSelect={selectAction}
          />
        </section>

        <section className="detail">
          {loading && (
            <div className="loading">
              <div className="spinner" />
              <p>Analyzing with Claude...</p>
            </div>
          )}
          {!loading && analysis && (
            <ActionDetail analysis={analysis} />
          )}
          {!loading && !analysis && (
            <div className="empty">
              <p>Select a governance action to view the PIL analysis</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
