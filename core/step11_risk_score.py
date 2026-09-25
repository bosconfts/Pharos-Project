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

# Quantas propostas comparáveis precisam ter terminado para a taxa de entrega
# valer alguma coisa. Os componentes 1 e 6 somam 35 dos 100 pontos e saem os
# dois da mesma taxa: com uma única comparável aprovada, a taxa dá 100% e a
# proposta ganhava 35 pontos cheios a partir de uma amostra de tamanho 1 —
# 26 propostas da base estavam nessa situação. Abaixo disto, neutro.
MIN_COMPARABLES = 3


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
    concluded = dr["delivered"] + dr["expired"]
    if concluded < MIN_COMPARABLES:
        c1 = 13
        c1_ev = (f"Only {concluded} comparable proposal(s) have concluded — "
                 f"too few to judge (neutral)")
    else:
        rate = dr["rate"] if dr["rate"] is not None else 50
        c1   = round(rate / 100 * 25)
        c1_ev = f"{dr['delivered']}/{concluded} similar proposals delivered ({rate}%)"
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
    components["conflict_of_interest"] = conflict_component(action_type, conflicts)

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
    if concluded < MIN_COMPARABLES:
        c6    = 5
        c6_ev = (f"{dr['total']} comparable proposal(s) found, {concluded} concluded — "
                 f"too few to judge (neutral)")
    else:
        rate = dr["rate"] if dr["rate"] is not None else 50
        c6   = round(rate / 100 * 10)
        c6_ev = f"{concluded} concluded comparable proposals — {rate}% delivery rate"
    components["historical_precedent"] = {
        "label":    "Historical Precedent",
        "score":    c6,
        "max":      10,
        "weight":   "10%",
        "evidence": c6_ev,
    }

    return _finalize(record.get("gov_action_id"), components)


def _finalize(gov_action_id, components: dict) -> dict:
    """Total é a soma dos componentes; o nível sai do total."""
    total = sum(c["score"] for c in components.values())
    if   total >= 70: level = "LOW RISK"
    elif total >= 45: level = "MEDIUM RISK"
    else:             level = "HIGH RISK"

    return {
        "gov_action_id": gov_action_id,
        "total":         total,
        "max":           100,
        "level":         level,
        "components":    components,
    }


def conflict_component(action_type: str, conflicts: list | None) -> dict:
    """Componente 3 do M4.

    Hoje nenhuma checagem de conflito de interesse roda. A que existia comparava
    o histórico da carteira que pagou a taxa de submissão com o da carteira
    beneficiária — mas quem paga a submissão costuma ser um administrador (a
    Intersect submeteu 39 dos 104 saques, em lote, por desenvolvedores
    diferentes), então ela media se duas carteiras já tinham se tocado, o que em
    saque de tesouro é quase sempre normal. Das 11 acusações HIGH que produziu,
    4 comparavam uma carteira com ela mesma.

    Os pontos ficam cheios, como já ficavam para quase todas as propostas, e a
    evidência diz a verdade: não avaliado. Um achado real (HIGH/MEDIUM/LOW) de
    uma checagem futura volta a tirar pontos.

    Os valores abaixo são publicados como legenda no painel "Who benefits"
    (dashboard/src/components/ConflictPanel.jsx): mudar um exige mudar o outro.
    """
    conflicts = conflicts or []
    high = sum(1 for c in conflicts if c.get("severity") == "HIGH")
    med  = sum(1 for c in conflicts if c.get("severity") == "MEDIUM")
    low  = sum(1 for c in conflicts if c.get("severity") == "LOW")

    if action_type != "TreasuryWithdrawals":
        score, ev = 20, "Not applicable (no direct financial beneficiaries)"
    elif high:
        score, ev = 0, f"{high} HIGH severity conflict(s) detected"
    elif med:
        score, ev = 8, f"{med} MEDIUM + {low} LOW conflict(s) detected"
    elif low:
        score, ev = 14, f"{low} LOW severity conflict(s) detected"
    else:
        score, ev = 20, ("Not assessed — no conflict-of-interest check currently runs. "
                         "Recipients and their treasury history are listed under Who benefits.")

    return {
        "label":    "Conflict of Interest",
        "score":    score,
        "max":      20,
        "weight":   "20%",
        "evidence": ev,
    }


def rescore_conflict(risk: dict, action_type: str, conflicts: list | None) -> dict:
    """Troca só o componente de conflito de um M4 já calculado.

    Recalcular o M4 inteiro chamaria o find_similar com o corpus de hoje, e o
    score se moveria por causa da similaridade — não do conflito, que é o que
    mudou. Aqui os outros cinco componentes ficam exatamente como estavam.
    """
    components = dict(risk.get("components") or {})
    components["conflict_of_interest"] = conflict_component(action_type, conflicts)
    return _finalize(risk.get("gov_action_id"), components)
