"""Os arquivos de casos são conferidos antes de qualquer medição: um erro de digitação não pode estragar uma noite."""

import json
from pathlib import Path

import pytest

from juiz import URGENCIAS, esperadas

PROJETO = Path(__file__).resolve().parent.parent
USUARIOS = {u["email"] for u in json.loads((PROJETO / "servidores/empresa/dados/usuarios.json").read_text(encoding="utf-8"))}
CHAMADOS_BASE = {c["id"] for c in json.loads((PROJETO / "servidores/empresa/dados/chamados.json").read_text(encoding="utf-8"))}
ARQUIVOS = sorted((PROJETO / "medicao/casos").glob("*.json"))


@pytest.mark.parametrize("arquivo", ARQUIVOS, ids=lambda a: a.name)
def test_casos_bem_formados(arquivo):
    casos = json.loads(arquivo.read_text(encoding="utf-8"))
    ids = [c["id"] for c in casos]
    chamados = [c["chamado"]["id"] for c in casos]
    assert len(ids) == len(set(ids)), "id de caso repetido"
    assert len(chamados) == len(set(chamados)), "número de chamado repetido"
    for caso in casos:
        chamado = caso["chamado"]
        assert chamado["solicitante"] in USUARIOS, f"{caso['id']}: solicitante fora do cadastro"
        assert chamado["id"] not in CHAMADOS_BASE, f"{caso['id']}: número já usado nos dados iniciais"
        assert chamado["urgencia"] in URGENCIAS
        # Monta o estado final igual ao inicial: só confere que todo tipo de expectativa é conhecido pelo juiz.
        esperadas(caso, [], {chamado["id"]: chamado})


def test_sao_10_tarefas_legitimas():
    assert len(json.loads((PROJETO / "medicao/casos/legitimas.json").read_text(encoding="utf-8"))) == 10
