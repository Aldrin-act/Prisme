# Guide d'Utilisation des Instances TRCO avec Objectifs Variés

## Vue d'ensemble

Ce répertoire contient **6 instances TRCO** diversifiées conçues pour tester et valider
la pipeline de génération de PRISME avec différents types d'objectifs d'optimisation.

## Instances disponibles

| Fichier | Objectif(s) | Complexité | Tâches | Ressources | Cas d'usage |
|---------|------------|------------|---------|------------|-------------|
| `01_makespan_simple.json` | Minimiser makespan | Simple | 4 | 3 | Validation de base |
| `02_equilibrage_charge.json` | Équilibrage (70%) + Makespan (30%) | Moyenne | 6 | 3 | Utilisation équitable |
| `03_minimiser_retards.json` | Retards (80%) + Makespan (20%) | Moyenne | 5 | 2 | Gestion des délais |
| `04_maximiser_utilisation.json` | Utilisation (60%) + Makespan (40%) | Moyenne | 6 | 3 | ROI équipements |
| `05_minimiser_changements.json` | Changements (50%) + 2 autres | Moyenne | 7 | 3 | Réduction setup |
| `06_multi_objectifs_complexe.json` | 5 objectifs pondérés | Élevée | 8 | 4 | Scénario réaliste |

## Utilisation dans la pipeline

### 1. Charger une instance

```python
from dsl.validation.charger_instance import charger_instance_depuis_json

# Charger une instance
instance = charger_instance_depuis_json(
    "dsl/examples/objectifs_varies/02_equilibrage_charge.json"
)

print(f"Instance chargee: {len(instance.taches)} taches, {len(instance.ressources)} ressources")
print(f"Objectifs: {[obj.type for obj in instance.objectifs]}")
```

### 2. Générer un solveur pour l'instance

```python
from generation.tentative_unique import generer_et_tester_solveur

# Générer un solveur pour cette instance
resultat = generer_et_tester_solveur(instance)

if resultat.solveur:
    print("Solveur genere avec succes!")
    print(f"Verdict: {resultat.verdict_cascade}")
else:
    print("Echec de la generation")
    print(f"Erreur: {resultat.erreur}")
```

### 3. Exécuter le solveur sur l'instance

```python
# Exécuter le solveur généré
planning = resultat.solveur(instance)

if planning:
    print(f"Planning genere avec makespan: {max(op.debut + op.duree for op in planning.operations)}")
else:
    print("Aucun planning trouve")
```

### 4. Valider le planning avec la cascade

```python
from validation_engine.cascade import evaluer_cascade

# Valider le solveur
diagnostic = evaluer_cascade(resultat.solveur)

print(f"Faisabilite: {diagnostic.verdict_global}")
print(f"Tests reussis: {sum(1 for d in diagnostic.diagnostics if d.reussi)}/{len(diagnostic.diagnostics)}")
```

### 5. Tests automatisés

```python
import pytest
from pathlib import Path

def test_instance_equilibrage_charge():
    """Test de l'instance avec équilibrage de charge."""
    instance = charger_instance_depuis_json(
        "dsl/examples/objectifs_varies/02_equilibrage_charge.json"
    )

    # Vérifier la structure
    assert len(instance.taches) == 6
    assert len(instance.ressources) == 3
    assert len(instance.objectifs) == 2

    # Vérifier les objectifs
    types_objectifs = {obj.type for obj in instance.objectifs}
    assert "equilibrer_charge" in types_objectifs
    assert "minimiser_makespan" in types_objectifs

def test_toutes_les_instances_sont_valides():
    """Vérifie que toutes les instances peuvent être chargées."""
    instances_dir = Path("dsl/examples/objectifs_varies")
    fichiers_json = list(instances_dir.glob("*.json"))

    assert len(fichiers_json) == 6, "Devrait y avoir 6 instances"

    for fichier in fichiers_json:
        instance = charger_instance_depuis_json(str(fichier))
        assert instance is not None
        assert len(instance.taches) > 0
        assert len(instance.ressources) > 0
        assert len(instance.objectifs) > 0
```

## Pipeline complète : Exemple bout-en-bout

```python
#!/usr/bin/env python
"""Exemple de pipeline complète avec une instance multi-objectifs."""

from dsl.validation.charger_instance import charger_instance_depuis_json
from generation.tentative_unique import generer_et_tester_solveur
from validation_engine.cascade import evaluer_cascade
from solver_store.registry import Registre
from sandbox.runner import executer_dans_sandbox

def pipeline_complete(chemin_instance: str):
    """Exécute la pipeline complète de PRISME."""

    # ÉTAPE 1: Chargement et validation de l'instance
    print("ETAPE 1: Chargement de l'instance...")
    instance = charger_instance_depuis_json(chemin_instance)
    print(f"  - {len(instance.taches)} taches, {len(instance.ressources)} ressources")
    print(f"  - Objectifs: {[obj.type for obj in instance.objectifs]}")

    # ÉTAPE 2: Génération du solveur
    print("\nETAPE 2: Generation du solveur...")
    resultat = generer_et_tester_solveur(instance)

    if not resultat.solveur:
        print(f"  ERREUR: {resultat.erreur}")
        return None

    print("  Solveur genere avec succes")

    # ÉTAPE 3: Validation par la cascade
    print("\nETAPE 3: Validation par la cascade...")
    diagnostic = evaluer_cascade(resultat.solveur)
    print(f"  Verdict: {diagnostic.verdict_global}")

    if diagnostic.verdict_global != "vert":
        print(f"  ATTENTION: Certains tests ont echoue")
        for d in diagnostic.diagnostics:
            if not d.reussi:
                print(f"    - {d.nom_instance}: {d.raison_echec}")

    # ÉTAPE 4: Persistance dans le registre
    print("\nETAPE 4: Enregistrement dans le registre...")
    registre = Registre()
    solver_id = registre.enregistrer(
        code_source=resultat.code_genere,
        diagnostic_cascade=diagnostic,
        client_id="demo",
    )
    print(f"  Solveur enregistre avec ID: {solver_id}")

    # ÉTAPE 5: Exécution dans le sandbox
    print("\nETAPE 5: Execution dans le sandbox...")
    artifact_path = registre.chemin_artifact(solver_id)
    planning = executer_dans_sandbox(artifact_path, instance)

    if planning:
        makespan = max(op.debut + op.duree for op in planning.operations)
        print(f"  Planning genere avec makespan: {makespan} minutes")
        print(f"  Nombre d'operations: {len(planning.operations)}")
    else:
        print("  Aucun planning trouve")

    return planning

if __name__ == "__main__":
    # Tester avec l'instance multi-objectifs complexe
    planning = pipeline_complete(
        "dsl/examples/objectifs_varies/06_multi_objectifs_complexe.json"
    )
```

