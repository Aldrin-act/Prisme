# Vérifie que Docker Desktop est prêt avant de lancer docker-compose

Write-Host "`n🐳 Vérification Docker Desktop..." -ForegroundColor Cyan

# Test 1 : Docker CLI accessible ?
try {
    $dockerVersion = docker --version 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker CLI non accessible"
    }
    Write-Host "✅ Docker CLI : " -NoNewline -ForegroundColor Green
    Write-Host "$dockerVersion" -ForegroundColor White
} catch {
    Write-Host "❌ Docker Desktop n'est pas installé ou pas dans PATH" -ForegroundColor Red
    Write-Host "`n📥 Installation :" -ForegroundColor Yellow
    Write-Host "   https://www.docker.com/products/docker-desktop/`n" -ForegroundColor Cyan
    exit 1
}

# Test 2 : Docker daemon accessible ?
Write-Host "🔍 Test connexion daemon..." -ForegroundColor Yellow
try {
    $dockerInfo = docker info 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Daemon non accessible"
    }
    Write-Host "✅ Docker daemon actif" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker Desktop n'est PAS lancé" -ForegroundColor Red
    Write-Host "`n🚀 Actions :" -ForegroundColor Yellow
    Write-Host "   1. Ouvrez Docker Desktop depuis le menu Démarrer" -ForegroundColor White
    Write-Host "   2. Attendez le message 'Docker Desktop is running' (icône verte)" -ForegroundColor White
    Write-Host "   3. Relancez ce script`n" -ForegroundColor White
    exit 1
}

# Test 3 : Docker Compose disponible ?
try {
    $composeVersion = docker-compose --version 2>$null
    if ($LASTEXITCODE -ne 0) {
        # Essayer 'docker compose' (v2)
        $composeVersion = docker compose version 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "Docker Compose non disponible"
        }
    }
    Write-Host "✅ Docker Compose : " -NoNewline -ForegroundColor Green
    Write-Host "$composeVersion" -ForegroundColor White
} catch {
    Write-Host "⚠️  Docker Compose non trouvé (inclus dans Docker Desktop normalement)" -ForegroundColor Yellow
}

# Test 4 : Conteneurs existants ?
$containers = docker ps -a --filter "name=prisme-" --format "{{.Names}}" 2>$null
if ($containers) {
    Write-Host "`n📦 Conteneurs PRISME existants :" -ForegroundColor Cyan
    foreach ($container in $containers) {
        $status = docker ps --filter "name=$container" --format "{{.Status}}" 2>$null
        if ($status) {
            Write-Host "   🟢 $container : " -NoNewline -ForegroundColor Green
            Write-Host "RUNNING" -ForegroundColor White
        } else {
            Write-Host "   ⚪ $container : " -NoNewline -ForegroundColor Gray
            Write-Host "STOPPED" -ForegroundColor White
        }
    }
}

Write-Host "`n✅ Docker Desktop est prêt !" -ForegroundColor Green
Write-Host "`n🚀 Prochaine étape :" -ForegroundColor Cyan
Write-Host "   cd monitoring && docker-compose up -d`n" -ForegroundColor White
