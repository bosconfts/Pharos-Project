import "./StatsBar.css";

export default function StatsBar({ stats }) {
  return (
    <div className="statsbar">
      <div className="stat">
        <span className="stat-value">{stats.total_analyzed ?? "—"}</span>
        <span className="stat-label">Proposals analyzed</span>
      </div>
      <div className="stat-divider" />
      <div className="stat">
        <span className="stat-value" style={{ color: "#68d391" }}>mainnet</span>
        <span className="stat-label">Cardano Network</span>
      </div>
      <div className="stat-divider" />
      <div className="stat">
        <span className="stat-value" style={{ color: "#fbd38d" }}>PIL v1.0</span>
        <span className="stat-label">Pipeline version</span>
      </div>
    </div>
  );
}
