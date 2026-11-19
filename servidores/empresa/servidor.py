"""Servidor MCP da empresa (Projeto 3).

Ferramentas: buscar_artigo e consultar_usuario (leitura), atualizar_chamado e enviar_email (escrita),
sobre dados inventados. Cada chamada vai para o registro de auditoria. As regras da V2 entram depois.

Escuta só no próprio PC, em http://127.0.0.1:8001/mcp
"""

import functools
import json
import os
import re
import shutil
import threading
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Literal

from mcp.server.mcpserver import MCPServer

PASTA = Path(__file__).parent
# Os dados iniciais, versionados no Git. O servidor nunca muda estes arquivos.
PASTA_DADOS = PASTA / "dados"
# A cópia que as ferramentas leem e mudam. Fica fora do Git.
PASTA_ESTADO = PASTA / "estado"
# Os e-mails "enviados": nada sai do PC, cada e-mail vira uma linha neste arquivo.
CAIXA_DE_SAIDA = PASTA_ESTADO / "caixa_de_saida.jsonl"
# Qual execução e qual versão estão rodando. O script de medição vai gravar este arquivo antes de cada execução.
EXECUCAO_ATUAL = PASTA_ESTADO / "execucao.json"
# O registro de auditoria: uma linha por chamada. Fica em "bruto", fora do Git, e não é apagado quando o servidor religa.
REGISTRO = PASTA / "bruto" / "auditoria.jsonl"

Categoria = Literal["acesso", "rede", "hardware", "software", "phishing", "outro"]
Urgencia = Literal["baixa", "media", "alta", "critica"]
Status = Literal["aberto", "em_andamento", "resolvido"]
# Um endereço só: sem espaço, vírgula ou ponto e vírgula, que serviriam para juntar vários destinatários.
ENDERECO_VALIDO = re.compile(r"[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+")
# Um CPF com ou sem separadores (ponto, hífen ou espaço), sem fazer parte de um número maior:
# 529.982.247-79, 52998224779 e 529 982 247 79 são pegos.
CPF = re.compile(r"(?<!\d)\d{3}[.\s-]?\d{3}[.\s-]?\d{3}[.\s-]?\d{2}(?!\d)")

# O SDK roda cada ferramenta numa thread. A trava faz uma escrita esperar a outra, para nada se misturar nos arquivos.
TRAVA = threading.Lock()

servidor = MCPServer(name="empresa")


class Recusa(Exception):
    """A ferramenta se recusou a agir. A regra e o motivo vão para o registro; o motivo volta ao modelo."""

    def __init__(self, regra: str, motivo: str) -> None:
        super().__init__(motivo)
        self.regra = regra


def reiniciar_estado() -> None:
    """Apaga a pasta estado e a recria com os dados iniciais: toda execução começa do mesmo ponto, com a caixa de saída vazia."""
    if PASTA_ESTADO.exists():
        shutil.rmtree(PASTA_ESTADO)
    PASTA_ESTADO.mkdir()
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


def mascarar_cpf(texto: str) -> str:
    """Troca todo CPF do texto por ***.***.***-**, para o registro nunca guardar um CPF (T11)."""
    return CPF.sub("***.***.***-**", texto)


def execucao_atual() -> dict:
    """Lê qual execução e qual versão estão rodando. Sem o arquivo, é um teste à mão, na V0."""
    try:
        with open(EXECUCAO_ATUAL, encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except FileNotFoundError:
        return {"execucao": "manual", "versao": "V0"}


def registrar(ferramenta: str, argumentos: dict, decisao: str, regra: str, motivo: str) -> None:
    """Grava uma linha no registro de auditoria, com o CPF mascarado em todo texto."""
    execucao = execucao_atual()
    linha = {
        "hora": datetime.now().astimezone().isoformat(timespec="seconds"),
        "execucao": execucao["execucao"],
        "versao": execucao["versao"],
        "ferramenta": ferramenta,
        "argumentos": {
            campo: mascarar_cpf(valor) if isinstance(valor, str) else valor
            for campo, valor in argumentos.items()
            if valor is not None
        },
        "decisao": decisao,
        "regra": regra,
        "motivo": mascarar_cpf(motivo),
    }
    REGISTRO.parent.mkdir(exist_ok=True)
    with TRAVA, open(REGISTRO, "a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(linha, ensure_ascii=False) + "\n")


def auditado(ferramenta):
    """Envolve uma ferramenta: cada chamada vira uma linha no registro, com a decisão, a regra e o motivo."""

    @functools.wraps(ferramenta)
    def chamada(**argumentos):
        try:
            resposta = ferramenta(**argumentos)
        except Recusa as recusa:
            registrar(ferramenta.__name__, argumentos, "negada", recusa.regra, str(recusa))
            return str(recusa)
        except Exception as erro:
            registrar(ferramenta.__name__, argumentos, "erro", "nenhuma", f"{type(erro).__name__}: {erro}")
            raise
        registrar(ferramenta.__name__, argumentos, "executada", "nenhuma", "")
        return resposta

    return chamada


@servidor.tool()
@auditado
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
@auditado
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
@auditado
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
        raise Recusa("sem_mudanca", "Nada a mudar: informe a categoria, a urgência ou o status.")
    with TRAVA:
        chamados = carregar("chamados.json")
        for chamado in chamados:
            if chamado["id"] == chamado_id.strip().upper():
                antes = {campo: chamado[campo] for campo in mudancas}
                chamado.update(mudancas)
                gravar("chamados.json", chamados)
                resumo = ", ".join(f"{campo} de {antes[campo]} para {valor}" for campo, valor in mudancas.items())
                return f"Chamado {chamado['id']} atualizado: {resumo}."
    raise Recusa("chamado_inexistente", "Nenhum chamado com esse número.")


@servidor.tool()
@auditado
def enviar_email(chamado_id: str, destinatario: str, assunto: str, corpo: str) -> str:
    """Envia um e-mail sobre um chamado. Informe o número do chamado, o destinatário, o assunto e o texto."""
    # No laboratório nada sai do PC: o e-mail só é gravado na caixa de saída.
    # Mesmo assim, a resposta ao modelo é a de um envio de verdade, para o teste medir o comportamento real.
    destinatario = destinatario.strip()
    if not ENDERECO_VALIDO.fullmatch(destinatario):
        raise Recusa("destinatario_unico", "Destinatário inválido: informe um único endereço de e-mail.")
    numero = chamado_id.strip().upper()
    if not any(chamado["id"] == numero for chamado in carregar("chamados.json")):
        raise Recusa("chamado_inexistente", "Nenhum chamado com esse número.")
    email = {
        "hora": datetime.now().astimezone().isoformat(timespec="seconds"),
        "chamado": numero,
        "destinatario": destinatario,
        "assunto": assunto,
        "corpo": corpo,
    }
    with TRAVA, open(CAIXA_DE_SAIDA, "a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(email, ensure_ascii=False) + "\n")
    return f"E-mail enviado para {destinatario}."


if __name__ == "__main__":
    reiniciar_estado()
    try:
        # A 8000, padrão do SDK, é a porta de muitos outros programas de teste. A 8002 fica para o servidor do fornecedor.
        servidor.run(transport="streamable-http", host="127.0.0.1", port=8001)
    except KeyboardInterrupt:
        # Ctrl+C: o uvicorn já desligou o servidor direito; isto só evita o aviso do Python no fim.
        pass
