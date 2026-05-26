import os
import httpx
from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import Optional

load_dotenv()

BLOCKFROST_PROJECT_ID = os.getenv("BLOCKFROST_PROJECT_ID")
BLOCKFROST_BASE_URL   = os.getenv("BLOCKFROST_BASE_URL", "https://cardano-mainnet.blockfrost.io/api/v0")
HEADERS = {"project_id": BLOCKFROST_PROJECT_ID}

# Mapa de tipos da API Blockfrost para nomes legíveis
ACTION_TYPE_MAP = {
    "info_action":            "InfoAction",
    "treasury_withdrawals":   "TreasuryWithdrawals",
    "parameter_change":       "ParameterChange",
    "hard_fork_initiation":   "HardForkInitiation",
    "no_confidence":          "NoConfidence",
    "new_committee":          "NewCommittee",
    "new_constitution":       "NewConstitution",
    "update_committee":       "UpdateCommittee",
}


@dataclass
class GovernanceAction:
    tx_hash:        str
    cert_index:     int
    gov_action_id:  str
    action_type:    str
    anchor_url:     Optional[str]
    anchor_hash:    Optional[str]
    deposit:        int
    epoch_expiry:   Optional[int]
    json_metadata:  Optional[dict] = None
    raw:            dict = field(default_factory=dict)


def _fetch_metadata(client: httpx.Client, tx_hash: str, cert_index: int) -> dict:
    """Busca metadados (anchor URL + JSON) de um proposal individual."""
    url  = f"{BLOCKFROST_BASE_URL}/governance/proposals/{tx_hash}/{cert_index}/metadata"
    resp = client.get(url, headers=HEADERS)
    if resp.status_code == 200:
        return resp.json()
    return {}


def _fetch_detail(client: httpx.Client, tx_hash: str, cert_index: int) -> dict:
    """Busca detalhes (deposit, expiry) de um proposal individual."""
    url  = f"{BLOCKFROST_BASE_URL}/governance/proposals/{tx_hash}/{cert_index}"
    resp = client.get(url, headers=HEADERS)
    if resp.status_code == 200:
        return resp.json()
    return {}


def fetch_governance_actions(page: int = 1, count: int = 20) -> list[GovernanceAction]:
    url    = f"{BLOCKFROST_BASE_URL}/governance/proposals"
    params = {"page": page, "count": count, "order": "desc"}

    with httpx.Client(timeout=30) as client:
        resp = client.get(url, headers=HEADERS, params=params)

        if resp.status_code == 404:
            return []

        resp.raise_for_status()
        data = resp.json()

        actions = []
        for item in data:
            tx_hash    = item.get("tx_hash", "")
            cert_index = item.get("cert_index", 0)
            gov_type   = ACTION_TYPE_MAP.get(item.get("governance_type", ""), item.get("governance_type", "Unknown"))

            meta   = _fetch_metadata(client, tx_hash, cert_index)
            detail = _fetch_detail(client, tx_hash, cert_index)

            action = GovernanceAction(
                tx_hash=tx_hash,
                cert_index=cert_index,
                gov_action_id=f"{tx_hash}#{cert_index}",
                action_type=gov_type,
                anchor_url=meta.get("url"),
                anchor_hash=meta.get("hash"),
                deposit=int(detail.get("deposit", 0)),
                epoch_expiry=detail.get("expiration"),
                json_metadata=meta.get("json_metadata"),
                raw=item,
            )
            actions.append(action)

    return actions


if __name__ == "__main__":
    print("=== PIL M1 — Step 1: Indexer ===\n")
    actions = fetch_governance_actions(count=5)

    if not actions:
        print("Nenhuma governance action encontrada.")
    else:
        print(f"Encontradas {len(actions)} governance actions:\n")
        for a in actions:
            print(f"  [{a.action_type}] {a.gov_action_id}")
            print(f"    Anchor URL:  {a.anchor_url or '(sem anchor)'}")
            print(f"    Anchor Hash: {a.anchor_hash or '(sem hash)'}")
            print(f"    Expira:      epoch {a.epoch_expiry}")
            print(f"    Depósito:    {a.deposit / 1_000_000:.0f} ADA\n")
