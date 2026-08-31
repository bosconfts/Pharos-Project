import "./ConflictPanel.css";

const SEV_COLOR = {
  HIGH:   "#fc8181",
  MEDIUM: "#fbd38d",
  LOW:    "#90cdf4",
  INFO:   "#a0aec0",
};

// INFO é divulgação, não achado (ex.: o proponente é beneficiário declarado,
// que é o desenho normal de uma retirada de tesouraria). Separar os dois evita
// que o painel pareça acusar onde só está informando.
const isFinding = (c) => c.severity !== "INFO";

export default function ConflictPanel({ conflict }) {
  if (!conflict) return null;

  const { status, conflicts = [], proposer_addresses = [], beneficiary_stakes = [], total_withdrawal_lovelace } = conflict;

  if (status === "not_applicable") {
    return (
      <div className="conflict-card">
        <h3>Conflict of Interest</h3>
        <p className="conflict-na">Not applicable for this proposal type.</p>
      </div>
    );
  }

  const ada = total_withdrawal_lovelace ? (total_withdrawal_lovelace / 1_000_000).toLocaleString() : null;
  const findings    = conflicts.filter(isFinding);
  const disclosures = conflicts.filter((c) => !isFinding(c));

  return (
    <div className="conflict-card">
      <h3>Conflict of Interest</h3>

      {ada && (
        <div className="conflict-meta">
          <span className="conflict-meta-label">Total withdrawal</span>
          <span className="conflict-meta-value">₳ {ada}</span>
        </div>
      )}

      {proposer_addresses.length > 0 && (
        <div className="conflict-meta">
          <span className="conflict-meta-label">Proposer wallet</span>
          <span className="conflict-addr">{proposer_addresses[0].slice(0, 24)}…</span>
        </div>
      )}

      {findings.length === 0 && (
        <div className="conflict-clean">
          <span className="conflict-clean-icon">✅</span>
          <span>No undisclosed financial relationships detected</span>
        </div>
      )}

      {disclosures.length > 0 && (
        <div className="conflict-list">
          {disclosures.map((c, i) => (
            <div key={`d${i}`} className="conflict-item">
              <div className="conflict-item-header">
                <span className="conflict-sev" style={{ color: SEV_COLOR.INFO }}>
                  ● DISCLOSURE
                </span>
                <span className="conflict-type">{c.type?.replace(/_/g, " ")}</span>
              </div>
              <p className="conflict-desc">{c.description}</p>
              {c.note && <p className="conflict-desc">{c.note}</p>}
            </div>
          ))}
        </div>
      )}

      {findings.length > 0 && (
        <div className="conflict-list">
          {findings.map((c, i) => (
            <div key={i} className="conflict-item">
              <div className="conflict-item-header">
                <span className="conflict-sev" style={{ color: SEV_COLOR[c.severity] || "#a0aec0" }}>
                  ● {c.severity}
                </span>
                <span className="conflict-type">{c.type?.replace(/_/g, " ")}</span>
              </div>
              <p className="conflict-desc">{c.description}</p>
              {c.evidence_txhash && (
                <a
                  className="conflict-txhash"
                  href={`https://cardanoscan.io/transaction/${c.evidence_txhash}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Evidence: {c.evidence_txhash.slice(0, 24)}…
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
