"""
Step 8 — Similarity Search + Delivery Rate
Busca as N proposals mais similares e calcula o delivery rate histórico.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

import psycopg2.extras
from database import get_conn
from step7_embeddings import embed_text


def find_similar(
    gov_action_id: str,
    embedding: list[float] | None = None,
    top_n: int = 5,
    min_similarity: float = 0.5,
) -> list[dict]:
    """
    Retorna as top_n proposals mais similares (excluindo a própria).
    Usa cosine similarity via pgvector (<=> operador).
    """
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if embedding is None:
        # Busca embedding da própria action no banco
        cur.execute(
            "SELECT embedding FROM governance_actions WHERE gov_action_id = %s",
            (gov_action_id,)
        )
        row = cur.fetchone()
        if not row or row["embedding"] is None:
            cur.close()
            conn.close()
            return []
        embedding = row["embedding"]

    cur.execute("""
        SELECT
            gov_action_id,
            action_type,
            title,
            one_liner,
            ratified_epoch,
            enacted_epoch,
            expired_epoch,
            dropped_epoch,
            1 - (embedding <=> %s::vector) AS similarity
        FROM governance_actions
        WHERE gov_action_id != %s
          AND embedding IS NOT NULL
          AND 1 - (embedding <=> %s::vector) >= %s
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (embedding, gov_action_id, embedding, min_similarity, embedding, top_n))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def delivery_rate(similar: list[dict]) -> dict:
    """
    Calcula o delivery rate do conjunto de proposals similares.
    'Entregue' = ratified_epoch ou enacted_epoch não nulo.
    'Expirado/Descartado' = expired_epoch ou dropped_epoch não nulo.
    'Pendente' = nenhum dos acima.
    """
    if not similar:
        return {
            "total":     0,
            "delivered": 0,
            "expired":   0,
            "pending":   0,
            "rate":      None,
            "label":     "Insufficient history",
        }

    delivered = sum(1 for p in similar if p.get("ratified_epoch") or p.get("enacted_epoch"))
    expired   = sum(1 for p in similar if p.get("expired_epoch") or p.get("dropped_epoch"))
    pending   = len(similar) - delivered - expired
    concluded = delivered + expired

    rate  = round(delivered / concluded * 100, 1) if concluded > 0 else None
    label = f"{delivered}/{concluded} approved ({rate}%)" if rate is not None else "Insufficient data"

    return {
        "total":     len(similar),
        "delivered": delivered,
        "expired":   expired,
        "pending":   pending,
        "rate":      rate,
        "label":     label,
    }


def analyze_similarity(gov_action_id: str, text: str | None = None, top_n: int = 5) -> dict:
    """
    Pipeline completo: gera embedding (se texto fornecido), busca similares, calcula delivery rate.
    Retorna dict com similar_proposals e delivery_rate.
    """
    embedding = embed_text(text) if text else None
    similar   = find_similar(gov_action_id, embedding=embedding, top_n=top_n)
    dr        = delivery_rate(similar)

    return {
        "similar_proposals": [
            {
                "gov_action_id": p["gov_action_id"],
                "action_type":   p["action_type"],
                "title":         p["title"],
                "one_liner":     p["one_liner"],
                "similarity":    round(float(p["similarity"]), 3),
                "status":        _status(p),
            }
            for p in similar
        ],
        "delivery_rate": dr,
        "summary": f"{dr['total']} similar proposals found — {dr['label']}",
    }


def _status(p: dict) -> str:
    if p.get("enacted_epoch"):   return "enacted"
    if p.get("ratified_epoch"):  return "ratified"
    if p.get("expired_epoch"):   return "expired"
    if p.get("dropped_epoch"):   return "dropped"
    return "active"


if __name__ == "__main__":
    print("=== PIL M2 — Step 8: Similarity Search ===\n")
    print("Use analyze_similarity(gov_action_id, text) para testar após o backfill.")
