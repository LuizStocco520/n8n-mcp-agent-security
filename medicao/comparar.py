r"""Compara duas versões das defesas nos totais, com o teste exato de Fisher, bilateral.

Uso, na pasta do projeto, com o venv ativo:
    python medicao\comparar.py V0 V1
    python medicao\comparar.py V1 V2

Lê as tabelas medicao\resultados\taxas-<versão>.csv que o taxas.py grava e compara as duas versões:
- nas tarefas legítimas, as execuções certas e os alarmes falsos;
- nos ataques, as execuções com ação proibida e os alertas.
As tabelas trazem o intervalo de Wilson de cada taxa. O teste responde a outra pergunta: se a diferença entre as duas
versões é maior do que o acaso explicaria. Dois intervalos podem se tocar e a diferença ainda assim ser real.
"""

import argparse
import csv
import math
import sys
from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA_PROJETO / "medicao" / "garak"))
from resumir import por_cento  # noqa: E402

PASTA_RESULTADOS = PASTA_PROJETO / "medicao" / "resultados"
# O que se compara: (grupo da tabela, coluna contada, como aparece na tela).
COMPARACOES = [
    (("all_legit", "L01-L10"), "sucesso", "tarefas legítimas certas"),
    (("all_legit", "L01-L10"), "alerts", "alarmes falsos nas legítimas"),
    (("all_attacks", "A1-A6"), "proibida", "ataques com ação proibida"),
    (("all_attacks", "A1-A6"), "alerts", "ataques com alerta"),
]


def fisher(a: int, b: int, c: int, d: int) -> float:
    """O p bilateral do teste exato de Fisher na tabela [[a, b], [c, d]].

    Soma a probabilidade de toda tabela com as mesmas margens que é tão ou menos provável que a observada.
    """
    linha1, linha2, coluna1 = a + b, c + d, a + c
    total = math.comb(linha1 + linha2, coluna1)

    def probabilidade(x: int) -> float:
        return math.comb(linha1, x) * math.comb(linha2, coluna1 - x) / total

    observada = probabilidade(a)
    possiveis = range(max(0, coluna1 - linha2), min(coluna1, linha1) + 1)
    # A folga evita que um arredondamento tire da soma uma tabela tão provável quanto a observada.
    return min(1.0, sum(p for p in map(probabilidade, possiveis) if p <= observada * (1 + 1e-7)))


def valor_p(p: float) -> str:
    return "p < 0,001" if p < 0.001 else "p = " + f"{p:.3f}".replace(".", ",")


def ler_totais(versao: str) -> dict[tuple, dict]:
    caminho = PASTA_RESULTADOS / f"taxas-{versao}.csv"
    if not caminho.exists():
        sys.exit(f"Não existe {caminho.relative_to(PASTA_PROJETO)}: rode o taxas.py com --csv para a {versao}.")
    with open(caminho, encoding="utf-8", newline="") as arquivo:
        return {(linha["group"], linha["name"]): linha for linha in csv.DictReader(arquivo)}


def comparar(antes: dict, depois: dict) -> list[dict]:
    """Uma linha por comparação: as contagens de cada versão sobre a base dela e o p do teste."""
    resultado = []
    for grupo, coluna, nome in COMPARACOES:
        a, base_a = int(antes[grupo][coluna]), int(antes[grupo]["base"])
        c, base_c = int(depois[grupo][coluna]), int(depois[grupo]["base"])
        resultado.append({"nome": nome, "antes": (a, base_a), "depois": (c, base_c), "p": fisher(a, base_a - a, c, base_c - c)})
    return resultado


def main() -> None:
    parser = argparse.ArgumentParser(description="Compara duas versões das defesas com o teste exato de Fisher.")
    parser.add_argument("antes", help="a versão de referência, como V1")
    parser.add_argument("depois", help="a versão comparada, como V2")
    args = parser.parse_args()
    print(f"\n{args.antes} -> {args.depois}, nos totais. Teste exato de Fisher, bilateral.")
    for linha in comparar(ler_totais(args.antes), ler_totais(args.depois)):
        (a, base_a), (c, base_c) = linha["antes"], linha["depois"]
        print(f"{linha['nome']:<30} {a:>4} de {base_a:<4} ({por_cento(a / base_a):>6})  ->  "
              f"{c:>4} de {base_c:<4} ({por_cento(c / base_c):>6})   {valor_p(linha['p'])}")


if __name__ == "__main__":
    main()
