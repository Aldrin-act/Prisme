# Guide d'extraction des vraies données GreenSig (2165 tâches)

Ce guide vous aide à configurer l'extraction des données réelles depuis la base GreenSig.

## 🎯 Objectif

Extraire les **2165 tâches réelles** du backup `backup_20260503.sql` au lieu des 3-4 tâches de démonstration.

## 📋 Prérequis

- Docker Desktop installé ✅ (version détectée: 28.0.1)
- Le fichier `backup_20260503.sql` à la racine du projet ✅
- Le fichier `.env` configuré ✅

## 🚀 Installation (5 étapes)

### Étape 1 : Démarrer Docker Desktop

**Windows** : Lancez Docker Desktop depuis le menu Démarrer

Vérifiez que Docker est actif :
```bash
docker ps
```

Si vous voyez une liste (même vide), Docker est prêt ! ✅

### Étape 2 : Démarrer le conteneur PostgreSQL GreenSig

```bash
docker compose --profile greensig up -d db_greensig
```

**Ce que ça fait** :
- Télécharge l'image `postgis/postgis:16-3.4-alpine` (environ 200MB)
- Crée un conteneur PostgreSQL avec PostGIS activé
- Expose le port 5433 sur votre machine
- Crée une base vide `greensig`

**Vérification** :
```bash
docker compose ps
```

Vous devriez voir `db_greensig` avec le statut "running" et "healthy".

### Étape 3 : Restaurer le backup SQL (2165 tâches)

**PowerShell** (recommandé sous Windows) :
```powershell
cmd /c "docker compose exec -T db_greensig psql -U greensig -d greensig -f - < backup_20260503.sql"
```

**Git Bash / WSL** :
```bash
docker compose exec -T db_greensig psql -U greensig -d greensig -f - < backup_20260503.sql
```

**Ce que ça fait** :
- Lit le fichier `backup_20260503.sql` (environ 50MB)
- Restaure toutes les tables GreenSig
- Insère les 2165 tâches + équipes + opérateurs + compétences

**Durée** : 30-60 secondes

**Note** : Vous verrez quelques warnings `"already exists"` pour les schémas `tiger`/`topology` — c'est normal et attendu (voir commentaires dans `docker-compose.yml:70-74`).

**Vérification** :
```bash
docker compose exec db_greensig psql -U greensig -d greensig -c "SELECT COUNT(*) FROM api_planification_tache;"
```

Devrait afficher : `2165` ✅

### Étape 4 : Installer les dépendances Python

Le script a besoin de `psycopg` pour se connecter à PostgreSQL :

```bash
uv sync --extra sandbox
```

### Étape 5 : Lancer l'extraction

```bash
uv run python -m scripts.demo_greensig_vraies_donnees
```

**Ce que ça fait** :
1. Se connecte à `db_greensig` via `GREENSIG_DATABASE_URL`
2. Extrait les tâches avec `adapters/greensig/extraction.py`
3. Convertit en instance T-R-C-O avec `adapters/greensig/translator.py`
4. Affiche des statistiques détaillées
5. Sauvegarde dans :
   - `greensig_payload_reel.json` (format ERP)
   - `greensig_instance_trco_reel.json` (format T-R-C-O)

## 📊 Ce que vous verrez

```
🌿🌿🌿  EXTRACTION GREENSIG - VRAIES DONNÉES  🌿🌿🌿

═══════════════════════════════════════════════════════════════════
  EXTRACTION DEPUIS DB_GREENSIG
═══════════════════════════════════════════════════════════════════

📡 Connexion à la base GreenSig...
✅ Extraction réussie !

📊 STATISTIQUES :
  • Tâches extraites : 2165
  • Équipes : XX
  • Types de tâches : XX
  • Opérateurs : XX
  • Compétences : XX

═══════════════════════════════════════════════════════════════════
  CONVERSION GREENSIG → T-R-C-O
═══════════════════════════════════════════════════════════════════

✅ Instance T-R-C-O créée !

📊 STATISTIQUES :
  • Tâches : XXXX (tâches actives uniquement)
  • Ressources : XX (équipes actives uniquement)
  • Compatibilités ressource-tâche : XXXX
  • Précédences : 0 (GreenSig n'a pas de précédences)
```

## 🔧 Dépannage

### Erreur : "The system cannot find the file specified"

➡️ **Solution** : Docker Desktop n'est pas démarré. Lancez-le et attendez qu'il soit prêt.

### Erreur : "Connection refused" ou "could not connect"

➡️ **Solution** : Le conteneur n'est pas démarré ou pas encore healthy. Attendez 10-15 secondes après `docker compose up`.

Vérifiez :
```bash
docker compose ps
# État doit être "running (healthy)"
```

### Erreur : "relation api_planification_tache does not exist"

➡️ **Solution** : Le backup n'a pas été restauré. Relancez l'Étape 3.

### Le script affiche "0 tâches extraites"

➡️ **Cause probable** : Toutes les tâches ont un statut différent de `'PLANIFIEE'` ou `'EN_COURS'`.

Vérifiez :
```bash
docker compose exec db_greensig psql -U greensig -d greensig -c "SELECT statut, COUNT(*) FROM api_planification_tache GROUP BY statut;"
```

## 🧹 Nettoyage

Pour arrêter et supprimer le conteneur + données :

```bash
# Arrêter le conteneur
docker compose --profile greensig down

# Supprimer aussi le volume (⚠️ efface toutes les données)
docker compose --profile greensig down -v
```

Pour redémarrer plus tard :
```bash
docker compose --profile greensig up -d db_greensig
# Pas besoin de restaurer le backup, les données sont persistées
```

## 📚 Fichiers générés

Après l'exécution, vous trouverez à la racine :

- **greensig_payload_reel.json** : Données brutes GreenSig (format ERP)
  - Structure : `{taches, equipes, types_tache, operateurs, competences}`
  - Taille : ~5-10 MB

- **greensig_instance_trco_reel.json** : Instance canonique T-R-C-O
  - Structure : `{taches, ressources, contraintes, objectifs}`
  - Prête à être résolue par un solveur CP-SAT
  - Taille : ~2-5 MB

## ➡️ Prochaine étape

Une fois l'extraction réussie, vous pouvez :

1. **Générer un solveur** pour ces données :
   ```bash
   uv run python -m scripts.generer_et_executer_greensig
   ```

2. **Utiliser le solveur de référence** :
   ```bash
   # Adapter scripts/executer_greensig_avec_reference.py pour charger
   # greensig_instance_trco_reel.json au lieu de créer une instance test
   ```

3. **Analyser les données** :
   ```bash
   uv run python -m scripts.rapport_greensig_dsl
   ```

## 📖 Références

- **Adaptateur GreenSig** : `adapters/greensig/`
  - `extraction.py` : Extraction SQL depuis PostgreSQL
  - `translator.py` : Conversion GreenSig → T-R-C-O
  - `schema_greensig.py` : Schéma des tables GreenSig

- **Documentation** : `adapters/greensig/mapping/regles.md`
  - Règles de mapping compétences → types de tâches

- **Docker Compose** : `docker-compose.yml:65-96`
  - Service `db_greensig` avec PostGIS

- **Variables d'environnement** : `.env:13-26`
  - `GREENSIG_DATABASE_URL` : Connexion PostgreSQL
