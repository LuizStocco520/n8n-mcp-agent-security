# Projeto 3 - inicia o n8n só para este PC
# Rode dentro de C:\projetos\projeto3, numa janela comum (não a de administrador).
# Para desligar o n8n: Ctrl+C nesta janela.

# Escuta só no endereço do próprio PC. O padrão do n8n é "::", todas as interfaces de rede.
$env:N8N_LISTEN_ADDRESS = "127.0.0.1"

# Isolamento recomendado pela documentação do n8n: sem telemetria,
# sem aviso de versão nova e sem busca de modelos de workflow na internet.
$env:N8N_DIAGNOSTICS_ENABLED = "false"
$env:N8N_VERSION_NOTIFICATIONS_ENABLED = "false"
$env:N8N_TEMPLATES_ENABLED = "false"

node -v
# Versão fixa, a mesma do começo ao fim das medições.
npx --yes n8n@2.48.5
