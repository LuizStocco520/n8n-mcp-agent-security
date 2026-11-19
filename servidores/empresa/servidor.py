"""Servidor MCP da empresa (Projeto 3).

Primeira versão: uma ferramenta só, buscar_artigo, que lê artigos inventados.
As outras três ferramentas, o registro de auditoria e as regras da V2 entram nos próximos passos.

Escuta só no próprio PC, em http://127.0.0.1:8001/mcp
"""

import json
import unicodedata
from pathlib import Path

from mcp.server.mcpserver import MCPServer

PASTA_DADOS = Path(__file__).parent / "dados"

servidor = MCPServer(name="empresa")


def carregar(nome_do_arquivo: str) -> list[dict]:
    """Lê um arquivo da pasta dados.

    Lê de novo a cada chamada: uma mudança nos dados vale já na chamada seguinte, sem reiniciar o servidor.
    """
    with open(PASTA_DADOS / nome_do_arquivo, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def normalizar(texto: str) -> str:
    """Minúsculas e sem acentos: "Conexão" e "conexao" ficam iguais na busca."""
    sem_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acentos.lower()


@servidor.tool()
def buscar_artigo(termo: str) -> str:
    """Busca na base de conhecimento do suporte o artigo mais relevante para o termo e devolve o título e o texto dele."""
    # Palavras de uma ou duas letras ("a", "de", "o") apareceriam em todos os artigos.
    palavras = [palavra for palavra in normalizar(termo).split() if len(palavra) >= 3]
    melhor_artigo, melhor_pontuacao = None, 0
    for artigo in carregar("artigos.json"):
        onde_procurar = normalizar(artigo["titulo"] + " " + " ".join(artigo["palavras_chave"]))
        pontuacao = sum(1 for palavra in palavras if palavra in onde_procurar)
        # No empate, fica o primeiro artigo do arquivo: a mesma busca devolve sempre o mesmo artigo.
        if pontuacao > melhor_pontuacao:
            melhor_artigo, melhor_pontuacao = artigo, pontuacao
    if melhor_artigo is None:
        return "Nenhum artigo encontrado para esse termo."
    return f"{melhor_artigo['id']} - {melhor_artigo['titulo']}\n\n{melhor_artigo['texto']}"


if __name__ == "__main__":
    # A 8000, padrão do SDK, é a porta de muitos outros programas de teste. A 8002 fica para o servidor do fornecedor.
    servidor.run(transport="streamable-http", host="127.0.0.1", port=8001)
