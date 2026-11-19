"""Testa o servidor da empresa sem o n8n: lista as ferramentas e chama uma delas.

Rode com o servidor já ligado, noutro Terminal com o venv ativo.
"""

import asyncio

from mcp import Client

ENDERECO = "http://127.0.0.1:8001/mcp"


async def main() -> None:
    async with Client(ENDERECO) as cliente:
        lista = await cliente.list_tools()
        for ferramenta in lista.tools:
            print("Ferramenta:", ferramenta.name)
            print("Descrição, o texto que o modelo lê:", ferramenta.description)
            print("Parâmetros:", ferramenta.input_schema)
            print()

        resposta = await cliente.call_tool("buscar_artigo", {"termo": "VPN não conecta"})
        print("Resposta de buscar_artigo:")
        for parte in resposta.content:
            print(parte.text)


if __name__ == "__main__":
    asyncio.run(main())