## Tests de régression

Pour utiliser ces instances dans des tests de régression automatisés :

```python
# tests/integration/test_instances_objectifs_varies.py
import pytest
from pathlib import Path
from dsl.validation.charger_instance import charger_instance_depuis_json
from generation.tentative_unique import generer_et_tester_solveur

INSTANCES_DIR = Path("dsl/examples/objectifs_varies")
INSTANCES = list(INSTANCES_DIR.glob("*.json"))

@pytest.mark.parametrize("fichier_instance", INSTANCES)
def test_generation_pour_chaque_instance(fichier_instance):
    """Vérifie que la génération fonctionne pour chaque instance."""
    instance = charger_instance_depuis_json(str(fichier_instance))
    resultat = generer_et_tester_solveur(instance)

    # Au minimum, la génération ne doit pas crasher
    assert resultat is not None

    # Idéalement, un solveur devrait être généré
    if resultat.solveur:
        assert callable(resultat.solveur)
        # Tenter d'exécuter le solveur
        planning = resultat.solveur(instance)
        # Un planning None est acceptable (pas de solution trouvée)
        # mais ne devrait pas crasher

@pytest.mark.parametrize("fichier_instance", INSTANCES)
def test_validation_cascade_pour_chaque_instance(fichier_instance):
    """Vérifie que la cascade de validation fonctionne."""
    instance = charger_instance_depuis_json(str(fichier_instance))
    resultat = generer_et_tester_solveur(instance)

    if resultat.solveur:
        diagnostic = evaluer_cascade(resultat.solveur)
        assert diagnostic is not None
        assert diagnostic.verdict_global in ["vert", "orange", "rouge"]
```

## Benchmarking

Pour comparer les performances :

```python
import time
from statistics import mean, stdev

def benchmark_instance(chemin_instance: str, n_executions: int = 10):
    """Benchmark une instance avec plusieurs exécutions."""
    instance = charger_instance_depuis_json(chemin_instance)
    resultat = generer_et_tester_solveur(instance)

    if not resultat.solveur:
        print(f"Echec de generation pour {chemin_instance}")
        return

    temps_executions = []
    makespans = []

    for i in range(n_executions):
        debut = time.time()
        planning = resultat.solveur(instance)
        fin = time.time()

        temps_executions.append(fin - debut)

        if planning:
            makespan = max(op.debut + op.duree for op in planning.operations)
            makespans.append(makespan)

    print(f"\nBenchmark: {Path(chemin_instance).name}")
    print(f"  Temps moyen: {mean(temps_executions):.3f}s (±{stdev(temps_executions):.3f}s)")
    if makespans:
        print(f"  Makespan moyen: {mean(makespans):.1f} min (±{stdev(makespans):.1f} min)")
        print(f"  Makespan min/max: {min(makespans)}/{max(makespans)}")

# Benchmark toutes les instances
for instance_file in INSTANCES:
    benchmark_instance(str(instance_file))
```

## Notes importantes

### Compatibilité avec le code actuel

**ATTENTION**: Le fichier `dsl/schema/instance.py` définit actuellement le type d'objectifs comme
`list[MinimiserMakespan]` au lieu de `list[Objectif]`. Pour utiliser pleinement ces instances
avec objectifs variés, vous devrez mettre à jour cette ligne :

```python
# dsl/schema/instance.py - LIGNE 34
# AVANT:
objectifs: list[MinimiserMakespan] = Field(min_length=1)

# APRÈS:
from .objectifs_parametrables import Objectif
objectifs: list[Objectif] = Field(min_length=1)
```

### Régénération des instances

Pour régénérer toutes les instances (par exemple après modification des paramètres) :

```bash
python -m scripts.generer_instances_objectifs_varies
```

### Validation des instances

Pour valider que toutes les instances sont correctes :

```bash
python -m scripts.valider_instances_objectifs_varies
```

## Support et contribution

Ces instances sont maintenues dans le cadre du projet PRISME. Pour signaler un problème
ou proposer de nouvelles instances, consultez le `CONTRIBUTING.md` du projet.

## Licence

Ces instances de test font partie du projet PRISME (EIGSI Casablanca × BARAA Consult).
