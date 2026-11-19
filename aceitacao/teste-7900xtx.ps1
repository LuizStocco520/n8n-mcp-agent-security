<#
  Projeto 3 - teste de aceitação da RX 7900 XTX

  Gera texto sem parar no Ollama por um tempo fixo e registra cada execução num CSV.
  No fim, procura no Visualizador de Eventos falhas do driver de vídeo (evento 4101)
  e registros de hardware (WHEA-Logger) no período do teste, e mostra o ollama ps.

  Uso, dentro desta pasta:
      .\teste-7900xtx.ps1               # 90 minutos
      .\teste-7900xtx.ps1 -Minutos 60

  Só dados inventados. Nada sai do PC: a API é a do Ollama em 127.0.0.1.
  Pode parar a qualquer hora com Ctrl+C: o resumo sai mesmo assim.
#>
param(
    [int]$Minutos = 90,
    [string]$Modelo = 'gpt-oss:20b'
)

$inv     = [Globalization.CultureInfo]::InvariantCulture
$api     = 'http://127.0.0.1:11434/api/generate'
$pasta   = Join-Path $PSScriptRoot 'resultados'
New-Item -ItemType Directory -Force -Path $pasta | Out-Null
$carimbo = Get-Date -Format 'yyyyMMdd-HHmmss'
$csv     = Join-Path $pasta "aceitacao-$carimbo.csv"
$resumo  = Join-Path $pasta "aceitacao-$carimbo-resumo.txt"

function Escrever([string]$texto) {
    Write-Host $texto
    Add-Content -Path $resumo -Value $texto -Encoding UTF8
}

# Chamados inventados. O número da execução vai no começo e em cada linha,
# para o Ollama processar o prompt inteiro de novo a cada vez, como o agente fará.
function Montar-Prompt([int]$n) {
    $linhas = for ($k = 1; $k -le 60; $k++) {
        "Chamado $n-${k}: usuário do setor $($k % 7) relata lentidão ao abrir relatórios no sistema interno."
    }
    "Execução $n.`n" + ($linhas -join "`n") + "`n`nResuma os chamados acima em cinco tópicos curtos."
}

# 1. Ambiente, para o registro
$inicio = Get-Date
$fim    = $inicio.AddMinutes($Minutos)
Escrever ("Teste de aceitação da 7900 XTX: início {0}, {1} minutos" -f $inicio.ToString('yyyy-MM-dd HH:mm:ss'), $Minutos)
Escrever ("Ollama: " + (& ollama --version | Out-String).Trim())
Get-CimInstance Win32_VideoController | ForEach-Object {
    Escrever ("Placa: {0} | driver {1} | {2}" -f $_.Name, $_.DriverVersion, $_.Status)
}
Get-ChildItem Env:OLLAMA*, Env:HIP_VISIBLE_DEVICES -ErrorAction SilentlyContinue | ForEach-Object { Escrever ("{0}={1}" -f $_.Name, $_.Value) }
Escrever "Use o PC normalmente na 9060 XT e anote o horário de qualquer travada."

$n     = 0
$erros = 0
$taxas = New-Object System.Collections.Generic.List[double]
try {
    # 2. Geração contínua
    while ((Get-Date) -lt $fim) {
        $n++
        $corpo = @{
            model      = $Modelo
            prompt     = (Montar-Prompt $n)
            stream     = $false
            keep_alive = '30m'
            options    = @{ num_predict = 512 }
        } | ConvertTo-Json -Depth 4
        $linha = [ordered]@{
            horario        = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
            execucao       = $n
            ok             = 'nao'
            tokens_prompt  = ''
            tokens_gerados = ''
            tok_s_geracao  = ''
            tok_s_prompt   = ''
            duracao_s      = ''
            erro           = ''
        }
        try {
            $r = Invoke-RestMethod -Uri $api -Method Post -ContentType 'application/json' -Body ([Text.Encoding]::UTF8.GetBytes($corpo)) -TimeoutSec 300 -ErrorAction Stop
            $tg = 0.0
            if ($r.eval_duration -gt 0) { $tg = $r.eval_count / ($r.eval_duration / 1e9) }
            $tp = 0.0
            if ($r.prompt_eval_duration -gt 0) { $tp = $r.prompt_eval_count / ($r.prompt_eval_duration / 1e9) }
            $linha.ok             = 'sim'
            $linha.tokens_prompt  = $r.prompt_eval_count
            $linha.tokens_gerados = $r.eval_count
            $linha.tok_s_geracao  = $tg.ToString('0.00', $inv)
            $linha.tok_s_prompt   = $tp.ToString('0.00', $inv)
            $linha.duracao_s      = ($r.total_duration / 1e9).ToString('0.00', $inv)
            $taxas.Add($tg)
        } catch {
            $erros++
            $linha.erro = ($_.Exception.Message -replace '\s+', ' ')
        }
        [pscustomobject]$linha | Export-Csv -Path $csv -Append -NoTypeInformation -Encoding UTF8
        if ($n % 20 -eq 0) {
            $faltam = [math]::Max(0, [int]($fim - (Get-Date)).TotalMinutes)
            Write-Host ("{0} execuções, {1} erros, última {2} tok/s, faltam uns {3} min" -f $n, $erros, $linha.tok_s_geracao, $faltam)
        }
    }
} finally {
    # 3. Conferência (roda também se você parar com Ctrl+C)
    Escrever ("Fim {0}: {1} execuções, {2} erros" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $n, $erros)
    if ($taxas.Count -gt 0) {
        $ord     = @($taxas | Sort-Object)
        $mediana = $ord[[int][math]::Floor(($ord.Count - 1) / 2)]
        Escrever ("Geração (tok/s): mínima {0}, mediana {1}, máxima {2}" -f $ord[0].ToString('0.0', $inv), $mediana.ToString('0.0', $inv), $ord[-1].ToString('0.0', $inv))
        if ($ord[0] -lt 0.8 * $mediana) {
            Escrever "Atenção: a taxa mínima ficou abaixo de 80% da mediana. Veja no CSV quando caiu."
        }
    }
    $tdr  = @(Get-WinEvent -FilterHashtable @{ LogName = 'System'; ProviderName = 'Display'; Id = 4101; StartTime = $inicio } -ErrorAction SilentlyContinue)
    $whea = @(Get-WinEvent -FilterHashtable @{ LogName = 'System'; ProviderName = 'Microsoft-Windows-WHEA-Logger'; StartTime = $inicio } -ErrorAction SilentlyContinue)
    Escrever ("Evento 4101 (o driver de vídeo parou de responder): {0}" -f $tdr.Count)
    $tdr | ForEach-Object { Escrever ("  {0}" -f $_.TimeCreated) }
    Escrever ("Registros de hardware (WHEA-Logger): {0}" -f $whea.Count)
    $whea | ForEach-Object { Escrever ("  {0}  id {1}" -f $_.TimeCreated, $_.Id) }
    Escrever ("ollama ps no fim:`n" + (& ollama ps | Out-String).Trim())
    if (($erros -eq 0) -and ($tdr.Count -eq 0)) { $veredito = 'PASSOU' } else { $veredito = 'REPROVOU' }
    Escrever ("Critérios automáticos: {0} (zero erros e zero evento 4101). Falta o seu: travadas no uso normal." -f $veredito)
    if ($whea.Count -gt 0) { Escrever "Há registros WHEA: me mande os IDs para vermos se envolvem a placa." }
    Escrever ("Arquivos: {0} e {1}" -f $csv, $resumo)
}
