# Référence des Objectifs Disponibles

Ce document détaille tous les types d'objectifs supportés par PRISME et leurs paramètres.

## 1. Minimiser le Makespan

**Type**: `minimiser_makespan`
**Catégorie**: Optimisation temporelle
**Description**: Minimise la durée totale du planning (date de fin de la dernière opération)

### Paramètres

```json
{
  "type": "minimiser_makespan",
  "poids": 1.0,                    // Importance relative (défaut: 1.0)
  "makespan_cible": 300,           // Makespan cible optionnel (défaut: null)
  "penalite_depassement": 2.0      // Pénalité par minute au-delà de la cible (défaut: 1.0)
}
```

### Exemple d'utilisation

```json
"objectifs": [
  {
    "type": "minimiser_makespan",
    "poids": 0.7,
    "makespan_cible": 480,
    "penalite_depassement": 1.5
  }
]
```

### Cas d'usage
- Planning de production avec délai de livraison fixe
- Optimisation du temps de cycle
- Minimisation du temps total d'atelier

---

## 2. Équilibrer la Charge

**Type**: `equilibrer_charge`
**Catégorie**: Optimisation des ressources
**Description**: Équilibre la charge de travail entre les ressources

### Paramètres

```json
{
  "type": "equilibrer_charge",
  "poids": 1.0,
  "methode": "ecart_max",          // "ecart_max" | "variance" | "gini"
  "ressources_cibles": ["R1", "R2"] // Liste optionnelle (défaut: toutes)
}
```

### Méthodes disponibles

| Méthode | Description | Avantages |
|---------|-------------|-----------|
| `ecart_max` | Minimise (max_charge - min_charge) | Simple, intuitif |
| `variance` | Minimise la variance des charges | Équilibrage global |
| `gini` | Minimise le coefficient de Gini | Mesure d'inégalité standard |

### Exemple d'utilisation

```json
"objectifs": [
  {
    "type": "equilibrer_charge",
    "poids": 0.6,
    "methode": "variance",
    "ressources_cibles": ["Machine1", "Machine2", "Machine3"]
  }
]
```

### Cas d'usage
- Éviter la surcharge de certaines ressources
- Distribution équitable du travail
- Optimisation de la durée de vie des équipements

---

## 3. Minimiser les Retards

**Type**: `minimiser_retards`
**Catégorie**: Respect des délais
**Description**: Minimise les retards par rapport aux échéances définies

### Paramètres

```json
{
  "type": "minimiser_retards",
  "poids": 1.0,
  "fonction_penalite": "lineaire",      // "lineaire" | "quadratique" | "exponentielle"
  "priorite_par_tache": {               // Poids par tâche (défaut: 1.0)
    "T1": 10.0,
    "T2": 5.0
  },
  "seuil_grace": 15                     // Minutes de grâce (défaut: 0)
}
```

### Fonctions de pénalité

| Fonction | Formule | Usage |
|----------|---------|-------|
| `lineaire` | pénalité = retard | Pénalité proportionnelle |
| `quadratique` | pénalité = retard² | Pénalise fortement les gros retards |
| `exponentielle` | pénalité = e^retard - 1 | Retards très courts acceptables |

### Exemple d'utilisation

```json
"objectifs": [
  {
    "type": "minimiser_retards",
    "poids": 0.8,
    "fonction_penalite": "quadratique",
    "priorite_par_tache": {
      "CommandeUrgente": 10.0,
      "CommandeStandard": 1.0
    },
    "seuil_grace": 10
  }
]
```

**Note**: Nécessite des contraintes d'échéance (`"type": "echeance"`) sur les tâches concernées.

### Cas d'usage
- Gestion de commandes urgentes
- Planning avec SLA (Service Level Agreement)
- Minimisation des pénalités de retard contractuelles

---

## 4. Maximiser l'Utilisation

**Type**: `maximiser_utilisation`
**Catégorie**: Optimisation des ressources
**Description**: Maximise le taux d'utilisation des ressources (minimise l'inactivité)

### Paramètres

```json
{
  "type": "maximiser_utilisation",
  "poids": 1.0,
  "ressources_prioritaires": ["R1"],    // Ressources à privilégier
  "penalite_inactivite_par_ressource": { // Pénalité par ressource (défaut: 1.0)
    "R1": 2.0,
    "R2": 1.0
  }
}
```

