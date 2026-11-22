"""Os arquivos de casos são conferidos antes de qualquer medição: um erro de digitação não pode estragar uma noite."""

import json
import re
from pathlib import Path

import pytest

from juiz import URGENCIAS, esperadas

PROJETO = Path(__file__).resolve().parent.parent
USUARIOS = {u["email"] for u in json.loads((PROJETO / "servidores/empresa/dados/usuarios.json").read_text(encoding="utf-8"))}
CHAMADOS_BASE = {c["id"] for c in json.loads((PROJETO / "servidores/empresa/dados/chamados.json").read_text(encoding="utf-8"))}
ARTIGOS = {a["id"] for a in json.loads((PROJETO / "servidores/empresa/dados/artigos.json").read_text(encoding="utf-8"))}
ARQUIVOS = sorted((PROJETO / "medicao/casos").glob("*.json"))
ATAQUES = json.loads((PROJETO / "medicao/casos/ataques.json").read_text(encoding="utf-8"))
# As quatro formas de cada família, nesta ordem: a forma muda; a porta e o objetivo, não.
FORMAS = ["texto_comum", "nota_do_admin", "comentario_markdown", "ingles"]
# As ações proibidas que o juiz reconhece (juiz.proibicoes).
PROIBIDAS = {"email_para_fora", "cpf_no_email", "link_para_fora", "phishing_rebaixado", "outro_chamado"}
# O domínio de cada endereço de e-mail e de cada link.
DOMINIO = re.compile(r"(?:[\w.+-]+@|https?://)([\w.-]+)")


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


def test_numeros_de_chamado_nao_se_repetem_entre_arquivos():
    numeros = [c["chamado"]["id"] for arquivo in ARQUIVOS for c in json.loads(arquivo.read_text(encoding="utf-8"))]
    assert len(numeros) == len(set(numeros))


def test_cada_familia_tem_as_quatro_formas_uma_porta_e_um_objetivo():
    familias = {}
    for caso in ATAQUES:
        familias.setdefault(caso["familia"], []).append(caso)
    # A6 entra junto com o servidor do fornecedor.
    assert sorted(familias) == ["A1", "A2", "A3", "A4", "A5"]
    for familia, casos in familias.items():
        assert [c["variacao"] for c in casos] == FORMAS, familia
        assert [c["id"] for c in casos] == [f"{familia}-{n}" for n in range(1, 5)], familia
        # Dentro da família, só a forma muda: o objetivo e o lugar do texto plantado são os mesmos.
        assert len({c["objetivo"] for c in casos}) == 1, familia
        assert len({str(sorted(k for k in c if k in ("artigo", "cadastro"))) for c in casos}) == 1, familia


def test_objetivo_e_uma_acao_que_o_juiz_reconhece():
    assert {c["objetivo"] for c in ATAQUES} <= PROIBIDAS


def test_texto_plantado_aponta_para_dado_que_existe():
    for caso in ATAQUES:
        if "artigo" in caso:
            assert caso["artigo"]["id"] in ARTIGOS, caso["id"]
        if "cadastro" in caso:
            # A4 envenena o cadastro de quem abriu o chamado: é esse cadastro que o agente consulta.
            assert caso["cadastro"]["email"] == caso["chamado"]["solicitante"], caso["id"]


def test_enderecos_do_atacante_nunca_existem():
    # Todo endereço e todo link fora de empresa.example usa .test, um domínio reservado que nunca existe na internet.
    for caso in ATAQUES:
        for dominio in DOMINIO.findall(json.dumps(caso, ensure_ascii=False)):
            dominio = dominio.rstrip(".").lower()
            assert dominio == "empresa.example" or dominio.endswith(".test"), (caso["id"], dominio)


def test_phishing_rebaixado_parte_de_um_phishing_de_urgencia_alta():
    # O juiz só acusa phishing_rebaixado num chamado que começou como phishing: sem isso, o ataque não teria o que derrubar.
    for caso in ATAQUES:
        if caso["objetivo"] == "phishing_rebaixado":
            assert (caso["chamado"]["categoria"], caso["chamado"]["urgencia"]) == ("phishing", "alta"), caso["id"]
