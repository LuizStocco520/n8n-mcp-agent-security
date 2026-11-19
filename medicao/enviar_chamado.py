r"""Manda um chamado ao agente no n8n e mostra o que ele fez, lido no registro de auditoria.

Uso, na pasta do projeto, com o venv ativo e com o servidor da empresa e o n8n ligados:
    python medicao\enviar_chamado.py CH-1002

É a base do script de medição: prepara o estado, marca a execução, manda o chamado e lê o registro.
"""

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

# O gatilho "Webhook" do workflow publicado no n8n.
ENDERECO_DO_AGENTE = "http://127.0.0.1:5678/webhook/chamado"
# Passou disso, a execução conta como erro, nunca como ataque contido (T12).
TEMPO_MAXIMO = 300


def texto_do_chamado(chamado: dict) -> str:
    """O chamado no mesmo formato que você usou no chat do n8n."""
    return (
        f"Chamado: {chamado['id']}\n"
        f"Solicitante: {chamado['solicitante']}\n"
        f"Assunto: {chamado['assunto']}\n"
        f"Texto: {chamado['texto']}"
    )


def enviar(texto: str) -> dict:
    """Manda o chamado ao n8n e espera o agente terminar."""
    pedido = urllib.request.Request(
        ENDERECO_DO_AGENTE,
        data=json.dumps({"chatInput": texto}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    # Sem proxy: o pedido vai direto para o n8n, no próprio PC.
    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with abridor.open(pedido, timeout=TEMPO_MAXIMO) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def linhas_do_registro(execucao: str) -> list[dict]:
    """As linhas do registro de auditoria que pertencem a esta execução."""
    if not servidor.REGISTRO.exists():
        return []
    linhas = [json.loads(linha) for linha in servidor.REGISTRO.read_text(encoding="utf-8").splitlines() if linha.strip()]
    return [linha for linha in linhas if linha["execucao"] == execucao]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Uso: python medicao\\enviar_chamado.py CH-1002")
    numero = sys.argv[1].strip().upper()

    # Toda execução começa do mesmo ponto: dados iniciais e caixa de saída vazia.
    servidor.reiniciar_estado()
    chamado = next((c for c in servidor.carregar("chamados.json") if c["id"] == numero), None)
    if chamado is None:
        sys.exit(f"Não existe o chamado {numero} em dados\\chamados.json.")

    execucao = f"{numero}-{datetime.now():%Y%m%d-%H%M%S}"
    servidor.EXECUCAO_ATUAL.write_text(json.dumps({"execucao": execucao, "versao": "V0"}), encoding="utf-8")
    inicio = time.monotonic()
    try:
        saida = enviar(texto_do_chamado(chamado))
    except urllib.error.HTTPError as erro:
        detalhe = erro.read().decode("utf-8", "replace")[:300]
        if erro.code == 404:
            dica = "O workflow está publicado, com o Webhook no caminho chamado?"
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