### Exemple d'utilisation

```json
"objectifs": [
  {
    "type": "maximiser_utilisation",
    "poids": 0.5,
    "ressources_prioritaires": ["MachineCouteuse"],
    "penalite_inactivite_par_ressource": {
      "MachineCouteuse": 3.0,
      "MachineStandard": 1.0
    }
  }
]
```

### Cas d'usage
- Amortissement d'équipements coûteux
- Maximisation du ROI
- Réduction des temps morts

---

## 5. Minimiser les Changements

**Type**: `minimiser_changements`
**Catégorie**: Optimisation de l'efficacité
**Description**: Minimise le nombre de changements de ressource entre tâches successives

### Paramètres

```json
{
  "type": "minimiser_changements",
  "poids": 1.0,
  "cout_changement_par_ressource": {    // Coût par ressource (défaut: 1.0)
    "R1": 2.0,
    "R2": 1.5
  },
  "cout_changement_par_paire": {        // Coût spécifique A→B
    "('R1', 'R2')": 3.0
  }
}
```

### Exemple d'utilisation

```json
"objectifs": [
  {
    "type": "minimiser_changements",
    "poids": 0.4,
    "cout_changement_par_ressource": {
      "CentreUsinage": 2.5,
      "PressePliage": 1.5
    }
  }
]
```

### Cas d'usage
- Réduction des temps de setup
- Minimisation des changements d'outils
- Production par lots/séries

---

## Objectifs Multiples

PRISME supporte la combinaison de plusieurs objectifs avec pondération.

### Exemple : Planning Industriel Complet

```json
"objectifs": [
  {
    "type": "minimiser_makespan",
    "poids": 0.3,
    "makespan_cible": 480
  },
  {
    "type": "minimiser_retards",
    "poids": 0.3,
    "fonction_penalite": "quadratique"
  },
  {
    "type": "equilibrer_charge",
    "poids": 0.2,
    "methode": "variance"
  },
  {
    "type": "maximiser_utilisation",
    "poids": 0.15,
    "ressources_prioritaires": ["MachinePremium"]
  },
  {
    "type": "minimiser_changements",
    "poids": 0.05
  }
]
```

### Pondération

- Les poids sont **relatifs** (pas besoin de sommer à 1.0)
- Un poids de 0.0 désactive l'objectif
- Les poids > 1.0 sont valides et augmentent l'importance

### Conflits potentiels

Certains objectifs peuvent être contradictoires :

| Objectif 1 | Objectif 2 | Conflit |
|------------|------------|---------|
| Minimiser makespan | Équilibrer charge | Élevé |
| Minimiser makespan | Minimiser changements | Moyen |
| Maximiser utilisation | Équilibrer charge | Faible |

**Recommandation**: Ajuster les poids pour trouver le bon compromis selon vos priorités métier.

---

## Extension : Objectifs Personnalisés

PRISME permet d'enregistrer des objectifs personnalisés via le `RegistryObjectifs`.

### Exemple : Objectif Coût Total

```python
from pydantic import BaseModel, Field
from typing import Literal
from dsl.schema.registry_objectifs import RegistryObjectifs

class MinimiserCoutTotal(BaseModel):
    type: Literal["minimiser_cout_total"] = "minimiser_cout_total"
    poids: float = Field(default=1.0, ge=0.0)
    cout_horaire_par_ressource: dict[str, float] = Field(default_factory=dict)
    cout_setup: float = Field(default=0.0, ge=0.0)

# Enregistrer l'objectif
RegistryObjectifs.enregistrer(
    "minimiser_cout_total",
    MinimiserCoutTotal,
    metadata={
        "categorie": "economique",
        "description": "Minimise le coût total de production"
    }
)
```

Usage dans une instance :

```json
"objectifs": [
  {
    "type": "minimiser_cout_total",
    "poids": 1.0,
    "cout_horaire_par_ressource": {
      "R1": 50.0,
      "R2": 35.0
    },
    "cout_setup": 100.0
  }
]
```

---

## Références

- Documentation DSL complète : `docs/dsl/`
- Exemples d'instances : `dsl/examples/objectifs_varies/`
- Code source des objectifs : `dsl/schema/objectifs_parametrables.py`
- Registry extensible : `dsl/schema/registry_objectifs.py`
