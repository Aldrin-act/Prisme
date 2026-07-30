# Guide Complet - Données Brutes vers Pipeline PRISME

Ce guide explique le workflow complet de transformation des données, depuis les exports
ERP bruts jusqu'à l'exécution d'un planning optimisé.

## Vue d'Ensemble du Workflow

```
┌─────────────────────┐
│  Données Brutes     │  ← Export ERP / Saisie manuelle
│  (JSON, CSV, Excel) │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Adaptateur ERP     │  ← Transformation format propriétaire → TRCO
│  (translator.py)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Instance TRCO      │  ← Format canonique validé
│  (DSL)              │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Génération Solveur │  ← Benchmarker choisit l'algorithme (cp_sat ou
│  (generation/)      │    heuristique), puis le LLM génère le code
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Validation Cascade │  ← Tests faisabilité/optimalité
│  (validation/)      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Registre + Sandbox │  ← Persistance + exécution isolée
│  (solver_store/)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Planning Optimisé  │  ← Résultat final
│  (JSON)             │
└─────────────────────┘
```

## Structure des Répertoires

```
data/
├── donnees_brutes/          # Données sources (format ERP)
│   ├── json_erp/           # Format JSON ERP de référence
│   ├── csv/                # Format CSV simple
│   └── README.md
├── instances_trco/          # Instances TRCO transformées
│   ├── atelier_mecanique.json
│   ├── assemblage_electronique.json
│   └── ...
└── GUIDE_DONNEES.md        # Ce fichier
```

## Étape 1 : Données Brutes

### Format JSON (ERP de référence)

**Fichier**: `donnees_brutes/json_erp/atelier_mecanique.json`

```json
{
  "operations": [
    {
      "code_operation": "DECOUP_001",
      "duree_minutes": 45,
      "poste_id": "DECOUPEUSE_LASER",
      "operation_precedente": null
    },
    {
      "code_operation": "PERCAGE_001",
      "duree_minutes": 30,
      "poste_id": "PERCEUSE_CNC",
      "operation_precedente": "DECOUP_001"
    }
  ],
  "postes": [
    {"code_poste": "DECOUPEUSE_LASER"},
    {"code_poste": "PERCEUSE_CNC"}
  ]
}
```

**Caractéristiques**:
- Format simple avec 1 poste par opération (Job-Shop classique)
- Précédences linéaires (une seule opération précédente)
- Vocabulaire propriétaire (operations/postes, pas taches/ressources)

### Format CSV

**Fichiers**:
- `donnees_brutes/csv/atelier_mecanique_operations.csv`
- `donnees_brutes/csv/atelier_mecanique_postes.csv`

**operations.csv**:
```csv
code_operation,duree_minutes,poste_id,operation_precedente
DECOUP_001,45,DECOUPEUSE_LASER,
PERCAGE_001,30,PERCEUSE_CNC,DECOUP_001
```

**postes.csv**:
```csv
code_poste
DECOUPEUSE_LASER
PERCEUSE_CNC
```

### Génération de Données Brutes

```bash
# Générer les 5 jeux de données brutes (JSON + CSV)
python -m scripts.generer_donnees_brutes
```

**Jeux de données disponibles**:
1. `atelier_mecanique` - Fabrication métallique (8 operations)
2. `assemblage_electronique` - PCB manufacturing (10 operations)
3. `production_agroalimentaire` - Transformation alimentaire (9 operations)
4. `maintenance_industrielle` - Gestion de pannes (7 operations)
5. `imprimerie` - Impression offset (9 operations)

## Étape 2 : Transformation en Instances TRCO

### Transformation Automatique

```bash
# Transformer tous les fichiers JSON du répertoire par défaut
python -m scripts.transformer_donnees_brutes

# Transformer un fichier JSON spécifique
python -m scripts.transformer_donnees_brutes --input data/donnees_brutes/json_erp/atelier_mecanique.json

# Transformer depuis CSV
python -m scripts.transformer_donnees_brutes \
    --csv-operations data/donnees_brutes/csv/atelier_mecanique_operations.csv \
    --csv-postes data/donnees_brutes/csv/atelier_mecanique_postes.csv
```

### Transformation Programmatique

```python
from pathlib import Path
import json
from adapters.erp_reference.schema_erp import PayloadERP
from adapters.erp_reference.translator import traduire

# Charger les données brutes
with open("data/donnees_brutes/json_erp/atelier_mecanique.json") as f:
    payload_erp = PayloadERP(**json.load(f))

# Traduire en TRCO
instance_trco = traduire(payload_erp)

# Vérifier
print(f"Taches: {len(instance_trco.taches)}")
print(f"Ressources: {len(instance_trco.ressources)}")
print(f"Contraintes: {len(instance_trco.contraintes)}")

# Sauvegarder
with open("data/instances_trco/ma_instance.json", "w") as f:
    json.dump(instance_trco.model_dump(mode="json"), f, indent=2)
```

