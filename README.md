# Pharos — Proposal Intelligence Layer

> *An informed vote is the foundation of democracy. Pharos builds the infrastructure so that every vote on Cardano is one.*

**Pharos** is an open-source on-chain intelligence platform for Cardano governance. It solves the central problem of decentralized governance: the radical information asymmetry between those who propose and those who vote.

Cardano completed its transition to the Voltaire Era in 2025 — the first blockchain with fully on-chain constitutional governance, operated by elected DReps, SPOs, and a Constitutional Committee. The first budget cycle involved 39 treasury withdrawals totaling 275 million ADA (≈US$275M). The second cycle, in 2026, promises to be even larger.

The problem is structural: a typical DRep cannot adequately evaluate dozens of technical proposals per epoch with zero analytical support. The result is governance by social bias — voting based on who you know and trust, not on verifiable merit. This is passive governance capture, even without malicious actors.

**Mission:** Eliminate the information asymmetry between proposers and voters, making every vote an informed and auditable decision — not a social bet.

---

## The Four Problems Pharos Solves

**Problem 1 — Information Asymmetry**
A 5M ADA treasury withdrawal arrives on-chain with 3,000 technical words. The proposer spent weeks crafting the proposal. The DRep has a 73-epoch voting window, dozens of simultaneous proposals, and zero analytical support. Available information systematically favors the proposer.

**Problem 2 — Absence of Conflict Traceability**
When a proposer has a prior financial relationship with wallets that will receive proposal funds, that information is technically available on-chain — but no one crosses it systematically. The Governance Health Working Group explicitly identified "protection against undue influence" as a critical governance health dimension, but no tool operates on it.

**Problem 3 — Fragmented Institutional Memory**
Similar proposals were approved and didn't deliver. But that history is not indexed, crossed, or accessible at voting time. Governance doesn't learn from its mistakes because there is no memory infrastructure.

**Problem 4 — Non-existent Risk Score**
There is no standardized, auditable, and verifiable system that synthesizes multiple risk factors into a consultable score. The Cardano Foundation abstained on PyCardano and hardware wallet maintenance proposals — not for technical rejection, but for "procedural gaps or unmet evaluation criteria." Pharos would have surfaced those problems before the vote.

---

## What Pharos Delivers

- Automatic analysis of every governance action at 3 levels of detail (layperson, technical, complete)
- Conflict of interest detection via on-chain wallet graph analysis
- Auditable and traceable Risk Score for every proposal
- Historical cross-reference with similar proposals and their real outcomes
- Immutable on-chain registration of analyses via CIP-100/108 with blake2b-256 hash
- Public API for integration with GovTool, Tempo.vote, and other governance tools

---

## Platform Architecture

Pharos operates as a four-module pipeline over every indexed governance action. The output of each analysis is published to IPFS/Arweave and anchored on-chain via metadatum label 1694, making it verifiable, immutable, and accessible to any governance tool.

```
M1 Translation Engine → M2 Historical Cross-Ref → M3 Conflict of Interest → M4 Risk Score → IPFS + Chain
```

### M1 — Translation Engine

For every governance action indexed on-chain, the system fetches the anchor metadata (URL + hash CIP-100/108), validates content integrity against the published blake2b-256 hash, and runs a three-layer analysis pipeline:

- **One-Liner Summary (≤2 lines):** For the ADA holder layperson. What is being requested, how much ADA, by whom, in what timeframe.
- **Technical Summary (1 paragraph):** For the active DRep. Governance action type, value relative to treasury, milestones, risks declared by the proposer themselves.
- **Full Analysis (structured):** For analysts and researchers. Technical impact, alignment with Cardano Vision 2030, preliminary constitutional analysis, comparison with the current NCL.

The generated summary is hashed and registered on-chain as part of the PIL document, making any subsequent distortion detectable by any participant.

### M2 — Historical Cross-Reference

Every proposal has predecessors. The historical database indexes all governance actions since Chang (August 2024), with final status (approved, rejected, expired, withdrawn), execution evidence for approved ones, and semantic similarity score against the current proposal.

The output for the voter is concrete: *"3 similar proposals were approved in the last 18 months. 1 delivered fully, 1 partially (2/4 milestones), 1 expired without execution evidence."* This transforms the vote from an isolated decision into one based on a verifiable historical pattern.

### M3 — Conflict of Interest Detector

When someone submits a treasury withdrawal to fund a project, and the proposer's wallet has historical transactions with wallets that will receive the funds, that is a conflict of interest that should be public. The analysis pipeline builds a transaction graph on Neo4j, identifies wallet clusters related to the proposer, and crosses them against wallets listed as beneficiaries in the proposal.

