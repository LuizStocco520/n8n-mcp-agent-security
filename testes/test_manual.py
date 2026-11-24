"""O manual que o modelo lê é o mesmo em todas as versões das defesas.

O manual é o que o n8n recebe de cada servidor e passa ao modelo: o nome, a descrição e os argumentos de cada
ferramenta, com as listas de valores aceitos. Se ele mudasse de uma versão para outra, a comparação entre as versões
mediria também a mudança no manual, e não só a defesa. A impressão digital abaixo é a do manual da V0, da V1 e da V2,
conferida no código das três medições (commits 292dd7e, 2752e01 e cbd3fe5). Mudar o manual tem que ser de propósito,
e o teste falha até alguém trocar a impressão digital aqui.
"""

import hashlib
import json

import pytest
from mcp import Client

pytestmark = pytest.mark.anyio

DA_EMPRESA = "f9e0975e803757220450b6f0796bf301525cf5b9fd4de3784972e9981c59e428"
# A descrição limpa: na A6, o acréscimo envenenado entra só na execução do ataque (test_fornecedor.py).
DO_FORNECEDOR = "c0e30930888547989e287de69d3655a66f82bd01d7ae67c97337b63955a0d048"


async def impressao_digital(servidor) -> str:
    """O SHA-256 do manual como o cliente o recebe: nome, descrição e argumentos de cada ferramenta."""
    async with Client(servidor) as cliente:
        ferramentas = (await cliente.list_tools()).tools
    manual = [{"name": f.name, "description": f.description, "input_schema": f.input_schema} for f in ferramentas]
    return hashlib.sha256(json.dumps(manual, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


async def test_manual_da_empresa_e_o_mesmo_desde_a_v0(empresa):
    assert await impressao_digital(empresa.servidor) == DA_EMPRESA


async def test_manual_do_fornecedor_e_o_mesmo_desde_a_v0(fornecedor):
    assert await impressao_digital(fornecedor.servidor) == DO_FORNECEDOR
