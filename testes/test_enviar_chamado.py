"""Cada versão do agente tem o seu workflow no n8n, e o endereço sai da mesma marca que os servidores leem."""

import json
import urllib.error

import pytest

import enviar_chamado


def test_cada_versao_tem_o_seu_endereco_e_a_v0_fica_no_de_sempre():
    assert enviar_chamado.endereco("V0") == "http://127.0.0.1:5678/webhook/chamado"
    assert enviar_chamado.endereco("V1") == "http://127.0.0.1:5678/webhook/chamado-v1"
    # Uma versão sem workflow para logo, em vez de dar erro em todas as execuções.
    with pytest.raises(ValueError):
        enviar_chamado.endereco("V9")


def test_o_workflow_chamado_e_o_da_versao_marcada(empresa, monkeypatch):
    # O workflow que atende e o que os servidores fazem nunca podem ficar em versões diferentes.
    pedidos = []

    class SemN8n:
        def open(self, pedido, timeout):
            pedidos.append(pedido.full_url)
            raise urllib.error.URLError("n8n desligado no teste")

    monkeypatch.setattr(enviar_chamado.urllib.request, "build_opener", lambda *_: SemN8n())
    empresa.EXECUCAO_ATUAL.write_text(json.dumps({"execucao": "V1-teste", "versao": "V1"}), encoding="utf-8")
    with pytest.raises(urllib.error.URLError):
        enviar_chamado.enviar("Chamado: CH-1002")
    # Sem marca, é um teste à mão: V0.
    empresa.EXECUCAO_ATUAL.unlink()
    with pytest.raises(urllib.error.URLError):
        enviar_chamado.enviar("Chamado: CH-1002")
    assert pedidos == ["http://127.0.0.1:5678/webhook/chamado-v1", "http://127.0.0.1:5678/webhook/chamado"]
