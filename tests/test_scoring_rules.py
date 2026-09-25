"""
Duas regras que o score não pode perder.

A primeira: a taxa de entrega só vale com amostra. Com uma única comparável
aprovada a taxa dava 100%, e 35 dos 100 pontos saíam de uma amostra de tamanho
um — 26 propostas da base estavam assim.

A segunda: uma análise ancorada não muda de nota. O documento no bloco é o
registro, e reescrever o número faria o site contradizer o hash que qualquer um
pode conferir.

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
        self.assertEqual(c["proposer_track_record"]["score"], 13)
        self.assertEqual(c["historical_precedent"]["score"], 5)
        self.assertIn("too few", c["proposer_track_record"]["evidence"])

    def test_duas_ainda_sao_poucas(self):
        c = self._score([_comparable("enacted"), _comparable("ratified")])["components"]
        self.assertEqual(c["proposer_track_record"]["score"], 13)

    def test_tres_concluidas_valem(self):
        c = self._score([_comparable("enacted")] * 3)["components"]
        self.assertEqual(c["proposer_track_record"]["score"], 25)
        self.assertEqual(c["historical_precedent"]["score"], 10)

    def test_pendentes_nao_contam_como_amostra(self):
        """Quem ainda está em votação não entregou nem deixou de entregar."""
        similar = [_comparable("enacted")] + [_comparable("pending")] * 4
        c = self._score(similar)["components"]
        self.assertEqual(c["proposer_track_record"]["score"], 13)

    def test_tres_concluidas_com_metade_entregue(self):
        similar = [_comparable("enacted"), _comparable("expired"), _comparable("expired")]
        c = self._score(similar)["components"]
        self.assertLess(c["proposer_track_record"]["score"], 25)
        self.assertGreater(c["proposer_track_record"]["score"], 0)


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
