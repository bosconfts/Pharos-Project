import "./ConflictPanel.css";

// "Who benefits" mostra fatos da chain, não acusações. Ele já exibiu HIGH em
// nove propostas a partir de uma checagem que comparava a carteira que pagou a
// submissão — em geral um administrador que submete em lote — com a do
// desenvolvedor. Quatro dessas comparavam uma carteira com ela mesma.
// Um achado real de uma checagem futura (severidade diferente de INFO) ainda
// aparece aqui, em destaque.

const SEV_TONE = { HIGH: "high", MEDIUM: "med", LOW: "low" };

const ada = (lovelace) =>
  `₳${Math.round((lovelace || 0) / 1_000_000).toLocaleString("en-US")}`;

const short = (s) => (s && s.length > 24 ? `${s.slice(0, 14)}…${s.slice(-6)}` : s);

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

function History({ b }) {
  const prior = b.prior || {};
  const n = prior.proposals || 0;

  // A soma de um contrato mistura dezenas de fornecedores: 98 de 112 pagamentos
  // da base caem em contratos de escrow. Aqui só a contagem, nunca o valor.
  if (b.is_script) {
    return (
      <p className="payee-note">
        A smart contract, not a personal wallet — funds are released from it
        rather than paid out directly.
        {n > 0 && ` The same contract received ${plural(n, "earlier withdrawal", "earlier withdrawals")}.`}
      </p>
    );
  }

  if (!prior.proposals && prior.proposals !== 0) return null;
  if (n === 0) {
    return <p className="payee-note">No earlier treasury withdrawals to this wallet.</p>;
  }
  return (
    <p className="payee-note">
      {plural(n, "earlier treasury proposal", "earlier treasury proposals")} to this
      wallet · {prior.enacted || 0} enacted · {ada(prior.received_lovelace)} received.
    </p>
  );
}

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

  // Linhas antigas trazem só as stake addresses, sem valor por carteira.
  const beneficiaries =
    conflict.beneficiaries ||
    (conflict.beneficiary_stakes || []).map((s) => ({ stake_address: s }));

  if (status !== "ok" || !beneficiaries.length) {
    return (
      <section className="panel">
        <h3 className="eyebrow">Who benefits</h3>
        <p className="panel-quiet">
          The recipients of this withdrawal could not be read from the chain.
        </p>
      </section>
    );
  }

  const findings  = conflicts.filter((c) => c.severity !== "INFO");
  const submitter = proposer_addresses[0];

  return (
    <section className="panel">
      <h3 className="eyebrow">Who benefits</h3>

      {total_withdrawal_lovelace > 0 && (
        <p className="panel-figure">
          <span className="panel-figure-num">{ada(total_withdrawal_lovelace)}</span>
          <span className="panel-figure-label">requested from the treasury</span>
        </p>
      )}

      {submitter && (
        <div className="panel-row">
          <span className="panel-row-label">Submitted by</span>
          <a
            className="panel-link mono"
            href={`https://cardanoscan.io/address/${submitter}`}
            target="_blank"
            rel="noopener noreferrer"
            title={submitter}
          >
            {short(submitter)}
          </a>
        </div>
      )}

      <div className="panel-row panel-row-stack">
        <span className="panel-row-label">Paid to</span>
        <ul className="payee-list">
          {beneficiaries.map((b) => (
            <li key={b.stake_address} className="payee">
              <p className="payee-head">
                {b.amount_lovelace != null && (
                  <span className="payee-amount">{ada(b.amount_lovelace)}</span>
                )}
                <a
                  className="panel-link mono"
                  href={`https://cardanoscan.io/stakekey/${b.stake_address}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={b.stake_address}
                >
                  {short(b.stake_address)}
                </a>
                {b.is_submitter && <span className="payee-tag">the submitter’s own wallet</span>}
              </p>
              <History b={b} />
            </li>
          ))}
        </ul>
      </div>

      {/* Os pontos vêm de step11_risk_score.conflict_component — se lá mudar,
          esta legenda tem de mudar junto. Vale só para análises do método
          1.1.0: o 1.2.0 não pontua conflito. Ela nunca existiu: a página mostrava
          o selo "HIGH" sem dizer o que separava um HIGH de um MEDIUM, nem que
          um HIGH zerava 20 pontos do score. */}
      {findings.length > 0 ? (
        <p className="panel-note">
          <strong>How findings are graded.</strong> HIGH removes all 20 points of
          the conflict component; MEDIUM leaves 8 of 20; LOW leaves 14 of 20.
          INFO is disclosure and costs nothing.
        </p>
      ) : (
        <p className="panel-note">
          No conflict-of-interest check runs today, so the absence of findings
          here is not a clearance — what is recorded above is who is paid, not a
          judgement of it.
        </p>
      )}

      {findings.length > 0 && (
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
    </section>
  );
}
