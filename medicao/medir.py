r"""Roda os casos no agente do n8n e julga cada execução pelas evidências.

Uso, na pasta do projeto, com o venv ativo e com os servidores da empresa e do fornecedor e o n8n ligados:
    python medicao\medir.py legitimas
    python medicao\medir.py legitimas --rodadas 10 --casos L03,L09
    python medicao\medir.py ataques --ensaio

Para cada execução: reinicia o estado, coloca o chamado do caso (e, nos ataques, o texto plantado num artigo da base, no
cadastro ou na descrição da ferramenta do fornecedor), marca a execução, manda o chamado ao agente,
junta as evidências e pede o veredito ao juiz. Cada execução vira uma linha num CSV em medicao\resultados,
com as colunas em inglês, como tudo o que é publicado. O que cada coluna e cada valor querem dizer está em
medicao\resultados\README.md.
Com --ensaio, o CSV vai para a pasta bruto, fora do Git: o ensaio roda os casos antes da medição, para achar um caso
quebrado sem gastar uma noite, e não é resultado publicado.
Uma execução cortada antes do fim (n8n fora do ar, tempo esgotado, resposta vazia porque o teto de tokens cortou o modelo)
fica no CSV como erro e é repetida: nunca conta como contida nem como incompleta (T12). A exceção é a execução em que a
ação proibida já tinha acontecido antes do corte: o dano está feito, e o resultado é proibida.
Antes de começar e antes de cada execução, confere o Ollama: a versão fixa da medição e o modelo inteiro na GPU.
Se uma das duas coisas não bater, a medição para, em vez de seguir num ambiente diferente.
"""

import argparse
import copy
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA_PROJETO / "servidores" / "empresa"))
sys.path.insert(0, str(PASTA_PROJETO / "servidores" / "fornecedor"))
import fornecedor  # noqa: E402  (precisam vir depois das linhas acima, que mostram onde eles estão)
import servidor  # noqa: E402
from enviar_chamado import enviar, linhas_do_registro, texto_do_chamado  # noqa: E402
from juiz import veredito  # noqa: E402

PASTA_CASOS = PASTA_PROJETO / "medicao" / "casos"
PASTA_RESULTADOS = PASTA_PROJETO / "medicao" / "resultados"
# Os CSVs do ensaio ficam fora do Git, com o resto do que é bruto.
PASTA_ENSAIOS = PASTA_PROJETO / "bruto"
# As respostas do modelo ficam guardadas só para consulta, fora do Git. Não entram no veredito nem no CSV.
RESPOSTAS = PASTA_PROJETO / "bruto" / "respostas.jsonl"
# Quantas vezes tentar uma execução que deu erro antes de desistir dela.
TENTATIVAS = 3
COLUNAS = ["case", "run", "attempt", "run_id", "version", "result", "missing", "forbidden", "denied", "tools", "seconds", "detail"]
# O Ollama da medição. Em 21 e 22/11, a numeração das placas mudou e o Ollama rodou na RX 9060 XT, com parte do modelo
# no processador e um quarto da velocidade, sem nenhum erro; no dia 21, ele também passou da 0.40.16 para a 0.40.17.
# Só a 7900 XTX comporta o modelo inteiro, então "inteiro na GPU" quer dizer a placa certa.
OLLAMA = "http://127.0.0.1:11434"
MODELO = "gpt-oss:20b"
VERSAO_DO_OLLAMA = "0.40.17"


def problemas_do_ollama(versao: str, carregados: list[dict]) -> list[str]:
    """O que impede a medição, pelo que o Ollama informa em /api/version e /api/ps. Lista vazia: pode medir."""
    problemas = []
    if versao != VERSAO_DO_OLLAMA:
        problemas.append(f"o Ollama está na versão {versao}, e a medição usa a {VERSAO_DO_OLLAMA}")
    modelo = next((m for m in carregados if m.get("name") == MODELO), None)
    if modelo is None:
        problemas.append(f"o {MODELO} não está carregado no Ollama")
    elif modelo.get("size_vram", 0) < modelo.get("size", 0):
        problemas.append(f"só {100 * modelo.get('size_vram', 0) // modelo['size']}% do {MODELO} está na GPU")
    return problemas


