"""V1: o texto livre que volta das ferramentas de leitura sai marcado como dado; na V0, sai igual.

A marca é o spotlighting na variante datamarking: um ^ no lugar de cada espaço. O prompt da V1 explica a marca ao
modelo. A V2 e a V3 somam defesas à V1, e a V4 parte dela, então todas marcam.
"""

import json

import pytest


def marcar_versao(empresa, versao: str) -> None:
    """O que o medir.py faz antes de cada execução: diz ao servidor qual versão está rodando."""
    empresa.EXECUCAO_ATUAL.write_text(json.dumps({"execucao": f"{versao}-teste", "versao": versao}), encoding="utf-8")


def texto_do_artigo(empresa, artigo_id: str) -> str:
    return next(a for a in empresa.carregar("artigos.json") if a["id"] == artigo_id)["texto"]


def test_marca_troca_os_espacos_e_mantem_as_linhas_e_os_links(empresa):
    texto = "1. Abra https://senha.empresa.example\n2. Crie  uma senha nova"
    assert empresa.marcar_dado(texto) == "1.^Abra^https://senha.empresa.example\n2.^Crie^uma^senha^nova"


@pytest.mark.parametrize("versao", ["V1", "V2", "V3", "V4"])
def test_texto_do_artigo_sai_marcado_da_v1_em_diante(empresa, versao):
    marcar_versao(empresa, versao)
    titulo, texto = empresa.buscar_artigo(termo="VPN").split("\n\n", 1)
    # O título é da base, não de quem edita o texto: fica como está.
    assert titulo.startswith("KB-002 - ") and " " in titulo
    assert texto == empresa.marcar_dado(texto_do_artigo(empresa, "KB-002"))
    assert " " not in texto


def test_texto_do_artigo_sai_igual_na_v0_e_num_teste_a_mao(empresa):
    original = texto_do_artigo(empresa, "KB-002")
    marcar_versao(empresa, "V0")
    assert empresa.buscar_artigo(termo="VPN").endswith("\n\n" + original)
    # Sem marca de execução, é um teste à mão, que conta como V0.
    empresa.EXECUCAO_ATUAL.unlink()
    assert empresa.buscar_artigo(termo="VPN").endswith("\n\n" + original)


def test_so_as_observacoes_do_cadastro_saem_marcadas(empresa):
    marcar_versao(empresa, "V1")
    campos = dict(linha.split(": ", 1) for linha in empresa.consultar_usuario(email="fabio.nunes@empresa.example").splitlines())
    # Nome, e-mail e departamento vêm do cadastro da empresa; as observações, o funcionário escreve (A4).
    assert campos["Nome"] == "Fábio Nunes"
    assert campos["Observações"] == "Usa^um^notebook^emprestado^até^março."
    # Sem observação, o servidor diz que não há nenhuma, sem marca.
    elisa = dict(linha.split(": ", 1) for linha in empresa.consultar_usuario(email="elisa.prado@empresa.example").splitlines())
    assert elisa["Observações"] == "(nenhuma)"
