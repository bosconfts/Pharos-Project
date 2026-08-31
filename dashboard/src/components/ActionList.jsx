import "./ActionList.css";

const TYPE_COLORS = {
  InfoAction:           "#90cdf4",
  TreasuryWithdrawals:  "#fbd38d",
  ParameterChange:      "#9ae6b4",
  HardForkInitiation:   "#fc8181",
  NoConfidence:         "#f687b3",
  NewConstitution:      "#b794f4",
  NewCommittee:         "#76e4f7",
  UpdateCommittee:      "#76e4f7",
};

function statusDot(action) {
  if (action.enacted_epoch)  return { color: "#68d391", label: "enacted" };
  if (action.ratified_epoch) return { color: "#90cdf4", label: "ratified" };
  if (action.expired_epoch)  return { color: "#fc8181", label: "expired" };
  if (action.dropped_epoch)  return { color: "#718096", label: "dropped" };
  return { color: "#fbd38d", label: "active" };
}

const RISK_COLOR = (score) =>
  score >= 70 ? "#68d391" : score >= 45 ? "#fbd38d" : "#fc8181";

export default function ActionList({ actions, state, tab, selected, onSelect }) {
  // Uma lista vazia por API fora do ar e uma lista vazia por não haver
  // propostas são situações diferentes, e antes as duas apareciam iguais.
  if (state === "loading") {
    return <div className="action-list-empty">Loading…</div>;
  }
  if (state === "offline") {
    return <div className="action-list-empty">API unavailable</div>;
  }
  if (!actions.length) {
    return (
      <div className="action-list-empty">
        {tab === "history"
          ? "No analyses published yet"
          : "No governance actions on-chain"}
      </div>
    );
  }

  return (
    <div className="action-list">
      {actions.map((a) => {
        const id      = a.gov_action_id;
        const dot     = statusDot(a);
        const color   = TYPE_COLORS[a.action_type] || "#e2e8f0";
        const isActive = selected === id;

        return (
          <button
            key={id}
            className={`action-item ${isActive ? "active" : ""}`}
            onClick={() => onSelect(id)}
          >
            <div className="action-header">
              <span className="action-type" style={{ color }}>{a.action_type}</span>
              {a.risk_score != null ? (
                <span className="action-status" style={{ color: RISK_COLOR(a.risk_score) }}>
                  {a.risk_score}/100
                </span>
              ) : (
                <span className="action-status" style={{ color: dot.color }}>● {dot.label}</span>
              )}
            </div>
            <div className="action-title">
              {a.title || a.one_liner || id.slice(0, 20) + "..."}
            </div>
            {a.completeness_score != null && (
              <div className="action-score">
                <div
                  className="score-bar"
                  style={{ width: `${a.completeness_score}%` }}
                />
                <span>{a.completeness_score}/100</span>
              </div>
            )}
            <div className="action-id">{id.slice(0, 16)}…</div>
          </button>
        );
      })}
    </div>
  );
}
