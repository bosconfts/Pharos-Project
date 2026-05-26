"""
Gera uma nova carteira PIL para a Preview Testnet.
Salva as chaves em wallet/ (NUNCA commitar este diretório).
"""
import os
import json
from pycardano import (
    PaymentSigningKey,
    PaymentVerificationKey,
    Address,
    Network,
)

WALLET_DIR = os.path.join(os.path.dirname(__file__), "wallet")


def create_wallet():
    os.makedirs(WALLET_DIR, exist_ok=True)

    skey_path  = os.path.join(WALLET_DIR, "payment.skey")
    vkey_path  = os.path.join(WALLET_DIR, "payment.vkey")
    addr_path  = os.path.join(WALLET_DIR, "payment.addr")
    info_path  = os.path.join(WALLET_DIR, "wallet_info.json")

    # Gera par de chaves
    skey = PaymentSigningKey.generate()
    vkey = PaymentVerificationKey.from_signing_key(skey)

    # Endereço na Mainnet
    address = Address(payment_part=vkey.hash(), network=Network.MAINNET)

    # Salva chaves
    skey.save(skey_path)
    vkey.save(vkey_path)

    with open(addr_path, "w") as f:
        f.write(str(address))

    info = {
        "network":  "mainnet",
        "address":  str(address),
        "vkey_hash": vkey.hash().payload.hex(),
        "files": {
            "signing_key":      skey_path,
            "verification_key": vkey_path,
            "address":          addr_path,
        },
        "warning": "NUNCA compartilhe o arquivo payment.skey",
    }

    with open(info_path, "w") as f:
        json.dump(info, f, indent=2)

    print("=" * 60)
    print("Nova carteira PIL gerada — Mainnet")
    print("=" * 60)
    print(f"\nEndereço:  {address}")
    print(f"\nArquivos salvos em:  wallet/")
    print(f"  payment.skey  ← chave privada (PROTEJA ESTE ARQUIVO)")
    print(f"  payment.vkey  ← chave pública")
    print(f"  payment.addr  ← endereço")
    print("\n" + "─" * 60)
    print("Próximo passo: financie a carteira com ADA de teste.")
    print("Faucet oficial: https://docs.cardano.org/cardano-testnet/tools/faucet")
    print("  → Envie ADA real para este endereço para cobrir taxas de tx (~1 ADA suficiente)")
    print("  → Cada publicação on-chain custa ~0.17 ADA em taxas")
    print("─" * 60)

    return info


if __name__ == "__main__":
    create_wallet()
