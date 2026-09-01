import "./ActionList.css";

// O tipo da ação era uma de oito cores. Vira texto: a distinção é semântica,
// não cromática, e oito cores competindo é o que fazia a página parecer ruído.
const TYPE_LABEL = {
  InfoAction:          "Info",
  TreasuryWithdrawals: "Treasury",
  ParameterChange:     "Parameter",
  HardForkInitiation:  "Hard fork",
  NoConfidence:        "No confidence",
  NewConstitution:     "Constitution",
  NewCommittee:        "Committee",
  UpdateCommittee:     "Committee",
};

const riskTone = (s) => (s >= 70 ? "low" : s >= 45 ? "med" : "high");

function status(a) {
  if (a.enacted_epoch)  return "Enacted";
  if (a.ratified_epoch) return "Ratified";
  if (a.expired_epoch)  return "Expired";
  if (a.dropped_epoch)  return "Dropped";
  return "Open";
}

export default function ActionList({ actions, state, tab, selected, onSelect }) {
  if (state === "loading") {
    return <p className="index-note">Loading index…</p>;
  }
  if (state === "offline") {
    return <p className="index-note">Index unavailable. Reload in a moment.</p>;
  }
  if (!actions.length) {
    return (
      <p className="index-note">
        {tab === "analysed"
          ? "No analyses published yet."
          : "No governance actions on chain."}
      </p>
    );
  }

  return (
    <ol className="index-list">
      {actions.map((a) => {
        const id = a.gov_action_id;
        const isActive = selected === id;
        const score = a.risk_score;

        return (
          <li key={id}>
            <button
              className={isActive ? "entry is-active" : "entry"}
              onClick={() => onSelect(id)}
              aria-current={isActive ? "true" : undefined}
            >
              <span className="entry-meta">
                <span className="entry-type">{TYPE_LABEL[a.action_type] || a.action_type}</span>
                <span className="entry-status">{status(a)}</span>
              </span>

              <span className="entry-title">
                {a.title || a.one_liner || `${id.slice(0, 18)}…`}
              </span>

              {score != null && (
                <span className={`entry-score tone-${riskTone(score)}`}>
                  <span className="entry-score-num">{score}</span>
                  <span className="entry-score-unit">/100</span>
                </span>
              )}
            </button>
          </li>
        );
      })}
    </ol>
  );
}
