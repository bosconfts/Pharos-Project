import "./RiskScoreGauge.css";

const tone = (s) => (s >= 70 ? "low" : s >= 45 ? "med" : "high");

// Em linguagem simples, para quem não acompanha governança de perto.
const PLAIN = {
  low:  "Nothing in the record stands out as a concern.",
  med:  "Parts of the record are thin or unresolved. Worth reading before voting.",
  high: "The record raises concerns that deserve an answer before this is funded.",
};

export default function RiskScoreGauge({ riskScore }) {
  if (!riskScore) return null;

  const { total, max, level, components } = riskScore;
  const t = tone(total);
  const entries = Object.entries(components || {});

  return (
    <section className={`verdict tone-${t}`}>
      <div className="verdict-head">
        <div className="verdict-figure">
          <span className="verdict-num">{total}</span>
          <span className="verdict-denom">/{max}</span>
        </div>
        <div className="verdict-read">
          <p className="verdict-level">{level}</p>
          <p className="verdict-plain">{PLAIN[t]}</p>
        </div>
      </div>

      <div className="verdict-scale" aria-hidden="true">
        <span className="verdict-scale-fill" style={{ width: `${(total / max) * 100}%` }} />
      </div>

      <h3 className="eyebrow verdict-breakdown-label">How the score is made</h3>

      <ol className="ledger">
        {entries.map(([key, c]) => (
          <li key={key} className="ledger-row">
            <div className="ledger-line">
              <span className="ledger-label">{c.label}</span>
              <span className="ledger-leader" aria-hidden="true" />
              <span className="ledger-weight">{c.weight}</span>
              <span className={`ledger-score tone-${tone((c.score / c.max) * 100)}`}>
                {c.score}<span className="ledger-of">/{c.max}</span>
              </span>
            </div>
            <p className="ledger-evidence">{c.evidence}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
