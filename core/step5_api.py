"""
API pública do PIL — estritamente read-only.

Não roda o pipeline e não assina transações. Serve o que o worker
(`core/worker.py`) e o publisher (`core/publisher.py`) escreveram no banco.
Isso mantém requests rápidos, o processo sem estado e a signing key fora
de qualquer caminho acessível pela rede.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from step1_indexer import fetch_governance_actions
from step4_publish import network_name
from database      import get_all_actions, count_actions, get_analysis, get_conn

NETWORK = network_name()

app = FastAPI(
    title="Proposal Intelligence Layer API",
    version="1.0.0",
    description="Análises PIL de governance actions da Cardano. Somente leitura.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"name": "Proposal Intelligence Layer", "version": "1.0.0", "network": NETWORK}


@app.get("/health")
def health():
    """Health check com verificação real de banco — usado pelo Render."""
    try:
        conn = get_conn()
        conn.cursor().execute("SELECT 1")
        conn.close()
        return {"status": "ok", "database": "ok", "network": NETWORK}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"database unavailable: {e}")


@app.get("/stats")
def stats():
    try:
        return {"total_analyzed": count_actions(), "network": NETWORK}
    except Exception:
        return {"total_analyzed": 0, "network": NETWORK}


@app.get("/governance/history")
def history(limit: int = 50, offset: int = 0):
    """Proposals já analisadas e persistidas."""
    limit = max(1, min(limit, 200))
    try:
        actions = get_all_actions(limit=limit, offset=offset)
        return {"count": len(actions), "total": count_actions(), "actions": actions}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Banco indisponível: {e}")


@app.get("/governance/actions")
def list_actions(page: int = 1, count: int = 10):
    """Governance actions ao vivo da chain — sem análise."""
    count = max(1, min(count, 100))
    try:
        actions = fetch_governance_actions(page=page, count=count)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Blockfrost indisponível: {e}")
    return {
        "count": len(actions),
        "actions": [
            {
                "gov_action_id": a.gov_action_id,
                "action_type":   a.action_type,
                "epoch_expiry":  a.epoch_expiry,
                "anchor_url":    a.anchor_url,
            }
            for a in actions
        ],
    }


@app.get("/analysis/{gov_action_id:path}")
def get_action_analysis(gov_action_id: str):
    """Análise PIL completa. 404 enquanto o worker ainda não processou a action."""
    try:
        analysis = get_analysis(gov_action_id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Banco indisponível: {e}")

    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail=f"Análise de '{gov_action_id}' ainda não disponível. "
                   "As análises são geradas em lote pelo worker PIL.",
        )
    return analysis


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"API ({NETWORK}) em http://localhost:{port}")
    print(f"Docs em          http://localhost:{port}/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