The system doesn't accuse — it exposes. The output is a set of on-chain evidence linked by txhash, with values and epochs. The DRep decides what to do with that information.

### M4 — Risk Score

The Risk Score is an auditable composition of six factors. Every component is clickable and shows the raw data that generated that sub-score. No black box. A score from 0–100 where every point is traceable to on-chain evidence.

| Component | Weight | What it measures |
|-----------|--------|-----------------|
| **Proposer Track Record** | 25% | Delivery rate of previous proposals. Milestones delivered vs. committed. Unrealized refunds. |
| **Scope Clarity** | 20% | Defined milestones? Verifiable acceptance criteria on-chain? Realistic timeline? |
| **Conflict of Interest** | 20% | M3 output. Undeclared financial relationships between proposer and beneficiaries. |
| **Treasury Value** | 15% | Percentage of current NCL being requested. Allocation concentration by proposer. |
| **Proposal Maturity** | 10% | Prior off-chain discussion (Ekklesia, forum). Time between idea and on-chain submission. |
| **Historical Precedent** | 10% | Similar proposals (M2): delivery rate weighted by semantic similarity. |

**Score interpretation:** ≥ 70 = LOW RISK · 45–69 = MEDIUM RISK · < 45 = HIGH RISK

---

## Design Principles

**Immutability of input:** `pilBodyHash` guarantees the analysis was made on that specific document. Impossible to reuse analysis from a good proposal for a bad one.

**Auditability of process:** Merkle root with described leaves allows anyone to run the pipeline locally and verify the output is identical. Open box, not black box.

**Determinism:** Given the same set of on-chain inputs, the system always produces the same output. There is no probabilistic component in the evidence pipeline.

**Extensibility without breaking compatibility:** Tools that don't know PIL still display standard CIP-108 fields (title, abstract). Graceful fallback guaranteed by JSON-LD.

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| On-chain indexing | Blockfrost API + PyCardano | Governance actions, anchor metadata, wallet transactions (Mainnet + Preprod) |
| Wallet graph | Neo4j + Cypher | Relationship analysis between proposer and beneficiary wallets. Path and clustering queries |
| ETL Pipeline | Python 3.12 + asyncio | Orchestration of 4 analytical modules. Parallelism by epoch |
| NLP / Analysis | Claude API (Sonnet) | 3-level summary generation. Semantic analysis for similarity search |
| Similarity search | PostgreSQL + pgvector | Historical proposal embeddings. Semantic neighborhood search for M2 |
| Public API | FastAPI + Redis cache | Endpoints for GovTool, Tempo.vote, explorers. Analysis cache by gov_action_id |
| Immutable storage | IPFS / Arweave | CIP-100 compliant analysis documents. URL + blake2b-256 hash in on-chain anchor |
| On-chain registration | PyCardano + Blockfrost | Transaction with metadatum label 1694. PIL document hash as anchor |
| Score engine | Pure Python | Deterministic and auditable logic. Identical output for identical inputs (verifiable) |
| Frontend | React 18 + Vite + Recharts | Public dashboard for PIL analyses |

---

## CIP Alignment

Pharos does not create a parallel format. It legitimately extends CIP-100 (Governance Metadata) and CIP-108 (Governance Actions Metadata) via JSON-LD, registering the PIL context as its own namespace hosted on IPFS.

| CIP | Function | How Pharos relates |
|-----|----------|-------------------|
| CIP-0100 | Governance Metadata — base | Base structure of the PIL document. hashAlgorithm, authors, anchor |
| CIP-0108 | Governance Actions Metadata | title, abstract, motivation fields inherited for compatibility with existing explorers |
| CIP-1694 | On-chain Governance Framework | Reserved metadatum label 1694. Anchoring PIL analyses in governance transactions |
| PIL Context v1 | pil: namespace (own extension) | JSON-LD vocabulary hosted on IPFS. Defines all pil: fields used across the 4 modules |

---

## Pharos vs. Existing Tools

Pharos does not compete with existing governance tools — it is an analysis layer that feeds them with data they cannot produce on their own.

| Tool | What it does | What it doesn't do | How Pharos complements |
|------|-------------|-------------------|----------------------|
| **GovTool (Intersect)** | DRep voting interface. Displays on-chain proposals | Doesn't analyze. Doesn't detect conflicts. No risk score | Pharos exposes REST API. GovTool displays Risk Score badge and link to full analysis |
| **Proposal Examiner (Griffin AI + CF)** | AI proposal evaluation. Beta tool | Output is not auditable nor registered on-chain. No wallet analysis | Pharos registers everything on-chain with verifiable hash. Analyses are publicly disputable |
| **Cardanoscan / PoolTool** | Blockchain explorer. Shows raw on-chain data | Doesn't synthesize, doesn't detect patterns, doesn't cross entities | Pharos consumes explorer data and returns structured analysis linked by txhash |
| **GHWG KPI Framework** | Defines governance health metrics | Theoretical framework. Doesn't implement. Points to off-chain data pipelines "still needing to be built" | Pharos implements the pipelines GHWG identified as necessary: DRep Rationale Rate, Contention, Conflict detection |