### Format de l'Instance TRCO Résultante

**Fichier**: `instances_trco/atelier_mecanique.json`

```json
{
  "taches": [
    {"id": "DECOUP_001", "nom": null, "priorite": null},
    {"id": "PERCAGE_001", "nom": null, "priorite": null}
  ],
  "ressources": [
    {"id": "DECOUPEUSE_LASER", "nom": null, "competences": []},
    {"id": "PERCEUSE_CNC", "nom": null, "competences": []}
  ],
  "contraintes": [
    {
      "type": "compatibilite_ressource_tache",
      "tache": "DECOUP_001",
      "ressource": "DECOUPEUSE_LASER",
      "duree": 45
    },
    {
      "type": "precedence",
      "avant": "DECOUP_001",
      "apres": "PERCAGE_001"
    }
  ],
  "objectifs": [
    {"type": "minimiser_makespan"}
  ]
}
```

**Différences avec les données brutes**:
- Vocabulaire canonique (taches/ressources vs operations/postes)
- Structure discriminée par type (contraintes avec champ `type`)
- Validation Pydantic appliquée (garde-fou amont §6.7)

## Étape 3 : Validation de l'Instance

```python
from dsl.validation.charger_instance import charger_instance_depuis_json

# Charger et valider
instance = charger_instance_depuis_json("data/instances_trco/atelier_mecanique.json")

# L'instance est automatiquement validée :
# - IDs uniques par axe
# - Chaque tâche a au moins une compatibilité ressource
# - Les contraintes référencent des entités déclarées
# - Pas de cycles dans les précédences (si applicable)
```

## Étape 4 : Génération du Solveur

```python
from generation.tentative_unique import generer_et_tester_solveur

# Générer un solveur pour cette instance
resultat = generer_et_tester_solveur(instance)

if resultat.solveur:
    print("Solveur genere avec succes!")
    print(f"Code genere: {len(resultat.code_genere)} caracteres")
else:
    print(f"Echec: {resultat.erreur}")
```

## Étape 5 : Validation par Cascade

```python
from validation_engine.cascade import evaluer_cascade

# Valider le solveur sur les 3 briques
diagnostic = evaluer_cascade(resultat.solveur)

print(f"Verdict global: {diagnostic.verdict_global}")
for d in diagnostic.diagnostics:
    print(f"  - {d.nom_instance}: {'OK' if d.reussi else 'ECHEC'}")
```

## Étape 6 : Persistance dans le Registre

```python
from solver_store.registry import Registre

# Enregistrer le solveur validé
registre = Registre()
solver_id = registre.enregistrer(
    code_source=resultat.code_genere,
    diagnostic_cascade=diagnostic,
    client_id="client_demo",
)

print(f"Solveur enregistre avec ID: {solver_id}")
```

## Étape 7 : Exécution dans le Sandbox

```python
from sandbox.runner import executer_dans_sandbox

# Récupérer l'artifact
artifact_path = registre.chemin_artifact(solver_id)

# Exécuter dans un conteneur isolé
planning = executer_dans_sandbox(artifact_path, instance)

if planning:
    makespan = max(op.debut + op.duree for op in planning.operations)
    print(f"Planning genere avec makespan: {makespan} minutes")

    # Afficher le planning
    for op in planning.operations:
        print(f"  {op.tache} sur {op.ressource}: debut={op.debut}, duree={op.duree}")
```

## Workflow Complet - Exemple Bout-en-Bout

```python
#!/usr/bin/env python
"""Pipeline complète : Données brutes → Planning optimisé."""

import json
from pathlib import Path

# Étape 1: Charger données brutes
from adapters.erp_reference.schema_erp import PayloadERP
from adapters.erp_reference.translator import traduire

with open("data/donnees_brutes/json_erp/atelier_mecanique.json") as f:
    payload_erp = PayloadERP(**json.load(f))

# Étape 2: Traduire en TRCO
instance_trco = traduire(payload_erp)
print(f"Instance TRCO: {len(instance_trco.taches)} taches")

# Étape 3: Générer solveur
from generation.tentative_unique import generer_et_tester_solveur
resultat = generer_et_tester_solveur(instance_trco)

if not resultat.solveur:
    print(f"ERREUR generation: {resultat.erreur}")
    exit(1)

print("Solveur genere avec succes")

# Étape 4: Valider
from validation_engine.cascade import evaluer_cascade
diagnostic = evaluer_cascade(resultat.solveur)
print(f"Verdict cascade: {diagnostic.verdict_global}")

# Étape 5: Enregistrer
from solver_store.registry import Registre
registre = Registre()
solver_id = registre.enregistrer(
    code_source=resultat.code_genere,
    diagnostic_cascade=diagnostic,
    client_id="demo",
)

# Étape 6: Exécuter
from sandbox.runner import executer_dans_sandbox
artifact_path = registre.chemin_artifact(solver_id)
planning = executer_dans_sandbox(artifact_path, instance_trco)

# Étape 7: Résultat
if planning:
    makespan = max(op.debut + op.duree for op in planning.operations)
    print(f"\nPlanning final - Makespan: {makespan} minutes")
    print(f"Operations planifiees: {len(planning.operations)}")
else:
    print("Aucune solution trouvee")
```

