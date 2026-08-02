# API CSV Local - Documentation

## Vue d'ensemble

L'endpoint `POST /adapters/csv-local/ingerer` permet de convertir des fichiers CSV locaux (présents sur le serveur) en instances TRCO et de les enregistrer dans le système.

Cet endpoint est utile pour :
- **Imports en masse** depuis le serveur
- **Tests et développement** avec des données de référence
- **Scripts automatisés** d'ingestion périodique

## Endpoints disponibles

### 1. Ingestion depuis fichiers uploadés (existant)

```http
POST /adapters/csv/{client_id}
Content-Type: multipart/form-data

taches: fichier CSV
ressources: fichier CSV
contraintes: fichier CSV
```

**Utilisation** : Upload de fichiers depuis le client (navigateur, application)

### 2. Ingestion depuis dossier local (nouveau)

```http
POST /adapters/csv-local/ingerer
Content-Type: application/json

{
  "chemin_dossier": "data/donnees_brutes/csv/industrie_manufacturiere/assemblage_electronique",
  "client_id": "mon_client"
}
```

**Utilisation** : Conversion de fichiers déjà présents sur le serveur

## Détails de l'endpoint CSV Local

### Requête

**URL** : `/adapters/csv-local/ingerer`
**Méthode** : `POST`
**Content-Type** : `application/json`

