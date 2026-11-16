# Lance la démo du chat en une commande : vérifie les fichiers et le port, démarre le serveur
# local (127.0.0.1) puis ouvre le navigateur. Usage :
#   powershell -ExecutionPolicy Bypass -File scripts/run_demo.ps1 [-Checkpoint <pt>] [-Tokenizer <json>] [-Port 8765]
param([string]$Checkpoint, [string]$Tokenizer, [int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$repo = Resolve-Path "$PSScriptRoot\.."
# Dossier principal du dépôt (même depuis un worktree) : data/ et runs/ y sont, hors git.
$main = Split-Path (git -C $repo rev-parse --path-format=absolute --git-common-dir)
# Par défaut : le chat v3 (pré-entraîné + Molière + SFT) et le tokenizer 8 192.
if (-not $Checkpoint) { $Checkpoint = Join-Path $main 'runs\chat-v3\chat.pt' }
if (-not $Tokenizer) { $Tokenizer = Join-Path $main 'data\processed\ablation-extra\tokenizer.json' }

# Fichiers présents ?
foreach ($file in @($Checkpoint, $Tokenizer)) {
    if (-not (Test-Path $file)) { Write-Error "Fichier introuvable : $file" }
}
# Port libre ?
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    Write-Error "Le port $Port est déjà utilisé : arrêtez l'autre serveur ou passez -Port <autre>."
}

# Serveur en arrière-plan, dans la même fenêtre (Ctrl+C pour l'arrêter).
$server = Start-Process -NoNewWindow -PassThru -WorkingDirectory $repo -FilePath 'uv' -ArgumentList @(
    'run', 'python', '-m', 'minigpt.web_chat', '--checkpoint', (Resolve-Path $Checkpoint), '--tokenizer', (Resolve-Path $Tokenizer), '--port', $Port)

# Attend que la page réponde (chargement du modèle : quelques secondes), puis ouvre le navigateur.
# 127.0.0.1 et pas localhost : sous Windows, localhost tente d'abord IPv6 (::1), où le serveur n'écoute pas.
$url = "http://127.0.0.1:$Port"
for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-WebRequest "$url/api/info" -UseBasicParsing -TimeoutSec 2 | Out-Null; break }
    catch {
        if ($server.HasExited) { Write-Error "Le serveur s'est arrêté (voir le message ci-dessus)." }
        Start-Sleep -Seconds 1
    }
}
Start-Process $url
Write-Host "Démo ouverte sur $url — Ctrl+C pour arrêter."
Wait-Process -Id $server.Id
