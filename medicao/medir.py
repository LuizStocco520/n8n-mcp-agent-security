r"""Roda os casos no agente do n8n e julga cada execução pelas evidências.

Uso, na pasta do projeto, com o venv ativo e com o servidor da empresa e o n8n ligados:
    python medicao\medir.py legitimas
    python medicao\medir.py legitimas --rodadas 10 --casos L03,L09

Para cada execução: reinicia o estado, coloca o chamado do caso, marca a execução, manda o chamado ao agente,
junta as evidências e pede o veredito ao juiz. Cada execução vira uma linha num CSV em medicao\resultados,
com as colunas em inglês, como tudo o que é publicado. O que cada coluna e cada valor querem dizer está em
medicao\resultados\README.md.
Uma execução que dá erro (n8n fora do ar, tempo esgotado) fica no CSV como erro e é repetida: nunca conta como resultado.
"""

import argparse
import copy
import csv
import json
import sys
import time
import urllib.error
from datetime import datetime
from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA_PROJETO / "servidores" / "empresa"))
import servidor  # noqa: E402  (precisa vir depois da linha acima, que mostra onde ele está)
from enviar_chamado import enviar, linhas_do_registro, texto_do_chamado  # noqa: E402
from juiz import veredito  # noqa: E402

PASTA_CASOS = PASTA_PROJETO / "medicao" / "casos"
PASTA_RESULTADOS = PASTA_PROJETO / "medicao" / "resultados"
# As respostas do modelo ficam guardadas só para consulta, fora do Git. Não entram no veredito nem no CSV.
RESPOSTAS = PASTA_PROJETO / "bruto" / "respostas.jsonl"
# Quantas vezes tentar uma execução que deu erro antes de desistir dela.
TENTATIVAS = 3
COLUNAS = ["case", "run", "attempt", "run_id", "version", "result", "missing", "forbidden", "denied", "tools", "seconds", "detail"]


def preparar(caso: dict) -> dict:
    """Estado inicial: os dados iniciais mais o chamado do caso. Devolve os chamados como estão antes da execução."""
    servidor.reiniciar_estado()
    chamados = [c for c in servidor.carregar("chamados.json") if c["id"] != caso["chamado"]["id"]]
    chamados.append(caso["chamado"])
    servidor.gravar("chamados.json", chamados)
    return {c["id"]: copy.deepcopy(c) for c in chamados}


def evidencias(execucao: str) -> tuple:
    """As evidências que o servidor gravou: registro, caixa de saída, chamados e os CPFs do cadastro."""
    linhas = linhas_do_registro(execucao)
    caixa = servidor.CAIXA_DE_SAIDA
    emails = [json.loads(l) for l in caixa.read_text(encoding="utf-8").splitlines() if l.strip()] if caixa.exists() else []
    depois = {c["id"]: c for c in servidor.carregar("chamados.json")}
    cpfs = [u["cpf"] for u in servidor.carregar("usuarios.json")]
    return linhas, emails, depois, cpfs


def executar(caso: dict, rodada: int, tentativa: int, versao: str) -> dict:
    """Uma execução do caso, do estado inicial ao veredito. Devolve a linha do CSV."""
    antes = preparar(caso)
    execucao = f"{versao}-{caso['id']}-r{rodada:02d}-t{tentativa}-{datetime.now():%Y%m%d-%H%M%S}"
    marca = {"execucao": execucao, "versao": versao, "chamado": caso["chamado"]["id"]}
    servidor.EXECUCAO_ATUAL.write_text(json.dumps(marca), encoding="utf-8")
    linha = dict.fromkeys(COLUNAS, "") | {"case": caso["id"], "run": rodada, "attempt": tentativa, "run_id": execucao, "version": versao}
    inicio = time.monotonic()
    try:
        saida = enviar(texto_do_chamado(caso["chamado"]))
    except urllib.error.HTTPError as erro:
        return linha | {"result": "erro", "detail": f"o n8n respondeu {erro.code}", "seconds": round(time.monotonic() - inicio)}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as erro:
        return linha | {"result": "erro", "detail": f"{type(erro).__name__}: {erro}"[:200], "seconds": round(time.monotonic() - inicio)}
    finally:
        servidor.EXECUCAO_ATUAL.unlink(missing_ok=True)
    segundos = round(time.monotonic() - inicio)
    with open(RESPOSTAS, "a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps({"execucao": execucao, "resposta": saida}, ensure_ascii=False) + "\n")
    linhas, emails, depois, cpfs = evidencias(execucao)
    resultado = veredito(caso, linhas, emails, antes, depois, cpfs)
    return linha | {
        "result": resultado["resultado"],
        "missing": "|".join(resultado["faltou"]),
        "forbidden": "|".join(resultado["proibidas"]),
        "denied": "|".join(resultado["negadas"]),
        "tools": " ".join(f"{l['ferramenta']}:{l['decisao']}" for l in linhas),
        "seconds": segundos,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Roda os casos no agente e julga cada execução.")
    parser.add_argument("arquivo", help="o arquivo de casos, sem o .json. Por exemplo: legitimas")
    parser.add_argument("--rodadas", type=int, default=1, help="quantas vezes rodar cada caso (padrão: 1)")
    parser.add_argument("--versao", default="V0", help="a versão das defesas que está ligada (padrão: V0)")
    parser.add_argument("--casos", default="", help="só estes casos, separados por vírgula. Por exemplo: L03,L09")
    args = parser.parse_args()

    casos = json.loads((PASTA_CASOS / f"{args.arquivo}.json").read_text(encoding="utf-8"))
    if args.casos:
        escolhidos = {c.strip().upper() for c in args.casos.split(",")}
        casos = [c for c in casos if c["id"] in escolhidos]
    PASTA_RESULTADOS.mkdir(exist_ok=True)
    RESPOSTAS.parent.mkdir(exist_ok=True)
    destino = PASTA_RESULTADOS / f"{args.arquivo}-{args.versao}-{datetime.now():%Y%m%d-%H%M%S}.csv"

    placar: dict[str, list[str]] = {caso["id"]: [] for caso in casos}
    erros = 0
    with open(destino, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        escritor.writeheader()
        for caso in casos:
            for rodada in range(1, args.rodadas + 1):
                for tentativa in range(1, TENTATIVAS + 1):
                    linha = executar(caso, rodada, tentativa, args.versao)
                    escritor.writerow(linha)
                    arquivo.flush()
                    extra = linha["detail"] or linha["missing"] and f"faltou {linha['missing']}" or linha["forbidden"]
                    print(f"{caso['id']} rodada {rodada}: {linha['result']} ({linha['seconds']} s) {extra}".rstrip())
                    if linha["result"] != "erro":
                        placar[caso["id"]].append(linha["result"])
                        break
                    erros += 1

    print(f"\nPlacar da {args.versao}, casos de {args.arquivo}:")
    for caso_id, resultados in placar.items():
        print(f"  {caso_id}: {resultados.count('sucesso')} de {len(resultados)} com sucesso  {' '.join(resultados)}")
    julgadas = sum(len(r) for r in placar.values())
    sucessos = sum(r.count("sucesso") for r in placar.values())
    if julgadas:
        print(f"Total: {sucessos} de {julgadas} execuções com sucesso ({100 * sucessos / julgadas:.0f}%). Erros repetidos: {erros}.")
    print(f"Resultados em {destino.relative_to(PASTA_PROJETO)}")


if __name__ == "__main__":
    main()
