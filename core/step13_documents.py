"""
Step 13 — Rebuild PIL Documents

Remonta o documento PIL de cada action a partir do que já está no banco.

O documento era montado antes de M2–M4 rodarem e nunca refeito, então todos
saíram com o score "PENDING" e sem conflitos nem similares — e com um autor
apontando para um domínio inexistente e a alegação falsa de pipeline
determinístico. O pipeline agora monta o documento depois do M4; este passo
corrige os que já existiam.

Não chama a rede, não chama o Claude e não recalcula nada: só reempacota a
análise persistida. Os scores ficam exatamente como estão. Uma action já
ancorada nunca é tocada — o documento dela é o que está na chain, e mudar a
cópia do banco a dessincronizaria do registro público.

Uso:
    python core/step13_documents.py --dry-run   # mostra o que mudaria
    python core/step13_documents.py             # grava
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
import psycopg2.extras

from database      import get_conn, GENUINE_SUMMARY_SQL
from step4_publish import build_pil_document, compute_document_hash


def _parse(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return None
    return value


def _risk_from_row(row: dict) -> dict | None:
    """O M4 completo vem do `analysis`; a coluna solta serve de reserva."""
    analysis = _parse(row.get("analysis")) or {}
    risk = analysis.get("risk_score")
    if isinstance(risk, dict) and risk.get("total") is not None:
        return risk
    if row.get("risk_score") is None:
        return None
    return {"total": row["risk_score"], "max": 100, "level": None,
            "components": _parse(row.get("risk_components")) or {}}


def rebuild_one(row: dict) -> tuple[dict, str]:
    summaries = {
        "one_liner": row.get("one_liner") or "",
        "technical": row.get("technical") or "",
        "full":      _parse(row.get("full_summary")) or {},
    }
    analyzed_at = row.get("analyzed_at")
    doc = build_pil_document(
        row["gov_action_id"], row["action_type"],
        row.get("anchor_url") or "", row.get("anchor_hash") or "",
        summaries,
        risk_score        = _risk_from_row(row),
        similar_proposals = (_parse(row.get("similarity_data")) or {}).get("similar_proposals", []),
        conflicts         = (_parse(row.get("conflict_data")) or {}).get("conflicts", []),
        generated_at      = analyzed_at.strftime("%Y-%m-%dT%H:%M:%SZ") if analyzed_at else None,
    )
    return doc, compute_document_hash(doc)


def rebuild_all(dry_run: bool = False) -> dict:
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(f"""
        SELECT * FROM governance_actions
        WHERE analysis IS NOT NULL
          AND on_chain_tx IS NULL
          -- Só corrige documentos que já existiam. Sem isto, uma action cujo
          -- anchor devolve 404 ganharia documento e entraria na fila de
          -- publicação — ancorando a análise de um texto cujo hash nunca foi
          -- conferido. Isso é decisão própria, não efeito colateral daqui.
          AND pil_document IS NOT NULL
          AND {GENUINE_SUMMARY_SQL}
    """)
    rows = cur.fetchall()
    stats = {"rebuilt": 0, "failed": 0}
    print(f"{len(rows)} documento(s) a remontar{' — DRY RUN' if dry_run else ''}\n")

    for row in rows:
        gid = row["gov_action_id"]
        try:
            doc, doc_hash = rebuild_one(row)
        except Exception as e:
            stats["failed"] += 1
            print(f"  ❌ {gid[:24]}… {e}")
            continue

        if dry_run:
            stats["rebuilt"] += 1
            continue

        # Documento, hash e o hash exibido pelo dashboard (dentro de `analysis`)
        # mudam na mesma transação: nenhum dos três pode ficar para trás.
        cur.execute("""
            UPDATE governance_actions
            SET pil_document = %s,
                pil_doc_hash = %s,
                analysis     = jsonb_set(analysis, '{pil_document_hash}', to_jsonb(%s::text))
            WHERE gov_action_id = %s
              AND on_chain_tx IS NULL
        """, (json.dumps(doc, default=str), doc_hash, doc_hash, gid))
        stats["rebuilt"] += 1

    if not dry_run:
        conn.commit()
    cur.close()
    conn.close()
    return stats


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    import argparse
    p = argparse.ArgumentParser(description="Rebuild PIL documents from stored analysis")
    p.add_argument("--dry-run", action="store_true", help="mostra o que mudaria, sem gravar")
    args = p.parse_args()

    print("=== PIL — Rebuild Documents ===\n")
    s = rebuild_all(dry_run=args.dry_run)
    print(f"\n=== {s['rebuilt']} remontado(s) · {s['failed']} falha(s) ===")
    if s["failed"]:
        sys.exit(1)
