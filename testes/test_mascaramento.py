"""T11: o registro de auditoria nunca guarda um CPF. Estes testes não precisam do servidor ligado."""

import pytest

import fornecedor
import servidor
from servidor import mascarar_cpf


def test_o_fornecedor_mascara_com_o_mesmo_padrao():
    # O servidor do fornecedor roda separado e tem uma cópia do padrão: se um mudar, o outro tem que mudar junto.
    assert fornecedor.CPF.pattern == servidor.CPF.pattern


@pytest.mark.parametrize(
    "cpf",
    [
        "529.982.247-79",  # com pontos e hífen
        "52998224779",  # só os números
        "529 982 247 79",  # com espaços
        "529.982.247.79",  # com ponto no lugar do hífen
    ],
)
def test_cpf_em_qualquer_formato_comum_e_mascarado(cpf):
    assert mascarar_cpf(f"CPF: {cpf}.") == "CPF: ***.***.***-**."


def test_dois_cpfs_no_mesmo_texto():
    assert mascarar_cpf("529.982.247-79 e 318.457.902-12") == "***.***.***-** e ***.***.***-**"


@pytest.mark.parametrize(
    "texto",
    [
        "CH-1001",  # número de chamado
        "Ramal 2041.",  # número curto
        "2026-11-19T01:56:09-03:00",  # data e hora do registro
        "Pedido 1234567890123.",  # número com mais de 11 dígitos
    ],
)
def test_o_que_nao_e_cpf_fica_igual(texto):
    assert mascarar_cpf(texto) == texto


@pytest.mark.xfail(reason="Limite conhecido: CPF escrito dígito por dígito passa. A regra da V2 vai precisar cobrir.")
def test_cpf_digito_por_digito():
    assert mascarar_cpf("5 2 9 9 8 2 2 4 7 7 9") == "***.***.***-**"
