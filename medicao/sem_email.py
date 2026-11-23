r"""Por que o funcionário ficou sem o e-mail, nas execuções medidas de uma versão.

Uso, na pasta do projeto, com o venv ativo, dando os CSVs pelo nome completo:
    python medicao\sem_email.py medicao\resultados\legitimas-V2-20261123-144025.csv medicao\resultados\ataques-V2-20261123-150349.csv

Pega, nos CSVs, as execuções julgadas em que faltou o e-mail ao solicitante e lê a resposta final do agente em cada
uma, em bruto\respostas.jsonl, onde o medir.py a guarda. Cada execução cai num motivo:
- email_para_outro: o servidor enviou e-mail, mas para outra pessoa, e o funcionário ficou sem;
- chamadas_como_texto: a resposta final traz chamadas de ferramenta escritas em JSON, em vez de feitas;
- email_na_resposta: nenhum e-mail saiu, e a resposta final traz o e-mail que devia ter ido pela ferramenta;
- outro: nada disso, como um resumo que só diz que o e-mail foi enviado;
- sem_resposta: a resposta final não foi guardada.
A separação é por padrões no texto, então as de outro e sem_resposta se leem uma a uma.
Marca também as execuções com uma recusa de regra de segurança: depois dela, o modelo pode não ter tentado de novo.
Mostra só contagens e execuções, nenhum texto do modelo.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from medir import RESPOSTAS
from taxas import alerta, ler

MOTIVOS = ["email_na_resposta", "chamadas_como_texto", "email_para_outro", "outro", "sem_resposta"]
# Uma chamada de ferramenta escrita como texto: o JSON com o nome dela ou com os argumentos do chamado e do e-mail.
CHAMADA_COMO_TEXTO = re.compile(r'"name"\s*:\s*"(?:empresa|fornecedor)_|"(?:chamado_id|destinatario|termo)"\s*:')
# Um e-mail escrito na resposta: a linha de assunto ou a saudação, em português ou em inglês.
EMAIL_ESCRITO = re.compile(r"^\W*(?:assunto|subject)\W*:|\b(?:olá|ola|oi|prezad[oa]|dear|hello)\b", re.IGNORECASE | re.MULTILINE)


def respostas(caminho: Path) -> dict[str, str]:
    """O texto da resposta final de cada execução, pelo run_id."""
    textos = {}
    with open(caminho, encoding="utf-8") as arquivo:
        for linha in arquivo:
            registro = json.loads(linha)
            resposta = registro["resposta"]
            textos[registro["execucao"]] = str(resposta.get("output") or "") if isinstance(resposta, dict) else str(resposta or "")
    return textos


def motivo(linha: dict, texto: str | None) -> str:
    """Por que faltou o e-mail ao solicitante nesta execução."""
    # Se o servidor enviou e-mail e o funcionário ficou sem, o e-mail foi para outra pessoa.
    if "enviar_email:executada" in linha["tools"].split():
        return "email_para_outro"
    if texto is None:
        return "sem_resposta"
    # Antes do e-mail escrito: uma chamada como texto traz o corpo do e-mail dentro, com a saudação.
    if CHAMADA_COMO_TEXTO.search(texto):
        return "chamadas_como_texto"
    if EMAIL_ESCRITO.search(texto):
        return "email_na_resposta"
    return "outro"


def sem_email(linhas: list[dict]) -> list[dict]:
    """As execuções julgadas em que faltou o e-mail ao solicitante. As de erro foram repetidas e não contam."""
    return [linha for linha in linhas if linha["result"] != "erro" and "email_ao_solicitante" in linha["missing"].split("|")]


def main() -> None:
    parser = argparse.ArgumentParser(description="Separa por motivo as execuções em que o funcionário ficou sem o e-mail.")
    parser.add_argument("csvs", type=Path, nargs="+", help="os CSVs da medição, pelo nome completo")
    args = parser.parse_args()

    linhas = ler(args.csvs)
    textos = respostas(RESPOSTAS)
    for versao in sorted({linha["version"] for linha in linhas}):
        julgadas = [linha for linha in linhas if linha["version"] == versao and linha["result"] != "erro"]
        legitimas = sum(linha["case"].startswith("L") for linha in julgadas)
        faltou = sem_email(julgadas)
        contagem = Counter()
        execucoes = {nome: [] for nome in MOTIVOS}
        for linha in faltou:
            nome = motivo(linha, textos.get(linha["run_id"]))
            parte = "legitimas" if linha["case"].startswith("L") else "ataques"
            contagem[(nome, parte)] += 1
            contagem[(nome, "recusa")] += alerta(linha)
            execucoes[nome].append(f"{linha['case']} r{linha['run']}" + (" (recusa)" if alerta(linha) else ""))
        sem_legitimas = sum(linha["case"].startswith("L") for linha in faltou)
        print(f"\n{versao}: {len(faltou)} de {len(julgadas)} execuções julgadas sem o e-mail ao funcionário "
              f"({sem_legitimas} de {legitimas} tarefas legítimas, {len(faltou) - sem_legitimas} de {len(julgadas) - legitimas} ataques)")
        print(f"  {'motivo':<20} {'legítimas':>9} {'ataques':>8} {'total':>6}  com recusa de segurança")
        for nome in MOTIVOS:
            leg, ata = contagem[(nome, "legitimas")], contagem[(nome, "ataques")]
            print(f"  {nome:<20} {leg:>9} {ata:>8} {leg + ata:>6}  {contagem[(nome, 'recusa')]}")
        for nome in MOTIVOS:
            if execucoes[nome]:
                print(f"  {nome}: {', '.join(execucoes[nome])}")


if __name__ == "__main__":
    main()
