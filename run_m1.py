import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "core"))

from dotenv import load_dotenv
load_dotenv()

from step1_indexer    import fetch_governance_actions
from step2_anchor     import fetch_and_validate_anchor, extract_cip108_fields
from step3_summarizer import generate_summaries
from step4_publish    import build_pil_document, compute_document_hash, publish_on_chain


def run_pipeline(gov_action, verbose=True):
    gid = gov_action.gov_action_id
    sep = "─" * 60
    result = {"gov_action_id": gid, "steps": {}, "errors": []}

    if verbose:
        print(f"\n{sep}")
        print(f"PIL M1 Pipeline — {gid}")
        print(f"Tipo: {gov_action.action_type}")
        print(sep)

    # S1
    result["steps"]["s1_indexer"] = "ok"
    if verbose:
        print(f"\n✅ S1 Indexer — action encontrada")
        print(f"   Anchor URL:  {gov_action.anchor_url or '(sem anchor)'}")

    if not gov_action.anchor_url:
        result["errors"].append("Sem anchor_url.")
        result["steps"]["s2_anchor"] = "skipped"
        return result

    # S2
    if verbose: print(f"\n🔄 S2 Anchor — buscando documento...")
    try:
        anchor_doc = fetch_and_validate_anchor(gov_action.anchor_url, gov_action.anchor_hash or "")
        result["steps"]["s2_anchor"] = "ok" if anchor_doc.hash_valid else "hash_mismatch"
        if verbose:
            status = "✅ válido" if anchor_doc.hash_valid else "⚠️  mismatch"
            print(f"   Hash: {status}")
            print(f"   Bytes recebidos: {len(anchor_doc.raw_bytes)}")

        if not anchor_doc.parsed:
            result["errors"].append(f"Parse error: {anchor_doc.parse_error}")
            return result

        fields = extract_cip108_fields(anchor_doc.parsed)
        if verbose:
            print(f"   Título: {fields.get('title', '(sem título)')[:70]}")

    except Exception as e:
        result["errors"].append(f"S2 erro: {e}")
        result["steps"]["s2_anchor"] = "error"
        if verbose: print(f"   ❌ Erro: {e}")
        return result

    # S3
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key or key == "sk-ant-...":
        if verbose: print(f"\n⚠️  S3 Summarizer — ANTHROPIC_API_KEY não configurada, pulando")
        result["steps"]["s3_summarizer"] = "skipped"
        result["summaries"] = None
    else:
        if verbose: print(f"\n🔄 S3 Summarizer — gerando resumos...")
        try:
            summaries = generate_summaries(fields, gov_action.action_type, gov_action.deposit)
            result["summaries"] = summaries
            result["steps"]["s3_summarizer"] = "ok"
            if verbose:
                print(f"   ✅ {summaries.get('one_liner','')[:70]}...")
                print(f"   ✅ Completeness: {summaries.get('metadata',{}).get('completeness_score','?')}/100")
        except Exception as e:
            result["errors"].append(f"S3 erro: {e}")
            result["steps"]["s3_summarizer"] = "error"
            if verbose: print(f"   ❌ Erro: {e}")

    # S4
    if verbose: print(f"\n🔄 S4 Document Builder...")
    try:
        summaries_for_doc = result.get("summaries") or {
            "one_liner": "(resumos pendentes — configure ANTHROPIC_API_KEY)",
            "technical": "",
            "full": {},
        }
        doc      = build_pil_document(gid, gov_action.action_type, gov_action.anchor_url, gov_action.anchor_hash or "", summaries_for_doc)
        doc_hash = compute_document_hash(doc)
        result["pil_document_hash"] = doc_hash
        result["steps"]["s4_document"] = "ok"

        out = f"pil_{gid.replace('#','_')}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)

        if verbose:
            print(f"   ✅ Hash: {doc_hash[:32]}...")
            print(f"   📄 Salvo em: {out}")

        # S4b — Publicação on-chain
        if verbose: print(f"\n🔄 S4b On-chain — submetendo metadatum 1694...")
        on_chain = publish_on_chain(doc, doc_hash)
        result["on_chain"] = on_chain
        result["steps"]["s4_onchain"] = on_chain.get("status", "error")
        if verbose:
            if on_chain["status"] == "submitted":
                print(f"   ✅ TX submetida: {on_chain['tx_hash']}")
            elif on_chain["status"] == "skipped":
                print(f"   ⚠️  Pulado: {on_chain['reason']}")
            else:
                print(f"   ❌ Erro: {on_chain.get('reason','')}")
                if on_chain.get("traceback"):
                    print(on_chain["traceback"])

    except Exception as e:
        result["errors"].append(f"S4 erro: {e}")
        result["steps"]["s4_document"] = "error"
        if verbose: print(f"   ❌ Erro: {e}")

    if verbose:
        print(f"\n{sep}")
        print("RESUMO")
        print(sep)
        for step, status in result["steps"].items():
            icon = "✅" if status in ("ok", "submitted") else ("⚠️ " if status in ("skipped", "hash_mismatch") else "❌")
            print(f"  {icon} {step}: {status}")
        if result["errors"]:
            print("\nAvisos:")
            for e in result["errors"]:
                print(f"  ⚠️  {e}")

    return result


if __name__ == "__main__":
    import os
    network = os.getenv("BLOCKFROST_BASE_URL", "").replace("https://", "").split(".")[0]
    print("=== PIL M1 — Pipeline Runner ===\n")
    print(f"Rede: {network}\n")
    print("Buscando governance actions...\n")

    actions = fetch_governance_actions(count=50)

    action_with_anchor = next((a for a in actions if a.anchor_url), None)

    if not action_with_anchor:
        print(f"Encontradas {len(actions)} actions, nenhuma com anchor URL.")
        print("Tente rodar novamente — a mainnet tem centenas de proposals.")
    else:
        print(f"Encontradas {len(actions)} actions. Processando primeira com anchor...\n")
        run_pipeline(action_with_anchor, verbose=True)