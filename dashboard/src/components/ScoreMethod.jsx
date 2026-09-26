import "./ScoreMethod.css";

// Espelha core/step11_risk_score.py (método 1.2.0) — se lá mudar, aqui muda
// junto. A página não explicava o método em lugar nenhum; com duas versões
// convivendo, um 82 do 1.1.0 aparecia ao lado de um 61 do 1.2.0 e o leitor
// concluía o contrário do que os números dizem.
const COMPONENTS = [
  {
    label:  "Delivery of similar proposals",
    points: "60",
    note:   "100 when no treasury funds are requested",
    what:   "Of the most similar past proposals, by any author, the share that delivered. " +
            "Needs at least three that have concluded; with fewer, it scores half.",
  },
  {
    label:  "Treasury withdrawal size",
    points: "40",
    note:   "treasury withdrawals only",
    what:   "The amount requested against the Net Change Limit of 300M ADA: under 1% " +
            "scores 40, under 3% 32, under 7% 21, under 15% 11, and above that 0.",
  },
];

const LEVELS = [
  { tone: "low",  range: "70–100", label: "Low risk" },
  { tone: "med",  range: "45–69",  label: "Medium risk" },
  { tone: "high", range: "0–44",   label: "High risk" },
];

export default function ScoreMethod({ onClose }) {
  return (
    <section id="how-scored" className="method-band" aria-labelledby="how-scored-title">
      <div className="method-inner">
        <div className="method-head">
          <h2 id="how-scored-title" className="method-title">How the score works</h2>
          <button className="method-close" onClick={onClose} aria-label="Close">Close</button>
        </div>

        <p className="method-lede">
          A score from 0 to 100, where higher means lower risk. It is built only from
          signals that actually separate one proposal from another. A signal that does
          not apply is left out rather than awarded for free, so a proposal that asks
          for no funds is judged on delivery alone.
        </p>

        <ol className="method-list">
          {COMPONENTS.map((c) => (
            <li key={c.label} className="method-row">
              <div className="method-row-head">
                <span className="method-label">{c.label}</span>
                <span className="method-points">
                  {c.points} <span className="method-unit">pts</span>
                </span>
              </div>
              <p className="method-note">{c.note}</p>
              <p className="method-what">{c.what}</p>
            </li>
          ))}
        </ol>

        <dl className="method-levels">
          {LEVELS.map((l) => (
            <div key={l.tone} className={`method-level tone-${l.tone}`}>
              <dt>{l.label}</dt>
              <dd className="mono">{l.range}</dd>
            </div>
          ))}
        </dl>

        <p className="method-fine">
          The score does not judge conflicts of interest. Who receives treasury funds
          is listed on each proposal under “Who benefits”, without a verdict.
        </p>

        <p className="method-fine">
          <strong>Earlier analyses use a different method.</strong> Records produced
          under PIL v1.1.0 summed six components, three of which gave nearly every
          proposal full marks, so those scores ran from 50 to 100 and read higher. They
          are never recalculated, because the document anchored on chain is the record.
          The two versions are not comparable, and each proposal shows which one
          produced its number.
        </p>
      </div>
    </section>
  );
}
