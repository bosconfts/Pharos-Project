# Risk Score (M4) Audit — 25 September 2026

Measured over the 158 proposals in the database. The decision is at the end.

## What each component actually separates

| Component | Points | Share at full marks | What it measures |
|---|---|---|---|
| Conflict of Interest | 20 | **100%** | Nothing: no check runs |
| Scope Clarity | 20 | **97%** | Whether title, abstract, motivation and rationale exist and exceed 50–100 characters |
| Documentation Quality | 10 | **87%** | Word count above 500 |
| Treasury Value | 15 | 65% | Share of the Net Change Limit requested. It discriminates |
| Proposer Track Record | 25 | 22% | Vote approval rate of **semantically similar** proposals (labelled "delivery" at the time) |
| Historical Precedent | 10 | 22% | **The same rate, again** |

## Conclusion

**50 of the 100 points are near-constant.** Conflict gives 20 to everyone, Scope Clarity is full for 97% of proposals and Documentation for 87%. They do not separate a good proposal from a poor one; they inflate the number.

The real variation comes from **two signals**: the approval rate of similar proposals, counted twice for 35 points, and the withdrawal size (15 points).

Distribution: scores from **50 to 100**, mean 82.7, standard deviation 11.6. Half the scale is never used, and no proposal ever reached HIGH RISK (< 45). A "76/100" looks like a fine judgement; in practice it says "not one of the largest, and an average history".

**The strongest name is the least true:** "Proposer Track Record" does not look at the proposer. It looks at proposals on a similar subject, by any author.

## Options

1. **Keep and document.** The page already shows the evidence behind each component. No cost, moderate honesty.
2. **Cut to what measures something.** Keep the real signals (the approval history once, not twice, and the withdrawal size), redistribute the weights, and rename the component to describe the calculation. The score starts to vary for real.
3. **Drop the single score.** Show the signals side by side without adding them up. More honest and more radical: a round number gives comfort the data does not support.

Recommendation: **2**. Option 3 is intellectually better, but a public record with no score loses its ability to flag quickly.

## Decision: option 2, with two signals (method 1.2.0)

Option 2 as first written also listed "clarity" among the real signals, but Scope Clarity is one of the components that gives full marks to 97% of proposals. That leaves **two**:

| Component | Points |
|---|---|
| Approval of Similar Proposals | 60, or 100 when there is no withdrawal |
| Treasury Withdrawal Size | 40, treasury withdrawals only |

A signal that does not apply is left out instead of being awarded for free. Without enough sample, a signal sits at the middle of its scale, so a proposal about which there is nothing to say lands in MEDIUM. Simulated over the stored signals of the 158 proposals:

| | Range | Mean | Std. dev. | LOW / MEDIUM / HIGH |
|---|---|---|---|---|
| 1.0.0 / 1.1.0 | 50–100 | 82.7 | 11.6 | 135 / 23 / 0 |
| 1.2.0 | 0–100 | 61.4 | 22.0 | 54 / 75 / 29 |

(The 154 anchored analyses do not change; the table only shows how the new method would score them.)

**Name correction, 30 September 2026.** The component first shipped as "Delivery of Similar Proposals", but what the function counts as delivered is ratified or enacted, which means approval by vote. It was renamed "Approval of Similar Proposals" before any 1.2.0 analysis was anchored.

**Open question for the next method:** 60 of the 100 points say "similar proposals tend to be approved". That predicts approval, not risk, and it is circular: voters consult the score, and the score repeats how people voted before.

## Constraint that applies to every option

The 154 anchored analyses are **never recalculated**: the document on chain is the record. A new method applies to new analyses, with `PIL_VERSION` going up and each page stating which version produced its number.
