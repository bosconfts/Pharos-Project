"""
Publisher on-chain PIL.

Único componente do sistema com acesso à signing key. Lê do banco os documentos
PIL já analisados e ainda não ancorados, e submete uma transação com metadatum
1694 para cada um. Idempotente: uma action com on_chain_tx preenchido nunca é
republicada.

Gasta ADA real. Por isso exige dois consentimentos independentes:
  1. PIL_ENABLE_ONCHAIN=true no ambiente
  2. a flag --publish na linha de comando (sem ela, roda em dry-run)

Uso:
    python core/publisher.py                    # dry-run: lista o que seria publicado
    python core/publisher.py --publish          # submete de verdade
    python core/publisher.py --publish --limit 1
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from step4_publish import (
    publish_on_chain, compute_document_hash, network_name,
    PIL_ENABLE_ONCHAIN, PIL_WALLET_ADDRESS, PIL_SIGNING_KEY_PATH,
)
from database import get_pending_publish, set_on_chain_result


def preflight() -> list[str]:
    """Verifica pré-condições de publicação. Lista vazia = tudo pronto."""
    problems = []
    if not PIL_ENABLE_ONCHAIN:
        problems.append("PIL_ENABLE_ONCHAIN não está ligado")
    if not PIL_WALLET_ADDRESS:
        problems.append("PIL_WALLET_ADDRESS não configurado")
    if not PIL_SIGNING_KEY_PATH or not os.path.exists(PIL_SIGNING_KEY_PATH):
        problems.append(f"signing key não encontrada em '{PIL_SIGNING_KEY_PATH}'")
    if network_name() == "unknown":
        problems.append("BLOCKFROST_BASE_URL não identifica uma rede conhecida")
    return problems


def run(limit: int = 5, dry_run: bool = True) -> dict:
    pending = get_pending_publish(limit=limit)
    net     = network_name()
    stats   = {"submitted": 0, "failed": 0, "pending": len(pending)}

    if not pending:
        print("Nada pendente de publicação.")
        return stats

    print(f"Rede: {net} · {len(pending)} documento(s) pendente(s)"
          f"{' — DRY RUN' if dry_run else ''}\n")

    for row in pending:
        gid = row["gov_action_id"]

        # Cada documento é isolado: uma linha malformada não pode abortar o lote
        # e deixar os demais sem publicar — pior ainda se estourar depois de um
        # submit, que perderia o registro de uma transação já paga.
        try:
            doc    = row.get("pil_document")
            stored = row.get("pil_doc_hash")

            if not doc:
                print(f"⚠️  {gid[:24]}… sem documento PIL — pulando")
                stats["failed"] += 1
                continue

            # Recomputa o hash a partir do documento persistido em vez de
            # confiar na coluna: garante que o que vai on-chain corresponde ao
            # que está no banco.
            doc_hash = compute_document_hash(doc)

            # Falha fechado. Sem hash registrado não há com o que comparar, e
            # publicar assim gastaria ADA ancorando um documento cuja
            # integridade ninguém conferiu.
            if not stored:
                print(f"⚠️  {gid[:24]}… sem hash registrado para conferir — pulando")
                stats["failed"] += 1
                continue

            if doc_hash != stored:
                print(f"⚠️  {gid[:24]}… hash divergente do registrado — pulando")
                stats["failed"] += 1
                continue

            if dry_run:
                print(f"[dry-run] {gid[:24]}… → publicaria doc_hash {doc_hash[:32]}…")
                continue

            print(f"→ {gid[:24]}… submetendo…")
            result = publish_on_chain(doc, doc_hash)

            if result.get("status") == "submitted":
                # A partir daqui a transação já foi paga. Registrar o tx_hash
                # é o que impede uma segunda publicação da mesma action, então
                # uma falha aqui NÃO pode ser engolida pelo except abaixo:
                # ficaria uma tx paga e invisível, elegível para ser paga de
                # novo. Aborta ruidosamente, com o hash à vista para registro
                # manual.
                tx = result.get("tx_hash")
                try:
                    if not tx:
                        raise RuntimeError("submit retornou sem tx_hash")
                    set_on_chain_result(gid, "submitted", tx)
                except Exception as e:
                    print("\n" + "!" * 68)
                    print("ATENCAO: transacao submetida mas NAO registrada no banco.")
                    print(f"  gov_action_id: {gid}")
                    print(f"  tx_hash      : {tx}")
                    print(f"  causa        : {e}")
                    print("Registre manualmente antes de rodar o publisher de novo,")
                    print("ou esta action sera publicada e paga uma segunda vez:")
                    print(f"  UPDATE governance_actions SET on_chain_status='submitted',")
                    print(f"    on_chain_tx='{tx}', on_chain_at=NOW()")
                    print(f"    WHERE gov_action_id='{gid}';")
                    print("!" * 68 + "\n")
                    raise SystemExit(2)

                stats["submitted"] += 1
                print(f"   ✅ tx {tx}")
            else:
                set_on_chain_result(gid, result.get("status", "error"))
                stats["failed"] += 1
                print(f"   ❌ {result.get('status')}: {result.get('reason')}")

        # SystemExit herda de BaseException, então o abort acima passa por aqui
        # sem ser capturado — que é exatamente a intenção.
        except Exception as e:
            stats["failed"] += 1
            print(f"   ❌ {gid[:24]}… erro inesperado: {e}")

    return stats


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser(description="PIL on-chain publisher")
    p.add_argument("--publish", action="store_true", help="submete de verdade (sem isso, dry-run)")
    p.add_argument("--limit",   type=int, default=5, help="máximo de documentos por execução")
    args = p.parse_args()

    print("=== PIL On-Chain Publisher ===\n")

    if args.publish:
        problems = preflight()
        if problems:
            print("❌ Publicação bloqueada:")
            for prob in problems:
                print(f"   · {prob}")
            sys.exit(1)
        if network_name() == "mainnet":
            print("⚠️  MAINNET — esta execução gasta ADA real.\n")

    stats = run(limit=args.limit, dry_run=not args.publish)
    print(f"\n=== {stats['submitted']} submetidas · {stats['failed']} falhas ===")
    if stats["failed"]:
        sys.exit(1)
