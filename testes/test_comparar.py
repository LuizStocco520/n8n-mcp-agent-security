"""O comparar.py dá o p que o README publica entre duas versões, então o teste de Fisher tem os seus testes."""

import math

import pytest

import comparar


def test_fisher_da_o_p_publicado_entre_a_v0_e_a_v1():
    # Tarefas legítimas certas: 98 de 100 na V0 e 89 de 100 na V1. O README publica p = 0,018.
    assert round(comparar.fisher(98, 2, 89, 11), 4) == 0.0184
    # E-mail ao funcionário que faltou: 5 de 340 na V0 e 32 de 340 na V1.
    assert comparar.fisher(5, 335, 32, 308) == pytest.approx(4.277e-6, rel=1e-3)


def test_fisher_nos_casos_que_se_conferem_a_mao():
    # A tabela mais extrema de 10 contra 10: só ela e o espelho dela, cada uma com 1 / C(20, 10).
    assert comparar.fisher(10, 0, 0, 10) == pytest.approx(2 / math.comb(20, 10))
    # Nenhuma diferença: nada para explicar.
    assert comparar.fisher(1, 1, 1, 1) == 1.0
    # Trocar as versões de lugar não muda o p.
    assert comparar.fisher(15, 225, 0, 240) == comparar.fisher(0, 240, 15, 225)


def test_comparar_le_as_tabelas_publicadas(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["comparar.py", "V0", "V1"])
    comparar.main()
    saida = capsys.readouterr().out
    assert "tarefas legítimas certas" in saida and "p = 0,018" in saida
    assert "133 de 240" in saida and "15 de 240" in saida and "p < 0,001" in saida


def test_versao_sem_tabela_para_com_aviso(monkeypatch):
    monkeypatch.setattr("sys.argv", ["comparar.py", "V0", "V9"])
    with pytest.raises(SystemExit):
        comparar.main()
