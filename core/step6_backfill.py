"""
Step 6 — Backfill Histórico
Busca todas as governance actions da mainnet desde Chang (ago/2024)
e persiste no banco com embeddings.
Resumível: pula actions já processadas.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

import httpx
from database import init_db, upsert_action, get_action, count_actions
from step2_anchor import fetch_and_validate_anchor, extract_cip108_fields
from step3_summarizer import generate_summaries
from step4_publish import build_pil_document, compute_document_hash
from step7_embeddings import embed_text

BLOCKFROST_PROJECT_ID = os.getenv("BLOCKFROST_PROJECT_ID")
BLOCKFROST_BASE_URL   = os.getenv("BLOCKFROST_BASE_URL", "https://cardano-mainnet.blockfrost.io/api/v0")
HEADERS = {"project_id": BLOCKFROST_PROJECT_ID}

# Chang hard fork: epoch 509, ~setembro 2024
# Buscamos todas as proposals em ordem ascendente (mais antigas primeiro)


def _fetch_metadata(client, tx_hash, cert_index):
    url  = f"{BLOCKFROST_BASE_URL}/governance/proposals/{tx_hash}/{cert_index}/metadata"
    resp = client.get(url, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else {}


def _fetch_detail(client, tx_hash, cert_index):
    url  = f"{BLOCKFROST_BASE_URL}/governance/proposals/{tx_hash}/{cert_index}"
    resp = client.get(url, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else {}


ACTION_TYPE_MAP = {
    "info_action":           "InfoAction",
    "treasury_withdrawals":  "TreasuryWithdrawals",
    "parameter_change":      "ParameterChange",
    "hard_fork_initiation":  "HardForkInitiation",
    "no_confidence":         "NoConfidence",
    "new_committee":         "NewCommittee",
    "new_constitution":      "NewConstitution",
    "update_committee":      "UpdateCommittee",
}


def fetch_all_proposals() -> list[dict]:
    """Busca todas as proposals paginando até o fim."""
    all_proposals = []
    page = 1
    print("Fetching proposals from mainnet...", end="", flush=True)

    with httpx.Client(timeout=30) as client:
        while True:
            resp = client.get(
                f"{BLOCKFROST_BASE_URL}/governance/proposals",
                headers=HEADERS,
                params={"page": page, "count": 100, "order": "asc"},
            )
            if resp.status_code == 404 or not resp.json():
                break
            batch = resp.json()
            if not batch:
                break
            all_proposals.extend(batch)
            print(f" {len(all_proposals)}", end="", flush=True)
            if len(batch) < 100:
                break
            page += 1
            time.sleep(0.1)  # rate limit gentil

    print(f"\nTotal found: {len(all_proposals)} proposals")
    return all_proposals


def process_proposal(client: httpx.Client, item: dict, verbose: bool = True) -> bool:
    """Processa uma proposal: busca anchor, gera resumos, embeddings e persiste."""
    tx_hash    = item["tx_hash"]
    cert_index = item["cert_index"]
    gov_id     = f"{tx_hash}#{cert_index}"
    gov_type   = ACTION_TYPE_MAP.get(item.get("governance_type", ""), item.get("governance_type", "Unknown"))

    # Skip if already processed (unless force mode)
    existing = get_action(gov_id)
    if existing and existing.get("embedding") is not None and not getattr(process_proposal, "_force", False):
        if verbose: print(f"  ⏭  {gov_id[:20]}... already processed")
        return True

    meta   = _fetch_metadata(client, tx_hash, cert_index)
    detail = _fetch_detail(client, tx_hash, cert_index)

    anchor_url  = meta.get("url")
    anchor_hash = meta.get("hash", "")

    record = {
        "gov_action_id":    gov_id,
        "tx_hash":          tx_hash,
        "cert_index":       cert_index,
        "action_type":      gov_type,
        "anchor_url":       anchor_url,
        "anchor_hash":      anchor_hash,
        "deposit":          int(detail.get("deposit", 0)),
        "epoch_expiry":     detail.get("expiration"),
        "ratified_epoch":   detail.get("ratified_epoch"),
        "enacted_epoch":    detail.get("enacted_epoch"),
        "expired_epoch":    detail.get("expired_epoch"),
        "dropped_epoch":    detail.get("dropped_epoch"),
        "title":            None,
        "abstract":         None,
        "motivation":       None,
        "rationale":        None,
        "one_liner":        None,
        "technical":        None,
        "full_summary":     None,
        "completeness_score": None,
        "pil_doc_hash":     None,
        "on_chain_tx":      None,
        "embedding":        None,
    }

    # CIP-108 fields
    json_meta = meta.get("json_metadata") or {}
    if json_meta:
        try:
            fields = extract_cip108_fields(json_meta)
            record.update({
                "title":      fields.get("title"),
                "abstract":   fields.get("abstract"),
                "motivation": fields.get("motivation"),
                "rationale":  fields.get("rationale"),
            })
        except Exception:
            pass
    elif anchor_url:
        try:
            anchor_doc = fetch_and_validate_anchor(anchor_url, anchor_hash)
            if anchor_doc.parsed:
                fields = extract_cip108_fields(anchor_doc.parsed)
                record.update({
                    "title":      fields.get("title"),
                    "abstract":   fields.get("abstract"),
                    "motivation": fields.get("motivation"),
                    "rationale":  fields.get("rationale"),
                })
        except Exception:
            pass

    # Gera resumos se tiver conteúdo
    if record["title"] or record["abstract"]:
        try:
            fields_for_summary = {
                "title":      record["title"] or "",
                "abstract":   record["abstract"] or "",
                "motivation": record["motivation"] or "",
                "rationale":  record["rationale"] or "",
                "references": [],
                "authors":    [],
            }
            summaries = generate_summaries(fields_for_summary, gov_type, record["deposit"] or 0)
            record.update({
                "one_liner":          summaries.get("one_liner"),
                "technical":          summaries.get("technical"),
                "full_summary":       summaries.get("full"),
                "completeness_score": summaries.get("metadata", {}).get("completeness_score"),
            })
        except Exception as e:
            if verbose: print(f"    ⚠️  summarizer: {e}")

    # Embedding
    text_for_embed = " ".join(filter(None, [
        record.get("title"),
        record.get("abstract"),
        record.get("motivation"),
    ]))
    if text_for_embed.strip():
        try:
            record["embedding"] = embed_text(text_for_embed)
        except Exception as e:
            if verbose: print(f"    ⚠️  embedding: {e}")

    # PIL doc hash
    if record["one_liner"]:
        try:
            doc  = build_pil_document(gov_id, gov_type, anchor_url or "", anchor_hash, {
                "one_liner": record["one_liner"],
                "technical": record["technical"] or "",
                "full":      record["full_summary"] or {},
            })
            record["pil_doc_hash"] = compute_document_hash(doc)
        except Exception:
            pass

    import json
    if isinstance(record.get("full_summary"), dict):
        record["full_summary"] = json.dumps(record["full_summary"], ensure_ascii=False)

    upsert_action(record)

    status = "✅" if record["embedding"] is not None else "⚠️ "
    if verbose:
        print(f"  {status} [{gov_type}] {gov_id[:20]}... — {record.get('title', '(no title)')[:50]}")
    return True


def run_backfill(verbose: bool = True, force: bool = False):
    print("=== PIL M2 — Historical Backfill ===\n")
    if force:
        print("⚡ Force mode: re-generating summaries for all proposals\n")
        process_proposal._force = True
    else:
        process_proposal._force = False
    init_db()

    proposals = fetch_all_proposals()
    total     = len(proposals)
    initial   = count_actions()
    print(f"\nIn database: {initial} | To process: {total}\n")

    with httpx.Client(timeout=30) as client:
        for i, item in enumerate(proposals, 1):
            try:
                process_proposal(client, item, verbose=verbose)
            except Exception as e:
                print(f"  ❌ Erro em {item.get('tx_hash','?')}: {e}")
            if i % 10 == 0:
                time.sleep(0.5)  # pausa a cada 10 para não sobrecarregar APIs

    final = count_actions()
    print(f"\n✅ Backfill complete. Total in database: {final} (+{final - initial} new)")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-process all proposals (regenerate summaries)")
    args = parser.parse_args()
    run_backfill(force=args.force)
