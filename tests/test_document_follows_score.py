"""
O documento que vai para a chain precisa dizer a nota que o site mostra.

O step12 recalculava a nota de uma análise não ancorada e deixava o documento
como estava. O publisher conferia o hash — que cobre o documento, não as
colunas — e ancorava o número antigo. Ancoragem não se desfaz.

Roda sem rede e sem banco:
    python -m unittest discover tests
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import publisher
import step12_lifecycle as lifecycle


def _doc(total):
    return {"pilAnalysis": {"pilRiskScore": {"scoreTotal": total}}}


class TestPublisherRefusesStaleScore(unittest.TestCase):

    def test_nota_igual_passa(self):
        self.assertFalse(publisher.stale_score(_doc(61), 61))

    def test_nota_diferente_barra(self):
        self.assertTrue(publisher.stale_score(_doc(82), 61))

    def test_sem_nota_nos_dois_passa(self):
        self.assertFalse(publisher.stale_score(_doc(None), None))

    def test_documento_sem_bloco_de_score_barra_quando_ha_nota(self):
        self.assertTrue(publisher.stale_score({"pilAnalysis": {}}, 61))

    def test_run_nao_publica_documento_velho(self):
        doc = _doc(82)
        row = {"gov_action_id": "abc#0", "pil_document": doc,
               "pil_doc_hash": "h", "risk_score": 61}
        with mock.patch.object(publisher, "get_pending_publish", return_value=[row]), \
             mock.patch.object(publisher, "compute_document_hash", return_value="h"), \
             mock.patch.object(publisher, "publish_on_chain") as pub, \
             mock.patch("builtins.print"):
            stats = publisher.run(dry_run=False)
        pub.assert_not_called()
        self.assertEqual(stats["failed"], 1)


class TestRescoreRebuildsDocument(unittest.TestCase):

    def test_rescore_remonta_o_documento(self):
        risk = {"total": 61, "components": {}}
        with mock.patch.object(lifecycle, "get_action", return_value={"conflict_data": {}}), \
             mock.patch.object(lifecycle, "find_similar", return_value=[]), \
             mock.patch.object(lifecycle, "compute_risk_score", return_value=risk), \
             mock.patch.object(lifecycle, "save_conflict_and_risk") as save, \
             mock.patch.object(lifecycle, "rebuild_document") as rebuild:
            self.assertEqual(lifecycle.rescore("abc#0"), 61)
        save.assert_called_once()
        rebuild.assert_called_once_with("abc#0")


if __name__ == "__main__":
    unittest.main()
