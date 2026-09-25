"""
Step 3 — Translation Engine
Gera 3 níveis de resumo para uma governance action.
- Com ANTHROPIC_API_KEY: usa Claude para análise inteligente.
- Sem chave: extrai diretamente dos campos CIP-108 (fallback determinístico).
"""
import os
import re
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


class CredentialError(RuntimeError):
    """A chave da API não serve — recusada, sem permissão ou sem crédito.

    Diferente de um erro na proposta. O pipeline registra a etapa como "error"
    e segue em frente, o que é certo para um documento malformado e errado
    aqui: sem chave válida nenhuma proposta será resumida, e o worker
    terminaria verde marcando uma linha após a outra como analisada-com-erro —
    foi exatamente assim que 73 linhas passaram por prontas quando o crédito
    acabou. Esta exceção sobe até o topo e derruba a execução.
    """


def generate_summaries(fields: dict, action_type: str, deposit: int) -> dict:
    if ANTHROPIC_API_KEY and ANTHROPIC_API_KEY not in ("sk-ant-...", ""):
        return _summarize_with_claude(fields, action_type, deposit)
    return _summarize_fallback(fields, action_type, deposit)


# ──────────────────────────────────────────────
# Fallback determinístico (sem API key)
# ──────────────────────────────────────────────

def _summarize_fallback(fields: dict, action_type: str, deposit: int) -> dict:
    title      = fields.get("title", "").strip()
    abstract   = fields.get("abstract", "").strip()
    motivation = fields.get("motivation", "").strip()
    rationale  = fields.get("rationale", "").strip()
    withdraw   = fields.get("withdraw_amount")
    milestones = fields.get("milestones", [])

    one_liner = title or abstract[:120] or f"Governance action of type {action_type}"

    technical_parts = []
    if abstract:
        technical_parts.append(f"Summary: {abstract}")
    if withdraw:
        ada = int(withdraw) / 1_000_000
        technical_parts.append(f"Requested amount: {ada:,.0f} ADA")
    if deposit:
        technical_parts.append(f"Deposit: {deposit / 1_000_000:,.0f} ADA")
    if milestones:
        technical_parts.append(f"Milestones: {len(milestones)} defined")
    technical = " | ".join(technical_parts) if technical_parts else one_liner

    full = {
        "what_is_being_proposed": abstract or title,
        "why": motivation or "(not provided)",
        "how": rationale or "(not provided)",
        "financial_impact": f"{int(withdraw) / 1_000_000:,.0f} ADA" if withdraw else "N/A",
        "milestones": milestones,
    }

    score = _completeness_score(fields)

    return {
        "one_liner":  one_liner,
        "technical":  technical,
        "full":       full,
        "metadata": {
            "model":             "fallback-cip108",
            "completeness_score": score,
            "missing_fields":    _missing_fields(fields),
        },
    }


def _completeness_score(fields: dict) -> int:
    weights = {
        "title":           20,
        "abstract":        20,
        "motivation":      20,
        "rationale":       20,
        "references":      10,
        "authors":         10,
    }
    score = 0
    for key, weight in weights.items():
        val = fields.get(key)
        if val and (not isinstance(val, (list, dict)) or len(val) > 0):
            score += weight
    return score


def _missing_fields(fields: dict) -> list:
    important = ["title", "abstract", "motivation", "rationale", "authors"]
    return [f for f in important if not fields.get(f)]


# ──────────────────────────────────────────────
# Claude API
# ──────────────────────────────────────────────

# Preço do modelo, por milhão de tokens. Só serve para o log de consumo; se o
# modelo acima mudar, estes números precisam mudar junto.
_USD_PER_MTOK_IN  = 5.0
_USD_PER_MTOK_OUT = 25.0

# O consumo de cada chamada vai para um JSONL local. O `metadata` da resposta
# carrega os mesmos números, mas se perde antes de chegar ao banco, e sem
# registro não há como saber quanto um backfill custou senão pelo Console.
USAGE_LOG_PATH = os.getenv("PIL_USAGE_LOG", "usage_log.jsonl")


# Uma proposta de Summit trouxe 1,22 MB de rationale, dos quais 97% eram quatro
# imagens em data URI. Base64 num prompt de texto é ruído que o modelo não usa,
# e custaria US$ 1,85 de entrada por proposta. Remover não perde conteúdo.
_DATA_URI_RE = re.compile(
    r"data:[a-zA-Z0-9.+-]+/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+"
)

# Teto de segurança para o que sobrar. Um documento legítimo grande tem dezenas
# de milhares de caracteres; 120k já é folgado. O corte é registrado no
# metadata e avisado no log — truncar em silêncio esconderia o problema.
MAX_FIELD_CHARS = 120_000

