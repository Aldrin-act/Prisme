# Monitoring PRISME avec Grafana

Stack de monitoring complète pour visualiser les métriques du pipeline multi-agents en temps réel.

## 🎯 Stack

- **Prometheus** : Collecte des métriques (port 9090)
- **Grafana** : Visualisation (port 3000)
- **Node Exporter** : Métriques système (port 9100)

## 🚀 Démarrage Rapide

### 1. Lancer la stack

```powershell
cd monitoring
docker-compose up -d
```

**Vérification** :
```powershell
docker-compose ps
```

Vous devriez voir 3 conteneurs :
- `prisme-prometheus` (9090)
- `prisme-grafana` (3000)
- `prisme-node-exporter` (9100)

### 2. Accéder à Grafana

Ouvrez votre navigateur : http://localhost:3000

**Identifiants par défaut** :
- Username : `admin`
- Password : `prisme2026`

### 3. Générer des métriques

```powershell
cd ..
python scripts/generer_avec_metriques.py
```

Le script va :
- Exécuter le pipeline multi-agents
- Collecter les métriques (durée, coût, tokens)
- Exporter vers `metriques/grafana_metrics.prom`
- Prometheus récupère automatiquement les métriques

### 4. Voir le Dashboard

Dans Grafana :
1. Aller dans **Dashboards**
2. Ouvrir **PRISME - Pipeline Multi-Agents**

Vous verrez :
- Durée totale du pipeline
- Coût total ($)
- Tokens consommés
- Statut (succès/échec)
- Durée par agent (graphique en barres)
- Coût par agent (camembert)
- Tokens par agent
- Taux de réussite
- Timeline historique

---

## 📊 Métriques Disponibles

### Métriques Globales

| Métrique | Description | Type | Unité |
|----------|-------------|------|-------|
| `prisme_pipeline_duration_seconds` | Durée totale pipeline | Gauge | secondes |
| `prisme_pipeline_cost_usd` | Coût total | Gauge | USD |
| `prisme_pipeline_tokens_total` | Tokens total | Gauge | count |
| `prisme_pipeline_success` | Succès (1) ou échec (0) | Gauge | bool |
| `prisme_agents_executed` | Nombre d'agents exécutés | Gauge | count |
| `prisme_agents_success` | Nombre d'agents réussis | Gauge | count |
| `prisme_agents_failed` | Nombre d'agents échoués | Gauge | count |

### Métriques par Agent

| Métrique | Labels | Description |
|----------|--------|-------------|
| `prisme_agent_duration_seconds{agent="..."}` | agent | Durée d'exécution |
| `prisme_agent_cost_usd{agent="..."}` | agent | Coût estimé |
| `prisme_agent_tokens{agent="..."}` | agent | Tokens utilisés |

**Agents trackés** :
- Analyste
- Architecte
- Développeur
- Testeur
- Reviewer
- Debugger (conditionnel)
- Validation
- Optimiseur (conditionnel)

---

## 🔍 Requêtes PromQL Utiles

### Durée moyenne par agent
```promql
avg(prisme_agent_duration_seconds) by (agent)
```

### Agent le plus coûteux
```promql
topk(1, prisme_agent_cost_usd)
```

### Coût total sur les dernières 24h
```promql
sum(prisme_pipeline_cost_usd)
```

### Taux de succès (%)
```promql
(prisme_agents_success / prisme_agents_executed) * 100
```

### Évolution du coût dans le temps
```promql
rate(prisme_pipeline_cost_usd[5m])
```

---

## 📁 Structure des Fichiers

```
monitoring/
├── docker-compose.yml              # Configuration Docker
├── prometheus/
│   ├── prometheus.yml              # Config Prometheus
│   └── data/                       # Données (créé automatiquement)
├── grafana/
│   ├── datasources/
│   │   └── prometheus.yml          # Auto-provision Prometheus
│   ├── dashboards/
│   │   ├── dashboard.yml           # Auto-provision dashboards
│   │   └── json/
│   │       └── prisme-agents.json  # Dashboard principal
│   └── data/                       # Données Grafana (créé auto)
└── README.md                       # Ce fichier

../metriques/                       # Généré par scripts
├── run_YYYYMMDD_HHMMSS.json       # Métriques complètes par run
├── temps_reel.json                 # État actuel (dashboard web)
└── grafana_metrics.prom            # Format Prometheus (lu par Prometheus)
```

---

## 🎨 Dashboard Grafana - Panneaux

### Ligne 1 : KPIs Globaux
- **Durée Totale** : Temps d'exécution pipeline (stat)
- **Coût Total** : $ dépensés (stat)
- **Tokens Total** : Nombre total de tokens (stat)
- **Statut** : Succès/Échec (stat coloré)

### Ligne 2 : Détails Agents
- **Durée par Agent** : Graphique en barres horizontal
- **Coût par Agent** : Camembert (pie chart)

