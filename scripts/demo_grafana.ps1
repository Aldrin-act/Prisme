# Script de démo Grafana PRISME
# Lance la stack Grafana + génère métriques + ouvre le dashboard

Write-Host "`n🚀 Démarrage Stack Grafana..." -ForegroundColor Cyan

# 1. Lancer Docker Compose
Set-Location monitoring
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n❌ Erreur : Docker Compose a échoué" -ForegroundColor Red
    Write-Host "Vérifiez que Docker Desktop est lancé." -ForegroundColor Yellow
    exit 1
}

Write-Host "`n✅ Stack lancée (Prometheus:9090, Grafana:3000, Node Exporter:9100)" -ForegroundColor Green

# 2. Attendre que Grafana soit prêt
Write-Host "`n⏳ Attente démarrage Grafana (10s)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# 3. Générer métriques
Set-Location ..
Write-Host "`n📊 Génération des métriques..." -ForegroundColor Cyan
python scripts/generer_avec_metriques.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n⚠️  Génération échouée mais dashboard accessible" -ForegroundColor Yellow
}

# 4. Ouvrir Grafana
Write-Host "`n🌐 Ouverture de Grafana..." -ForegroundColor Cyan
Start-Process "http://localhost:3000"

Write-Host "`n" -NoNewline
Write-Host "═" -NoNewline -ForegroundColor Green
Write-Host "═" -NoNewline -ForegroundColor Green
Write-Host "═" -NoNewline -ForegroundColor Green
Write-Host " STACK PRÊTE " -NoNewline -ForegroundColor White
Write-Host "═" -NoNewline -ForegroundColor Green
Write-Host "═" -NoNewline -ForegroundColor Green
Write-Host "═`n" -ForegroundColor Green

Write-Host "Grafana     : " -NoNewline
Write-Host "http://localhost:3000" -ForegroundColor Cyan
Write-Host "Prometheus  : " -NoNewline
Write-Host "http://localhost:9090" -ForegroundColor Cyan
Write-Host "`nIdentifiants Grafana :" -ForegroundColor Yellow
Write-Host "  Username : admin" -ForegroundColor White
Write-Host "  Password : prisme2026" -ForegroundColor White
Write-Host "`nDashboard   : Dashboards > PRISME - Pipeline Multi-Agents`n" -ForegroundColor Magenta

Write-Host "Pour arrêter : " -NoNewline
Write-Host "cd monitoring && docker-compose down`n" -ForegroundColor Gray
