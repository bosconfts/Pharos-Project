"""
Step 10 — Conflict of Interest Detector (M3)
Detects financial relationships between proposal submitters and beneficiaries.
Only applicable to TreasuryWithdrawals.
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


def _payment_addrs(client, stake: str) -> list[str]:
    data = _get(client, f"/accounts/{stake}/addresses", {"count": 20})
    if not isinstance(data, list):
        return []
    return [item["address"] for item in data]


def _withdrawals(client, tx_hash: str, cert_index: int) -> list[dict]:
    data = _get(client, f"/governance/proposals/{tx_hash}/{cert_index}/withdrawals")
    return data if isinstance(data, list) else []


def _addr_txs(client, address: str, count: int = 30) -> set[str]:
    data = _get(client, f"/addresses/{address}/transactions", {"count": count, "order": "desc"})
    if not isinstance(data, list):
        return set()
    return {t["tx_hash"] for t in data}


def _tx_output_addrs(client, tx_hash: str) -> set[str]:
    data = _get(client, f"/txs/{tx_hash}/utxos")
    if not data:
        return set()
    return {o["address"] for o in data.get("outputs", [])}


# ── Main pipeline ─────────────────────────────────────────────────────────────

def detect_conflicts(gov_action_id: str, tx_hash: str, cert_index: int, action_type: str) -> dict:
    """
    Run M3 conflict detection for a governance action.
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

        conflicts: list[dict] = []

        # ── Check A: Proposer IS a beneficiary (same stake key) ───────────────
        for p_stake in proposer_stakes:
            if p_stake in beneficiary_stakes:
                conflicts.append({
                    "severity":         "HIGH",
                    "type":             "self_beneficiary",
                    "description":      f"Proposer stake address is a direct beneficiary of this withdrawal",
                    "proposer_stake":   p_stake,
                    "beneficiary_stake": p_stake,
                    "evidence_txhash":  tx_hash,
                })

        # ── Check B: Direct transactions between proposer and beneficiaries ───
        if len(conflicts) < 5:
            for p_addr in proposer_addrs[:2]:
                p_txs = _addr_txs(client, p_addr, count=40)
                time.sleep(0.15)

                for b_stake in beneficiary_stakes[:4]:
                    b_addrs = _payment_addrs(client, b_stake)
                    time.sleep(0.15)

                    for b_addr in b_addrs[:3]:
                        b_txs = _addr_txs(client, b_addr, count=40)
                        time.sleep(0.15)

                        shared = p_txs & b_txs
                        if not shared:
                            continue

                        evidence_tx = next(iter(shared))
                        out_addrs   = _tx_output_addrs(client, evidence_tx)
                        time.sleep(0.1)

                        if b_addr in out_addrs:
                            sev  = "HIGH"
                            desc = f"Proposer sent funds to beneficiary in tx {evidence_tx[:16]}…"
                        elif p_addr in out_addrs:
                            sev  = "MEDIUM"
                            desc = f"Beneficiary sent funds to proposer in tx {evidence_tx[:16]}…"
                        else:
                            sev  = "LOW"
                            desc = f"Proposer and beneficiary share a common transaction"

                        conflicts.append({
                            "severity":          sev,
                            "type":              "direct_transaction",
                            "description":       desc,
                            "proposer_address":  p_addr,
                            "beneficiary_stake": b_stake,
                            "evidence_txhash":   evidence_tx,
                        })

                        if _NEO4J:
                            try:
                                graph.add_transaction(evidence_tx, p_addr, b_addr, 0)
                            except Exception:
                                pass

                        if len(conflicts) >= 5:
                            break
                    if len(conflicts) >= 5:
                        break
                if len(conflicts) >= 5:
                    break

        # Sort: HIGH first
        order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        conflicts.sort(key=lambda c: order.get(c["severity"], 3))
        result["conflicts"] = conflicts
        return result
