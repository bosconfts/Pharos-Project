"""
Verify that a Pharos analysis is the one anchored on Cardano mainnet.

    python scripts/verify_analysis.py "<gov_action_id>"

Standard library only (certifi is used if installed), no API key. The
document comes from the Pharos API, the
transaction metadata from Koios (a public Cardano API). The script recomputes
the document's blake2b-256 hash exactly as the publisher does and compares it
with the hash written in metadatum 1694.
"""
import hashlib
import json
import ssl
import sys
import urllib.parse
import urllib.request

# Some machines ship an outdated certificate store (seen on Windows with
# Python 3.14). Use certifi's bundle when it is installed.
try:
    import certifi
    _TLS = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _TLS = ssl.create_default_context()

PHAROS_API = "https://pharos-project-sigma.vercel.app"
KOIOS      = "https://api.koios.rest/api/v1"


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "pharos-verify"})
    with urllib.request.urlopen(req, timeout=60, context=_TLS) as r:
        return json.load(r)


def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "pharos-verify"})
    with urllib.request.urlopen(req, timeout=60, context=_TLS) as r:
        return json.load(r)


def document_hash(doc: dict) -> str:
    # Same serialization as core/step4_publish.compute_document_hash.
    serialized = json.dumps(doc, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.blake2b(serialized, digest_size=32).hexdigest()


def verify(gov_action_id: str) -> bool:
    analysis = _get(f"{PHAROS_API}/analysis/{urllib.parse.quote(gov_action_id, safe='')}")
    doc      = analysis.get("pil_document")
    tx_hash  = (analysis.get("on_chain") or {}).get("tx_hash")
    if not doc:
        print("No PIL document for this action.")
        return False
    if not tx_hash:
        print("This analysis has not been anchored on chain yet.")
        return False

    recomputed = document_hash(doc)
    meta = _post(f"{KOIOS}/tx_metadata", {"_tx_hashes": [tx_hash]})
    on_chain = ((meta[0].get("metadata") or {}).get("1694") or {}) if meta else {}

    print(f"Proposal            {gov_action_id}")
    print(f"Anchoring tx        {tx_hash}")
    print(f"                    https://cardanoscan.io/transaction/{tx_hash}")
    print(f"Hash on chain       {on_chain.get('doc_hash')}")
    print(f"Hash recomputed     {recomputed}")
    print(f"Method version      {on_chain.get('pil_v')}")

    ok = (on_chain.get("doc_hash") == recomputed
          and on_chain.get("tx_hash") == gov_action_id.split("#")[0])
    print("MATCH — the published analysis is the anchored one." if ok else
          "MISMATCH — the published document differs from the anchored one.")
    return ok


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(0 if verify(sys.argv[1]) else 1)
