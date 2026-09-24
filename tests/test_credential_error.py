"""
Uma chave de API que não serve precisa derrubar a execução, não passar batido.

Quando o crédito da conta acabou, o summarizer falhou proposta a proposta, cada
linha foi gravada como analisada-com-erro e o worker terminou verde. O registro
público ficou com 73 análises que eram o título copiado, e ninguém foi avisado.

Roda sem rede e sem banco:
    python -m unittest discover tests
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import anthropic

import step3_summarizer as s3
import worker


def _api_error(cls, message):
    """Constrói uma exceção da SDK sem precisar de resposta HTTP real."""
    return cls(message, response=mock.Mock(status_code=401), body=None)


class TestCredentialMapping(unittest.TestCase):
    """O que vira CredentialError, e o que não pode virar."""

    def setUp(self):
        self.fields = {"title": "t" * 30, "abstract": "a" * 200,
                       "motivation": "m", "rationale": "r"}
        s3.ANTHROPIC_API_KEY = "sk-ant-api03-chave-de-teste"

    def _run_with(self, exc):
        client = mock.Mock()
        client.messages.create.side_effect = exc
        with mock.patch.object(anthropic, "Anthropic", return_value=client):
            return s3.generate_summaries(self.fields, "InfoAction", 0)

    def test_chave_recusada_vira_credential_error(self):
        with self.assertRaises(s3.CredentialError):
            self._run_with(_api_error(anthropic.AuthenticationError, "invalid x-api-key"))

    def test_sem_credito_vira_credential_error(self):
        with self.assertRaises(s3.CredentialError):
            self._run_with(_api_error(anthropic.BadRequestError,
                                      "Your credit balance is too low to access the Anthropic API"))

    def test_erro_de_conteudo_nao_vira_credential_error(self):
        """Um 400 comum é problema daquela proposta e não pode parar o lote."""
        with self.assertRaises(anthropic.BadRequestError):
            self._run_with(_api_error(anthropic.BadRequestError, "prompt is too long"))


class TestWorkerStops(unittest.TestCase):
    """O worker para na primeira e propaga, em vez de marcar linha por linha."""

    def test_run_propaga_credential_error(self):
        action = mock.Mock(gov_action_id="abc#0", action_type="InfoAction")
        with mock.patch.object(worker, "fetch_governance_actions", return_value=[action]), \
             mock.patch.object(worker, "get_action", return_value=None), \
             mock.patch.object(worker, "network_name", return_value="mainnet"), \
             mock.patch.object(worker, "analyze_action",
                               side_effect=s3.CredentialError("chave recusada")):
            with self.assertRaises(s3.CredentialError):
                worker.run(count=1, skip_lifecycle=True)

    def test_erro_comum_nao_derruba_a_execucao(self):
        """Uma proposta quebrada é contada como falha; as outras seguem."""
        action = mock.Mock(gov_action_id="abc#0", action_type="InfoAction")
        with mock.patch.object(worker, "fetch_governance_actions", return_value=[action]), \
             mock.patch.object(worker, "get_action", return_value=None), \
             mock.patch.object(worker, "network_name", return_value="mainnet"), \
             mock.patch.object(worker, "analyze_action",
                               side_effect=RuntimeError("documento malformado")):
            stats = worker.run(count=1, skip_lifecycle=True)
        self.assertEqual(stats["failed"], 1)


if __name__ == "__main__":
    unittest.main()
