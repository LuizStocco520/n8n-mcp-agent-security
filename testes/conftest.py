"""Preparação comum a todos os testes."""

import pytest

import servidor


@pytest.fixture
def anyio_backend():
    """Os testes assíncronos rodam no asyncio, o mesmo motor que o servidor usa."""
    return "asyncio"


@pytest.fixture
def empresa(tmp_path, monkeypatch):
    """O servidor com estado e registro numa pasta temporária: o teste nunca toca nos arquivos de verdade."""
    monkeypatch.setattr(servidor, "PASTA_ESTADO", tmp_path / "estado")
    monkeypatch.setattr(servidor, "CAIXA_DE_SAIDA", tmp_path / "estado" / "caixa_de_saida.jsonl")
    monkeypatch.setattr(servidor, "EXECUCAO_ATUAL", tmp_path / "estado" / "execucao.json")
    monkeypatch.setattr(servidor, "REGISTRO", tmp_path / "bruto" / "auditoria.jsonl")
    servidor.reiniciar_estado()
    return servidor
