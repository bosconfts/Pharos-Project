# Pharos — Proposal Intelligence Layer

> *An informed vote is the foundation of democracy. Pharos builds the infrastructure so that every vote on Cardano is one.*

**Pharos** is an open-source intelligence platform for Cardano governance. It reads every governance action on chain, writes a plain-language analysis of it, compares it with the proposals that came before, shows who receives the money, and anchors each analysis on Cardano mainnet so that anyone can check it was not altered afterwards.

- **Live dashboard:** [pharosgov.io](https://pharosgov.io)
- **Public API:** [pharos-project-sigma.vercel.app](https://pharos-project-sigma.vercel.app/stats) (read-only, see [API Endpoints](#api-endpoints))
- **How to verify an analysis yourself:** [`docs/verify.md`](docs/verify.md)

Cardano completed its transition to the Voltaire Era in 2025 — the first blockchain with fully on-chain constitutional governance, operated by elected DReps, SPOs, and a Constitutional Committee. The first budget cycle involved 39 treasury withdrawals totaling 275 million ADA. The second cycle, in 2026, is larger.

The problem is structural: a typical DRep cannot adequately evaluate dozens of technical proposals per epoch with no analytical support. The result is governance by social bias — voting based on who you know and trust, not on verifiable merit.

**Mission:** Reduce the information asymmetry between proposers and voters, so that every vote can be an informed and auditable decision.

---

## Status — October 2026

| | |
|---|---|
| Governance actions indexed | 158 (mainnet, since Chang) |
| Analyses produced | 155 — the other 3 actions carry no proposal document on chain |
| Analyses anchored on mainnet | 154, metadatum label 1694 — the 155th is not anchored because its author deleted the proposal document, so its hash can no longer be checked |
| Worker | Runs every 6 hours on GitHub Actions |
| Analysis method in use | PIL v1.2.0 for new analyses; all 154 anchored analyses are v1.0.0 and are never recalculated |

---

## The Problems Pharos Addresses

**Information asymmetry.** A 5M ADA treasury withdrawal arrives on chain with thousands of technical words. The proposer spent weeks writing it. The DRep has a fixed voting window, dozens of simultaneous proposals, and no analytical support.

**Who benefits is hard to see.** Where treasury money goes is on chain, but nobody lays it out next to the proposal. Most withdrawals pay smart contracts, not the vendor, which makes the trail harder to follow.

**Fragmented institutional memory.** Similar proposals have been voted on before. That history is not indexed or shown at voting time.

**No auditable signal.** There was no standardized, traceable summary of a proposal's risk factors that anyone could check.

---

## What Pharos Delivers Today

- Analysis of every governance action at 3 levels of detail (one line, one paragraph, structured)
- Similar past proposals and how their votes ended
- Who receives each treasury withdrawal, and what those wallets received before
- A Risk Score built from two signals, with the evidence behind each point
- Every analysis anchored on mainnet: its blake2b-256 hash in a metadatum-1694 transaction
- A read-only public API and a public dashboard

---

## Platform Architecture

Pharos runs a four-module pipeline over every indexed governance action. The analysis document is stored by Pharos and served by its API; its hash is anchored on chain, so any later change to the document is detectable.

```
M1 Translation → M2 Historical Cross-Ref → M3 Who Benefits → M4 Risk Score → PIL document → hash on chain
```

The platform runs as three separate processes with distinct privileges:

| Process | Entry point | Does | Holds signing key |
|---|---|---|---|
| **Worker** | `core/worker.py` | Indexes actions, runs M1–M4, persists to Postgres | No |
| **Publisher** | `core/publisher.py` | Anchors PIL document hashes on chain (metadatum 1694) | **Yes** |
| **API** | `core/step5_api.py` | Serves persisted analyses, read-only | No |

Separating these matters: analysis is expensive and batched, anchoring spends real ADA, and serving must be fast and stateless. No HTTP request can trigger a transaction. The publisher runs only on the maintainer's machine.

### M1 — Translation

For every governance action, the system fetches the anchor document (CIP-100/108), checks it against the blake2b-256 hash published on chain, and produces:

- **One line** for the ADA holder: what is being requested, how much, by whom.
- **One paragraph** for the DRep: type of action, financial impact, declared risks.
- **A structured analysis:** what is proposed, why, how, financial impact, and milestones.

Summaries are written by a language model (Claude) and are **not deterministic** — running the model again can word them differently. What is fixed is the record: the summaries are part of the anchored document, so the version voters saw can always be checked. If the anchor document fails its hash check, no analysis is produced.

### M2 — Historical Cross-Reference

Each proposal is embedded (sentence-transformers) and compared against every indexed action since Chang with pgvector. The page shows the five most similar proposals and how each vote ended: approved (ratified or enacted), expired, or still open.

This measures **how similar proposals fared in the vote**. Whether the funded work was then delivered happens off chain and is not measured — no milestone data exists on chain.

### M3 — Who Benefits

For each treasury withdrawal, Pharos lists the wallets that receive the funds, how much each receives, whether a wallet is a smart contract, and what the same wallets requested and received from the treasury before.

**Pharos does not run a conflict-of-interest check, and the page says so.** An earlier version compared the wallet that paid the submission fee with the wallets receiving the funds. In practice the submitter is usually an administrator filing many proposals at once (one wallet submitted 39 of 104 withdrawals, for different developers), and 98 of 112 payments go to smart contracts that later pay vendors. That check produced 11 HIGH-severity findings, 4 of which compared a wallet with itself. It was removed rather than publish false accusations on chain.

A study of whether DReps who vote on a withdrawal later receive part of it is in progress; it shows the link can be established for only 20 of 104 withdrawals, because most funds pass through shared contracts.

### M4 — Risk Score

The Risk Score is built only from the signals that actually separate one proposal from another. Every component shows the raw data that generated it.

| Component | Weight | What it measures |
|-----------|--------|-----------------|
| **Approval of Similar Proposals** | 60% (100% when no withdrawal) | Share of semantically similar proposals, from any author, that passed the vote (ratified or enacted). Whether the work was then delivered happens off-chain and is not measured. Needs at least 3 concluded comparables; below that it scores half (neutral). |
| **Treasury Withdrawal Size** | 40% | Amount requested as a percentage of the Net Change Limit. Only for treasury withdrawals. |

A signal that does not apply is left out rather than awarded for free. Earlier methods (1.0.0 and 1.1.0) summed six components, but half of their 100 points were near-constant across proposals — see [`docs/m4-score-audit.md`](docs/m4-score-audit.md). The analyses already anchored, all under 1.0.0, keep their original score; each page shows which method version produced it.

**Score interpretation:** ≥ 70 = LOW RISK · 45–69 = MEDIUM RISK · < 45 = HIGH RISK

**Known limitation:** the main signal predicts how a proposal is likely to fare in the vote more than how risky it is, and it partly reflects past voting behaviour. This is recorded as the open question for the next method version.

---

## Design Principles

**Immutability of input:** `pilBodyHash` records the hash of the exact proposal document that was analysed. An analysis cannot be reused for a different document.

**Tamper evidence:** the hash of each PIL document is written on chain. Anyone can recompute it from the document served by the API and compare — see [`docs/verify.md`](docs/verify.md). The document also carries a Merkle root over its parts (anchor hash, method version, summaries, score, conflicts, similar proposals), so a change in any one part is detectable on its own.

**What is and isn't deterministic:** the score, the similarity ranking for a given corpus, and the document hash are computed by deterministic code. The summaries are written by a language model and are not. Similarity depends on which proposals were indexed at analysis time (`pilGeneratedAt`).

**Anchored analyses are never rescored.** The document on chain is the record. A new method applies to new analyses, under a new `pilVersion`.

**Extensibility without breaking compatibility:** tools that don't know PIL still read the standard CIP-108 fields (title, abstract).

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Chain data | Blockfrost API | Governance actions, anchors, votes, withdrawals, wallet history (mainnet; preprod supported via `BLOCKFROST_BASE_URL`) |
| Pipeline | Python 3.12 | Worker running M1–M4 in batches |
| Summaries | Claude API | 3-level analysis of each proposal |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) | Proposal vectors for M2, worker only |
| Database | PostgreSQL 18 + pgvector (Neon) | Analyses, embeddings, similarity search |
| Public API | FastAPI on Vercel (serverless) | Read-only endpoints; no pipeline, no signing |
| On-chain registration | PyCardano + Blockfrost | Transaction with metadatum label 1694 carrying the PIL document hash |
| Frontend | React 18 + Vite | Public dashboard on GitHub Pages |
| Scheduling | GitHub Actions | Worker every 6 hours |

Neo4j appears in the code (`step9_wallet_graph.py`) as an optional wallet-graph backend, but it has never been provisioned in production; M3 runs on Blockfrost alone.

---

## CIP Alignment

Pharos extends CIP-100 (Governance Metadata) and CIP-108 (Governance Actions Metadata) via JSON-LD with its own `pil:` context.

| CIP | Function | How Pharos relates |
|-----|----------|-------------------|
| CIP-0100 | Governance Metadata — base | Base structure of the PIL document: hashAlgorithm, authors, references |
| CIP-0108 | Governance Actions Metadata | title, abstract, motivation, rationale kept for compatibility with existing explorers |
| CIP-1694 | On-chain Governance Framework | Metadatum label 1694 carries the PIL document hash |
| PIL Context v1 | `pil:` namespace | JSON-LD context on IPFS at `ipfs://bafkreia3tlkir4n7iornbfxhqbmu5gmlc4n7xw5pvpskbzhe5kmz3v2ktm`; a verified copy is in [`docs/pil-context-v1.jsonld`](docs/pil-context-v1.jsonld) |

**Known limitation:** context v1 maps `pil:` to `https://cardano-pil.org/ns/1.0#`, a domain Pharos does not own. The context file is immutable and referenced by every anchored analysis, so the fix belongs in context v2.

---

## Pharos vs. Existing Tools

Pharos does not compete with existing governance tools — it is an analysis layer meant to feed them.

| Tool | What it does | What it doesn't do | How Pharos complements |
|------|-------------|-------------------|----------------------|
| **GovTool (Intersect)** | DRep voting interface. Displays on-chain proposals | No analysis, no history of similar proposals | Pharos exposes a read-only API that a voting interface can link to (integration not yet built) |
| **Proposal Examiner (Griffin AI + CF)** | AI proposal evaluation | Output is not registered on chain. No wallet analysis | Pharos anchors each analysis's hash on chain and lists who receives the funds |
| **Cardanoscan / PoolTool** | Blockchain explorer. Shows raw on-chain data | Doesn't summarise or cross entities | Pharos links back to the explorer for every transaction it cites |
| **GHWG KPI Framework** | Defines governance health metrics | Points to off-chain data pipelines "still needing to be built" | Pharos's data covers proposal-level analysis. DRep-level metrics such as rationale rate are feasible from the same sources (36% of DRep votes on withdrawals carry a rationale link) but not yet built |

---

## Platform KPIs

| KPI | Question it answers | Today |
|-----|-------------------|-------|
| Proposal coverage | What share of governance actions have an analysis? | 155 of 158 |
| Anchoring coverage | What share of analyses are anchored on chain? | 154 of 155 |
| Analysis latency | How soon after submission is an analysis available? | Within 6 hours of indexing; anchoring is a separate manual step |
| Analysis integrity | Does the anchored hash match the published document? | Checked by the publisher before every anchor, and reproducible by anyone ([`docs/verify.md`](docs/verify.md)) |
| DRep adoption | What share of DReps consult Pharos before voting? | Not measured |
| Tool integrations | How many governance tools consume the API? | None yet |

---

## Roadmap

### Phase 1 — Foundation ✅
- Governance action indexer via Blockfrost
- M1: 3-level summaries with anchor hash validation
- CIP-100/108 document + `pil:` context on IPFS
- On-chain anchoring via PyCardano (metadatum 1694)
- Public API: `GET /analysis/{gov_action_id}`

### Phase 2 — Historical Intelligence ✅
- Backfill of all governance actions since Chang (Aug 2024)
- M2: embeddings + pgvector similarity search
- Output: similar proposals and how their votes ended
- Public dashboard at pharosgov.io

### Phase 3 — Who Benefits and Risk Score ✅ (scope changed)
- M3 planned as a conflict-of-interest detector over a Neo4j wallet graph. The detector was built and run against real data, produced false accusations, and was replaced by a factual "Who benefits" panel (see M3 above). Neo4j was not deployed.
- M4 shipped with six components (v1.0.0), was audited, and was reduced to the two that discriminate (v1.2.0). See [`docs/m4-score-audit.md`](docs/m4-score-audit.md).

### Phase 4 — Ecosystem Integration (not started)
- GovTool integration: link from proposals to the Pharos analysis
- Tempo.vote integration
- CIP extension submission to standardize the `pil:` namespace (with context v2)
- Treasury funding proposal for platform sustainability

---

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker (for local database)
- A [Blockfrost](https://blockfrost.io) API key (mainnet)
- An [Anthropic](https://console.anthropic.com) API key (optional — without it, summaries fall back to the proposal's own CIP-108 fields)

### 1. Clone and configure

```bash
git clone https://github.com/bosconfts/Pharos-Project.git
cd Pharos-Project
cp .env.example .env
# Fill in your keys in .env
```

### 2. Start the database

```bash
docker compose up -d
```

Starts PostgreSQL 16 with pgvector locally (production runs PostgreSQL 18 on Neon), plus an optional Neo4j 5.

### 3. Install Python dependencies

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-worker.txt   # worker and publisher; the API alone needs requirements.txt
```

### 4. Initialize the database schema

```bash
python core/database.py
```

### 5. Run the analysis worker

The worker indexes governance actions, runs M1–M4, and persists everything to Postgres. It never signs transactions.

```bash
python core/worker.py --init-db --count 50
```

### 6. Start the API

The API is strictly read-only — it serves what the worker wrote and runs no pipeline.

```bash
python core/step5_api.py
# API at http://localhost:8000
# Interactive docs at http://localhost:8000/docs
```

### 7. Publish analyses on-chain (optional)

The publisher is the only component that holds the wallet signing key. It requires two independent consents: `PIL_ENABLE_ONCHAIN=true` in the environment **and** the `--publish` flag.

```bash
python core/publisher.py             # dry-run — lists what would be published
python core/publisher.py --publish   # submits (spends real ADA on mainnet)
```

Publishing is idempotent: an action with a recorded `on_chain_tx` is never re-anchored. The publisher also refuses a document whose hash or score no longer matches the database.

### 8. Start the dashboard

```bash
cd dashboard
npm install
npm run dev
# Dashboard at http://localhost:5173
```

### Tests

```bash
python -m unittest discover tests   # no network, no database
```

---

## API Endpoints

Base URL: `https://pharos-project-sigma.vercel.app`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info |
| GET | `/health` | Health check |
| GET | `/stats` | Total proposals analyzed, network, current epoch |
| GET | `/governance/actions` | Live governance actions from Blockfrost |
| GET | `/governance/history` | Analyzed proposals from the database |
| GET | `/analysis/{gov_action_id}` | Full analysis: anchor validation, summaries, the PIL document and its hash, similar proposals, who benefits, risk score, and on-chain anchor status. Returns 404 until the worker has processed the action. `#` in the id must be URL-encoded as `%23` |

---

## Environment Variables

Copy `.env.example` to `.env`:

```env
# Blockfrost (https://blockfrost.io)
BLOCKFROST_PROJECT_ID=mainnetXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
BLOCKFROST_BASE_URL=https://cardano-mainnet.blockfrost.io/api/v0

# Anthropic — optional, enables Claude summaries
ANTHROPIC_API_KEY=sk-ant-...

# PostgreSQL + pgvector
DATABASE_URL=postgresql://pil:pil_secret@localhost:5432/pil

# Cardano wallet — optional, enables on-chain publishing
PIL_WALLET_ADDRESS=addr1v...
PIL_SIGNING_KEY_PATH=wallet/payment.skey

# Neo4j — optional, not used in production
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here
```

> Without an Anthropic key, the summarizer falls back to the proposal's own CIP-108 fields. A key that is set but rejected stops the worker instead of silently writing fallback summaries. Neo4j is optional and not used in production; M3 runs on Blockfrost.

---

## Democratic Foundation

Pharos is a response to a classic problem in democratic theory: asymmetric information in representative systems.

In traditional representative democracies, this problem is partially solved by independent press, public auditors, oversight bodies, and legally mandated transparency. In blockchains, all data is available — but the capacity to interpret it is concentrated.

> *A democracy where only specialists can evaluate proposals is not a democracy — it's a technocracy disguised as democracy. Pharos democratizes analysis, not the vote.*

Pharos operates on one principle: **the system decides for no one**. It doesn't vote, doesn't block proposals, doesn't recommend votes. It produces verifiable evidence and makes it accessible so that each DRep and ADA holder can make their own decision. That is also why it does not publish accusations it cannot support.

---

## Standards & References

**CIP Standards**
- [CIP-1694](https://cips.cardano.org/cip/CIP-1694) — On-Chain Governance Framework
- [CIP-0100](https://cips.cardano.org/cip/CIP-0100) — Governance Metadata Standard
- [CIP-0108](https://cips.cardano.org/cip/CIP-0108) — Governance Actions Metadata
- [CIP-0119](https://cips.cardano.org/cip/CIP-0119) — DRep Metadata Standard

**Community Documents**
- Cardano Governance Health KPI Report v1.0 — GHWG / Intersect Civics Committee (December 2025)
- Reflecting on Cardano Governance in 2025 — Cardano Foundation
- State of Cardano Q3 2025 — Messari Research (November 2025)
- Building a 2026 Ecosystem Budget for Cardano — Intersect MBO (2026)

**Referenced Tools**
- [GovTool](https://gov.tools) — Intersect
- [Tempo.vote](https://tempo.vote) — DRep voting platform
- [Blockfrost](https://blockfrost.io) — Cardano API

---

## License

MIT
