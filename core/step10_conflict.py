"""
Step 10 — Who Benefits (M3)

Para cada saque de tesouro, registra fatos verificáveis na chain: quem submeteu
a proposta, para quais carteiras o dinheiro vai e quanto cada uma recebe, e o
que essas mesmas carteiras já pediram ou receberam do tesouro antes.

Isto não é mais um detector de conflito de interesse. A checagem que havia
("proponente e beneficiário já transacionaram?") comparava a carteira que pagou
a taxa de submissão — em geral um administrador que submete em lote — com a do
desenvolvedor, e acusava como HIGH o que era rotina. Um detector real precisa
olhar para quem decide (DReps) se beneficiando da própria decisão.
"""
import os
import sys
import time
sys.path.insert(0, os.path.dirname(__file__))

import httpx
from dotenv import load_dotenv
load_dotenv()

BLOCKFROST_PROJECT_ID = os.getenv("BLOCKFROST_PROJECT_ID")
BLOCKFROST_BASE_URL   = os.getenv("BLOCKFROST_BASE_URL", "https://cardano-mainnet.blockfrost.io/api/v0")
HEADERS = {"project_id": BLOCKFROST_PROJECT_ID}

try:
    import step9_wallet_graph as graph
    _NEO4J = graph.is_available()
except Exception:
    _NEO4J = False


# ── Blockfrost helpers ────────────────────────────────────────────────────────

def _get(client: httpx.Client, path: str, params: dict | None = None) -> dict | list | None:
    resp = client.get(f"{BLOCKFROST_BASE_URL}{path}", headers=HEADERS, params=params or {})
    if resp.status_code == 200:
        return resp.json()
    return None


def _tx_inputs(client, tx_hash: str) -> list[str]:
    """Return unique input addresses of a transaction (= proposer wallets)."""
    data = _get(client, f"/txs/{tx_hash}/utxos")
    if not data:
        return []
    return list({inp["address"] for inp in data.get("inputs", [])})


def _stake_of(client, address: str) -> str | None:
    data = _get(client, f"/addresses/{address}")
    return data.get("stake_address") if data else None


def _withdrawals(client, tx_hash: str, cert_index: int) -> list[dict]:
    data = _get(client, f"/governance/proposals/{tx_hash}/{cert_index}/withdrawals")
    return data if isinstance(data, list) else []


# ── Main pipeline ─────────────────────────────────────────────────────────────

def detect_conflicts(gov_action_id: str, tx_hash: str, cert_index: int, action_type: str,
                     anchor_text: str = "") -> dict:
    """
    Run M3 conflict detection for a governance action.

    anchor_text: texto do documento âncora, usado para verificar se uma relação
    detectada já foi declarada pelo próprio proponente. Declarado é
    transparência; não declarado é o que interessa.

    Returns a dict with conflicts list and metadata.
    """
    result = {
        "gov_action_id":          gov_action_id,
        "action_type":            action_type,
        "proposer_addresses":     [],
        "beneficiary_stakes":     [],
        "total_withdrawal_lovelace": 0,
        "conflicts":              [],
        "status":                 "ok",
    }

    if action_type != "TreasuryWithdrawals":
        result["status"] = "not_applicable"
        return result

    with httpx.Client(timeout=20) as client:

        # ── 1. Proposer addresses ─────────────────────────────────────────────
        proposer_addrs = _tx_inputs(client, tx_hash)
        if not proposer_addrs:
            result["status"] = "no_proposer_data"
            return result
        result["proposer_addresses"] = proposer_addrs[:3]

        proposer_stakes: set[str] = set()
        for addr in proposer_addrs[:2]:
            s = _stake_of(client, addr)
            if s:
                proposer_stakes.add(s)
            time.sleep(0.15)

        # ── 2. Beneficiary addresses ──────────────────────────────────────────
        withdrawals = _withdrawals(client, tx_hash, cert_index)
        if not withdrawals:
            result["status"] = "no_withdrawal_data"
            return result

        result["total_withdrawal_lovelace"] = sum(int(w.get("amount", 0)) for w in withdrawals)
        beneficiary_stakes = [w["stake_address"] for w in withdrawals if w.get("stake_address")]
        result["beneficiary_stakes"] = beneficiary_stakes

        # ── Register in Neo4j graph if available ─────────────────────────────
        if _NEO4J:
            try:
                for addr in proposer_addrs[:2]:
                    stake = _stake_of(client, addr)
                    graph.upsert_wallet(addr, stake)
                    graph.mark_proposer(gov_action_id, addr)
                    time.sleep(0.1)
                for w in withdrawals:
                    graph.mark_beneficiary(gov_action_id, w.get("stake_address", ""), int(w.get("amount", 0)))
            except Exception:
                pass

        # Quanto cada carteira recebe, e se ela é a de quem submeteu. Vários
        # saques pagam mais de uma carteira; atribuir o total a cada uma seria
        # contar o mesmo dinheiro duas vezes.
        result["beneficiaries"] = [
            {
                "stake_address":   w["stake_address"],
                "amount_lovelace": int(w.get("amount", 0)),
                "is_submitter":    w["stake_address"] in proposer_stakes,
                "is_script":       is_script_stake(w["stake_address"]),
            }
            for w in withdrawals if w.get("stake_address")
        ]

        conflicts: list[dict] = []

        # Quem submete receber os fundos é o desenho normal de uma retirada:
        # organizações propõem saques para financiar a si mesmas. Divulgação,
        # não achado — por isso INFO, que não tira pontos.
        for p_stake in proposer_stakes:
            if p_stake in beneficiary_stakes:
                declared = bool(anchor_text) and p_stake in anchor_text
                conflicts.append({
                    "severity":           "INFO",
                    "type":               "self_beneficiary",
                    "description":        "The wallet that submitted this proposal also receives its funds",
                    "note":               "Structural for treasury withdrawals — disclosure, not a finding.",
                    "declared_in_anchor": declared,
                    "proposer_stake":     p_stake,
                    "beneficiary_stake":  p_stake,
                    "evidence_txhash":    tx_hash,
                })

        result["conflicts"] = conflicts
        return result


