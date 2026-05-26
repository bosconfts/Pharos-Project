import "./RiskScoreGauge.css";

const LEVEL_COLOR = {
  "LOW RISK":    "#68d391",
  "MEDIUM RISK": "#fbd38d",
  "HIGH RISK":   "#fc8181",
};

const COMPONENT_ICONS = {
  proposer_track_record:  "📊",
  scope_clarity:          "📋",
  conflict_of_interest:   "🔍",
  treasury_value:         "💰",
  documentation_quality:  "📝",
  historical_precedent:   "🕐",
};

export default function RiskScoreGauge({ riskScore }) {
  if (!riskScore) return null;

  const { total, max, level, components } = riskScore;
  const color  = LEVEL_COLOR[level] || "#a0aec0";
  const pct    = Math.round((total / max) * 100);

  return (
    <div className="risk-card">
      <h3>PIL Risk Score</h3>

      <div className="risk-header">
        <div className="risk-gauge">
          <svg viewBox="0 0 120 70" className="gauge-svg">
            {/* Background arc */}
            <path d="M10,60 A50,50 0 0,1 110,60" stroke="#2d3748" strokeWidth="10" fill="none" />
            {/* Colored arc */}
            <path
              d="M10,60 A50,50 0 0,1 110,60"
              stroke={color}
              strokeWidth="10"
              fill="none"
              strokeDasharray={`${pct * 1.57} 157`}
              strokeLinecap="round"
            />
            <text x="60" y="58" textAnchor="middle" fill={color} fontSize="22" fontWeight="800">
              {total}
            </text>
            <text x="60" y="68" textAnchor="middle" fill="#718096" fontSize="8">
              / {max}
            </text>
          </svg>
        </div>
        <div className="risk-level" style={{ color }}>
          {level}
        </div>
      </div>

      <div className="risk-components">
        {components && Object.entries(components).map(([key, comp]) => (
          <div key={key} className="risk-row">
            <span className="risk-icon">{COMPONENT_ICONS[key] || "•"}</span>
            <div className="risk-info">
              <div className="risk-comp-header">
                <span className="risk-comp-label">{comp.label}</span>
                <span className="risk-comp-weight">{comp.weight}</span>
                <span className="risk-comp-score" style={{ color: comp.score >= comp.max * 0.6 ? "#68d391" : comp.score >= comp.max * 0.3 ? "#fbd38d" : "#fc8181" }}>
                  {comp.score}/{comp.max}
                </span>
              </div>
              <div className="risk-bar-bg">
                <div
                  className="risk-bar-fill"
                  style={{
                    width: `${(comp.score / comp.max) * 100}%`,
                    background: comp.score >= comp.max * 0.6 ? "#68d391" : comp.score >= comp.max * 0.3 ? "#fbd38d" : "#fc8181",
                  }}
                />
              </div>
              <span className="risk-evidence">{comp.evidence}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