**Authentification** : JWT Bearer token (si l'auth est activée)

**Corps de la requête** :

```json
{
  "chemin_dossier": "string",  // Chemin absolu ou relatif vers le dossier CSV
  "client_id": "string"         // Identifiant du client
}
```

**Fichiers requis dans le dossier** :
- `taches.csv`
- `ressources.csv`
- `contraintes.csv`

### Réponse

**Status 200** - Succès

```json
{
  "instance_id": "550e8400-e29b-41d4-a716-446655440000",
  "structure_contraintes": "precedence+compatibilite_ressource_tache",
  "statistiques": {
    "taches": 10,
    "ressources": 9,
    "contraintes": 19,
    "objectifs": 1
  },
  "chemin_source": "data/donnees_brutes/csv/industrie_manufacturiere/assemblage_electronique"
}
```

**Status 404** - Dossier ou fichiers introuvables

```json
{
  "detail": "Dossier introuvable : /chemin/inexistant"
}
```

ou

```json
{
  "detail": "Fichier(s) manquant(s) dans /chemin: taches.csv, contraintes.csv"
}
```

**Status 422** - Fichiers CSV invalides ou instance non valide

```json
{
  "detail": "taches.csv : colonne(s) manquante(s) : id"
}
```

**Status 500** - Erreur serveur

```json
{
  "detail": "Erreur lors de la lecture des fichiers : ..."
}
```

## Exemples d'utilisation

### cURL (avec authentification)

```bash
# Obtenir un token (si l'auth est activée)
TOKEN=$(curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' \
  | jq -r '.access_token')

# Ingérer depuis un dossier local
curl -X POST http://localhost:8000/adapters/csv-local/ingerer \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "chemin_dossier": "data/donnees_brutes/csv/industrie_manufacturiere/assemblage_electronique",
    "client_id": "mon_client"
  }'
```

### cURL (sans authentification - mode dev)

```bash
# Avec PRISME_AUTH_DESACTIVEE=1
curl -X POST http://localhost:8000/adapters/csv-local/ingerer \
  -H "Content-Type: application/json" \
  -d '{
    "chemin_dossier": "data/donnees_brutes/csv/industrie_manufacturiere/assemblage_electronique",
    "client_id": "test_client"
  }'
```

### Python avec requests

```python
import requests

API_URL = "http://localhost:8000"

# Requête d'ingestion
response = requests.post(
    f"{API_URL}/adapters/csv-local/ingerer",
    json={
        "chemin_dossier": "data/donnees_brutes/csv/industrie_manufacturiere/assemblage_electronique",
        "client_id": "mon_client"
    }
)

if response.status_code == 200:
    resultat = response.json()
    print(f"Instance créée : {resultat['instance_id']}")
    print(f"Tâches : {resultat['statistiques']['taches']}")
    print(f"Ressources : {resultat['statistiques']['ressources']}")
else:
    print(f"Erreur : {response.status_code}")
    print(response.json())
```

### Python avec httpx (async)

```python
import httpx
import asyncio

async def ingerer_csv():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/adapters/csv-local/ingerer",
            json={
                "chemin_dossier": "data/donnees_brutes/csv/services/centre_appels",
                "client_id": "mon_client"
            }
        )
        return response.json()

resultat = asyncio.run(ingerer_csv())
print(resultat)
```

### JavaScript/TypeScript (fetch)

```typescript
const response = await fetch('http://localhost:8000/adapters/csv-local/ingerer', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    chemin_dossier: 'data/donnees_brutes/csv/industrie_manufacturiere/atelier_mecanique',
    client_id: 'mon_client'
  })
});

const resultat = await response.json();
console.log('Instance créée :', resultat.instance_id);
console.log('Statistiques :', resultat.statistiques);
```

## Format des fichiers CSV

### taches.csv

```csv
id,nom,duree_estimee_jours
PREP_PCB,Prep Pcb,1
POSE_CMS_FACE_A,Pose Cms Face A,2
```

**Colonnes requises** : `id`
**Colonnes optionnelles** : `nom`, `duree_estimee_jours`

### ressources.csv

```csv
id,nom,competences
STATION_PREP,Station Prep,station
MACHINE_PICK_PLACE_1,Machine Pick Place 1,machine
```

**Colonnes requises** : `id`
**Colonnes optionnelles** : `nom`, `competences`

**Note** : Les compétences multiples sont séparées par `;`

### contraintes.csv

```csv
type,tache_avant,tache_apres,tache,ressource,duree_jours,competence
precedence,PREP_PCB,POSE_CMS_FACE_A,,,,
compatibilite_ressource_tache,,,PREP_PCB,STATION_PREP,1,
competence_requise,,,PREP_PCB,,,station
```

**Colonnes requises** : `type`
**Colonnes optionnelles** : `tache_avant`, `tache_apres`, `tache`, `ressource`, `duree_jours`, `competence`

**Types de contraintes supportés** :
- `precedence` : Ordre d'exécution entre tâches
- `compatibilite_ressource_tache` : Associations tâche-ressource avec durée
- `competence_requise` : Compétence nécessaire pour une tâche

## Script de test

Un script de test complet est disponible :

```bash
# Démarrer l'API
uv run uvicorn api.app:app --reload

# Dans un autre terminal, exécuter le test
uv run python -m scripts.tester_endpoint_csv
```

## Workflow typique

1. **Préparer les CSV** sur le serveur dans un dossier
2. **Appeler l'endpoint** avec le chemin du dossier
3. **Récupérer l'instance_id** de la réponse
4. **Utiliser l'instance** pour génération de solveur ou exécution

```bash
# 1. Ingérer
INSTANCE_ID=$(curl -X POST http://localhost:8000/adapters/csv-local/ingerer \
  -H "Content-Type: application/json" \
  -d '{"chemin_dossier":"data/donnees_brutes/csv/services/centre_appels","client_id":"test"}' \
  | jq -r '.instance_id')

# 2. Récupérer l'instance
curl http://localhost:8000/ingestion/$INSTANCE_ID | jq

# 3. Générer un solveur
curl -X POST http://localhost:8000/generation/$INSTANCE_ID

# 4. Exécuter
curl -X POST http://localhost:8000/execution/$INSTANCE_ID
```

## Sécurité

### Validation des chemins

L'endpoint vérifie :
- ✓ Existence du dossier
- ✓ Présence des trois fichiers CSV requis
- ✓ Format UTF-8 valide
- ✓ Colonnes requises présentes
- ✓ Validation Pydantic de l'instance TRCO

### Autorisation

- Authentification JWT (si activée)
- Vérification d'accès au `client_id` spécifié
- Pas d'accès cross-client sans autorisation

### Limitations

⚠️ **Production** : Cet endpoint expose le système de fichiers du serveur. En production :
- Restreindre les chemins autorisés (whitelist)
- Logger tous les accès
- Limiter aux administrateurs ou services internes

## Dossiers CSV disponibles

Les dossiers de test suivants sont disponibles dans le projet :

```
data/donnees_brutes/csv/
├── industrie_manufacturiere/
│   ├── assemblage_electronique/    (10 tâches, 9 ressources)
│   ├── atelier_mecanique/           (8 tâches, 8 ressources)
│   ├── imprimerie/                  (9 tâches, 7 ressources)
│   └── production_agroalimentaire/  (9 tâches, 9 ressources)
└── services/
    ├── centre_appels/               (8 tâches, 4 ressources)
    └── maintenance_industrielle/    (7 tâches, 5 ressources)
```

## Voir aussi

- **Format CSV** : `data/donnees_brutes/csv/README.md`
- **Adaptateur CSV** : `adapters/csv_import/traducteur.py`
- **API OpenAPI** : http://localhost:8000/docs
- **Tests** : `scripts/tester_endpoint_csv.py`
