# Verify a Pharos analysis

Every analysis Pharos publishes is anchored on Cardano mainnet. The chain does
not hold the analysis itself; it holds its **blake2b-256 hash**, in a
transaction with metadatum label **1694**. If anyone changed the analysis after
it was anchored, its hash would no longer match the one on chain.

This page shows how to check that yourself. No account or API key is needed.

## With the script (one command)

```bash
python scripts/verify_analysis.py "f35285db3c4e085ad331843b3007737952b8a322bb3216311edc37fdf44ad3da#0"
```

```
Proposal            f35285db3c4e085ad331843b3007737952b8a322bb3216311edc37fdf44ad3da#0
Anchoring tx        eba395fdc3b2d80e5bc33bf706a56dcc1cf73eeae41419ce069d00aa2190564c
                    https://cardanoscan.io/transaction/eba395fdc3b2d80e5bc33bf706a56dcc1cf73eeae41419ce069d00aa2190564c
Hash on chain       55c5d968b236313b75fa2888c6aafefe163b7b6e03df76204c4773f23e542333
Hash recomputed     55c5d968b236313b75fa2888c6aafefe163b7b6e03df76204c4773f23e542333
Method version      1.0.0
MATCH — the published analysis is the anchored one.
```

The script uses only the Python standard library. It downloads the analysis
from the Pharos API, recomputes the hash the same way the publisher does, reads
the anchoring transaction from Koios (a public Cardano API), and compares the
two. It exits with status 0 on a match and 1 otherwise.

## By hand

1. **Open a proposal** on [pharosgov.io](https://pharosgov.io). Under
   *Provenance*, note **This analysis** (the document hash) and follow the
   **On-chain record** link to Cardanoscan.
2. **On Cardanoscan**, open the transaction's *Metadata* tab. Under label
   `1694` you will find:

   | Field | Meaning |
   |---|---|
   | `tx_hash`, `cert_index` | The governance action that was analysed |
   | `doc_hash` | blake2b-256 of the analysis document |
   | `pil_v` | The analysis method version |
   | `type`, `summary` | Action type and the first 64 bytes of the summary |

   `doc_hash` must equal the hash shown on the page.
3. **Recompute the hash** of the document the API serves. The document is the
   `pil_document` field of
   `https://pharos-project-sigma.vercel.app/analysis/<gov_action_id>` (write the
   `#` in the id as `%23`). The hash is taken over its JSON serialization with
   keys sorted and non-ASCII characters kept:

   ```python
   import hashlib, json
   hashlib.blake2b(json.dumps(doc, sort_keys=True, ensure_ascii=False).encode(), digest_size=32).hexdigest()
   ```

## What a match proves, and what it doesn't

A match proves the analysis you are reading is byte-for-byte the one Pharos
committed to on chain, at the time of that transaction. It also proves which
proposal document was analysed: `pilAnalysis.pilBodyHash` holds the hash of the
proposal's own anchor document.

It does not prove the analysis is right. The summaries are written by a
language model, and the score follows the method version shown in `pil_v`,
whose limits are documented in [`m4-score-audit.md`](m4-score-audit.md).

## Actions that cannot be verified

Of the 158 governance actions indexed, 154 have an anchored analysis. Three
carry no proposal document on chain, so there is nothing to analyse. One
proposal's document was deleted by its author after submission: Pharos cannot
check its hash, so it does not anchor an analysis of it.

## The `pil:` vocabulary

Each document references the JSON-LD context
`ipfs://bafkreia3tlkir4n7iornbfxhqbmu5gmlc4n7xw5pvpskbzhe5kmz3v2ktm`. A copy is
in [`pil-context-v1.jsonld`](pil-context-v1.jsonld); its content hashes to that
CID.
