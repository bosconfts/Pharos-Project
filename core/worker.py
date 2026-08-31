"""
Worker de análise PIL.

Roda fora do processo da API: indexa governance actions da chain, executa
M1–M4 e persiste tudo no Postgres. A API apenas lê o que este worker escreve.

Uso:
    python core/worker.py                 # analisa as actions novas mais recentes
    python core/worker.py --count 50      # amplia a janela de indexação
    python core/worker.py --all           # reprocessa também as já analisadas
    python core/worker.py --id <gov_id>   # processa uma action específica
"""
import os
import sys
import argparse
import traceback

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from step1_indexer import fetch_governance_actions
from step4_publish import network_name
from pipeline      import analyze_action, analyze_by_id
from database      import init_db, get_action


def run(count: int = 20, page: int = 1, reprocess: bool = False) -> dict:
    actions = fetch_governance_actions(page=page, count=count)
    print(f"Rede: {network_name()} · {len(actions)} actions indexadas\n")

    stats = {"analyzed": 0, "skipped": 0, "failed": 0}

    for action in actions:
        gid = action.gov_action_id
        if not reprocess:
            existing = get_action(gid)
            if existing and existing.get("analysis"):
                stats["skipped"] += 1
                continue

        print(f"→ {gid[:24]}… [{action.action_type}]")
        try:
            result = analyze_action(action, persist=True, verbose=True)
            stats["analyzed"] += 1
            if result["errors"]:
                for e in result["errors"]:
                    print(f"    ⚠️  {e}")
        except Exception:
            stats["failed"] += 1
            traceback.print_exc()
        print()

    return stats


if __name__ == "__main__":
    # Console do Windows é cp1252 e estoura nos emojis de status.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser(description="PIL analysis worker")
    p.add_argument("--count", type=int, default=20, help="actions por página a indexar")
    p.add_argument("--page",  type=int, default=1)
    p.add_argument("--all",   action="store_true", help="reprocessa actions já analisadas")
    p.add_argument("--id",    type=str, help="processa apenas esta gov_action_id")
    p.add_argument("--init-db", action="store_true", help="cria/atualiza o schema antes de rodar")
    args = p.parse_args()

    if args.init_db:
        init_db()

    print("=== PIL Analysis Worker ===\n")

    if args.id:
        result = analyze_by_id(args.id, persist=True, verbose=True)
        if result is None:
            print(f"❌ Action '{args.id}' não encontrada na chain.")
            sys.exit(1)
        print(f"\n✅ {args.id} analisada.")
    else:
        stats = run(count=args.count, page=args.page, reprocess=args.all)
        print(f"=== Concluído: {stats['analyzed']} analisadas · "
              f"{stats['skipped']} já existentes · {stats['failed']} falhas ===")
        if stats["failed"]:
            sys.exit(1)
