# Projeto 3 - salva o print que está na área de transferência na pasta prints.
# Uso: tire o print com Win+Shift+S e, numa janela comum, rode:
#   .\salvar-print.ps1 01-agente-v0
param(
    [Parameter(Mandatory = $true)]
    [string]$Nome
)

Add-Type -AssemblyName System.Drawing

# Só letras sem acento, números, hífen e sublinhado: o nome não consegue apontar para fora da pasta prints.
if ($Nome -notmatch '^[A-Za-z0-9_-]+$') {
    Write-Host "Use só letras sem acento, números, hífen e sublinhado no nome."
    exit 1
}

$pasta = Join-Path $PSScriptRoot "prints"
$arquivo = Join-Path $pasta "$Nome.png"

$imagem = Get-Clipboard -Format Image
if ($null -eq $imagem) {
    Write-Host "Não há imagem na área de transferência. Tire o print com Win+Shift+S e rode de novo."
    exit 1
}
if (Test-Path $arquivo) {
    Write-Host "Já existe $arquivo. Escolha outro nome."
    exit 1
}

New-Item -ItemType Directory -Force -Path $pasta | Out-Null
$imagem.Save($arquivo, [System.Drawing.Imaging.ImageFormat]::Png)
Write-Host "Salvo em $arquivo"