### Ligne 3 : Analyse
- **Tokens par Agent** : Barre gauge horizontal
- **Taux de Réussite** : Gauge circulaire

### Ligne 4-5 : Historique
- **Timeline Agents** : Évolution durée dans le temps
- **Évolution Coût** : Graphique coût cumulé

---

## ⚙️ Configuration Avancée

### Changer le mot de passe Grafana

Éditez `docker-compose.yml` :

```yaml
environment:
  - GF_SECURITY_ADMIN_PASSWORD=votre_nouveau_mdp
```

Puis :
```powershell
docker-compose down
docker-compose up -d
```

### Augmenter la rétention Prometheus

Éditez `prometheus/prometheus.yml` :

```yaml
storage:
  tsdb:
    retention:
      time: 90d    # 90 jours au lieu de 30
      size: 50GB   # 50GB au lieu de 10GB
```

### Ajouter des alertes

Créez `prometheus/alerts/agents.yml` :

```yaml
groups:
  - name: prisme_agents
    interval: 30s
    rules:
      - alert: PipelineCostHigh
        expr: prisme_pipeline_cost_usd > 2.0
        for: 1m
        annotations:
          summary: "Coût pipeline élevé (> $2)"

      - alert: AgentDurationHigh
        expr: prisme_agent_duration_seconds > 60
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Agent {{$labels.agent}} prend trop de temps"
```

---

## 🔧 Maintenance

### Voir les logs

```powershell
# Tous les services
docker-compose logs -f

# Service spécifique
docker-compose logs -f grafana
docker-compose logs -f prometheus
```

### Redémarrer un service

```powershell
docker-compose restart grafana
docker-compose restart prometheus
```

### Arrêter la stack

```powershell
docker-compose down
```

### Nettoyer tout (⚠️ supprime les données)

```powershell
docker-compose down -v
```

---

## 📈 Exemple de Workflow

### Générer et Visualiser

```powershell
# 1. Lancer Grafana (si pas déjà fait)
cd monitoring
docker-compose up -d

# 2. Générer métriques
cd ..
python scripts/generer_avec_metriques.py

# 3. Ouvrir Grafana
start http://localhost:3000

# 4. Aller dans Dashboard > PRISME - Pipeline Multi-Agents

# 5. Voir les métriques en temps réel ! 🎉
```

### Comparer Plusieurs Runs

```powershell
# Run 1
python scripts/generer_avec_metriques.py
# → Coût : $0.45, Durée : 95s

# Run 2 (avec un autre provider)
$env:PRISME_LLM_PROVIDER = "anthropic"
python scripts/generer_avec_metriques.py
# → Coût : $0.62, Durée : 78s

# Voir la comparaison dans Grafana
# Dashboard > Timeline → Compare les 2 runs
```

---

## 🐛 Troubleshooting

### Prometheus ne voit pas les métriques

**Vérifiez** :
1. Le fichier existe : `ls ../metriques/grafana_metrics.prom`
2. Prometheus le lit : http://localhost:9090/targets
3. Format correct : les lignes doivent être `nom_metrique valeur`

**Solution** : Relancez une génération avec métriques.

### Grafana : "No data"

**Causes** :
1. Prometheus pas connecté
2. Aucune métrique générée
3. TimeRange trop ancien

**Solutions** :
- Vérifier Datasource : Configuration > Data Sources > Prometheus > Test
- Générer des métriques : `python scripts/generer_avec_metriques.py`
- Ajuster Time Range : Top-right corner > Last 1 hour

### Dashboard ne s'affiche pas

**Solution** :
```powershell
# Re-provision
docker-compose restart grafana

# Attendre 10s, puis refresh
```

---

## 🚀 Prochaines Étapes

### Intégration Dashboard React

Grafana peut être embedé dans votre dashboard React :

```typescript
<iframe
  src="http://localhost:3000/d/prisme-agents?orgId=1&refresh=5s&kiosk"
  width="100%"
  height="600px"
/>
```

### API Grafana

Récupérer les métriques programmatiquement :

```python
import requests

resp = requests.get(
    "http://localhost:3000/api/datasources/proxy/1/api/v1/query",
    params={"query": "prisme_pipeline_cost_usd"},
    auth=("admin", "prisme2026")
)
print(resp.json())
```

### Alertes Slack/Email

Grafana peut envoyer des alertes :
- Configuration > Alert notification channels
- Add channel (Slack, Email, Webhook, etc.)

---

## 📚 Ressources

- **Prometheus** : https://prometheus.io/docs/
- **Grafana** : https://grafana.com/docs/
- **PromQL** : https://prometheus.io/docs/prometheus/latest/querying/basics/

---

**Stack prête ! 🎉**

Lancez `docker-compose up -d` et commencez à monitorer vos agents !
