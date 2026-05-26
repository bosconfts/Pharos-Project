import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import RiskScoreGauge from "./RiskScoreGauge";
import ConflictPanel  from "./ConflictPanel";
import "./ActionDetail.css";

const STATUS_COLORS = {
  enacted:  "#68d391",
  ratified: "#90cdf4",
  expired:  "#fc8181",
  dropped:  "#718096",
  active:   "#fbd38d",
};

const RISK_COLORS = {
  "LOW RISK":    "#68d391",
  "MEDIUM RISK": "#fbd38d",
  "HIGH RISK":   "#fc8181",
};

export default function ActionDetail({ analysis }) {
  if (analysis.error) {
    return <div className="detail-error">Error: {analysis.error}</div>;
  }

  const summaries = analysis.summaries  || {};
  const sim       = analysis.similarity;
  const dr        = sim?.delivery_rate;
  const similar   = sim?.similar_proposals || [];
  const onChain   = analysis.on_chain;
  const risk      = analysis.risk_score;
  const conflict  = analysis.conflict;

  const pieData = dr && dr.total > 0 ? [
    { name: "Approved", value: dr.delivered, color: "#68d391" },
    { name: "Expired",  value: dr.expired,   color: "#fc8181" },
    { name: "Pending",  value: dr.pending,   color: "#fbd38d" },
  ].filter(d => d.value > 0) : [];

  return (
    <div className="detail-wrap">

      {/* Header */}
      <div className="detail-card">
        <div className="detail-header-row">
          <div className="detail-type">{analysis.action_type}</div>
          {risk && (
            <div className="risk-badge" style={{ color: RISK_COLORS[risk.level] || "#a0aec0" }}>
              {risk.total}/100 · {risk.level}
            </div>
          )}
        </div>
        <h2 className="detail-title">
          {analysis.pil_document?.title?.replace("PIL Analysis — ", "") ||
           analysis.gov_action_id}
        </h2>

        {summaries.one_liner && (
          <p className="detail-oneliner">{summaries.one_liner}</p>
        )}

        <div className="steps-row">
          {Object.entries(analysis.steps || {}).map(([k, v]) => (
            <span key={k} className={`step-badge ${v === "ok" || v === "submitted" ? "ok" : v === "skipped" || v === "not_applicable" ? "skip" : "err"}`}>
              {k}: {v}
            </span>
          ))}
        </div>
      </div>

      <div className="detail-grid">

        {/* Technical Analysis */}
        {summaries.technical && (
          <div className="detail-card">
            <h3>Technical Analysis</h3>
            <p className="detail-text">{summaries.technical}</p>
          </div>
        )}

        {/* Risk Score Gauge */}
        {risk && <RiskScoreGauge riskScore={risk} />}

        {/* Conflict of Interest */}
        {conflict && <ConflictPanel conflict={conflict} />}

        {/* Delivery Rate */}
        {dr && (
          <div className="detail-card">
            <h3>Similar Proposals History</h3>
            <p className="sim-summary">{sim.summary}</p>
            {pieData.length > 0 && (
              <div className="pie-wrap">
                <ResponsiveContainer width="100%" height={180}>
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value"
                         label={({ name, value }) => `${name}: ${value}`}>
                      {pieData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v, n) => [v, n]} />
                  </PieChart>
                </ResponsiveContainer>
                {dr.rate != null && (
                  <div className="delivery-rate">
                    <span className="rate-number">{dr.rate}%</span>
                    <span className="rate-label">delivery rate</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Similar Proposals */}
        {similar.length > 0 && (
          <div className="detail-card span-full">
            <h3>Similar Proposals</h3>
            <div className="similar-list">
              {similar.map((p) => (
                <div key={p.gov_action_id} className="similar-item">
                  <div className="similar-header">
                    <span className="similar-type">{p.action_type}</span>
                    <span className="similar-score">{(p.similarity * 100).toFixed(0)}% similar</span>
                    <span className="similar-status" style={{ color: STATUS_COLORS[p.status] || "#e2e8f0" }}>
                      ● {p.status}
                    </span>
                  </div>
                  <div className="similar-title">{p.title || p.one_liner || p.gov_action_id.slice(0, 30)}</div>
                  <div className="similar-id">{p.gov_action_id.slice(0, 20)}…</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* On-chain Publication */}
        {onChain?.tx_hash && (
          <div className="detail-card">
            <h3>On-chain Publication</h3>
            <div className="onchain-info">
              <span className="onchain-label">TX Hash</span>
              <a className="onchain-hash"
                 href={`https://cardanoscan.io/transaction/${onChain.tx_hash}`}
                 target="_blank" rel="noopener noreferrer">
                {onChain.tx_hash.slice(0, 32)}…
              </a>
            </div>
            {analysis.pil_document_hash && (
              <div className="onchain-info">
                <span className="onchain-label">PIL Doc Hash</span>
                <code className="onchain-hash">{analysis.pil_document_hash.slice(0, 32)}…</code>
              </div>
            )}
          </div>
        )}

        {/* Full Analysis */}
        {summaries.full && Object.keys(summaries.full).length > 0 && (
          <div className="detail-card span-full">
            <h3>Full Analysis</h3>
            <div className="full-summary">
              {Object.entries(summaries.full).map(([k, v]) => (
                v && (
                  <div key={k} className="full-section">
                    <span className="full-key">{k.replace(/_/g, " ")}</span>
                    <p className="full-val">{typeof v === "string" ? v : JSON.stringify(v)}</p>
                  </div>
                )
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
