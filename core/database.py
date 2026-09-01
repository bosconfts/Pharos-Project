"""
Conexão com PostgreSQL + pgvector e schema do PIL.
"""
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://pil:pil_secret@localhost:5432/pil"
)


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    """Cria extensão pgvector e tabelas se não existirem."""
    conn = get_conn()
    cur  = conn.cursor()

    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS governance_actions (
            gov_action_id    TEXT PRIMARY KEY,
            tx_hash          TEXT NOT NULL,
            cert_index       INTEGER NOT NULL,
            action_type      TEXT,
            anchor_url       TEXT,
            anchor_hash      TEXT,
            deposit          BIGINT,
            epoch_expiry     INTEGER,
            -- Status on-chain
            ratified_epoch   INTEGER,
            enacted_epoch    INTEGER,
            expired_epoch    INTEGER,
            dropped_epoch    INTEGER,
            -- CIP-108 fields
            title            TEXT,
            abstract         TEXT,
            motivation       TEXT,
            rationale        TEXT,
            -- PIL summaries
            one_liner        TEXT,
            technical        TEXT,
            full_summary     JSONB,
            completeness_score INTEGER,
            -- PIL metadata
            pil_doc_hash     TEXT,
            on_chain_tx      TEXT,
            processed_at     TIMESTAMPTZ DEFAULT NOW(),
            -- Embedding (all-MiniLM-L6-v2 = 384 dims)
            embedding        vector(384)
        );
    """)

    # IVFFlat index for efficient similarity search
    cur.execute("""
        CREATE INDEX IF NOT EXISTS governance_actions_embedding_idx
        ON governance_actions
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 50);
    """)

    # M3/M4 columns (added via ALTER TABLE to preserve existing data)
    for col_sql in [
        "ALTER TABLE governance_actions ADD COLUMN IF NOT EXISTS withdrawal_amount BIGINT",
        "ALTER TABLE governance_actions ADD COLUMN IF NOT EXISTS proposer_address   TEXT",
        "ALTER TABLE governance_actions ADD COLUMN IF NOT EXISTS conflict_data      JSONB",
        "ALTER TABLE governance_actions ADD COLUMN IF NOT EXISTS risk_score         INTEGER",
        "ALTER TABLE governance_actions ADD COLUMN IF NOT EXISTS risk_components    JSONB",
        # Análise completa servida pela API read-only + estado de publicação on-chain
        "ALTER TABLE governance_actions ADD COLUMN IF NOT EXISTS analysis           JSONB",
        "ALTER TABLE governance_actions ADD COLUMN IF NOT EXISTS pil_document       JSONB",
        "ALTER TABLE governance_actions ADD COLUMN IF NOT EXISTS similarity_data    JSONB",
        "ALTER TABLE governance_actions ADD COLUMN IF NOT EXISTS analyzed_at        TIMESTAMPTZ",
        "ALTER TABLE governance_actions ADD COLUMN IF NOT EXISTS on_chain_status     TEXT",
        "ALTER TABLE governance_actions ADD COLUMN IF NOT EXISTS on_chain_at        TIMESTAMPTZ",
    ]:
        cur.execute(col_sql)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database initialized.")


def upsert_action(data: dict):
    """Insere ou atualiza uma governance action no banco."""
    conn = get_conn()
    cur  = conn.cursor()

    cur.execute("""
        INSERT INTO governance_actions (
            gov_action_id, tx_hash, cert_index, action_type,
            anchor_url, anchor_hash, deposit, epoch_expiry,
            ratified_epoch, enacted_epoch, expired_epoch, dropped_epoch,
            title, abstract, motivation, rationale,
            one_liner, technical, full_summary, completeness_score,
            pil_doc_hash, on_chain_tx, embedding
        ) VALUES (
            %(gov_action_id)s, %(tx_hash)s, %(cert_index)s, %(action_type)s,
            %(anchor_url)s, %(anchor_hash)s, %(deposit)s, %(epoch_expiry)s,
            %(ratified_epoch)s, %(enacted_epoch)s, %(expired_epoch)s, %(dropped_epoch)s,
            %(title)s, %(abstract)s, %(motivation)s, %(rationale)s,
            %(one_liner)s, %(technical)s, %(full_summary)s, %(completeness_score)s,
            %(pil_doc_hash)s, %(on_chain_tx)s, %(embedding)s
        )
        ON CONFLICT (gov_action_id) DO UPDATE SET
            action_type        = EXCLUDED.action_type,
            ratified_epoch     = EXCLUDED.ratified_epoch,
            enacted_epoch      = EXCLUDED.enacted_epoch,
            expired_epoch      = EXCLUDED.expired_epoch,
            dropped_epoch      = EXCLUDED.dropped_epoch,
            one_liner          = COALESCE(EXCLUDED.one_liner, governance_actions.one_liner),
            technical          = COALESCE(EXCLUDED.technical, governance_actions.technical),
            full_summary       = COALESCE(EXCLUDED.full_summary, governance_actions.full_summary),
            completeness_score = COALESCE(EXCLUDED.completeness_score, governance_actions.completeness_score),
            pil_doc_hash       = COALESCE(EXCLUDED.pil_doc_hash, governance_actions.pil_doc_hash),
            on_chain_tx        = COALESCE(EXCLUDED.on_chain_tx, governance_actions.on_chain_tx),
            embedding          = COALESCE(EXCLUDED.embedding, governance_actions.embedding);
    """, data)

    conn.commit()
    cur.close()
    conn.close()


def get_action(gov_action_id: str) -> dict | None:
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM governance_actions WHERE gov_action_id = %s",
        (gov_action_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def get_all_actions(limit: int = 100, offset: int = 0) -> list[dict]:
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT gov_action_id, action_type, title, one_liner,
                  completeness_score, ratified_epoch, enacted_epoch,
                  expired_epoch, dropped_epoch, processed_at,
                  risk_score, withdrawal_amount
           FROM governance_actions
           ORDER BY processed_at DESC
           LIMIT %s OFFSET %s""",
        (limit, offset)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def save_conflict_and_risk(gov_action_id: str, conflict_data: dict, risk_score: int,
                           risk_components: dict, withdrawal_amount: int | None = None,
                           proposer_address: str | None = None):
    """Persist M3/M4 results for a governance action."""
    import json
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE governance_actions
        SET conflict_data     = %s,
            risk_score        = %s,
            risk_components   = %s,
            withdrawal_amount = COALESCE(%s, withdrawal_amount),
            proposer_address  = COALESCE(%s, proposer_address)
        WHERE gov_action_id = %s
    """, (
        json.dumps(conflict_data),
        risk_score,
        json.dumps(risk_components),
        withdrawal_amount,
        proposer_address,
        gov_action_id,
    ))
    conn.commit()
    cur.close()
    conn.close()


def save_analysis(gov_action_id: str, analysis: dict, pil_document: dict | None = None,
                  similarity_data: dict | None = None):
    """Persiste o resultado completo do pipeline. A API lê exclusivamente daqui."""
    import json
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE governance_actions
        SET analysis        = %s,
            pil_document    = COALESCE(%s, pil_document),
            similarity_data = COALESCE(%s, similarity_data),
            analyzed_at     = NOW()
        WHERE gov_action_id = %s
    """, (
        json.dumps(analysis, default=str),
        json.dumps(pil_document, default=str) if pil_document is not None else None,
        json.dumps(similarity_data, default=str) if similarity_data is not None else None,
        gov_action_id,
    ))
    conn.commit()
    cur.close()
    conn.close()


