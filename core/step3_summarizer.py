"""
Step 3 — Translation Engine
Gera 3 níveis de resumo para uma governance action.
- Com ANTHROPIC_API_KEY: usa Claude para análise inteligente.
- Sem chave: extrai diretamente dos campos CIP-108 (fallback determinístico).
"""
import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


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

def _summarize_with_claude(fields: dict, action_type: str, deposit: int) -> dict:
    import anthropic

    title      = fields.get("title", "")
    abstract   = fields.get("abstract", "")
    motivation = fields.get("motivation", "")
    rationale  = fields.get("rationale", "")
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
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

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
