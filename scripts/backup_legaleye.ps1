# =====================================================================
#  LegalEye - Sauvegarde HEBDOMADAIRE locale (Windows / PowerShell)
# =====================================================================
#  Sauvegarde la base MySQL (partenaires, utilisateurs, alertes...)
#  dans un fichier .sql.gz horodate.
#
#  Frequence  : hebdomadaire (configuree dans Task Scheduler)
#  Retention  : 26 semaines (environ 6 mois) par defaut
#  Stockage   : C:\Apps\legaleye\backups\
#
#  Usage manuel :
#      powershell -ExecutionPolicy Bypass -File backup_legaleye.ps1
# =====================================================================

# --- Configuration ---
$ProjectDir    = "C:\Apps\legaleye"
$BackupDir     = Join-Path $ProjectDir "backups"
$RetentionDays = 182   # 26 semaines * 7 jours = 6 mois d'historique

# --- Preparation ---
Set-Location $ProjectDir
if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

# --- Charger MYSQL_ROOT_PASSWORD depuis .env ---
$envFile = Join-Path $ProjectDir ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "[ERREUR] Fichier .env introuvable" -ForegroundColor Red
    exit 1
}

$MysqlPassword = $null
Get-Content $envFile | ForEach-Object {
    if ($_ -match "^MYSQL_ROOT_PASSWORD=(.+)$") {
        $MysqlPassword = $Matches[1]
    }
}

if (-not $MysqlPassword) {
    Write-Host "[ERREUR] MYSQL_ROOT_PASSWORD introuvable dans .env" -ForegroundColor Red
    exit 1
}

# --- Verifier que MySQL tourne ---
$dbRunning = docker compose ps db --status running -q
if (-not $dbRunning) {
    Write-Host "[ERREUR] Le conteneur MySQL n'est pas demarre" -ForegroundColor Red
    Write-Host "Lance d'abord : docker compose up -d" -ForegroundColor Yellow
    exit 1
}

# --- Sauvegarde ---
$Date = Get-Date -Format "yyyyMMdd_HHmmss"
$WeekNumber = Get-Date -UFormat "%V"
$Year = Get-Date -Format "yyyy"
$BackupFile = Join-Path $BackupDir "legaleye_${Year}_sem${WeekNumber}_${Date}.sql.gz"

Write-Host "Sauvegarde hebdomadaire -> $BackupFile"

# mysqldump + gzip dans le conteneur
$TempContainerFile = "/tmp/legaleye_dump.sql.gz"

docker compose exec -T db bash -c "mysqldump --single-transaction --routines --triggers --add-drop-database --databases bo_watch -u root -p'$MysqlPassword' 2>/dev/null | gzip > $TempContainerFile && cat $TempContainerFile" `
    | Set-Content -Path $BackupFile -Encoding Byte

# Nettoyage du fichier temporaire dans le conteneur
docker compose exec -T db rm -f $TempContainerFile 2>$null

# --- Verification ---
if (-not (Test-Path $BackupFile) -or (Get-Item $BackupFile).Length -lt 100) {
    Write-Host "[ERREUR] Sauvegarde vide ou echouee" -ForegroundColor Red
    if (Test-Path $BackupFile) { Remove-Item $BackupFile }
    exit 1
}

$Size = [math]::Round((Get-Item $BackupFile).Length / 1MB, 2)
Write-Host "[OK] Sauvegarde : $BackupFile ($Size Mo)" -ForegroundColor Green
Write-Host "[OK] Semaine $WeekNumber de $Year" -ForegroundColor Green

# --- Nettoyage : conserver $RetentionDays jours ---
$Cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem $BackupDir -Filter "legaleye_*.sql.gz" | Where-Object {
    $_.LastWriteTime -lt $Cutoff
} | Remove-Item -Force

# --- Bilan ---
$Nb = (Get-ChildItem $BackupDir -Filter "legaleye_*.sql.gz").Count
$TotalMo = [math]::Round(((Get-ChildItem $BackupDir -Filter "legaleye_*.sql.gz" | Measure-Object Length -Sum).Sum / 1MB), 2)
Write-Host ""
Write-Host "Sauvegardes conservees : $Nb"
Write-Host "Espace total           : $TotalMo Mo"
Write-Host "Retention              : $RetentionDays jours (~26 semaines)"
