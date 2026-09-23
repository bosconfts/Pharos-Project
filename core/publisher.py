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
    BLOCKFROST_BASE_URL, BLOCKFROST_PROJECT_ID,
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


def wait_confirmed(tx_hash: str, timeout: int = 300) -> bool:
    """Espera a transação entrar em bloco. False se estourar o tempo."""
    import time
    import httpx

    url     = f"{BLOCKFROST_BASE_URL}/txs/{tx_hash}"
    headers = {"project_id": (BLOCKFROST_PROJECT_ID or "").strip()}
    started = time.time()

    print("   aguardando confirmação…", end="", flush=True)
    while time.time() - started < timeout:
        try:
            if httpx.get(url, headers=headers, timeout=20).status_code == 200:
                print(f" confirmada em {time.time() - started:.0f}s")
                return True
        except Exception:
            pass
        time.sleep(5)

    print(f" não confirmou em {timeout}s — parando por aqui")
    return False


def run(limit: int = 5, dry_run: bool = True, gov_action_id: str | None = None) -> dict:
    pending = get_pending_publish(limit=limit, gov_action_id=gov_action_id)

    # Um --id que não volta da fila é um id inelegível (já ancorado, sem resumo
    # real, sem documento) ou digitado errado. Dizer isso é melhor que um
    # "nada pendente" genérico, que pareceria sucesso.
    if gov_action_id and not pending:
        print(f"❌ '{gov_action_id}' não está na fila de publicação.")
        print("   Já foi ancorada, não tem análise real, ou o id está errado.")
        return {"submitted": 0, "failed": 1, "pending": 0}
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

                # Cada ancoragem gasta a UTxO e devolve o troco numa nova. O
                # BlockFrostChainContext só enxerga o que já está em bloco, então
                # submeter a próxima antes da confirmação faria ela tentar gastar
                # uma UTxO já consumida — sem custo, mas sem publicar. Espera.
                if row is not pending[-1] and not wait_confirmed(tx):
                    # Sem confirmação, a próxima gastaria uma UTxO já consumida
                    # e falharia em sequência. Para agora: o que foi publicado
                    # está registrado, e basta rodar de novo depois.
                    print("   Interrompendo o lote. Rode de novo quando a rede acompanhar.")
                    break
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
    # O pycardano formata o estado do TransactionBuilder com pprintpp num buffer
    # que usa a codificação do locale — cp1252 no Windows — e faz isso num
    # f-string avaliado mesmo com o log desligado. Qualquer "₳" no metadatum,
    # comum em proposta de tesouro, derrubava a montagem da transação. Só este
    # processo roda no Windows (é o único com a signing key), então é aqui que
    # quebra. No modo UTF-8 do Python o locale vira utf-8; sem ele, reexecuta.
    if not sys.flags.utf8_mode:
        import subprocess
        sys.exit(subprocess.call([sys.executable, "-X", "utf8", *sys.argv]))

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser(description="PIL on-chain publisher")
    p.add_argument("--publish", action="store_true", help="submete de verdade (sem isso, dry-run)")
    p.add_argument("--limit",   type=int, default=5, help="máximo de documentos por execução")
    p.add_argument("--id",      type=str, help="publica apenas esta gov_action_id, se elegível")
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

    stats = run(limit=args.limit, dry_run=not args.publish, gov_action_id=args.id)
    print(f"\n=== {stats['submitted']} submetidas · {stats['failed']} falhas ===")
    if stats["failed"]:
        sys.exit(1)