def get_analysis(gov_action_id: str) -> dict | None:
    """Retorna a análise persistida, ou None se a action ainda não foi processada."""
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT analysis, pil_document, on_chain_tx, on_chain_status, analyzed_at
        FROM governance_actions
        WHERE gov_action_id = %s
    """, (gov_action_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row or not row["analysis"]:
        return None

    result = dict(row["analysis"])
    result["pil_document"] = row["pil_document"]
    result["on_chain"] = {
        "status":  row["on_chain_status"] or "not_published",
        "tx_hash": row["on_chain_tx"],
    }
    result["analyzed_at"] = row["analyzed_at"].isoformat() if row["analyzed_at"] else None
    return result


def set_on_chain_result(gov_action_id: str, status: str, tx_hash: str | None = None):
    """Registra o resultado da publicação on-chain (chamado apenas pelo publisher)."""
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE governance_actions
        SET on_chain_status = %s,
            on_chain_tx     = COALESCE(%s, on_chain_tx),
            on_chain_at     = CASE WHEN %s IS NOT NULL THEN NOW() ELSE on_chain_at END
        WHERE gov_action_id = %s
    """, (status, tx_hash, tx_hash, gov_action_id))
    conn.commit()
    cur.close()
    conn.close()


def get_pending_publish(limit: int = 10) -> list[dict]:
    """Actions já analisadas que ainda não têm transação on-chain confirmada.

    A ausência de on_chain_tx é a garantia de idempotência: uma action publicada
    nunca é reprocessada, mesmo que o worker rode várias vezes.
    """
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT gov_action_id, pil_document, pil_doc_hash
        FROM governance_actions
        WHERE analysis IS NOT NULL
          AND pil_document IS NOT NULL
          AND on_chain_tx IS NULL
        ORDER BY analyzed_at ASC
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def get_unanalyzed_ids(limit: int = 100) -> list[str]:
    """IDs de actions indexadas mas ainda sem análise."""
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT gov_action_id FROM governance_actions
        WHERE analysis IS NULL
        ORDER BY processed_at DESC
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]


def count_actions() -> int:
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM governance_actions")
    n = cur.fetchone()[0]
    cur.close()
    conn.close()
    return n


if __name__ == "__main__":
    # O console do Windows usa cp1252 e estoura em emoji. Sem isso, um print
    # decorativo derruba o script depois do trabalho já ter sido feito.
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    init_db()