---

## Platform KPIs

| KPI | Question it answers | Dimension |
|-----|-------------------|-----------|
| Proposal coverage | What % of governance actions have a PIL analysis published before the voting window closes? | Operational |
| Analysis latency | How quickly after on-chain submission is the PIL analysis available? | Operational |
| Conflict detection rate | What % of proposals have at least 1 undeclared financial relationship detected? | Impact |
| DRep Risk Score adoption | What % of DReps consult the Risk Score before voting? | Impact |
| Vote × score correlation | Is there statistical correlation between high Risk Score and NO/ABSTAIN vote? | Impact |
| Analysis integrity | What % of PIL analyses are reproducible (input = verifiable output)? | Operational |
| Tool integrations | How many governance tools consume the PIL API? | Ecosystem |

---

## Roadmap

### Phase 1 — Foundation (Months 1–2) ✅
- Governance action indexer via Blockfrost (Preprod + Mainnet)
- M1: Translation Engine with 3 levels of summary
- CIP-100/108 schema + `pil:` namespace hosted on IPFS
- On-chain publication of analyses via PyCardano (metadatum 1694)
- Basic public API: `GET /analysis/{gov_action_id}`

### Phase 2 — Historical Intelligence (Months 3–4) ✅
- Historical backfill: all governance actions since Chang (Aug 2024)
- M2: embeddings + pgvector + similarity search
- Output: "N similar proposals, X% delivery rate"
- Public dashboard for PIL analyses

### Phase 3 — Conflict Detection (Months 5–6) ✅
- Wallet graph on Neo4j: proposer transaction indexing
- M3: financial relationship detection (proposer ↔ beneficiaries)
- Output: conflicts ranked by severity with txhash evidence
- Complete Risk Score (M4) with all 6 components

### Phase 4 — Ecosystem Integration (Months 7–8)
- GovTool integration: Risk Score badge on proposals
- Tempo.vote integration: inline PIL analysis
- CIP extension submission to CIP-100 to standardize `pil:` namespace
- Treasury funding proposal via governance action for platform sustainability

---

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker (for local database)
- A [Blockfrost](https://blockfrost.io) API key (mainnet)
- An [Anthropic](https://console.anthropic.com) API key (optional — enables Claude summaries)

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

Starts PostgreSQL 16 with pgvector and Neo4j 5 locally.

### 3. Install Python dependencies

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

### 4. Initialize the database schema

```bash
python core/database.py
```

### 5. Run the pipeline (CLI)

Processes the most recent governance action with an anchor document:

```bash
python run_m1.py
```

### 6. Start the API

```bash
python core/step5_api.py
# API at http://localhost:8000
# Interactive docs at http://localhost:8000/docs
```

### 7. Start the dashboard

```bash
cd dashboard
npm install
npm run dev
# Dashboard at http://localhost:5173
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info |
| GET | `/health` | Health check |
| GET | `/stats` | Total proposals analyzed |
| GET | `/governance/actions` | Live governance actions from Blockfrost |
| GET | `/governance/history` | Analyzed proposals from database |
| GET | `/analysis/{gov_action_id}` | Full analysis: anchor validation, summaries, PIL document hash, similarity matches, conflict detection, and risk score |

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

# Neo4j — optional, enables wallet graph
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here
```

> The summarizer works without an Anthropic key using a deterministic CIP-108 fallback. Neo4j is fully optional — conflict detection still runs via Blockfrost.

---

## Democratic Foundation

Pharos is not just a technical tool. It is a response to a classic problem in democratic theory: the problem of asymmetric information in representative systems.

In traditional representative democracies, this problem is partially solved by independent press, public auditors, oversight bodies, and legally mandated transparency. In blockchains, all data is available — but the capacity to interpret it is extremely concentrated.

> *A democracy where only specialists can evaluate proposals is not a democracy — it's a technocracy disguised as democracy. Pharos democratizes analysis, not the vote.*

Pharos operates within a central principle: **the system decides for no one**. It doesn't vote, doesn't block proposals, doesn't recommend votes. It produces verifiable evidence and makes it accessible so that each DRep and ADA holder can make their own informed decision.

This distinguishes Pharos from centralized reputation systems or curation mechanisms with veto power — both problematic in decentralized governance systems. Pharos is public infrastructure, not an arbiter.

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
