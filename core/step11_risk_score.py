"""
Step 11 — Risk Score Engine (M4)
Computes an auditable 0–100 score from the signals that actually separate one
proposal from another. Higher score = lower risk.

Método 1.2.0. O anterior somava seis componentes, e 50 dos 100 pontos eram
quase constantes: Conflict of Interest dava 20 a todos (nenhuma checagem roda),
Scope Clarity dava nota cheia a 97% das propostas e Documentation Quality a
87%. A taxa de entrega de similares entrava duas vezes, com dois nomes. As
notas iam de 50 a 100 e nenhuma proposta jamais chegou a HIGH RISK.

Ficaram os dois sinais que medem algo (docs/m4-score-audit.md):

  - entrega de propostas similares — 60 pontos, ou 100 quando o saque não se
    aplica;
  - tamanho do saque frente ao Net Change Limit — 40 pontos, só em saque de
    tesouro.

Sinal que não se aplica sai da conta, em vez de dar pontos de graça: uma
InfoAction é julgada só pelo histórico. Sem amostra suficiente, o sinal fica no
meio da escala, e uma proposta sem nada a dizer cai em MEDIUM, não em LOW.

Análises ancoradas com o método anterior continuam com seis componentes — o
documento no bloco é o registro. Ver "Armadilhas conhecidas" no CLAUDE.md.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from step8_similarity import find_similar, delivery_rate

NCL_LOVELACE = 300_000_000_000_000  # 300 million ADA

# Quantas propostas comparáveis precisam ter terminado para a taxa de entrega
# valer alguma coisa. Com uma única comparável aprovada a taxa dá 100%, e a
# proposta ganhava os pontos cheios a partir de uma amostra de tamanho 1 —
# 26 propostas da base estavam nessa situação. Abaixo disto, neutro.
MIN_COMPARABLES = 3

DELIVERY_MAX = 60   # 100 quando o saque não se aplica
TREASURY_MAX = 40

# Faixas de % do NCL → fração dos pontos do saque. As mesmas faixas do método
# anterior (15/12/8/4/0 de 15), agora sobre 40.
TREASURY_BANDS = ((1, 40), (3, 32), (7, 21), (15, 11))


def compute_risk_score(record: dict, conflicts: list | None = None, similar: list | None = None) -> dict:
    """
    Compute M4 Risk Score for a governance action record.
    Args:
        record:    row from governance_actions table (dict)
        conflicts: output of detect_conflicts — not scored: no conflict check
                   runs today, and M3 shows who benefits instead of judging it
        similar:   output of find_similar (list of similar proposal dicts)
    Returns dict with total (0-100), level, and per-component breakdown.
    """
    if similar is None:
        similar = find_similar(record.get("gov_action_id", ""), top_n=5)

    is_treasury = record.get("action_type") == "TreasuryWithdrawals"
    components  = {}
    components["similar_delivery"] = delivery_component(
        delivery_rate(similar), DELIVERY_MAX if is_treasury else 100)
    if is_treasury:
        components["treasury_size"] = treasury_component(record.get("withdrawal_amount"))

    return _finalize(record.get("gov_action_id"), components)


def delivery_component(dr: dict, max_pts: int) -> dict:
    """Taxa de entrega das propostas semanticamente similares, de qualquer autor.

    Chamava-se "Proposer Track Record", mas nunca olhou o proponente — o nome
    agora descreve o cálculo.
    """
    concluded = dr["delivered"] + dr["expired"]
    if concluded < MIN_COMPARABLES:
        score = round(max_pts / 2)
        ev = (f"{dr['total']} similar proposal(s) found, only {concluded} concluded — "
              f"too few to judge (neutral)")
    else:
        rate  = dr["rate"] if dr["rate"] is not None else 50
        score = round(rate / 100 * max_pts)
        ev = f"{dr['delivered']}/{concluded} concluded similar proposals were delivered ({rate}%)"
    return {
        "label":    "Delivery of Similar Proposals",
        "score":    score,
        "max":      max_pts,
        "weight":   f"{max_pts}%",
        "evidence": ev,
    }


def treasury_component(lovelace: int | None) -> dict:
    """Tamanho do saque como % do Net Change Limit."""
    if lovelace and lovelace > 0:
        pct   = lovelace / NCL_LOVELACE * 100
        score = next((pts for lim, pts in TREASURY_BANDS if pct < lim), 0)
        ev    = f"{pct:.2f}% of NCL (300M ADA limit)"
    else:
        score = TREASURY_MAX // 2
        ev    = "Withdrawal amount unknown (neutral)"
    return {
        "label":    "Treasury Withdrawal Size",
        "score":    score,
        "max":      TREASURY_MAX,
        "weight":   f"{TREASURY_MAX}%",
        "evidence": ev,
    }


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
    """Componente 3 do M4 no método 1.1.0 — o 1.2.0 não o tem.

    Continua aqui porque o step14 ainda troca este componente em análises
    1.1.0 não ancoradas.

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
    # Método 1.2.0 não pontua conflito: injetar o componente aqui somaria 20
    # pontos a um score que não os tem.
    if "conflict_of_interest" not in components:
        return risk
    components["conflict_of_interest"] = conflict_component(action_type, conflicts)
    return _finalize(risk.get("gov_action_id"), components)
