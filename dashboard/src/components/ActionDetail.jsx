import RiskScoreGauge from "./RiskScoreGauge";
import ConflictPanel from "./ConflictPanel";
import "./ActionDetail.css";

const TYPE_LABEL = {
  InfoAction:          "Info action",
  TreasuryWithdrawals: "Treasury withdrawal",
  ParameterChange:     "Parameter change",
  HardForkInitiation:  "Hard fork",
  NoConfidence:        "No confidence",
  NewConstitution:     "Constitution",
  NewCommittee:        "Committee",
  UpdateCommittee:     "Committee update",
};

export default function ActionDetail({ analysis }) {
  const summaries = analysis.summaries || {};
  const sim       = analysis.similarity;
  const dr        = sim?.delivery_rate;
  const similar   = sim?.similar_proposals || [];
  const onChain   = analysis.on_chain;
  const risk      = analysis.risk_score;
  const full      = summaries.full || {};

  const title =
    analysis.cip108_title ||
    analysis.pil_document?.title?.replace("PIL Analysis — ", "") ||
    analysis.gov_action_id;

  return (
    <article className="record">
      {/* Abertura: o que é, em linguagem simples, antes de qualquer número. */}
      <header className="record-head">
        <p className="eyebrow">
          {TYPE_LABEL[analysis.action_type] || analysis.action_type}
        </p>
        <h2 className="record-title">{title}</h2>
        {summaries.one_liner && summaries.one_liner !== title && (
          <p className="record-lede">{summaries.one_liner}</p>
        )}
      </header>

      {risk && <RiskScoreGauge riskScore={risk} />}

      <div className="record-grid">
        {analysis.conflict && <ConflictPanel conflict={analysis.conflict} />}

        {dr && (
          <section className="panel">
            <h3 className="eyebrow">What happened before</h3>
            {dr.total > 0 ? (
              <>
                <p className="precedent-figure">
                  <span className="precedent-num">{dr.total}</span>
                  <span className="precedent-label">
                    comparable {dr.total === 1 ? "proposal" : "proposals"} on record
                  </span>
                </p>
                <div className="precedent-bar" aria-hidden="true">
                  {dr.delivered > 0 && (
                    <span className="seg seg-approved" style={{ flex: dr.delivered }} />
                  )}
                  {dr.expired > 0 && (
                    <span className="seg seg-expired" style={{ flex: dr.expired }} />
                  )}
                  {dr.pending > 0 && (
                    <span className="seg seg-pending" style={{ flex: dr.pending }} />
                  )}
                </div>
                <ul className="precedent-key">
                  {dr.delivered > 0 && <li><i className="k k-approved" />{dr.delivered} approved</li>}
                  {dr.expired  > 0 && <li><i className="k k-expired" />{dr.expired} expired</li>}
                  {dr.pending  > 0 && <li><i className="k k-pending" />{dr.pending} still open</li>}
                </ul>
              </>
            ) : (
              <p className="panel-quiet">
                Nothing comparable in the record yet. As more proposals are analysed,
                this section fills in.
              </p>
            )}
          </section>
        )}
      </div>

      {summaries.technical && (
        <section className="panel">
          <h3 className="eyebrow">In detail</h3>
          <p className="prose">{summaries.technical}</p>
        </section>
      )}

      {Object.keys(full).length > 0 && (
        <section className="panel">
          <h3 className="eyebrow">Full analysis</h3>
          <dl className="full">
            {Object.entries(full).map(([k, v]) =>
              v ? (
                <div key={k} className="full-item">
                  <dt>{k.replace(/_/g, " ")}</dt>
                  <dd>{typeof v === "string" ? v : JSON.stringify(v)}</dd>
                </div>
              ) : null
            )}
          </dl>
        </section>
      )}

      {similar.length > 0 && (
        <section className="panel">
          <h3 className="eyebrow">Comparable proposals</h3>
          <ul className="similar">
            {similar.map((p) => (
              <li key={p.gov_action_id} className="similar-item">
                <span className="similar-title">
                  {p.title || p.one_liner || `${p.gov_action_id.slice(0, 24)}…`}
                </span>
                <span className="similar-leader" aria-hidden="true" />
                <span className="similar-status">{p.status}</span>
                <span className="similar-match mono">{Math.round(p.similarity * 100)}%</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Proveniência: como verificar que esta análise é a que foi ancorada. */}
      <section className="panel provenance">
        <h3 className="eyebrow">Provenance</h3>
        <dl className="prov">
          <div>
            <dt>Governance action</dt>
            <dd className="mono">{analysis.gov_action_id}</dd>
          </div>
          {analysis.anchor_hash_valid !== undefined && (
            <div>
              <dt>Proposal document</dt>
              <dd>
                {analysis.anchor_hash_valid
                  ? "Hash matches the on-chain anchor"
                  : "Hash does not match the on-chain anchor"}
              </dd>
            </div>
          )}
          {analysis.pil_document_hash && (
            <div>
              <dt>This analysis</dt>
              <dd className="mono">{analysis.pil_document_hash}</dd>
            </div>
          )}
          <div>
            <dt>On-chain record</dt>
            <dd>
              {onChain?.tx_hash ? (
                <a
                  className="mono"
                  href={`https://cardanoscan.io/transaction/${onChain.tx_hash}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {onChain.tx_hash}
                </a>
              ) : (
                "Not anchored yet"
              )}
            </dd>
          </div>
        </dl>
      </section>
    </article>
  );
}
