param([switch]$PlanOnly)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $root
try {
    # Le suffixe protège les poids et les journaux des essais interrompus.
    $out = 'runs/night-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
    $tokenizer = '../../data/processed/bpe_moliere_1024.json'
    $corpus = '../../kit/Piscine/corpus'
    $cosine = '../moliere-continuation-20261111/cosine/best.pt'
    $chat = 'runs/chat-main-v2-r30/step-1000.pt'
    $data = 'runs/chat-data-repair/train.json'
    $extra = 'runs/moliere-extra/train_extra.txt'
    foreach ($inputPath in $tokenizer,$cosine,$chat,$data,$extra,"$corpus/moliere_train.txt","$corpus/moliere_val.txt") {
        if (-not (Test-Path -LiteralPath $inputPath -PathType Leaf)) { throw "Fichier manquant : $inputPath" }
    }
    # Séquentiel pour éviter de saturer la machine et conserver un journal par essai.
    $jobs = @(
        @{ Name='chat'; Module='minigpt.chat_sft'; Args=@('--checkpoint',$chat,'--data',$data,'--steps','1600','--every','250','--lr','0.00009','--replay','0.45','--repair-bench') },
        @{ Name='kit'; Module='minigpt.continue_moliere'; Args=@('--checkpoint',$cosine,'--steps','6000','--every','400','--lr','0.00025') },
        @{ Name='dropout'; Module='minigpt.continue_moliere'; Args=@('--checkpoint',$cosine,'--steps','3500','--every','400','--lr','0.00015','--dropout','0.1') },
        @{ Name='wikisource'; Module='minigpt.continue_moliere'; Args=@('--checkpoint',$cosine,'--steps','4000','--every','400','--lr','0.00015','--extra',$extra) }
    )
    if (-not $PlanOnly) { New-Item -ItemType Directory -Path $out | Out-Null }
    foreach ($job in $jobs) {
        $runArgs = @('-m',$job.Module,'--tokenizer',$tokenizer,'--corpus',$corpus,'--out',"$out/$($job.Name)") + $job.Args
        Write-Host "uv run --frozen python -u $($runArgs -join ' ')"
        if ($PlanOnly) { continue }
        & uv run --frozen python -u @runArgs 2>&1 | Tee-Object -FilePath "$out/$($job.Name).log"
        if ($LASTEXITCODE -ne 0) { throw "Échec de l'essai $($job.Name), code $LASTEXITCODE." }
    }
} finally {
    Pop-Location
}