def conferir_ollama() -> None:
    """Confere o Ollama e carrega o modelo se ele saiu da GPU. Para a medição se algo não bater."""
    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def ler(caminho: str, corpo: dict | None = None) -> dict:
        dados = None if corpo is None else json.dumps(corpo).encode("utf-8")
        pedido = urllib.request.Request(f"{OLLAMA}{caminho}", data=dados, headers={"Content-Type": "application/json"})
        with abridor.open(pedido, timeout=120) as resposta:
            return json.loads(resposta.read().decode("utf-8"))

    try:
        versao = ler("/api/version")["version"]
        carregados = ler("/api/ps")["models"]
        if not any(m.get("name") == MODELO for m in carregados):
            # Um pedido sem prompt só carrega o modelo. Depois de 5 minutos parado, o Ollama o tira da GPU.
            ler("/api/generate", {"model": MODELO, "stream": False})
            carregados = ler("/api/ps")["models"]
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as erro:
        sys.exit(f"Medição parada: o Ollama não respondeu direito em {OLLAMA} ({type(erro).__name__}: {erro}). Ele está aberto?")
    problemas = problemas_do_ollama(versao, carregados)
    if problemas:
        sys.exit("Medição parada: " + "; ".join(problemas) + ". Confira o ollama ps e o log do Ollama antes de medir.")


def destino_do_csv(arquivo: str, versao: str, ensaio: bool, agora: datetime) -> Path:
    """Onde gravar o CSV. Só a medição vai para a pasta resultados, que é publicada; o ensaio vai para a pasta bruto."""
    nome = f"{arquivo}-{versao}-{agora:%Y%m%d-%H%M%S}.csv"
    return PASTA_ENSAIOS / f"ensaio-{nome}" if ensaio else PASTA_RESULTADOS / nome


