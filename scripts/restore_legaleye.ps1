# =====================================================================
#  LegalEye - Restauration de la base depuis une sauvegarde
#  Usage :
#      powershell -ExecutionPolicy Bypass -File restore_legaleye.ps1 -File "C:\Apps\legaleye\backups\legaleye_20260301_020000.sql.gz"
# =====================================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$File
)

$ProjectDir = "C:\Apps\legaleye"
Set-Location $ProjectDir

if (-not (Test-Path $File)) {
    Write-Host "[ERREUR] Fichier introuvable : $File" -ForegroundColor Red
    exit 1
}

# Charger le mot de passe
$envFile = Join-Path $ProjectDir ".env"
$MysqlPassword = $null
Get-Content $envFile | ForEach-Object {
    if ($_ -match "^MYSQL_ROOT_PASSWORD=(.+)$") {
        $MysqlPassword = $Matches[1]
    }
}

Write-Host "ATTENTION : la base actuelle va etre ECRASEE par $File" -ForegroundColor Yellow
$Confirm = Read-Host "Tape OUI pour confirmer"
if ($Confirm -ne "OUI") {
    Write-Host "Annule" -ForegroundColor Yellow
    exit 0
}

# Copier le fichier dans le conteneur, decompresser, restaurer
$Bytes = [System.IO.File]::ReadAllBytes($File)
$Base64 = [Convert]::ToBase64String($Bytes)

docker compose exec -T db bash -c "echo '$Base64' | base64 -d | gunzip | mysql -u root -p'$MysqlPassword' legaleye"

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Restauration terminee" -ForegroundColor Green
} else {
    Write-Host "[ERREUR] Restauration echouee" -ForegroundColor Red
    exit 1
}
