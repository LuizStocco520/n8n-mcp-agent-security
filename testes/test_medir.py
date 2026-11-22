"""O formato do CSV da medição e a trava do Ollama: o que o medir.py grava e quando ele se recusa a medir."""

import csv

import medir

# Como o ollama ps mostrou em 22/11, com a 7900 XTX: 12 GB, 100% GPU.
INTEIRO = {"name": medir.MODELO, "size": 12_000_000_000, "size_vram": 12_000_000_000}


def test_colunas_publicadas():
    # Mudar o nome de uma coluna quebra quem já lê os CSVs, então a mudança tem que ser de propósito.
    assert medir.COLUNAS == ["case", "run", "attempt", "run_id", "version", "result",
                             "missing", "forbidden", "denied", "tools", "seconds", "detail"]
    gravados = [p for p in sorted(medir.PASTA_RESULTADOS.glob("*.csv")) if not p.name.startswith("garak-")]
    assert gravados, "nenhum CSV da medição em medicao/resultados"
    for caminho in gravados:
        with open(caminho, encoding="utf-8", newline="") as arquivo:
            assert next(csv.reader(arquivo)) == medir.COLUNAS, caminho.name


def test_ollama_certo_libera_a_medicao():
    assert medir.problemas_do_ollama(medir.VERSAO_DO_OLLAMA, [INTEIRO]) == []


def test_modelo_em_parte_no_processador_para_a_medicao():
    # Como em 22/11, com o Ollama preso na RX 9060 XT: 7,6 GB, 16%/84% CPU/GPU.
    dividido = {"name": medir.MODELO, "size": 7_600_000_000, "size_vram": 6_384_000_000}
    assert medir.problemas_do_ollama(medir.VERSAO_DO_OLLAMA, [dividido]) == [f"só 84% do {medir.MODELO} está na GPU"]


def test_outra_versao_do_ollama_para_a_medicao():
    # Como em 21/11, quando o Ollama passou da 0.40.16 para a 0.40.17.
    esperado = f"o Ollama está na versão 0.40.16, e a medição usa a {medir.VERSAO_DO_OLLAMA}"
    assert medir.problemas_do_ollama("0.40.16", [INTEIRO]) == [esperado]


def test_modelo_fora_da_memoria_para_a_medicao():
    # Só o nome não basta: outro modelo carregado não conta.
    outro = {"name": "gpt-oss-garak:latest", "size": 1, "size_vram": 1}
    assert medir.problemas_do_ollama(medir.VERSAO_DO_OLLAMA, [outro]) == [f"o {medir.MODELO} não está carregado no Ollama"]