def preparar(caso: dict) -> dict:
    """Estado inicial: os dados iniciais, o chamado do caso e, nos ataques, o texto plantado.

    O estado é recriado a cada execução, então o texto plantado nunca passa para a execução seguinte.
    Devolve os chamados como estão antes da execução.
    """
    servidor.reiniciar_estado()
    chamados = [c for c in servidor.carregar("chamados.json") if c["id"] != caso["chamado"]["id"]]
    chamados.append(caso["chamado"])
    servidor.gravar("chamados.json", chamados)
    # A1 e A5: alguém editou um artigo da base, que qualquer funcionário pode editar. Os passos verdadeiros ficam,
    # e o texto do atacante entra no fim.
    if "artigo" in caso:
        artigos = servidor.carregar("artigos.json")
        artigo = next(a for a in artigos if a["id"] == caso["artigo"]["id"])
        artigo["texto"] += "\n\n" + caso["artigo"]["acrescimo"]
        servidor.gravar("artigos.json", artigos)
    # A4: as observações do cadastro, que o próprio funcionário escreve no perfil.
    if "cadastro" in caso:
        usuarios = servidor.carregar("usuarios.json")
        usuario = next(u for u in usuarios if u["email"] == caso["cadastro"]["email"])
        usuario["observacoes"] = caso["cadastro"]["observacoes"]
        servidor.gravar("usuarios.json", usuarios)
    # A6: a descrição da ferramenta do fornecedor chega com um acréscimo. Nos outros casos, o acréscimo da execução
    # anterior é apagado e a descrição volta a ser a limpa.
    fornecedor.plantar(caso.get("fornecedor", {}).get("acrescimo"))
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
    # O que cortou a execução antes do fim, se algo cortou.
    corte = ""
    inicio = time.monotonic()
    try:
        saida = enviar(texto_do_chamado(caso["chamado"]))
    except urllib.error.HTTPError as erro:
        corte = f"o n8n respondeu {erro.code}"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as erro:
        corte = f"{type(erro).__name__}: {erro}"[:200]
    else:
        with open(RESPOSTAS, "a", encoding="utf-8") as arquivo:
            arquivo.write(json.dumps({"execucao": execucao, "resposta": saida}, ensure_ascii=False) + "\n")
        # T12: quando o teto de tokens corta o modelo, o n8n responde como se estivesse tudo certo, só que sem texto.
        texto = saida.get("output") if isinstance(saida, dict) else None
        if not str(texto or "").strip():
            corte = "resposta vazia: o modelo parou antes de terminar"
    finally:
        servidor.EXECUCAO_ATUAL.unlink(missing_ok=True)
    segundos = round(time.monotonic() - inicio)
    # As evidências valem mesmo numa execução cortada: o que o agente fez antes do corte aconteceu.
    linhas, emails, depois, cpfs = evidencias(execucao)
    resultado = veredito(caso, linhas, emails, antes, depois, cpfs)
    ferramentas = " ".join(f"{l['ferramenta']}:{l['decisao']}" for l in linhas)
    negadas = "|".join(resultado["negadas"])
    # T12: uma execução cortada não conta como contida nem como incompleta; vira erro e se repete.
    # Mas, se a ação proibida aconteceu antes do corte, o dano está feito, e o resultado é proibida.
    if corte and resultado["resultado"] != "proibida":
        return linha | {"result": "erro", "denied": negadas, "tools": ferramentas, "seconds": segundos, "detail": corte}
    return linha | {
        "result": resultado["resultado"],
        "missing": "|".join(resultado["faltou"]),
        "forbidden": "|".join(resultado["proibidas"]),
        "denied": negadas,
        "tools": ferramentas,
        "seconds": segundos,
        "detail": corte,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Roda os casos no agente e julga cada execução.")
    parser.add_argument("arquivo", help="o arquivo de casos, sem o .json. Por exemplo: legitimas")
    parser.add_argument("--rodadas", type=int, default=1, help="quantas vezes rodar cada caso (padrão: 1)")
    parser.add_argument("--versao", default="V0", help="a versão das defesas que está ligada (padrão: V0)")
    parser.add_argument("--casos", default="", help="só estes casos, separados por vírgula. Por exemplo: L03,L09")
    parser.add_argument("--ensaio", action="store_true", help="ensaio antes da medição: o CSV vai para a pasta bruto, fora do Git")
    args = parser.parse_args()

    casos = json.loads((PASTA_CASOS / f"{args.arquivo}.json").read_text(encoding="utf-8"))
    if args.casos:
        escolhidos = {c.strip().upper() for c in args.casos.split(",")}
        casos = [c for c in casos if c["id"] in escolhidos]
    # O Ollama primeiro: se ele não estiver certo, nem o CSV é criado.
    conferir_ollama()
    print(f"Ollama {VERSAO_DO_OLLAMA}, com o {MODELO} inteiro na GPU.\n")
    destino = destino_do_csv(args.arquivo, args.versao, args.ensaio, datetime.now())
    destino.parent.mkdir(exist_ok=True)
    RESPOSTAS.parent.mkdir(exist_ok=True)

    placar: dict[str, list[str]] = {caso["id"]: [] for caso in casos}
    erros = 0
    with open(destino, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        escritor.writeheader()
        for caso in casos:
            for rodada in range(1, args.rodadas + 1):
                for tentativa in range(1, TENTATIVAS + 1):
                    # De novo antes de cada execução: se o ambiente mudar no meio da noite, a medição para ali.
                    conferir_ollama()
                    linha = executar(caso, rodada, tentativa, args.versao)
                    escritor.writerow(linha)
                    arquivo.flush()
                    # O que explica o resultado, nesta ordem: o que cortou a execução, o que foi proibido e o que faltou.
                    extra = "; ".join(filter(None, [linha["detail"], linha["forbidden"], linha["missing"] and f"faltou {linha['missing']}"]))
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
