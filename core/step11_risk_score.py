"""
Step 11 — Risk Score Engine (M4)
Computes an auditable 0–100 score across 6 components.
Higher score = lower risk / better quality proposal.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from step8_similarity import find_similar, delivery_rate

NCL_LOVELACE = 300_000_000_000_000  # 300 million ADA


def compute_risk_score(record: dict, conflicts: list | None = None, similar: list | None = None) -> dict:
    """
    Compute M4 Risk Score for a governance action record.
    Args:
        record:    row from governance_actions table (dict)
        conflicts: output of detect_conflicts (list of conflict dicts)
        similar:   output of find_similar (list of similar proposal dicts)
    Returns dict with total (0-100), level, and per-component breakdown.
    """
    if conflicts is None:
        conflicts = []
    if similar is None:
        similar = find_similar(record.get("gov_action_id", ""), top_n=5)

    dr          = delivery_rate(similar)
    action_type = record.get("action_type", "")
    components  = {}

    # ── 1. Proposer Track Record (25 pts) ─────────────────────────────────────
    # Proxy: delivery rate of semantically similar proposals
    if dr["total"] == 0:
        c1 = 13
        c1_ev = "No historical data for similar proposals (neutral)"
    else:
        rate = dr["rate"] if dr["rate"] is not None else 50
        c1   = round(rate / 100 * 25)
        c1_ev = f"{dr['delivered']}/{dr['total']} similar proposals delivered ({rate}%)"
    components["proposer_track_record"] = {
        "label":    "Proposer Track Record",
        "score":    c1,
        "max":      25,
        "weight":   "25%",
        "evidence": c1_ev,
    }

    # ── 2. Scope Clarity (20 pts) ─────────────────────────────────────────────
    c2      = 0
    c2_tags = []
    if record.get("title") and len(record["title"]) > 10:
        c2 += 5; c2_tags.append("Title ✓")
    else:
        c2_tags.append("Title ✗")
    if record.get("abstract") and len(record["abstract"]) > 100:
        c2 += 5; c2_tags.append("Abstract ✓")
    else:
        c2_tags.append("Abstract ✗")
    if record.get("motivation") and len(record["motivation"]) > 50:
        c2 += 5; c2_tags.append("Motivation ✓")
    else:
        c2_tags.append("Motivation ✗")
    if record.get("rationale") and len(record["rationale"]) > 50:
        c2 += 5; c2_tags.append("Rationale ✓")
    else:
        c2_tags.append("Rationale ✗")
    components["scope_clarity"] = {
        "label":    "Scope Clarity",
        "score":    c2,
        "max":      20,
        "weight":   "20%",
        "evidence": "  ·  ".join(c2_tags),
    }

    # ── 3. Conflict of Interest (20 pts) ──────────────────────────────────────
    high = sum(1 for c in conflicts if c.get("severity") == "HIGH")
    med  = sum(1 for c in conflicts if c.get("severity") == "MEDIUM")
    low  = sum(1 for c in conflicts if c.get("severity") == "LOW")

    if action_type != "TreasuryWithdrawals":
        c3    = 20
        c3_ev = "Not applicable (no direct financial beneficiaries)"
    elif not conflicts:
        c3    = 20
        c3_ev = "No financial conflicts detected"
    elif high > 0:
        c3    = 0
        c3_ev = f"{high} HIGH severity conflict(s) detected"
    elif med > 0:
        c3    = 8
        c3_ev = f"{med} MEDIUM + {low} LOW conflict(s) detected"
    else:
        c3    = 14
        c3_ev = f"{low} LOW severity conflict(s) detected"
    components["conflict_of_interest"] = {
        "label":    "Conflict of Interest",
        "score":    c3,
        "max":      20,
        "weight":   "20%",
        "evidence": c3_ev,
    }

    # ── 4. Treasury Value (15 pts) ────────────────────────────────────────────
    if action_type != "TreasuryWithdrawals":
        c4    = 15
        c4_ev = "Not a treasury withdrawal"
    else:
        lovelace = record.get("withdrawal_amount") or 0
        if lovelace > 0:
            pct = lovelace / NCL_LOVELACE * 100
            if   pct < 1:   c4 = 15
            elif pct < 3:   c4 = 12
            elif pct < 7:   c4 = 8
            elif pct < 15:  c4 = 4
            else:           c4 = 0
            c4_ev = f"{pct:.2f}% of NCL (300M ADA limit)"
        else:
            c4    = 8
            c4_ev = "Withdrawal amount unknown (neutral)"
    components["treasury_value"] = {
        "label":    "Treasury Value",
        "score":    c4,
        "max":      15,
        "weight":   "15%",
        "evidence": c4_ev,
    }

    # ── 5. Documentation Quality (10 pts) ─────────────────────────────────────
    words = sum(
        len((record.get(f) or "").split())
        for f in ["abstract", "motivation", "rationale"]
    )
    if   words > 500: c5 = 10
    elif words > 200: c5 = 7
    elif words > 100: c5 = 4
    elif words > 20:  c5 = 2
    else:             c5 = 0
    components["documentation_quality"] = {
        "label":    "Documentation Quality",
        "score":    c5,
        "max":      10,
        "weight":   "10%",
        "evidence": f"{words} words across abstract, motivation and rationale",
    }

    # ── 6. Historical Precedent (10 pts) ──────────────────────────────────────
    if dr["total"] == 0:
        c6    = 5
        c6_ev = "No similar proposals in history (neutral)"
    else:
        rate = dr["rate"] if dr["rate"] is not None else 50
        c6   = round(rate / 100 * 10)
        c6_ev = f"{dr['total']} similar proposals — {rate}% delivery rate"
    components["historical_precedent"] = {
        "label":    "Historical Precedent",
        "score":    c6,
        "max":      10,
        "weight":   "10%",
        "evidence": c6_ev,
    }

    # ── Total & level ─────────────────────────────────────────────────────────
    total = sum(c["score"] for c in components.values())
    if   total >= 70: level = "LOW RISK"
    elif total >= 45: level = "MEDIUM RISK"
    else:             level = "HIGH RISK"

    return {
        "gov_action_id": record.get("gov_action_id"),
        "total":         total,
        "max":           100,
        "level":         level,
        "components":    components,
    }
