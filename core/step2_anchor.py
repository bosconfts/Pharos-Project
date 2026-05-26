import hashlib
import json
import httpx
from dataclasses import dataclass
from typing import Optional


def blake2b_256(data: bytes) -> str:
    return hashlib.blake2b(data, digest_size=32).hexdigest()


def resolve_ipfs_url(url: str) -> str:
    if url.startswith("ipfs://"):
        cid = url[7:]
        return f"https://ipfs.io/ipfs/{cid}"
    return url


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
    resolved_url = resolve_ipfs_url(anchor_url)

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        resp = client.get(resolved_url)
        resp.raise_for_status()
        raw_bytes = resp.content

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