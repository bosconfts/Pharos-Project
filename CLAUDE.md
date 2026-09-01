# Pharos — Proposal Intelligence Layer

On-chain intelligence platform for Cardano governance. Indexes governance
actions, analyzes them (M1–M4), and anchors the analyses on-chain via
metadatum 1694.

## Contas e credenciais

Pharos é um **projeto público** — o repositório e o dashboard são abertos.

`joaobosco.ada@gmail.com` é o **email de infraestrutura do projeto**: serviços
novos do Pharos são criados nele, para não depender do email pessoal.

| Serviço | Conta | Uso |
|---|---|---|
| **Anthropic** | `joaobosco.ada@gmail.com` | `ANTHROPIC_API_KEY` — org `Pharos` |
| **Neon** | `joaobosco.ada@gmail.com` | Postgres 18 + pgvector — org `Pharos`, projeto `pharos`, branch `production`, região AWS us-east-2 |
| **Vercel** | `joaobosco.ada@gmail.com` | Hospedagem da API read-only (plano Hobby) |
| ~~Hugging Face Spaces~~ | `joaobosco.ada@gmail.com` | **Não usado.** Docker Spaces viraram PRO-only; o free tier só serve arquivos estáticos. |
| **GitHub** | `bosconfts@gmail.com` (user `bosconfts`) | Repo público `bosconfts/Pharos-Project`, Pages (`pharosgov.io`) **e execução do worker via Actions** |
| **Blockfrost** | `bosconfts@gmail.com` | `BLOCKFROST_PROJECT_ID` (mainnet). **A única fonte de dados da chain** — sem ele não há o que indexar, o M3 não roda e nada é publicado. Quando o token expirou, o projeto parou inteiro. |
| Render | — | **Abandonado.** Login quebrado, sem acesso. Não é mais o orquestrador. |
| Neo4j Aura | — | **Nunca provisionado.** O `step9_wallet_graph.py` existe e o M3 tenta usá-lo, mas cai no caminho via Blockfrost quando ausente — que é como roda hoje. |
| Registrador de `pharosgov.io` | — | Não registrado aqui; o domínio aponta para o GitHub Pages. |

Padrão que se repete: o login dos serviços é `joaobosco.ada`, mas o repositório
é do GitHub `bosconfts`. As duas identidades convivem — o serviço pede
autorização OAuth ao GitHub na hora de conectar o repo, e isso não exige que os
emails coincidam.

### Onde cada peça roda

| Peça | Host | Custo |
|---|---|---|
| Worker (M1–M4, cron 6h) | GitHub Actions | Grátis — minutos ilimitados em repo público |
| Postgres 18 + pgvector | Neon | Free tier |
| API read-only | Vercel (Python serverless) | Hobby, grátis |
| Dashboard | GitHub Pages | Grátis |
| Neo4j (opcional) | Aura Free — **não criado** | M3 roda sem ele, via Blockfrost |

Isso só é viável porque a API ficou read-only e não carrega mais `torch`. Todo
o peso está no worker, que é um job em lote — e job em lote é o que o Actions
faz de graça.

**Duas connection strings do Neon, de propósito:**

- A API na Vercel usa a **pooled** (host com `-pooler`). Serverless abre muitas
  conexões curtas e esgotaria o limite do Postgres sem o pooler.
- O worker e a máquina local usam a **direta** (sem `-pooler`), porque o
  pooler interfere em DDL — `CREATE EXTENSION`, `ALTER TABLE` do `init_db()`.

**Dependências separadas por processo:** `requirements.txt` é só a API (é o que
a Vercel instala, e torch não caberia no limite de tamanho de função);
`requirements-worker.txt` inclui aquele e soma o pipeline pesado.

A chave Anthropic anterior, criada na conta pessoal, foi exposta e **deve ser
revogada**. Toda chave nova do projeto sai da conta Anthropic acima.

