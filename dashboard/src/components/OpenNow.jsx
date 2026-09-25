import "./OpenNow.css";

// O registro tem 155 análises e 152 já acabaram. Quem chega para decidir um
// voto precisava caçar as poucas que ainda estão abertas no meio do arquivo.
// Esta faixa responde primeiro a pergunta que traz o DRep ao site.

const EPOCH_DAYS = 5; // um epoch do Cardano dura 5 dias

export const isOpen = (a) =>
  !a.enacted_epoch && !a.ratified_epoch && !a.expired_epoch && !a.dropped_epoch;

function Remaining({ expiry, epoch }) {
  if (!expiry) return null;
  if (!epoch) return <span className="open-when">closes at epoch {expiry}</span>;

  const days = (expiry - epoch) * EPOCH_DAYS;
  if (days <= 0) return <span className="open-when is-urgent">closing now</span>;
  return (
    <span className={days <= 10 ? "open-when is-urgent" : "open-when"}>
      ~{days} days left
    </span>
  );
}

export default function OpenNow({ actions, epoch, selected, onSelect }) {
  const open = actions
    .filter(isOpen)
    .sort((a, b) => (a.epoch_expiry ?? 0) - (b.epoch_expiry ?? 0));

  if (!open.length) return null;

  return (
    <section className="open-band" aria-label="Proposals open for voting">
      <div className="open-inner">
        <p className="open-head">
          <span className="open-count">{open.length}</span>
          <span className="eyebrow">
            {open.length === 1 ? "proposal open for voting" : "proposals open for voting"}
          </span>
        </p>

        <ul className="open-list">
          {open.map((a) => (
            <li key={a.gov_action_id}>
              <button
                className={selected === a.gov_action_id ? "open-item is-active" : "open-item"}
                onClick={() => onSelect(a.gov_action_id)}
              >
                <span className="open-title">
                  {a.title || a.one_liner || `${a.gov_action_id.slice(0, 18)}…`}
                </span>
                <span className="open-meta">
                  <Remaining expiry={a.epoch_expiry} epoch={epoch} />
                  {a.risk_score != null && (
                    <span className="open-score">
                      {a.risk_score}<span className="open-score-unit">/100</span>
                    </span>
                  )}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
