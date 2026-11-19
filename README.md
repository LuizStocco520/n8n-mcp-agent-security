# Securing a tool-using AI agent

**Work in progress.** A local IT-support agent (n8n + gpt-oss:20b on Ollama) uses tools served over MCP: four from the company and one from a third-party vendor. It is attacked on purpose with 24 prompt-injection and tool-poisoning cases, and each defense version (V0 to V4) is measured on the same cases, together with 10 legitimate tasks that measure the cost of each defense.

Everything runs on one PC, bound to 127.0.0.1, with invented data. No real credentials, no real e-mail.

## Layout

| Folder | Contents |
|---|---|
| `aceitacao/` | GPU acceptance test: script and results (RX 7900 XTX, 1,738 generations in 90 minutes, zero errors) |
| `agente/` | n8n workflows, exported and cleaned (V0 to V4) |
| `ataques/` | the 24 attack cases and the 10 legitimate tasks |
| `docs/` | threat model and design decisions |
| `medicao/` | measurement script and results per version |
| `prints/` | screenshots |
| `servidores/` | MCP servers: company and third-party vendor |
| `testes/` | pytest tests for the V2 rules |

Folders are created as the project reaches them.

## How this was built

To be written at the end of the project, including how AI tools were used.
