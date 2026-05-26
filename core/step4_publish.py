import os
import json
import hashlib
import datetime
from dotenv import load_dotenv

load_dotenv()

PIL_VERSION = "1.0.0"
BLOCKFROST_PROJECT_ID = os.getenv("BLOCKFROST_PROJECT_ID", "")
BLOCKFROST_BASE_URL   = os.getenv("BLOCKFROST_BASE_URL", "https://cardano-preview.blockfrost.io/api/v0")
PIL_SIGNING_KEY_PATH  = os.getenv("PIL_SIGNING_KEY_PATH", "wallet/payment.skey")
PIL_WALLET_ADDRESS    = os.getenv("PIL_WALLET_ADDRESS", "")


def blake2b_256(data: bytes) -> str:
    return hashlib.blake2b(data, digest_size=32).hexdigest()

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def now_iso() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def build_pil_document(
    gov_action_id:        str,
    action_type:          str,
    original_anchor_url:  str,
    original_anchor_hash: str,
    summaries:            dict,
    risk_score:           dict = None,
    similar_proposals:    list = None,
    conflicts:            list = None,
) -> dict:

    one_liner = summaries.get("one_liner", "")
    technical = summaries.get("technical", "")
    full      = summaries.get("full", {})

    doc = {
        "@context": [
            "https://raw.githubusercontent.com/cardano-foundation/CIPs/master/CIP-0100/cip-0100.common.jsonld",
            "https://raw.githubusercontent.com/cardano-foundation/CIPs/master/CIP-0108/cip-0108.jsonld",
            "ipfs://bafkreia3tlkir4n7iornbfxhqbmu5gmlc4n7xw5pvpskbzhe5kmz3v2ktm",
        ],
        "@type": "GovernanceMetadata",
        "hashAlgorithm": "blake2b-256",
        "authors": [{"name": f"Proposal Intelligence Layer {PIL_VERSION}", "uri": "https://cardano-pil.org"}],
        "title":      f"PIL Analysis — {gov_action_id}",
        "abstract":   one_liner,
        "motivation": "Reduzir assimetria de informação entre proponentes e votantes.",
        "rationale":  f"Análise gerada pelo PIL v{PIL_VERSION}. Pipeline determinístico open-source.",
        "pilAnalysis": {
            "pilVersion":     PIL_VERSION,
            "pilGeneratedAt": now_iso(),
            "pilActionType":  action_type,
            "pilBodyHash": {
                "algorithm": "blake2b-256",
                "value":     original_anchor_hash,
                "sourceUri": original_anchor_url,
            },
            "pilSummary": {
                "summaryOneLiner": one_liner,
                "summaryTechnical": technical,
                "summaryFull": full,
            },
            "pilSimilarProposals": similar_proposals or [],
            "pilConflicts":        conflicts or [],
            "pilRiskScore": risk_score or {
                "scoreTotal": None,
                "scoreInterpretation": "PENDING",
                "note": "Disponível após M2 e M3.",
            },
            "pilMerkleRoot": None,
        },
        "references": [
            {
                "@type": "Other",
                "label": "Governance Action Original",
                "uri":   original_anchor_url,
                "referenceHash": {"hashDigest": original_anchor_hash, "hashAlgorithm": "blake2b-256"},
            }
        ],
    }

    leaves = [
        blake2b_256(original_anchor_hash.encode()),
        blake2b_256(PIL_VERSION.encode()),
        blake2b_256(json.dumps(summaries, sort_keys=True).encode()),
    ]
    doc["pilAnalysis"]["pilMerkleRoot"] = {
        "algorithm": "sha256",
        "value":     sha256_hex("".join(leaves).encode()),
        "leaves":    ["blake2b-256(anchor_hash)", "blake2b-256(pil_version)", "blake2b-256(summaries)"],
    }

    return doc


def compute_document_hash(doc: dict) -> str:
    serialized = json.dumps(doc, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return blake2b_256(serialized)


def publish_on_chain(doc: dict, doc_hash: str) -> dict:
    """
    Publica o hash do documento PIL on-chain na Preview Testnet
    usando metadatum 1694 (CIP-100).
    Retorna {"tx_hash": "...", "status": "submitted"} ou {"status": "skipped", "reason": "..."}.
    """
    if not PIL_SIGNING_KEY_PATH or not os.path.exists(PIL_SIGNING_KEY_PATH):
        return {"status": "skipped", "reason": "PIL_SIGNING_KEY_PATH não configurado ou arquivo não encontrado"}

    if not PIL_WALLET_ADDRESS:
        return {"status": "skipped", "reason": "PIL_WALLET_ADDRESS não configurado"}

    if not BLOCKFROST_PROJECT_ID:
        return {"status": "skipped", "reason": "BLOCKFROST_PROJECT_ID não configurado"}

    try:
        from pycardano import (
            BlockFrostChainContext,
            TransactionBuilder,
            Address,
            PaymentSigningKey,
            AuxiliaryData,
            AlonzoMetadata,
            Metadata,
        )

        from blockfrost import ApiUrls
        context = BlockFrostChainContext(
            project_id=BLOCKFROST_PROJECT_ID.strip(),
            base_url=ApiUrls.mainnet.value,
        )

        skey    = PaymentSigningKey.load(PIL_SIGNING_KEY_PATH)
        address = Address.decode(PIL_WALLET_ADDRESS)

        # Metadatum 1694 — CIP-100 governance metadata
        # Cardano metadata: strings max 64 bytes cada
        def _trunc(s: str, max_bytes: int = 64) -> str:
            enc = s.encode("utf-8")
            return enc[:max_bytes].decode("utf-8", errors="ignore") if len(enc) > max_bytes else s

        pil_analysis  = doc.get("pilAnalysis", {})
        gov_action_id = doc.get("title", "").replace("PIL Analysis — ", "")
        tx_hash, cert_index = gov_action_id.split("#") if "#" in gov_action_id else (gov_action_id, "0")
        metadata_payload = {
            1694: {
                "pil_v":      PIL_VERSION,
                "tx_hash":    tx_hash,
                "cert_index": int(cert_index),
                "doc_hash":   doc_hash,
                "type":       _trunc(pil_analysis.get("pilActionType", "")),
                "summary":    _trunc(doc.get("abstract", "")),
            }
        }

        auxiliary_data = AuxiliaryData(
            AlonzoMetadata(metadata=Metadata(metadata_payload))
        )

        builder = TransactionBuilder(context)
        builder.add_input_address(address)
        builder.auxiliary_data = auxiliary_data

        tx = builder.build_and_sign([skey], change_address=address)
        context.submit_tx(tx)

        tx_hash = str(tx.id)
        return {"status": "submitted", "tx_hash": tx_hash}

    except Exception as e:
        import traceback
        return {"status": "error", "reason": str(e), "traceback": traceback.format_exc()}


if __name__ == "__main__":
    print("=== PIL M1 — Step 4: Document Builder ===\n")

    sample_summaries = {
        "one_liner": "Teste de documento PIL.",
        "technical": "Documento gerado para validação do pipeline.",
        "full": {"o_que_esta_sendo_proposto": "Teste"},
    }

    doc  = build_pil_document("test#0", "InfoAction", "https://example.com", "abc123" + "0"*58, sample_summaries)
    hash = compute_document_hash(doc)

    print(f"Documento montado com sucesso.")
    print(f"Hash: {hash}")
    print(f"Merkle root: {doc['pilAnalysis']['pilMerkleRoot']['value']}")

    with open("pil_test_document.json", "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    print(f"\nDocumento salvo em: pil_test_document.json")