Autenticação Anthropic: **API key estática**. Vale reavaliar — o worker migrou
para o GitHub Actions, que É um provedor de identidade suportado pela federação
(junto de GCP, AWS e Azure). Trocar eliminaria o segredo estático de vez, o que
importa aqui: a chave anterior já vazou uma vez.

Onde cada segredo vive:

| Segredo | `.env` local | GitHub Secrets (worker) | Vercel (API) |
|---|---|---|---|
| `DATABASE_URL` | direta | direta | **pooled** |
| `BLOCKFROST_PROJECT_ID` | sim | sim | sim |
| `ANTHROPIC_API_KEY` | sim | sim | **não** — a API não chama o Claude |
| `PIL_WALLET_ADDRESS` / `PIL_SIGNING_KEY_PATH` | sim | **não** | **não** |

Nunca commitar chaves, e nunca dar a signing key da carteira a nada que a
internet alcance. O publisher roda apenas na máquina local.

## Stack

**Backend:** Python 3.12 · FastAPI · psycopg2 · httpx · sentence-transformers +
torch (embeddings do M2, só no worker) · pycardano (assinatura, só no publisher).
**Frontend:** React 18 · Vite — e nada além disso. O `recharts` foi removido no
redesign; o bundle caiu de 517 KB para 156 KB. Não reintroduzir biblioteca de
gráfico sem necessidade real.
**Dados:** PostgreSQL 18 + pgvector. **Local:** Docker Compose.

Links externos sem conta: `cardanoscan.io` (verificação de transação pelo
usuário) e `ipfs.io` (gateway para documentos de propostas ancorados em IPFS).

## Arquitetura de execução

Três processos com privilégios distintos — a separação é intencional:

| Processo | Entry point | Faz | Tem signing key |
|---|---|---|---|
| Worker | `core/worker.py` | Indexa, roda M1–M4, persiste no Postgres | Não |
| Publisher | `core/publisher.py` | Ancora documentos PIL on-chain | **Sim** |
| API | `core/step5_api.py` | Serve análises persistidas, read-only | Não |

**Nenhum request HTTP pode disparar uma transação.** A API não roda pipeline e
não importa `pycardano`, `torch`, `sentence_transformers` nem `neo4j` — se um
desses aparecer no caminho de import dela, algo regrediu.

A publicação on-chain exige dois consentimentos independentes:
`PIL_ENABLE_ONCHAIN=true` no ambiente **e** a flag `--publish` na CLI. O default
é dry-run. Idempotência vem da coluna `on_chain_tx`: uma action ancorada nunca
é republicada.

## Comandos

```bash
docker compose up -d                          # Postgres+pgvector e Neo4j locais
python core/database.py                       # cria/atualiza schema
python core/worker.py --init-db --count 50    # analisa e persiste
python core/step6_backfill.py                 # backfill histórico desde Chang
python core/publisher.py                      # dry-run da publicação
python core/publisher.py --publish            # submete (gasta ADA real)
python core/step5_api.py                      # API em :8000
cd dashboard && npm run dev                   # dashboard em :5173
```

O venv fica em `venv/` (Windows: `./venv/Scripts/python.exe`).

## Convenções

- Código e docstrings novos em inglês; comentários explicativos podem ser em
  português, seguindo o que já existe no arquivo.
- Módulos do pipeline são numerados por etapa (`step1_` … `step11_`).
  `pipeline.py` orquestra; os `step*` são as unidades.
- `run_m1.py` é CLI de desenvolvimento legado — o caminho de produção é
  `worker.py`.

## Armadilhas conhecidas

- O embedding precisa ser persistido **antes** do upsert, senão a action fica
  fora do corpus e o M2 degrada em silêncio (já mordeu uma vez).
- Os campos `ratified/enacted/expired/dropped_epoch` alimentam o delivery rate
  do M2 e os componentes 1 e 6 do M4. Se vierem nulos, o score cai no neutro
  sem erro visível.
- `network_name()` deriva a rede de `BLOCKFROST_BASE_URL` — não hardcodar
  mainnet em lugar nenhum.
