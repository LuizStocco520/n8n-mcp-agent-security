"""Testa o servidor da empresa sem o n8n: lista as ferramentas e chama cada uma.

Rode com o servidor já ligado, noutro Terminal com o venv ativo.
"""

import asyncio

from mcp import Client

ENDERECO = "http://127.0.0.1:8001/mcp"


async def chamar(cliente: Client, ferramenta: str, argumentos: dict) -> None:
    resposta = await cliente.call_tool(ferramenta, argumentos)
    print(f"Resposta de {ferramenta} {argumentos}:")
    for parte in resposta.content:
        print(parte.text)
    print()


async def main() -> None:
    async with Client(ENDERECO) as cliente:
        lista = await cliente.list_tools()
        for ferramenta in lista.tools:
            print("Ferramenta:", ferramenta.name)
            print("Descrição, o texto que o modelo lê:", ferramenta.description)
            print("Parâmetros:", ferramenta.input_schema)
            print()

        await chamar(cliente, "buscar_artigo", {"termo": "VPN não conecta"})
        await chamar(cliente, "consultar_usuario", {"email": "ana.souza@empresa.example"})
        await chamar(cliente, "consultar_usuario", {"email": "ninguem@empresa.example"})


if __name__ == "__main__":
    asyncio.run(main())
