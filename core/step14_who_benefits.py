"""
Step 14 — Refresh "Who Benefits" (M3) over stored actions

Refaz o M3 de todos os saques de tesouro já analisados e troca só o componente
de conflito do M4. Existe porque o M3 mudou: a checagem "proponente e
beneficiário já transacionaram?" saiu — ela produzia acusações HIGH a partir de
rotina — e entraram fatos: quanto cada carteira recebe, se é a de quem
submeteu, e o que ela já pediu e recebeu do tesouro antes.

Duas passagens, porque o histórico de uma carteira depende dos beneficiários
gravados nas *outras* propostas:
  1. Blockfrost: remonta beneficiários e divulgações de cada saque e grava.
  2. Banco: calcula o histórico de cada beneficiária e reescreve o M4.

Os outros cinco componentes do M4 ficam exatamente como estavam — recalcular
tudo usaria a similaridade com o corpus de hoje. Não chama o Claude.

Depois disto, rode `step13_documents.py` para remontar os documentos PIL.

Uso:
    python core/step14_who_benefits.py --dry-run   # só mostra o que mudaria
    python core/step14_who_benefits.py
"""
import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

import psycopg2.extras

from database          import get_conn, save_conflict_and_risk
from step10_conflict   import detect_conflicts, beneficiary_history
from step11_risk_score import rescore_conflict


def _parse(v):
    return json.loads(v) if isinstance(v, str) else v


def _stored_risk(row: dict) -> dict | None:
    risk = (_parse(row.get("analysis")) or {}).get("risk_score")
    if isinstance(risk, dict) and risk.get("components"):
        return risk
    if row.get("risk_components"):
        return {"gov_action_id": row["gov_action_id"],
                "components": _parse(row["risk_components"])}
    return None


def _anchor_text(row: dict) -> str:
    return " ".join(str(row.get(f) or "") for f in ("title", "abstract", "motivation", "rationale"))


def _findings(conflict: dict) -> int:
    return sum(1 for c in (conflict or {}).get("conflicts", []) if c.get("severity") != "INFO")


def run(dry_run: bool = False) -> dict:
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM governance_actions
        WHERE action_type = 'TreasuryWithdrawals' AND analysis IS NOT NULL
        ORDER BY epoch_expiry
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    print(f"{len(rows)} saque(s) de tesouro{' — DRY RUN' if dry_run else ''}\n")
    stats = {"refreshed": 0, "failed": 0, "findings_before": 0, "findings_after": 0,
             "score_changed": 0}
    fresh: dict[str, dict] = {}

    # ── 1. Blockfrost: fatos de cada saque ──────────────────────────────────────
    for i, row in enumerate(rows, 1):
        gid = row["gov_action_id"]
        tx, idx = gid.split("#")
        # ~500 chamadas ao Blockfrost por execução: um timeout de TLS aparece
        # quase toda vez. Sem retentar, a linha que falha fica com os dados
        # antigos — e na primeira execução isso era a soma enganosa de contrato.
        conflict, error = None, None
        for attempt in range(3):
            try:
                conflict = detect_conflicts(gid, tx, int(idx), row["action_type"],
                                            anchor_text=_anchor_text(row))
                break
            except Exception as e:
                error = e
                time.sleep(2 * (attempt + 1))
        if conflict is None:
            stats["failed"] += 1
            print(f"  ❌ {gid[:24]}… {error}")
            continue

        fresh[gid] = conflict
        stats["findings_before"] += _findings(_parse(row.get("conflict_data")))
        stats["findings_after"]  += _findings(conflict)

        if not dry_run:
            # Só a coluna: a passagem 2 precisa ler os beneficiários de todas.
            c = get_conn(); k = c.cursor()
            k.execute("UPDATE governance_actions SET conflict_data = %s WHERE gov_action_id = %s",
                      (json.dumps(conflict), gid))
            c.commit(); k.close(); c.close()
        if i % 20 == 0:
            print(f"  passagem 1: {i}/{len(rows)}")

    # ── 2. Banco: histórico e M4 ────────────────────────────────────────────────
    for row in rows:
        gid = row["gov_action_id"]
        conflict = fresh.get(gid)
        risk = _stored_risk(row)
        if conflict is None or risk is None:
            continue

        new_risk = rescore_conflict(risk, row["action_type"], conflict.get("conflicts", []))
        if new_risk["total"] != row.get("risk_score"):
            stats["score_changed"] += 1
            print(f"  {row.get('risk_score')} → {new_risk['total']}  {(row.get('title') or gid)[:56]}")

        if dry_run:
            stats["refreshed"] += 1
            continue

        conflict["beneficiaries"] = beneficiary_history(
            gid, conflict.get("beneficiaries", []), row.get("epoch_expiry"))
        save_conflict_and_risk(
            gov_action_id     = gid,
            conflict_data     = conflict,
            risk_score        = new_risk["total"],
            risk_components   = new_risk["components"],
            withdrawal_amount = conflict.get("total_withdrawal_lovelace"),
            proposer_address  = (conflict.get("proposer_addresses") or [None])[0],
            risk              = new_risk,
        )
        stats["refreshed"] += 1

    return stats


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    import argparse
    p = argparse.ArgumentParser(description="Refresh M3 (who benefits) and the M4 conflict component")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    print("=== PIL — Refresh Who Benefits ===\n")
    s = run(dry_run=args.dry_run)
    print(f"\n=== {s['refreshed']} atualizado(s) · {s['failed']} falha(s) · "
          f"achados {s['findings_before']} → {s['findings_after']} · "
          f"{s['score_changed']} score(s) mudaram ===")
    if s["failed"]:
        sys.exit(1)
