"""
Três regras que o score não pode perder.

A primeira: a taxa de entrega só vale com amostra. Com uma única comparável
aprovada a taxa dava 100%, e 35 dos 100 pontos saíam de uma amostra de tamanho
um — 26 propostas da base estavam assim.

A segunda: uma análise ancorada não muda de nota. O documento no bloco é o
registro, e reescrever o número faria o site contradizer o hash que qualquer um
pode conferir.

A terceira: só entra no score o que separa uma proposta da outra, e sinal que
não se aplica sai da conta em vez de dar pontos de graça.

Roda sem rede e sem banco:
    python -m unittest discover tests
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import step11_risk_score as m4
import step12_lifecycle as lifecycle


def _comparable(status):
    """Uma proposta similar, do jeito que o find_similar a devolve."""
    return {
        "enacted":  {"enacted_epoch": 500},
        "ratified": {"ratified_epoch": 500},
        "expired":  {"expired_epoch": 500},
        "pending":  {},
    }[status]


def _record():
    return {
        "gov_action_id": "abc#0",
        "action_type":   "TreasuryWithdrawals",
        "title":         "t" * 30,
        "abstract":      "a" * 200,
        "motivation":    "m" * 200,
        "rationale":     "r" * 200,
        "withdrawal_amount": 1_000_000_000,
    }


class TestMinimumSample(unittest.TestCase):

    def _score(self, similar):
        return m4.compute_risk_score(_record(), conflicts=[], similar=similar)

    def test_uma_comparavel_aprovada_nao_da_nota_cheia(self):
        c = self._score([_comparable("enacted")])["components"]
        self.assertEqual(c["similar_delivery"]["score"], 30)
        self.assertIn("too few", c["similar_delivery"]["evidence"])

    def test_duas_ainda_sao_poucas(self):
        c = self._score([_comparable("enacted"), _comparable("ratified")])["components"]
        self.assertEqual(c["similar_delivery"]["score"], 30)

    def test_tres_concluidas_valem(self):
        c = self._score([_comparable("enacted")] * 3)["components"]
        self.assertEqual(c["similar_delivery"]["score"], 60)

    def test_pendentes_nao_contam_como_amostra(self):
        """Quem ainda está em votação não entregou nem deixou de entregar."""
        similar = [_comparable("enacted")] + [_comparable("pending")] * 4
        c = self._score(similar)["components"]
        self.assertEqual(c["similar_delivery"]["score"], 30)

    def test_tres_concluidas_com_metade_entregue(self):
        similar = [_comparable("enacted"), _comparable("expired"), _comparable("expired")]
        c = self._score(similar)["components"]
        self.assertLess(c["similar_delivery"]["score"], 60)
        self.assertGreater(c["similar_delivery"]["score"], 0)


class TestOnlySignalsThatDiscriminate(unittest.TestCase):
    """Método 1.2.0: sai o que dava a mesma nota a quase todos."""

    def test_saque_tem_so_os_dois_sinais(self):
        r = m4.compute_risk_score(_record(), conflicts=[], similar=[])
        self.assertEqual(set(r["components"]), {"similar_delivery", "treasury_size"})
        self.assertEqual(sum(c["max"] for c in r["components"].values()), 100)

    def test_sinal_que_nao_se_aplica_sai_da_conta(self):
        """Uma InfoAction não ganha 40 pontos de graça por não ser saque."""
        rec = dict(_record(), action_type="InfoAction")
        r = m4.compute_risk_score(rec, conflicts=[], similar=[_comparable("expired")] * 3)
        self.assertEqual(list(r["components"]), ["similar_delivery"])
        self.assertEqual(r["components"]["similar_delivery"]["max"], 100)
        self.assertEqual(r["total"], 0)
        self.assertEqual(r["level"], "HIGH RISK")

    def test_sem_nada_a_dizer_e_medio_nao_baixo(self):
        rec = dict(_record(), withdrawal_amount=None)
        r = m4.compute_risk_score(rec, conflicts=[], similar=[])
        self.assertEqual(r["total"], 50)
        self.assertEqual(r["level"], "MEDIUM RISK")

    def test_faixas_do_saque(self):
        ncl = m4.NCL_LOVELACE
        for pct, pts in ((0.5, 40), (2, 32), (5, 21), (10, 11), (20, 0)):
            self.assertEqual(m4.treasury_component(int(ncl * pct / 100))["score"], pts, pct)

    def test_conflito_nao_entra_em_score_novo(self):
        """O step14 não pode enxertar 20 pontos de conflito num score 1.2.0."""
        r = m4.compute_risk_score(_record(), conflicts=[], similar=[])
        self.assertEqual(m4.rescore_conflict(r, "TreasuryWithdrawals", []), r)

    def test_score_antigo_continua_trocando_conflito(self):
        old = {"gov_action_id": "abc#0", "components": {
            "conflict_of_interest": {"score": 20, "max": 20},
            "outros": {"score": 60, "max": 80}}}
        r = m4.rescore_conflict(old, "TreasuryWithdrawals", [{"severity": "HIGH"}])
        self.assertEqual(r["total"], 60)


class TestAnchoredIsFrozen(unittest.TestCase):

    def _run(self, on_chain_tx):
        row = {"gov_action_id": "abc#0", "tx_hash": "abc", "cert_index": 0,
               "on_chain_tx": on_chain_tx}
        with mock.patch.object(lifecycle, "pending_actions", return_value=[row]), \
             mock.patch.object(lifecycle, "fetch_lifecycle",
                               return_value={"ratified_epoch": 500, "enacted_epoch": 501,
                                             "expired_epoch": None, "dropped_epoch": None}), \
             mock.patch.object(lifecycle, "update_lifecycle") as upd, \
             mock.patch.object(lifecycle, "rescore", return_value=88) as res:
            stats = lifecycle.refresh_lifecycle(verbose=False)
        return stats, upd, res

    def test_ancorada_atualiza_desfecho_mas_nao_rescora(self):
        stats, upd, res = self._run("5d6d2385")
        upd.assert_called_once()          # o desfecho é fato da chain
        res.assert_not_called()           # a nota, não
        self.assertEqual(stats["frozen"], 1)
        self.assertEqual(stats["rescored"], 0)

    def test_nao_ancorada_rescora_normalmente(self):
        stats, upd, res = self._run(None)
        upd.assert_called_once()
        res.assert_called_once()
        self.assertEqual(stats["rescored"], 1)
        self.assertEqual(stats["frozen"], 0)


if __name__ == "__main__":
    unittest.main()