_truncated_fields: list = []


def _clean(text) -> str:
    """Tira imagens embutidas e limita o tamanho de um campo do documento."""
    if not text:
        return ""
    cleaned = _DATA_URI_RE.sub("[embedded image removed]", str(text))
    if len(cleaned) > MAX_FIELD_CHARS:
        print(f"    ⚠️  campo com {len(cleaned):,} chars truncado em {MAX_FIELD_CHARS:,}")
        _truncated_fields.append(len(cleaned))
        cleaned = cleaned[:MAX_FIELD_CHARS] + "\n[truncated]"
    return cleaned


def _log_usage(usage) -> None:
    """Anexa uma linha de consumo ao JSONL. Nunca interrompe a análise."""
    import json
    from datetime import datetime, timezone

    try:
        cost = (usage.input_tokens  / 1e6 * _USD_PER_MTOK_IN
                + usage.output_tokens / 1e6 * _USD_PER_MTOK_OUT)
        entry = {
            "at":            datetime.now(timezone.utc).isoformat(),
            "model":         "claude-opus-4-6",
            "input_tokens":  usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "usd":           round(cost, 6),
        }
        with open(USAGE_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def _summarize_with_claude(fields: dict, action_type: str, deposit: int) -> dict:
    import anthropic

    title      = _clean(fields.get("title", ""))
    abstract   = _clean(fields.get("abstract", ""))
    motivation = _clean(fields.get("motivation", ""))
    rationale  = _clean(fields.get("rationale", ""))
    withdraw   = fields.get("withdraw_amount")
    milestones = fields.get("milestones", [])

    deposit_ada  = deposit / 1_000_000 if deposit else 0
    withdraw_ada = int(withdraw) / 1_000_000 if withdraw else None

    prompt = f"""You are an expert analyst specializing in Cardano blockchain governance.
Analyze the following governance action and generate summaries at 3 levels. All output must be in English.

=== PROPOSAL DATA ===
Type: {action_type}
Title: {title}
Abstract: {abstract}
Motivation: {motivation}
Rationale: {rationale}
Requested amount: {f"{withdraw_ada:,.0f} ADA" if withdraw_ada else "N/A"}
Deposit: {deposit_ada:,.0f} ADA
Milestones: {len(milestones)} defined

=== INSTRUCTIONS ===
Respond ONLY with valid JSON, no markdown, in this exact format:
{{
  "one_liner": "<max 120 chars: what this proposal does>",
  "technical": "<max 400 chars: technical analysis with financial impact and risks>",
  "full": {{
    "what_is_being_proposed": "<complete description>",
    "why": "<justification and problem being solved>",
    "how": "<implementation and methodology>",
    "financial_impact": "<amount, use of funds, sustainability>",
    "milestones": "<summary of milestones if any>"
  }},
  "completeness_score": <0-100 based on proposal quality and completeness>
}}"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
        raise CredentialError(f"chave recusada pela API: {e}") from e
    except anthropic.BadRequestError as e:
        # Crédito acabado não é erro de conteúdo: nenhuma proposta vai ser
        # resumida enquanto não for resolvido, e tratar como falha da proposta
        # deixaria o worker terminar verde marcando linha por linha.
        if "credit balance" in str(e).lower():
            raise CredentialError(f"sem crédito na conta Anthropic: {e}") from e
        raise

    _log_usage(message.usage)

    import json, re
    raw = message.content[0].text.strip()
    # Remove markdown code block se Claude envolver o JSON
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw).strip()
    parsed = json.loads(raw)

    return {
        "one_liner":  parsed.get("one_liner", ""),
        "technical":  parsed.get("technical", ""),
        "full":       parsed.get("full", {}),
        "metadata": {
            "model":             "claude-opus-4-6",
            "completeness_score": parsed.get("completeness_score", 0),
            "missing_fields":    _missing_fields(fields),
            "input_tokens":      message.usage.input_tokens,
            "output_tokens":     message.usage.output_tokens,
        },
    }


if __name__ == "__main__":
    print("=== PIL M1 — Step 3: Summarizer ===\n")
    sample = {
        "title":      "Teste PIL Summarizer",
        "abstract":   "Esta proposta solicita fundos para desenvolver uma ferramenta de análise.",
        "motivation": "A comunidade precisa de melhores ferramentas para avaliar propostas.",
        "rationale":  "Usaremos IA para gerar resumos acessíveis a todos os votantes.",
        "references": [],
        "authors":    [{"name": "PIL Team"}],
    }
    result = generate_summaries(sample, "TreasuryWithdrawals", 500_000_000)
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
