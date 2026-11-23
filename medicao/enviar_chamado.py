r"""Manda um chamado ao agente no n8n e mostra o que ele fez, lido no registro de auditoria.

Uso, na pasta do projeto, com o venv ativo e com os servidores da empresa e do fornecedor e o n8n ligados:
    python medicao\enviar_chamado.py CH-1002
    python medicao\enviar_chamado.py CH-1002 --versao V1

É a base do script de medição: prepara o estado, marca a execução, manda o chamado e lê o registro.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA_PROJETO / "servidores" / "empresa"))
import servidor  # noqa: E402  (precisa vir depois da linha acima, que mostra onde ele está)

# Cada versão do agente é um workflow próprio no n8n, com o gatilho "Webhook" no seu caminho. A V0 continua no
# caminho de sempre e pode ser medida de novo a qualquer hora.
CAMINHOS = {"V0": "chamado", "V1": "chamado-v1", "V2": "chamado-v2"}
# Um pouco mais que o tempo máximo do workflow no n8n, de 5 minutos: o n8n encerra primeiro e o erro vem dele.
# Um TimeoutError aqui quer dizer que o limite do servidor falhou (T12).
TEMPO_MAXIMO = 330


def texto_do_chamado(chamado: dict) -> str:
    """O chamado no mesmo formato que você usou no chat do n8n."""
    return (
        f"Chamado: {chamado['id']}\n"
        f"Solicitante: {chamado['solicitante']}\n"
        f"Assunto: {chamado['assunto']}\n"
        f"Texto: {chamado['texto']}"
    )


def endereco(versao: str) -> str:
    """O endereço do workflow de uma versão no n8n."""
    if versao not in CAMINHOS:
        raise ValueError(f"A versão {versao} ainda não tem workflow no n8n.")
    return f"http://127.0.0.1:5678/webhook/{CAMINHOS[versao]}"


def versao_marcada() -> str:
    """A versão da execução em andamento, lida da mesma marca que os servidores leem. Sem marca, é a V0."""
    try:
        return json.loads(servidor.EXECUCAO_ATUAL.read_text(encoding="utf-8"))["versao"]
    except FileNotFoundError:
        return "V0"


def enviar(texto: str) -> dict:
    """Manda o chamado ao workflow da versão marcada e espera o agente terminar.

    A versão sai da marca da execução, a mesma que os servidores leem: o workflow que atende e o que os servidores
    fazem nunca ficam em versões diferentes.
    """
    pedido = urllib.request.Request(
        endereco(versao_marcada()),
        data=json.dumps({"chatInput": texto}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    # Sem proxy: o pedido vai direto para o n8n, no próprio PC.
    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with abridor.open(pedido, timeout=TEMPO_MAXIMO) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def linhas_do_registro(execucao: str, registro: Path | None = None) -> list[dict]:
    """As linhas de um registro de auditoria que pertencem a esta execução. Sem registro, o do servidor da empresa."""
    registro = registro or servidor.REGISTRO
    if not registro.exists():
        return []
    linhas = [json.loads(linha) for linha in registro.read_text(encoding="utf-8").splitlines() if linha.strip()]
    return [linha for linha in linhas if linha["execucao"] == execucao]


def main() -> None:
    parser = argparse.ArgumentParser(description="Manda um chamado ao agente e mostra o que ele fez.")
    parser.add_argument("chamado", help="o número do chamado. Por exemplo: CH-1002")
    parser.add_argument("--versao", default="V0", choices=sorted(CAMINHOS), help="a versão do agente (padrão: V0)")
    args = parser.parse_args()
    numero = args.chamado.strip().upper()

    # Toda execução começa do mesmo ponto: dados iniciais e caixa de saída vazia.
    servidor.reiniciar_estado()
    chamado = next((c for c in servidor.carregar("chamados.json") if c["id"] == numero), None)
    if chamado is None:
        sys.exit(f"Não existe o chamado {numero} em dados\\chamados.json.")

    execucao = f"{numero}-{datetime.now():%Y%m%d-%H%M%S}"
    servidor.EXECUCAO_ATUAL.write_text(json.dumps({"execucao": execucao, "versao": args.versao}), encoding="utf-8")
    inicio = time.monotonic()
    try:
        saida = enviar(texto_do_chamado(chamado))
    except urllib.error.HTTPError as erro:
        detalhe = erro.read().decode("utf-8", "replace")[:300]
        if erro.code == 404:
            dica = f"O workflow da {args.versao} está publicado, com o Webhook no caminho {CAMINHOS[args.versao]}?"
        else:
            dica = "A execução falhou dentro do n8n: o erro aparece na aba Executions."
        sys.exit(f"O n8n respondeu {erro.code}: {detalhe}\n{dica}")
    except (urllib.error.URLError, TimeoutError) as erro:
        sys.exit(f"Sem resposta do n8n: {erro}. Ele está ligado?")
    finally:
        # Depois da execução, os testes à mão voltam a ser registrados como manual.
        servidor.EXECUCAO_ATUAL.unlink(missing_ok=True)
    duracao = time.monotonic() - inicio

    print(f"Execução {execucao}, em {duracao:.0f} segundos.\n")
    print("Resposta do agente:")
    print(saida.get("output", json.dumps(saida, ensure_ascii=False)))
    print("\nO que o registro de auditoria mostra:")
    for linha in linhas_do_registro(execucao):
        argumentos = linha["argumentos"]
        resumo = argumentos.get("destinatario") or argumentos.get("email") or argumentos.get("termo") or argumentos.get("chamado_id", "")
        print(f"  {linha['ferramenta']:18} {linha['decisao']:9} {resumo}")


if __name__ == "__main__":
    main()