## Cas d'Usage Avancés

### 1. Enrichir une Instance TRCO

```python
from dsl.schema import Echeance, CompetenceRequise

# Charger instance de base
instance = charger_instance_depuis_json("data/instances_trco/atelier_mecanique.json")

# Ajouter des échéances
instance.contraintes.append(
    Echeance(tache="CONTROLE_QUALITE", echeance=300)  # 5h max
)

# Ajouter des compétences
instance.contraintes.append(
    CompetenceRequise(tache="SOUDURE_001", competence="certification_soudure")
)
instance.ressources[3].competences.append("certification_soudure")

# Modifier l'objectif
from dsl.schema.objectifs_parametrables import MinimiserRetards, EquilibrerCharge
instance.objectifs = [
    MinimiserRetards(poids=0.7, fonction_penalite="quadratique"),
    MinimiserMakespan(poids=0.3),
]

# Sauvegarder la version enrichie
with open("data/instances_trco/atelier_mecanique_enrichi.json", "w") as f:
    json.dump(instance.model_dump(mode="json"), f, indent=2)
```

### 2. Créer un Adaptateur Personnalisé

```python
# custom_adapter/translator.py
from dsl.schema import InstanceTRCO, Tache, Ressource, CompatibiliteRessourceTache, Precedence
from .schema_custom import PayloadCustom  # Votre format propriétaire

def traduire(payload: PayloadCustom) -> InstanceTRCO:
    """Traduit votre format ERP personnalisé en TRCO."""

    # Mapper vos entités vers le DSL TRCO
    taches = [Tache(id=job.code, nom=job.libelle) for job in payload.jobs]
    ressources = [Ressource(id=m.id, competences=m.skills) for m in payload.machines]

    contraintes = []
    for job in payload.jobs:
        for machine_id, duration in job.possible_machines.items():
            contraintes.append(
                CompatibiliteRessourceTache(
                    tache=job.code,
                    ressource=machine_id,
                    duree=duration
                )
            )

        if job.depends_on:
            contraintes.append(
                Precedence(avant=job.depends_on, apres=job.code)
            )

    return InstanceTRCO(
        taches=taches,
        ressources=ressources,
        contraintes=contraintes,
        objectifs=[MinimiserMakespan()],
    )
```

### 3. Import Batch depuis une Base de Données

```python
import psycopg2
from adapters.erp_reference.schema_erp import OperationERP, PosteERP, PayloadERP
from adapters.erp_reference.translator import traduire

# Connexion à la base
conn = psycopg2.connect("dbname=erp_prod user=prisme")
cur = conn.cursor()

# Extraire les données
cur.execute("SELECT code, duree, poste_id, operation_precedente FROM operations WHERE statut='A_PLANIFIER'")
operations = [
    OperationERP(
        code_operation=row[0],
        duree_minutes=row[1],
        poste_id=row[2],
        operation_precedente=row[3],
    )
    for row in cur.fetchall()
]

cur.execute("SELECT code_poste FROM postes WHERE actif=true")
postes = [PosteERP(code_poste=row[0]) for row in cur.fetchall()]

# Créer le payload et traduire
payload_erp = PayloadERP(operations=operations, postes=postes)
instance_trco = traduire(payload_erp)

print(f"Instance creee depuis la base: {len(instance_trco.taches)} taches")
```

## Dépannage

### Erreur: "tâche(s) sans aucune contrainte de compatibilité"

**Cause**: Une tâche n'a pas de ressource compatible déclarée.

**Solution**: Vérifier que chaque opération a un `poste_id` valide dans les données brutes.

### Erreur: "compatibilité référence une ressource inconnue"

**Cause**: Un `poste_id` référencé n'existe pas dans la liste des postes.

**Solution**: Ajouter le poste manquant dans `postes` ou corriger le `poste_id`.

### Erreur ValidationError lors du chargement JSON

**Cause**: Le JSON ne respecte pas le schéma Pydantic.

**Solution**: Vérifier la structure, les types de données, les champs obligatoires.

## Ressources

- **Schemas DSL**: `dsl/schema/`
- **Adaptateurs**: `adapters/`
- **Scripts de transformation**: `scripts/`
- **Documentation**: `CLAUDE.md`, `CONTRIBUTING.md`
- **Note de cadrage**: `PRISME_Note_de_Cadrage (2).md`

## Support

Pour toute question ou problème, consultez d'abord :
1. Ce guide
2. Le README dans `data/donnees_brutes/`
3. Le code source des adaptateurs (`adapters/erp_reference/translator.py`)
