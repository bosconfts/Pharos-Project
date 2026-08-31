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
| **Vercel** | conta criada via GitHub `bosconfts` | Hospedagem da API read-only (plano Hobby) |
| ~~Hugging Face Spaces~~ | `joaobosco.ada@gmail.com` | **Não usado.** Docker Spaces viraram PRO-only; o free tier só serve arquivos estáticos. |
| **GitHub** | `bosconfts@gmail.com` (user `bosconfts`) | Repo público `bosconfts/Pharos-Project`, Pages (`pharosgov.io`) **e execução do worker via Actions** |
| Blockfrost | `bosconfts@gmail.com` | `BLOCKFROST_PROJECT_ID` (mainnet) |
| Render | — | **Abandonado.** Login quebrado, sem acesso. Não é mais o orquestrador. |

### Onde cada peça roda

| Peça | Host | Custo |
|---|---|---|
| Worker (M1–M4, cron 6h) | GitHub Actions | Grátis — minutos ilimitados em repo público |
| Postgres 18 + pgvector | Neon | Free tier |
| API read-only | Vercel (Python serverless) | Hobby, grátis |
| Dashboard | GitHub Pages | Grátis |
| Neo4j (opcional) | Aura Free | M3 funciona sem ele |

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

Autenticação Anthropic: **API key estática**, não identity federation — o worker
roda como cron Docker no Render, que não é um provedor de identidade suportado
(a federação cobre GCP, AWS, Azure e GitHub Actions). Reavaliar se o worker
algum dia migrar para GitHub Actions.

Segredos vivem apenas no `.env` (gitignorado) e nas variáveis de ambiente do
Render. Nunca commitar chaves, e nunca colocar a signing key da carteira no
serviço web.

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
