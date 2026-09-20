import hashlib
import json
import httpx
from dataclasses import dataclass
from typing import Optional


def blake2b_256(data: bytes) -> str:
    return hashlib.blake2b(data, digest_size=32).hexdigest()


# Gateways públicos de IPFS, em ordem de preferência. Um 504 do ipfs.io é
# rotina e já deixou dez actions sem M1 — o documento é endereçado por conteúdo
# e o hash é conferido abaixo, então buscar de outro gateway é equivalente.
IPFS_GATEWAYS = (
    "https://ipfs.io/ipfs/",
    "https://gateway.pinata.cloud/ipfs/",
    "https://dweb.link/ipfs/",
    "https://cf-ipfs.com/ipfs/",
)


def extract_ipfs_cid(url: str) -> Optional[str]:
    """CID de um `ipfs://` ou de uma URL de gateway; None se não for IPFS."""
    if url.startswith("ipfs://"):
        return url[7:].lstrip("/") or None
    marker = "/ipfs/"
    idx = url.find(marker)
    if idx != -1:
        return url[idx + len(marker):].lstrip("/") or None
    return None


def resolve_ipfs_url(url: str) -> str:
    cid = extract_ipfs_cid(url)
    if url.startswith("ipfs://") and cid:
        return IPFS_GATEWAYS[0] + cid
    return url


def anchor_url_candidates(url: str) -> list:
    """A URL declarada primeiro, depois os demais gateways para o mesmo CID."""
    cid = extract_ipfs_cid(url)
    if not cid:
        return [url]

    candidates = [resolve_ipfs_url(url)]
    for gateway in IPFS_GATEWAYS:
        candidate = gateway + cid
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


@dataclass
class AnchorDocument:
    url:           str
    raw_bytes:     bytes
    computed_hash: str
    declared_hash: str
    hash_valid:    bool
    parsed:        Optional[dict]
    parse_error:   Optional[str]


def fetch_and_validate_anchor(anchor_url: str, anchor_hash: str) -> AnchorDocument:
    candidates = anchor_url_candidates(anchor_url)
    raw_bytes  = None
    last_error = None

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for candidate in candidates:
            try:
                resp = client.get(candidate)
                resp.raise_for_status()
                raw_bytes = resp.content
                break
            except Exception as e:
                last_error = e

    if raw_bytes is None:
        raise RuntimeError(
            f"nenhum dos {len(candidates)} gateway(s) respondeu para "
            f"'{anchor_url}' — último erro: {last_error}"
        )

    computed_hash = blake2b_256(raw_bytes)
    hash_valid    = (computed_hash.lower() == anchor_hash.lower())

    parsed      = None
    parse_error = None
    try:
        parsed = json.loads(raw_bytes)
    except Exception as e:
        parse_error = str(e)

    return AnchorDocument(
        url=anchor_url,
        raw_bytes=raw_bytes,
        computed_hash=computed_hash,
        declared_hash=anchor_hash,
        hash_valid=hash_valid,
        parsed=parsed,
        parse_error=parse_error,
    )


def extract_cip108_fields(doc: dict) -> dict:
    body = doc.get("body", doc)
    return {
        "title":           body.get("title", ""),
        "abstract":        body.get("abstract", ""),
        "motivation":      body.get("motivation", ""),
        "rationale":       body.get("rationale", ""),
        "references":      body.get("references", []),
        "authors":         doc.get("authors", []),
        "hash_algorithm":  doc.get("hashAlgorithm", "blake2b-256"),
        "withdraw_amount": body.get("withdrawAmount"),
        "milestones":      body.get("milestones", []),
    }


if __name__ == "__main__":
    print("=== PIL M1 — Step 2: Anchor Fetcher ===\n")
    print("Use fetch_and_validate_anchor(url, hash) para testar.")
    print("Exemplo de uso no run_m1.py")