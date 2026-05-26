import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from step1_indexer    import fetch_governance_actions
from step2_anchor     import fetch_and_validate_anchor, extract_cip108_fields
from step3_summarizer import generate_summaries
from step4_publish    import build_pil_document, compute_document_hash, publish_on_chain
from database         import get_all_actions, get_action, count_actions, save_conflict_and_risk
from step8_similarity import analyze_similarity
from step10_conflict  import detect_conflicts
from step11_risk_score import compute_risk_score

_cache: dict = {}

app = FastAPI(title="Proposal Intelligence Layer API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/")
def root():
    return {"name": "Proposal Intelligence Layer", "version": "1.0.0", "network": "preview"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stats")
def stats():
    try:
        total = count_actions()
        return {"total_analyzed": total, "network": "mainnet"}
    except Exception:
        return {"total_analyzed": 0, "network": "mainnet"}


@app.get("/governance/history")
def history(limit: int = 50, offset: int = 0):
    """Lista proposals já analisadas e salvas no banco."""
    try:
        actions = get_all_actions(limit=limit, offset=offset)
        return {"count": len(actions), "total": count_actions(), "actions": actions}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Banco indisponível: {e}")


@app.get("/governance/actions")
def list_actions(page: int = 1, count: int = 10):
    actions = fetch_governance_actions(page=page, count=count)
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
def get_analysis(gov_action_id: str, force: bool = False):
    if gov_action_id in _cache and not force:
        return _cache[gov_action_id]

    actions = fetch_governance_actions(count=50)
    action  = next((a for a in actions if a.gov_action_id == gov_action_id), None)
    if not action:
        raise HTTPException(status_code=404, detail=f"Governance action '{gov_action_id}' not found.")

    result = {"gov_action_id": gov_action_id, "action_type": action.action_type, "steps": {}, "errors": []}
    fields = {}

    # ── S2–S4: only when anchor URL exists ───────────────────────────────────
    if not action.anchor_url:
        result["errors"].append("No anchor URL.")
        result["steps"]["s2_anchor"] = "skipped"
    else:
        # S2 — Anchor
        try:
            anchor_doc = fetch_and_validate_anchor(action.anchor_url, action.anchor_hash or "")
            result["steps"]["s2_anchor"] = "ok" if anchor_doc.hash_valid else "hash_mismatch"
            result["anchor_hash_valid"]  = anchor_doc.hash_valid
            if not anchor_doc.parsed:
                result["errors"].append(f"Parse error: {anchor_doc.parse_error}")
            else:
                fields = extract_cip108_fields(anchor_doc.parsed)
                result["cip108_title"] = fields.get("title", "")
        except Exception as e:
            result["errors"].append(f"S2 error: {e}")
            result["steps"]["s2_anchor"] = "error"

        # S3 — Summarizer (only if we have fields)
        if fields:
            summaries = {}
            try:
                summaries = generate_summaries(fields, action.action_type, action.deposit)
                result["summaries"]              = summaries
                result["steps"]["s3_summarizer"] = "ok"
            except Exception as e:
                result["errors"].append(f"S3 error: {e}")
                result["steps"]["s3_summarizer"] = "error"
                summaries = {"one_liner": fields.get("title", ""), "technical": "", "full": {}}

            # S4 — Document + on-chain
            try:
                doc      = build_pil_document(gov_action_id, action.action_type,
                                              action.anchor_url, action.anchor_hash or "", summaries)
                doc_hash = compute_document_hash(doc)
                result["pil_document_hash"]    = doc_hash
                result["pil_document"]         = doc
                result["steps"]["s4_document"] = "ok"

                try:
                    on_chain = publish_on_chain(doc, doc_hash)
                    result["on_chain"]            = on_chain
                    result["steps"]["s4_onchain"] = on_chain.get("status", "error")
                except Exception as e:
                    result["errors"].append(f"On-chain error: {e}")
                    result["steps"]["s4_onchain"] = "error"
            except Exception as e:
                result["errors"].append(f"S4 error: {e}")
                result["steps"]["s4_document"] = "error"

    # ── M2 — Similarity search ────────────────────────────────────────────────
    text_for_embed = " ".join(filter(None, [
        fields.get("title"), fields.get("abstract"), fields.get("motivation")
    ]))
    try:
        sim = analyze_similarity(gov_action_id, text=text_for_embed or None)
        result["similarity"]             = sim
        result["steps"]["s8_similarity"] = "ok"
    except Exception as e:
        result["similarity"]             = None
        result["steps"]["s8_similarity"] = "skipped"

    # ── M3 — Conflict of Interest ─────────────────────────────────────────────
    conflict_result = {}
    try:
        print(f"[M3] Starting conflict detection for {gov_action_id[:20]}...")
        tx_hash_part  = gov_action_id.split("#")[0]
        cert_idx_part = int(gov_action_id.split("#")[1]) if "#" in gov_action_id else 0
        conflict_result                = detect_conflicts(gov_action_id, tx_hash_part, cert_idx_part, action.action_type)
        result["conflict"]             = conflict_result
        result["steps"]["m3_conflict"] = conflict_result.get("status", "error")
        print(f"[M3] Done: {conflict_result.get('status')}, {len(conflict_result.get('conflicts', []))} conflicts")
    except Exception as e:
        import traceback; traceback.print_exc()
        result["conflict"]             = {"status": "error", "conflicts": [], "error": str(e)}
        result["steps"]["m3_conflict"] = "error"

    # ── M4 — Risk Score ───────────────────────────────────────────────────────
    try:
        print(f"[M4] Computing risk score...")
        db_record = get_action(gov_action_id) or {}
        if conflict_result.get("total_withdrawal_lovelace"):
            db_record["withdrawal_amount"] = conflict_result["total_withdrawal_lovelace"]
        db_record.setdefault("gov_action_id", gov_action_id)
        db_record.setdefault("action_type",   action.action_type)
        for f in ("title", "abstract", "motivation", "rationale"):
            db_record.setdefault(f, fields.get(f, ""))

        from step8_similarity import find_similar
        raw_similar = find_similar(gov_action_id, top_n=5)
        risk                        = compute_risk_score(db_record, conflicts=conflict_result.get("conflicts", []), similar=raw_similar)
        result["risk_score"]        = risk
        result["steps"]["m4_risk"]  = "ok"
        print(f"[M4] Done: {risk['total']}/100 — {risk['level']}")

        try:
            save_conflict_and_risk(
                gov_action_id     = gov_action_id,
                conflict_data     = conflict_result,
                risk_score        = risk["total"],
                risk_components   = risk["components"],
                withdrawal_amount = conflict_result.get("total_withdrawal_lovelace"),
                proposer_address  = (conflict_result.get("proposer_addresses") or [None])[0],
            )
        except Exception as e:
            print(f"[M4] DB save error: {e}")
    except Exception as e:
        import traceback; traceback.print_exc()
        result["risk_score"]       = None
        result["steps"]["m4_risk"] = "error"

    _cache[gov_action_id] = result
    return result


if __name__ == "__main__":
    print("API rodando em http://localhost:8000")
    print("Docs em      http://localhost:8000/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
