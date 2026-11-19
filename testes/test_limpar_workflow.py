"""O workflow exportado do n8n só vai para o Git sem nada que identifique a instalação."""

import json

from limpar_workflow import PROIBIDOS, limpar

# Uma exportação inventada, com os mesmos campos que o n8n 2.48 grava.
EXPORTADO = {
    "id": "Zz99Yy88Xx77Ww66",
    "name": "Projeto 3 - Agente V0",
    "versionId": "0b5f3c3e-8a51-4e46-9d5f-2f6d1e0e4a77",
    "active": False,
    "meta": {"templateCredsSetupCompleted": True, "instanceId": "4f1c2d0e9b8a7f6e5d4c3b2a19087f6e"},
    "tags": [{"id": "Tg1", "name": "projeto3"}],
    "pinData": {"When chat message received": [{"json": {"chatInput": "teste"}}]},
    "settings": {"executionOrder": "v1", "errorWorkflow": "XyZ123"},
    "connections": {"When chat message received": {"main": [[{"node": "AI Agent", "type": "main", "index": 0}]]}},
    "nodes": [
        {
            "id": "n1",
            "name": "When chat message received",
            "type": "@n8n/n8n-nodes-langchain.chatTrigger",
            "typeVersion": 1.5,
            "position": [0, 0],
            "parameters": {"options": {}},
            "webhookId": "5b0f2d64-2c0e-4f3e-9a55-2d0b1f6f6c11",
        },
        {
            "id": "n2",
            "name": "Ollama Chat Model",
            "type": "@n8n/n8n-nodes-langchain.lmChatOllama",
            "typeVersion": 1,
            "position": [0, 200],
            "parameters": {"model": "gpt-oss:20b", "options": {}},
            "credentials": {"ollamaApi": {"id": "Ab12Cd34Ef56Gh78", "name": "Ollama account"}},
        },
    ],
}


def test_sai_o_que_identifica_a_instalacao():
    texto = json.dumps(limpar(EXPORTADO))
    for proibido in PROIBIDOS + ["Zz99Yy88Xx77Ww66", "Ab12Cd34Ef56Gh78", "XyZ123", "chatInput"]:
        assert proibido not in texto


def test_fica_o_que_reproduz_o_agente():
    limpo = limpar(EXPORTADO)
    assert limpo["name"] == "Projeto 3 - Agente V0"
    assert [no["name"] for no in limpo["nodes"]] == ["When chat message received", "Ollama Chat Model"]
    assert limpo["nodes"][1]["parameters"]["model"] == "gpt-oss:20b"
    assert limpo["nodes"][1]["credentials"] == {"ollamaApi": {"name": "Ollama account"}}
    assert limpo["connections"] == EXPORTADO["connections"]
    assert limpo["settings"] == {"executionOrder": "v1"}


def test_o_original_nao_muda():
    antes = json.dumps(EXPORTADO, sort_keys=True)
    limpar(EXPORTADO)
    assert json.dumps(EXPORTADO, sort_keys=True) == antes
