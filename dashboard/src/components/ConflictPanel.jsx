import "./ConflictPanel.css";

// INFO é divulgação, não achado: numa retirada de tesouraria o normal é que
// quem propõe receba os fundos. Separar os dois evita que o painel pareça
// acusar onde só está informando.
const isFinding = (c) => c.severity !== "INFO";

const SEV_TONE = { HIGH: "high", MEDIUM: "med", LOW: "low" };

export default function ConflictPanel({ conflict }) {
  if (!conflict) return null;

  const {
    status,
    conflicts = [],
    proposer_addresses = [],
    total_withdrawal_lovelace,
  } = conflict;

  if (status === "not_applicable") {
    return (
      <section className="panel">
        <h3 className="eyebrow">Who benefits</h3>
        <p className="panel-quiet">
          This proposal moves no treasury funds, so there are no beneficiaries to
          cross-check.
        </p>
      </section>
    );
  }

  const findings    = conflicts.filter(isFinding);
  const disclosures = conflicts.filter((c) => !isFinding(c));
  const ada = total_withdrawal_lovelace
    ? (total_withdrawal_lovelace / 1_000_000).toLocaleString("en-US")
    : null;

  return (
    <section className="panel">
      <h3 className="eyebrow">Who benefits</h3>

      {ada && (
        <p className="panel-figure">
          <span className="panel-figure-num">₳{ada}</span>
          <span className="panel-figure-label">requested from the treasury</span>
        </p>
      )}

      {proposer_addresses.length > 0 && (
        <p className="panel-addr mono">{proposer_addresses[0]}</p>
      )}

      {findings.length === 0 ? (
        <p className="panel-verdict">
          No undisclosed financial relationship found between the proposer and the
          wallets receiving these funds.
        </p>
      ) : (
        <ul className="finding-list">
          {findings.map((c, i) => (
            <li key={i} className={`finding tone-${SEV_TONE[c.severity] || "low"}`}>
              <span className="finding-sev">{c.severity}</span>
              <p className="finding-desc">{c.description}</p>
              {c.evidence_txhash && (
                <a
                  className="finding-evidence mono"
                  href={`https://cardanoscan.io/transaction/${c.evidence_txhash}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {c.evidence_txhash.slice(0, 28)}…
                </a>
              )}
            </li>
          ))}
        </ul>
      )}

      {disclosures.length > 0 && (
        <div className="disclosures">
          <h4 className="eyebrow">Disclosed</h4>
          {disclosures.map((c, i) => (
            <p key={i} className="disclosure">
              {c.description}
              {c.note && <span className="disclosure-note">{c.note}</span>}
            </p>
          ))}
        </div>
      )}
    </section>
  );
}
