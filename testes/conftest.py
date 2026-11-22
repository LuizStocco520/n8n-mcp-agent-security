"""Preparação comum a todos os testes."""

import pytest

import fornecedor as servidor_do_fornecedor
import servidor


@pytest.fixture
def anyio_backend():
    """Os testes assíncronos rodam no asyncio, o mesmo motor que o servidor usa."""
    return "asyncio"


@pytest.fixture
def fornecedor(tmp_path, monkeypatch):
    """O servidor do fornecedor com o estado numa pasta temporária: o teste nunca toca no acréscimo de verdade."""
    monkeypatch.setattr(servidor_do_fornecedor, "PASTA_ESTADO", tmp_path / "fornecedor")
    monkeypatch.setattr(servidor_do_fornecedor, "ACRESCIMO", tmp_path / "fornecedor" / "acrescimo.txt")
    return servidor_do_fornecedor


@pytest.fixture
def empresa(tmp_path, monkeypatch, fornecedor):
    """O servidor com estado e registro numa pasta temporária: o teste nunca toca nos arquivos de verdade.

    Isola também o fornecedor, porque o preparar() do medir.py mexe nos dois servidores.
    """
    monkeypatch.setattr(servidor, "PASTA_ESTADO", tmp_path / "estado")
    monkeypatch.setattr(servidor, "CAIXA_DE_SAIDA", tmp_path / "estado" / "caixa_de_saida.jsonl")
    monkeypatch.setattr(servidor, "EXECUCAO_ATUAL", tmp_path / "estado" / "execucao.json")
    monkeypatch.setattr(servidor, "REGISTRO", tmp_path / "bruto" / "auditoria.jsonl")
    servidor.reiniciar_estado()
    return servidor
