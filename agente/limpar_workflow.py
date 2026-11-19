r"""Limpa um workflow exportado do n8n antes de ele ir para o Git.

Uso, na pasta do projeto, com o venv ativo:
    python agente\limpar_workflow.py bruto\agente-v0.json agente\agente-v0.json

Fica só o que alguém precisa para importar e reproduzir o agente: o nome, os nós, as ligações e as configurações.
Sai o que identifica a sua instalação do n8n: o ID da instância, o ID e a versão do workflow, as etiquetas,
os dados fixados, o ID das credenciais (fica só o nome delas) e o ID do webhook do gatilho de chat.
"""

import copy
import json
import sys
from pathlib import Path

# Uma lista do que fica, e não do que sai: um campo novo numa versão futura do n8n não vaza por descuido.
CAMPOS_QUE_FICAM = ["name", "nodes", "connections", "settings", "nodeGroups"]
# Se algum destes textos sobrar no arquivo limpo, a limpeza falhou e nada é gravado.
PROIBIDOS = ["instanceId", "webhookId", "versionId"]


def limpar(exportado: dict) -> dict:
    """Devolve uma cópia limpa do workflow; o original não muda."""
    exportado = copy.deepcopy(exportado)
    limpo = {campo: exportado[campo] for campo in CAMPOS_QUE_FICAM if campo in exportado}
    # O workflow de erro é apontado pelo ID, que só existe na sua instalação.
    limpo["settings"] = {chave: valor for chave, valor in limpo.get("settings", {}).items() if chave != "errorWorkflow"}
    for no in limpo["nodes"]:
        no.pop("webhookId", None)
        if "credentials" in no:
            no["credentials"] = {tipo: {"name": credencial["name"]} for tipo, credencial in no["credentials"].items()}
    limpo["pinData"] = {}
    limpo["active"] = False
    return limpo


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("Uso: python agente\\limpar_workflow.py <arquivo exportado> <arquivo limpo>")
    origem, destino = Path(sys.argv[1]), Path(sys.argv[2])
    limpo = limpar(json.loads(origem.read_text(encoding="utf-8")))
    texto = json.dumps(limpo, ensure_ascii=False, indent=2)
    sobras = [proibido for proibido in PROIBIDOS if proibido in texto]
    if sobras:
        sys.exit(f"Nada foi gravado: o arquivo limpo ainda tem {', '.join(sobras)}.")
    destino.write_text(texto + "\n", encoding="utf-8")
    print(f"Gravado em {destino}, com {len(limpo['nodes'])} nós:")
    for no in limpo["nodes"]:
        print(f"  - {no['name']} ({no['type']})")


if __name__ == "__main__":
    main()