def is_script_stake(stake_address: str) -> bool:
    """A carteira de stake é um contrato inteligente, e não uma chave?

    O primeiro caractere depois do separador "1" do bech32 carrega os 5 bits
    altos do cabeçalho: 0xE1 (chave) vira "u", 0xF1 (script) vira "7" — em
    mainnet ("stake1") e testnet ("stake_test1"). Conferido contra a
    decodificação completa nas 29 beneficiárias da base.
    """
    _, _, data = (stake_address or "").partition("1")
    return data[:1] == "7"


def beneficiary_history(gov_action_id: str, beneficiaries: list[dict],
                        epoch_expiry: int | None) -> list[dict]:
    """Acrescenta a cada beneficiária o que ela já pediu e recebeu do tesouro.

    "Antes" é por epoch_expiry estritamente menor: as propostas submetidas no
    mesmo lote vencem juntas e não contam como histórico umas das outras.
    Recebido é o que foi promulgado (enacted) — pedir não é receber.

    Contexto para quem vota, não penalidade: não entra no score.
    """
    if not beneficiaries or epoch_expiry is None:
        return beneficiaries

    from database import get_conn

    conn = get_conn()
    cur  = conn.cursor()
    enriched = []
    for b in beneficiaries:
        cur.execute("""
            SELECT (item->>'amount_lovelace')::bigint, g.enacted_epoch IS NOT NULL
            FROM governance_actions g,
                 jsonb_array_elements(g.conflict_data->'beneficiaries') AS item
            WHERE g.action_type = 'TreasuryWithdrawals'
              AND g.gov_action_id <> %s
              AND g.epoch_expiry < %s
              AND item->>'stake_address' = %s
        """, (gov_action_id, epoch_expiry, b["stake_address"]))
        rows = cur.fetchall()
        script = is_script_stake(b["stake_address"])

        # 98 de 112 pagamentos da base caem em contratos (escrow do orçamento),
        # de onde o dinheiro é liberado para cada fornecedor. Somar o que um
        # contrato já recebeu e exibir na proposta de um fornecedor diria que
        # ele recebeu centenas de milhões — verdade sobre o contrato, falso
        # sobre a proposta. Para contrato, só a contagem de saques que o usam.
        if script:
            prior = {"proposals": len(rows), "shared_contract": True}
        else:
            prior = {
                "proposals":          len(rows),
                "requested_lovelace": sum(r[0] or 0 for r in rows),
                "enacted":            sum(1 for r in rows if r[1]),
                "received_lovelace":  sum(r[0] or 0 for r in rows if r[1]),
            }
        enriched.append({**b, "is_script": script, "prior": prior})
    cur.close()
    conn.close()
    return enriched
