# Pharos — Proposal Intelligence Layer

**Pharos** is an open-source intelligence pipeline for Cardano on-chain governance. It automatically indexes governance proposals, validates their anchor documents, generates multi-level AI summaries, detects conflicts of interest, and computes an auditable risk score — making it easier for DReps and community members to evaluate proposals before voting.

---

## What it does

For every governance action on the Cardano mainnet, Pharos runs an 11-step pipeline:

| Step | Module | Description |
|------|--------|-------------|
| S1 | `step1_indexer` | Fetches governance actions from Cardano mainnet via Blockfrost |
| S2 | `step2_anchor` | Downloads and validates the anchor document (IPFS or HTTP) using blake2b-256 |
| S3 | `step3_summarizer` | Generates 3-level summaries via Claude AI (one-liner, technical, full) |
| S4 | `step4_publish` | Builds a PIL document and optionally publishes its hash on-chain (CIP-100 metadatum 1694) |
| S5 | `step5_api` | REST API that orchestrates all steps |
| S6 | `step6_backfill` | Backfills historical proposals into the database |
| S7 | `step7_embeddings` | Generates semantic vectors with `all-MiniLM-L6-v2` (384 dimensions, local model) |
| S8 | `step8_similarity` | Finds semantically similar past proposals via pgvector cosine search |
| S9 | `step9_wallet_graph` | Builds a wallet relationship graph in Neo4j (optional) |
| S10 | `step10_conflict` | Detects conflicts of interest between proposers and beneficiaries (M3) |
| S11 | `step11_risk_score` | Computes an auditable 0–100 risk score across 6 components (M4) |

---

## Risk Score (M4)

Every proposal receives a score from 0 to 100 across 6 components:

| Component | Weight | Description |
|-----------|--------|-------------|
| Proposer Track Record | 25% | Delivery rate of semantically similar past proposals |
| Scope Clarity | 20% | Presence and quality of title, abstract, motivation, rationale |
| Conflict of Interest | 20% | Financial links between proposer and beneficiary wallets |
| Treasury Value | 15% | Withdrawal amount as % of the NCL (300M ADA limit) |
| Documentation Quality | 10% | Word count across abstract, motivation and rationale |
| Historical Precedent | 10% | How similar proposals have performed historically |

**Score interpretation:** ≥ 70 = LOW RISK · 45–69 = MEDIUM RISK · < 45 = HIGH RISK

---

## Tech Stack

**Backend**
- Python 3.12 + FastAPI + Uvicorn
- PostgreSQL 16 + pgvector (semantic similarity search)
- Neo4j 5 (wallet graph — optional)
- `sentence-transformers` — `all-MiniLM-L6-v2` local embedding model
- `pycardano` — on-chain transaction submission

**AI**
- Anthropic Claude API (`claude-opus-4-6`) for proposal summaries
- Falls back to deterministic CIP-108 extraction if no API key is set

**Data Sources**
- [Blockfrost](https://blockfrost.io) — Cardano mainnet indexer
- IPFS / HTTP — anchor document fetching

**Frontend**
- React 18 + Vite
- Recharts — risk score gauges and charts

---

## Project Structure

```
pharos/
├── core/
│   ├── step1_indexer.py       # Blockfrost governance action fetcher
│   ├── step2_anchor.py        # Anchor document validator
│   ├── step3_summarizer.py    # Claude AI summarizer (with fallback)
│   ├── step4_publish.py       # PIL document builder + on-chain publisher
│   ├── step5_api.py           # FastAPI REST API
│   ├── step6_backfill.py      # Historical data backfill
│   ├── step7_embeddings.py    # Semantic embedding generator
│   ├── step8_similarity.py    # pgvector similarity search
│   ├── step9_wallet_graph.py  # Neo4j wallet graph
│   ├── step10_conflict.py     # Conflict of interest detector
│   ├── step11_risk_score.py   # Risk score engine
│   └── database.py            # PostgreSQL connection + schema
├── dashboard/                 # React frontend
│   └── src/
│       ├── App.jsx
│       ├── api.js
│       └── components/
│           ├── ActionList.jsx
│           ├── ActionDetail.jsx
│           ├── RiskScoreGauge.jsx
│           ├── ConflictPanel.jsx
│           └── StatsBar.jsx
├── run_m1.py                  # CLI pipeline runner
├── docker-compose.yml         # PostgreSQL + Neo4j local setup
├── Dockerfile                 # Backend container
├── render.yaml                # Render deploy config
└── .env.example               # Environment variable template
```

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

This starts PostgreSQL 16 with pgvector and Neo4j 5 locally.

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
# API available at http://localhost:8000
# Interactive docs at http://localhost:8000/docs
```

### 7. Start the dashboard

```bash
cd dashboard
npm install
npm run dev
# Dashboard available at http://localhost:5173
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
| GET | `/analysis/{gov_action_id}` | Full analysis for a specific proposal |

### Example

```bash
curl http://localhost:8000/analysis/abc123txhash#0
```

Returns anchor validation, AI summaries, PIL document hash, similarity matches, conflict detection, and risk score.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values:

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

> **Note:** The summarizer works without an Anthropic key using a deterministic CIP-108 fallback. Neo4j is fully optional — conflict detection still runs via Blockfrost.

---

## Standards

- [CIP-100](https://github.com/cardano-foundation/CIPs/tree/master/CIP-0100) — Governance metadata standard
- [CIP-108](https://github.com/cardano-foundation/CIPs/tree/master/CIP-0108) — Governance action metadata fields

---

## License

MIT
