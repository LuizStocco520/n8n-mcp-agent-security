"""Servidor MCP da empresa (Projeto 3).

Ferramentas: buscar_artigo e consultar_usuario (leitura) e atualizar_chamado (escrita), sobre dados inventados.
A enviar_email, o registro de auditoria e as regras da V2 entram nos próximos passos.

Escuta só no próprio PC, em http://127.0.0.1:8001/mcp
"""

import json
import os
import shutil
import unicodedata
from pathlib import Path
from typing import Literal

from mcp.server.mcpserver import MCPServer

PASTA = Path(__file__).parent
# Os dados iniciais, versionados no Git. O servidor nunca muda estes arquivos.
PASTA_DADOS = PASTA / "dados"
# A cópia que as ferramentas leem e mudam. Fica fora do Git.
PASTA_ESTADO = PASTA / "estado"

Categoria = Literal["acesso", "rede", "hardware", "software", "phishing", "outro"]
Urgencia = Literal["baixa", "media", "alta", "critica"]
Status = Literal["aberto", "em_andamento", "resolvido"]

servidor = MCPServer(name="empresa")


def reiniciar_estado() -> None:
    """Copia os dados iniciais para a pasta estado: toda execução começa do mesmo ponto."""
    PASTA_ESTADO.mkdir(exist_ok=True)
    for arquivo in PASTA_DADOS.glob("*.json"):
        shutil.copyfile(arquivo, PASTA_ESTADO / arquivo.name)


def carregar(nome_do_arquivo: str) -> list[dict]:
    """Lê um arquivo da pasta estado.

    Lê de novo a cada chamada: uma mudança nos dados vale já na chamada seguinte, sem reiniciar o servidor.
    """
    with open(PASTA_ESTADO / nome_do_arquivo, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def gravar(nome_do_arquivo: str, dados: list[dict]) -> None:
    """Grava primeiro num arquivo temporário e depois troca de uma vez: o arquivo nunca fica pela metade."""
    temporario = PASTA_ESTADO / (nome_do_arquivo + ".tmp")
    with open(temporario, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
    os.replace(temporario, PASTA_ESTADO / nome_do_arquivo)


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


@servidor.tool()
def consultar_usuario(email: str) -> str:
    """Consulta o cadastro de um funcionário pelo e-mail e devolve nome, e-mail, CPF, departamento e observações."""
    # Só a busca exata por e-mail: a ferramenta não lista cadastros nem procura por nome ou CPF (menor privilégio).
    procurado = email.strip().lower()
    for usuario in carregar("usuarios.json"):
        if usuario["email"].lower() == procurado:
            # As observações são escritas pelo próprio funcionário no perfil: é texto não confiável.
            return (
                f"Nome: {usuario['nome']}\n"
                f"E-mail: {usuario['email']}\n"
                f"CPF: {usuario['cpf']}\n"
                f"Departamento: {usuario['departamento']}\n"
                f"Observações: {usuario['observacoes'] or '(nenhuma)'}"
            )
    return "Nenhum usuário com esse e-mail."


@servidor.tool()
def atualizar_chamado(
    chamado_id: str,
    categoria: Categoria | None = None,
    urgencia: Urgencia | None = None,
    status: Status | None = None,
) -> str:
    """Muda a categoria, a urgência ou o status de um chamado. Informe só os campos que vão mudar."""
    # Menor privilégio: só esses três campos, só os valores da lista. Não apaga chamado nem troca o solicitante.
    mudancas = {"categoria": categoria, "urgencia": urgencia, "status": status}
    mudancas = {campo: valor for campo, valor in mudancas.items() if valor is not None}
    if not mudancas:
        return "Nada a mudar: informe a categoria, a urgência ou o status."
    chamados = carregar("chamados.json")
    for chamado in chamados:
        if chamado["id"] == chamado_id.strip().upper():
            antes = {campo: chamado[campo] for campo in mudancas}
            chamado.update(mudancas)
            gravar("chamados.json", chamados)
            resumo = ", ".join(f"{campo} de {antes[campo]} para {valor}" for campo, valor in mudancas.items())
            return f"Chamado {chamado['id']} atualizado: {resumo}."
    return "Nenhum chamado com esse número."


if __name__ == "__main__":
    reiniciar_estado()
    try:
        # A 8000, padrão do SDK, é a porta de muitos outros programas de teste. A 8002 fica para o servidor do fornecedor.
        servidor.run(transport="streamable-http", host="127.0.0.1", port=8001)
    except KeyboardInterrupt:
        # Ctrl+C: o uvicorn já desligou o servidor direito; isto só evita o aviso do Python no fim.
        pass
