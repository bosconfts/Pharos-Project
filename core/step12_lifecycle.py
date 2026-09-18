"""
Step 12 — Lifecycle Refresh

Os campos `ratified/enacted/expired/dropped_epoch` só aparecem na chain quando a
proposta resolve — sempre depois de a linha ter sido indexada. Nada no pipeline
voltava para buscá-los: o worker pula action já analisada e o backfill pula
action que já tem embedding. Uma proposta indexada enquanto ainda votava ficava
pendente para sempre, e o delivery rate do M2 e os componentes 1 e 6 do M4
caíam no neutro sem erro visível.

Este passo revisita só as pendentes — as que não têm nenhum dos quatro epochs.
Um desfecho na chain é final, então linha já resolvida nunca é reconsultada, e o
custo por execução é uma chamada ao Blockfrost por proposta ainda em aberto.

Uso:
    python core/step12_lifecycle.py           # refresca e recalcula o M4
    python core/step12_lifecycle.py --dry-run # só mostra o que mudaria
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

import httpx

from database          import get_conn, get_action, save_conflict_and_risk, update_lifecycle
from step8_similarity  import find_similar
from step11_risk_score import compute_risk_score

BLOCKFROST_BASE_URL   = os.getenv("BLOCKFROST_BASE_URL", "https://cardano-mainnet.blockfrost.io/api/v0")
BLOCKFROST_PROJECT_ID = os.getenv("BLOCKFROST_PROJECT_ID")
HEADERS = {"project_id": BLOCKFROST_PROJECT_ID}

EPOCH_FIELDS = ("ratified_epoch", "enacted_epoch", "expired_epoch", "dropped_epoch")


def pending_actions() -> list[dict]:
    """Actions persistidas que ainda não têm desfecho registrado."""
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(f"""
        SELECT gov_action_id, tx_hash, cert_index
        FROM governance_actions
        WHERE {' AND '.join(f'{f} IS NULL' for f in EPOCH_FIELDS)}
        ORDER BY epoch_expiry
    """)
    rows = [{"gov_action_id": r[0], "tx_hash": r[1], "cert_index": r[2]} for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def fetch_lifecycle(client: httpx.Client, tx_hash: str, cert_index: int) -> dict | None:
    """Os quatro epochs como a chain os reporta; None se a proposta sumiu."""
    url  = f"{BLOCKFROST_BASE_URL}/governance/proposals/{tx_hash}/{cert_index}"
    resp = client.get(url, headers=HEADERS)
    if resp.status_code != 200:
        return None
    detail = resp.json()
    return {f: detail.get(f) for f in EPOCH_FIELDS}


def rescore(gov_action_id: str) -> int | None:
    """Recalcula o M4 com os epochs novos. Sem LLM — é função pura sobre o banco."""
    record = get_action(gov_action_id)
    if not record:
        return None

    conflict_data = record.get("conflict_data") or {}

    # O `similarity_data` persistido é a versão resumida; o M4 espera o retorno
    # cru do find_similar, como em pipeline.analyze_action.
    try:
        similar = find_similar(gov_action_id, top_n=5)
    except Exception:
        similar = []

    risk = compute_risk_score(
        record,
        conflicts=conflict_data.get("conflicts", []),
        similar=similar,
    )
    save_conflict_and_risk(
        gov_action_id   = gov_action_id,
        conflict_data   = conflict_data,
        risk_score      = risk["total"],
        risk_components = risk["components"],
    )
    return risk["total"]


def refresh_lifecycle(dry_run: bool = False, verbose: bool = True) -> dict:
    log   = print if verbose else (lambda *a, **k: None)
    stats = {"checked": 0, "updated": 0, "rescored": 0, "failed": 0}

    pending = pending_actions()
    log(f"{len(pending)} action(s) sem desfecho registrado.\n")

    with httpx.Client(timeout=30) as client:
        for row in pending:
            gid = row["gov_action_id"]
            stats["checked"] += 1
            try:
                epochs = fetch_lifecycle(client, row["tx_hash"], row["cert_index"])
            except Exception as e:
                stats["failed"] += 1
                log(f"  ⚠️  {gid[:24]}… erro na consulta: {e}")
                continue

            if epochs is None:
                stats["failed"] += 1
                log(f"  ⚠️  {gid[:24]}… não encontrada na chain")
                continue

            resolved = {f: v for f, v in epochs.items() if v is not None}
            if not resolved:
                log(f"  ·  {gid[:24]}… ainda em aberto")
                continue

            outcome = ", ".join(f"{f.split('_')[0]}={v}" for f, v in resolved.items())
            if dry_run:
                log(f"  [dry-run] {gid[:24]}… → {outcome}")
                stats["updated"] += 1
                continue

            update_lifecycle(gid, epochs)
            stats["updated"] += 1
            total = rescore(gid)
            if total is not None:
                stats["rescored"] += 1
            log(f"  ✅ {gid[:24]}… → {outcome} · risk {total}")

    return stats


if __name__ == "__main__":
    # Console do Windows é cp1252 e estoura nos emojis de status.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    import argparse
    p = argparse.ArgumentParser(description="PIL lifecycle refresh")
    p.add_argument("--dry-run", action="store_true", help="mostra o que mudaria, sem escrever")
    args = p.parse_args()

    print("=== PIL — Lifecycle Refresh ===\n")
    stats = refresh_lifecycle(dry_run=args.dry_run)
    print(f"\n=== {stats['checked']} verificadas · {stats['updated']} atualizadas · "
          f"{stats['rescored']} rescoradas · {stats['failed']} falhas ===")
