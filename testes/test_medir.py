"""As colunas do CSV da medição são o formato publicado: o medir.py e os CSVs já gravados têm que concordar."""

import csv

import medir


def test_colunas_publicadas():
    # Mudar o nome de uma coluna quebra quem já lê os CSVs, então a mudança tem que ser de propósito.
    assert medir.COLUNAS == ["case", "run", "attempt", "run_id", "version", "result",
                             "missing", "forbidden", "denied", "tools", "seconds", "detail"]
    gravados = [p for p in sorted(medir.PASTA_RESULTADOS.glob("*.csv")) if not p.name.startswith("garak-")]
    assert gravados, "nenhum CSV da medição em medicao/resultados"
    for caminho in gravados:
        with open(caminho, encoding="utf-8", newline="") as arquivo:
            assert next(csv.reader(arquivo)) == medir.COLUNAS, caminho.name
