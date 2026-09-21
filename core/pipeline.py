"""
Pipeline de análise PIL — M1 a M4.

Este módulo NUNCA publica on-chain. Ele produz e persiste a análise;
a publicação é responsabilidade exclusiva de `publisher.py`, que roda
fora do processo da API e é o único componente com acesso à signing key.
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(__file__))

from step1_indexer     import fetch_governance_actions, GovernanceAction
from step2_anchor      import fetch_and_validate_anchor, extract_cip108_fields
from step3_summarizer  import generate_summaries
from step4_publish     import build_pil_document, compute_document_hash
from step7_embeddings  import embed_text
from step8_similarity  import analyze_similarity, find_similar
from step10_conflict   import detect_conflicts
from step11_risk_score import compute_risk_score
from database          import upsert_action, get_action, save_analysis, save_conflict_and_risk


def has_genuine_summary(row: dict) -> bool:
    """A linha tem resumo de verdade, e não o fallback degradado.

    Quando o summarizer falha, o pipeline grava `one_liner = title`, `technical`
    vazio e `full` vazio, de propósito, para a página não ficar sem abertura em
    linguagem simples. Mas isso é indistinguível de uma análise real se o teste
    for só "tem one_liner" — e foi assim que 43 linhas entraram na fila de
    publicação com o título copiado no lugar da análise. Resumo real tem os três.
    """
    if not row.get("one_liner") or not row.get("technical"):
        return False

    full = row.get("full_summary")
    if isinstance(full, str):
        try:
            full = json.loads(full)
        except Exception:
            return False
    return isinstance(full, dict) and bool(full)


def _cached_summaries(gov_action_id: str, anchor_hash: str | None) -> dict | None:
    """Resumo já persistido para este mesmo documento de anchor, ou None.

    O anchor é endereçado por conteúdo: se o hash declarado pela chain é o mesmo
    que já está no banco, o texto é o mesmo e o resumo continua valendo. Isso
    existe porque o `step6_backfill` grava resumo e embedding mas não produz
    `analysis` nem `pil_document` — sem este reaproveitamento, completar o M3/M4
    dessas linhas pagaria de novo ao Claude por um texto idêntico.

    Sem hash declarado não há como provar identidade, então não reaproveita.
    """
    if not anchor_hash:
        return None

    row = get_action(gov_action_id)
    if not row or not has_genuine_summary(row):
        return None
    if (row.get("anchor_hash") or "").lower() != anchor_hash.lower():
        return None

    full = row.get("full_summary")
    if isinstance(full, str):
        try:
            full = json.loads(full)
        except Exception:
            full = {}

    return {
        "one_liner": row["one_liner"],
        "technical": row.get("technical") or "",
        "full":      full if isinstance(full, dict) else {},
        "metadata": {
            "completeness_score": row.get("completeness_score") or 0,
            "reused":             True,
        },
    }


def _index_record(action: GovernanceAction, fields: dict, summaries: dict,
                  doc_hash: str | None, embedding: list | None = None) -> dict:
    """Monta o dict que `upsert_action` espera, com todas as chaves obrigatórias."""
    meta = (summaries or {}).get("metadata", {})
    return {
        "gov_action_id": action.gov_action_id,
        "tx_hash":       action.tx_hash,
        "cert_index":    action.cert_index,
        "action_type":   action.action_type,
        "anchor_url":    action.anchor_url,
        "anchor_hash":   action.anchor_hash,
        "deposit":       action.deposit,
        "epoch_expiry":  action.epoch_expiry,
        "ratified_epoch": action.ratified_epoch,
        "enacted_epoch":  action.enacted_epoch,
        "expired_epoch":  action.expired_epoch,
        "dropped_epoch":  action.dropped_epoch,
        "title":         fields.get("title", ""),
        "abstract":      fields.get("abstract", ""),
        "motivation":    fields.get("motivation", ""),
        "rationale":     fields.get("rationale", ""),
        "one_liner":     (summaries or {}).get("one_liner"),
        "technical":     (summaries or {}).get("technical"),
        "full_summary":  json.dumps((summaries or {}).get("full", {})) if summaries else None,
        "completeness_score": meta.get("completeness_score"),
        "pil_doc_hash":  doc_hash,
        "on_chain_tx":   None,
        "embedding":     embedding,
    }


def analyze_action(action: GovernanceAction, persist: bool = True, verbose: bool = False) -> dict:
    """Roda M1–M4 sobre uma governance action e devolve o resultado estruturado.

    Nenhuma transação é submetida aqui. O documento PIL é construído e salvo
    para que o publisher possa ancorá-lo depois.
    """
    gid = action.gov_action_id
    log = print if verbose else (lambda *a, **k: None)

    result = {"gov_action_id": gid, "action_type": action.action_type, "steps": {}, "errors": []}
    fields, summaries, doc, doc_hash = {}, {}, None, None

    # ── M1: anchor → summaries → documento PIL ────────────────────────────────
    if not action.anchor_url:
        result["errors"].append("No anchor URL.")
        result["steps"]["s2_anchor"] = "skipped"
    else:
        try:
            anchor_doc = fetch_and_validate_anchor(action.anchor_url, action.anchor_hash or "")
            result["steps"]["s2_anchor"]  = "ok" if anchor_doc.hash_valid else "hash_mismatch"
            result["anchor_hash_valid"]   = anchor_doc.hash_valid
            if not anchor_doc.parsed:
                result["errors"].append(f"Parse error: {anchor_doc.parse_error}")
            else:
                fields = extract_cip108_fields(anchor_doc.parsed)
                result["cip108_title"] = fields.get("title", "")
            log(f"  S2 anchor: {result['steps']['s2_anchor']}")
        except Exception as e:
            result["errors"].append(f"S2 error: {e}")
            result["steps"]["s2_anchor"] = "error"

        if fields:
            summaries = _cached_summaries(gid, action.anchor_hash)
            if summaries:
                result["summaries"]              = summaries
                result["steps"]["s3_summarizer"] = "reused"
            else:
                try:
                    summaries = generate_summaries(fields, action.action_type, action.deposit)
                    result["summaries"]              = summaries
                    result["steps"]["s3_summarizer"] = "ok"
                except Exception as e:
                    result["errors"].append(f"S3 error: {e}")
                    result["steps"]["s3_summarizer"] = "error"
                    summaries = {"one_liner": fields.get("title", ""), "technical": "", "full": {}}
                    # Sem isto o resultado sai sem `summaries` e a pagina perde a
                    # abertura em linguagem simples: a degradacao some da vista.
                    result["summaries"] = summaries
            log(f"  S3 summarizer: {result['steps'].get('s3_summarizer')}")

    # O documento PIL (S4) é montado só depois do M4, lá embaixo. Ele era montado
    # aqui, antes de M2–M4 rodarem, e nunca refeito: o documento ancorado saía com
    # o score "PENDING" e sem conflitos nem similares — o M2–M4 inteiro ficava
    # de fora do registro on-chain.

    # ── Embedding: calculado antes do upsert para entrar no corpus de busca.
    # Se ficasse só na memória, esta action nunca seria encontrada como
    # "similar" por nenhuma outra e o M2 degradaria silenciosamente.
    text_for_embed = " ".join(filter(None, [
        fields.get("title"), fields.get("abstract"), fields.get("motivation")
    ])).strip()
    embedding = None
    if text_for_embed:
        try:
            embedding = embed_text(text_for_embed)
        except Exception as e:
            result["errors"].append(f"Embedding error: {e}")

    # Indexa antes de M2–M4 para que os UPDATEs seguintes encontrem a linha
    if persist:
        try:
            upsert_action(_index_record(action, fields, summaries, doc_hash, embedding))
        except Exception as e:
            result["errors"].append(f"DB upsert error: {e}")

    # ── M2: similaridade ──────────────────────────────────────────────────────
    similarity = None
    try:
        similarity = analyze_similarity(gid, text=text_for_embed or None)
        result["similarity"]             = similarity
        result["steps"]["s8_similarity"] = "ok"
    except Exception as e:
        result["similarity"]             = None
        result["steps"]["s8_similarity"] = "skipped"
        result["errors"].append(f"M2 skipped: {e}")
    log(f"  M2 similarity: {result['steps']['s8_similarity']}")

    # ── M3: conflito de interesse ─────────────────────────────────────────────
    conflict_result = {}
    try:
        cert_idx = int(gid.split("#")[1]) if "#" in gid else 0
        # O texto da proposta permite marcar relações que o próprio proponente
        # já declarou — declarado é transparência, não achado.
        anchor_text = " ".join(str(fields.get(f) or "") for f in
                               ("title", "abstract", "motivation", "rationale"))
        conflict_result                = detect_conflicts(gid, gid.split("#")[0], cert_idx,
                                                          action.action_type, anchor_text=anchor_text)
        result["conflict"]             = conflict_result
        result["steps"]["m3_conflict"] = conflict_result.get("status", "error")
    except Exception as e:
        result["conflict"]             = {"status": "error", "conflicts": [], "error": str(e)}
        result["steps"]["m3_conflict"] = "error"
        result["errors"].append(f"M3 error: {e}")
    log(f"  M3 conflict: {result['steps']['m3_conflict']} "
        f"({len(result['conflict'].get('conflicts', []))} conflitos)")

    # ── M4: risk score ────────────────────────────────────────────────────────
    try:
        db_record = (get_action(gid) if persist else None) or {}
        if conflict_result.get("total_withdrawal_lovelace"):
            db_record["withdrawal_amount"] = conflict_result["total_withdrawal_lovelace"]
        db_record.setdefault("gov_action_id", gid)
        db_record.setdefault("action_type",   action.action_type)
        for f in ("title", "abstract", "motivation", "rationale"):
            db_record.setdefault(f, fields.get(f, ""))

        try:
            raw_similar = find_similar(gid, top_n=5)
        except Exception:
            raw_similar = []

        risk = compute_risk_score(db_record,
                                  conflicts=conflict_result.get("conflicts", []),
                                  similar=raw_similar)
        result["risk_score"]       = risk
        result["steps"]["m4_risk"] = "ok"
        log(f"  M4 risk: {risk['total']}/100 — {risk['level']}")

        if persist:
            try:
                save_conflict_and_risk(
                    gov_action_id     = gid,
                    conflict_data     = conflict_result,
                    risk_score        = risk["total"],
                    risk_components   = risk["components"],
                    withdrawal_amount = conflict_result.get("total_withdrawal_lovelace"),
                    proposer_address  = (conflict_result.get("proposer_addresses") or [None])[0],
                )
            except Exception as e:
                result["errors"].append(f"DB conflict/risk save error: {e}")
    except Exception as e:
        result["risk_score"]       = None
        result["steps"]["m4_risk"] = "error"
        result["errors"].append(f"M4 error: {e}")

    # ── S4: documento PIL, agora com a análise completa ─────────────────────────
    if fields:
        try:
            doc = build_pil_document(
                gid, action.action_type, action.anchor_url, action.anchor_hash or "",
                summaries,
                risk_score        = result.get("risk_score"),
                similar_proposals = (similarity or {}).get("similar_proposals", []),
                conflicts         = (result.get("conflict") or {}).get("conflicts", []),
            )
            doc_hash = compute_document_hash(doc)
            result["pil_document_hash"]    = doc_hash
            result["steps"]["s4_document"] = "ok"
            log(f"  S4 document: {doc_hash[:32]}...")
        except Exception as e:
            doc, doc_hash = None, None
            result["errors"].append(f"S4 error: {e}")
            result["steps"]["s4_document"] = "error"

    if persist:
        try:
            save_analysis(gid, result, pil_document=doc, similarity_data=similarity,
                          pil_doc_hash=doc_hash)
        except Exception as e:
            result["errors"].append(f"DB analysis save error: {e}")

    return result


def analyze_by_id(gov_action_id: str, persist: bool = True, verbose: bool = False) -> dict | None:
    """Busca a action na chain pelo id e roda o pipeline. None se não encontrada."""
    for page in range(1, 6):
        actions = fetch_governance_actions(page=page, count=100)
        if not actions:
            break
        action = next((a for a in actions if a.gov_action_id == gov_action_id), None)
        if action:
            return analyze_action(action, persist=persist, verbose=verbose)
    return None
