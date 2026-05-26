"""
Step 9 — Wallet Graph (Neo4j)
Stores and queries wallet transaction relationships for conflict detection.
Gracefully degrades if Neo4j is unavailable.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "pil_neo4j_secret")

_driver = None


def _get_driver():
    global _driver
    if _driver is None:
        from neo4j import GraphDatabase
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _driver


def is_available() -> bool:
    try:
        d = _get_driver()
        d.verify_connectivity()
        return True
    except Exception:
        return False


def init_graph():
    d = _get_driver()
    with d.session() as s:
        s.run("CREATE CONSTRAINT wallet_addr IF NOT EXISTS FOR (w:Wallet) REQUIRE w.address IS UNIQUE")
        s.run("CREATE CONSTRAINT proposal_id  IF NOT EXISTS FOR (p:Proposal) REQUIRE p.gov_action_id IS UNIQUE")
        s.run("CREATE INDEX wallet_stake IF NOT EXISTS FOR (w:Wallet) ON (w.stake_address)")
    print("✅ Neo4j graph initialized.")


def upsert_wallet(address: str, stake_address: str | None = None):
    d = _get_driver()
    with d.session() as s:
        s.run(
            "MERGE (w:Wallet {address: $addr}) "
            "ON CREATE SET w.stake_address = $stake "
            "ON MATCH SET  w.stake_address = COALESCE($stake, w.stake_address)",
            addr=address, stake=stake_address,
        )


def add_transaction(tx_hash: str, from_addr: str, to_addr: str, amount: int, epoch: int | None = None):
    d = _get_driver()
    with d.session() as s:
        s.run("""
            MERGE (f:Wallet {address: $from_addr})
            MERGE (t:Wallet {address: $to_addr})
            MERGE (tx:Transaction {tx_hash: $tx_hash})
              ON CREATE SET tx.epoch = $epoch
            MERGE (f)-[:FUNDED]->(tx)
            MERGE (tx)-[r:PAID_TO]->(t)
              ON CREATE SET r.amount = $amount
        """, from_addr=from_addr, to_addr=to_addr, tx_hash=tx_hash, epoch=epoch, amount=amount)


def mark_proposer(gov_action_id: str, address: str):
    d = _get_driver()
    with d.session() as s:
        s.run("""
            MERGE (w:Wallet {address: $addr})
            MERGE (p:Proposal {gov_action_id: $gov_id})
            MERGE (w)-[:PROPOSED]->(p)
        """, addr=address, gov_id=gov_action_id)


def mark_beneficiary(gov_action_id: str, stake_address: str, amount: int):
    d = _get_driver()
    with d.session() as s:
        s.run("""
            MERGE (w:Wallet {address: $addr})
            MERGE (p:Proposal {gov_action_id: $gov_id})
            MERGE (p)-[r:BENEFITS]->(w)
              ON CREATE SET r.amount = $amount
        """, addr=stake_address, gov_id=gov_action_id, amount=amount)


def find_direct_connections(addr1: str, addr2: str) -> list[dict]:
    """Find transactions where addr1 paid addr2."""
    d = _get_driver()
    with d.session() as s:
        result = s.run("""
            MATCH (a:Wallet {address: $a})-[:FUNDED]->(tx:Transaction)-[:PAID_TO]->(b:Wallet {address: $b})
            RETURN tx.tx_hash AS tx_hash, tx.epoch AS epoch
            ORDER BY tx.epoch DESC
            LIMIT 5
        """, a=addr1, b=addr2)
        return [dict(r) for r in result]
