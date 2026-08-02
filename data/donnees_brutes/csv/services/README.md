# Services - Données CSV

Ce répertoire contient les données CSV pour 2 secteurs de services.

## Secteurs disponibles

### 1. Centre d'Appels (`centre_appels/`)

**Secteur**: Support client / Helpdesk

**Processus**: Réception → Qualification → Diagnostic → Escalade N2 → Résolution → Confirmation

**Caractéristiques**:
- 8 opérations
- 4 postes de travail (téléphonique N1/N2, CRM, support technique)
- Durées courtes (en heures, exprimées en fraction de jour)
- Escalade hiérarchique N1 → N2
- Durée totale: ~0.67 jour (16 heures)

**Fichiers**:
- `centre_appels_operations.csv`
- `centre_appels_postes.csv`

**Cas d'usage**: Tests durées courtes, workflows services, support client

**Particularités**:
- Durées fractionnaires (0.02j = 30min, 0.1j = 2h24)
- Escalade conditionnelle (certains tickets restent en N1)
- Utilisation intensive du CRM

---

### 2. Maintenance Industrielle (`maintenance_industrielle/`)

**Secteur**: Gestion de pannes et réparations

**Processus**: Diagnostic → Commande pièces → Démontage → Réparation → Tests → Remise en service

**Caractéristiques**:
- 7 opérations
- 5 postes de travail (équipes diagnostic, mécanique, tests, achats)
- Dépendance avec service achats (délai pièces)
- Durée totale: ~7 jours

**Fichiers**:
- `maintenance_industrielle_operations.csv`
- `maintenance_industrielle_postes.csv`

**Cas d'usage**: Tests dépendances externes, gestion urgence, GMAO

**Particularités**:
- Opération "Commande pièces" (2 jours) bloquante
- Parallélisme possible (diagnostic ∥ commande)
- Tests de validation obligatoires avant remise en service

---

## Format des fichiers

Même format que les autres secteurs:

### Fichier `*_operations.csv`

| Colonne | Type | Description | Exemple |
|---------|------|-------------|---------|
| `code_operation` | String | Identifiant unique | OP_001 |
| `duree_jours` | Float | Durée en jours (fraction = heures) | 0.1 |
| `poste_id` | String | Poste assigné | POSTE_TEL_N1 |
| `operation_precedente` | String | Précédence (vide si première) | OP_000 |

### Fichier `*_postes.csv`

| Colonne | Type | Description | Exemple |
|---------|------|-------------|---------|
| `code_poste` | String | Identifiant unique | POSTE_TEL_N1 |

## Statistiques

| Secteur | Opérations | Postes | Durée totale | Type durées |
|---------|------------|--------|--------------|-------------|
| Centre d'Appels | 8 | 4 | 0.67j (16h) | Fractionnaires |
| Maintenance Industrielle | 7 | 5 | 7j | Entières |

## Utilisation

### Import

```python
from adapters.csv_import.adapter import AdapterCSV

adapter = AdapterCSV()

# Centre d'appels (durées courtes)
instance_support = adapter.adapter_depuis_fichiers(
    "services/centre_appels/centre_appels_operations.csv",
    "services/centre_appels/centre_appels_postes.csv"
)

# Maintenance industrielle (durées longues)
instance_maintenance = adapter.adapter_depuis_fichiers(
    "services/maintenance_industrielle/maintenance_industrielle_operations.csv",
    "services/maintenance_industrielle/maintenance_industrielle_postes.csv"
)
```

## Différences avec l'industrie

### Centre d'Appels vs Production

| Aspect | Centre d'Appels | Production Manufacturière |
|--------|----------------|---------------------------|
| **Durées** | Heures (0.02 → 0.2j) | Jours (1 → 5j) |
| **Ressources** | Humaines (agents) | Machines/Équipements |
| **Flux** | Variable (tickets) | Linéaire (produits) |
| **Parallélisme** | Élevé (multi-tickets) | Faible (chaîne) |

### Maintenance vs Fabrication

| Aspect | Maintenance | Fabrication |
|--------|-------------|-------------|
| **Déclenchement** | Réactif (panne) | Planifié |
| **Dépendances** | Externes (pièces) | Internes |
| **Ressources** | Polyvalentes | Spécialisées |
| **Contraintes** | Urgence (SLA) | Qualité |

## Cas d'usage spécifiques

### Centre d'Appels

✅ **Tests**:
- Durées fractionnaires (< 1 jour)
- SLA (temps de résolution)
- Affectation dynamique (N1 → N2)

✅ **Démonstrations**:
- Workflows services
- Escalade hiérarchique
- Gestion de la charge

### Maintenance Industrielle

✅ **Tests**:
- Dépendances externes (délai pièces)
- Parallélisme (diagnostic ∥ commande)
- Validation avant clôture

✅ **Démonstrations**:
- GMAO (Gestion Maintenance Assistée par Ordinateur)
- Gestion d'urgence
- Traçabilité interventions

## Notes techniques

### Durées fractionnaires (Centre d'Appels)

Les durées sont exprimées en jours pour homogénéité, mais représentent des heures:

| Valeur CSV | Durée réelle |
|------------|--------------|
| 0.02 | 30 minutes |
| 0.05 | 1h12 |
| 0.1 | 2h24 |
| 0.15 | 3h36 |
| 0.2 | 4h48 |

### Dépendances externes (Maintenance)

L'opération "Commande pièces" simule une contrainte externe:
- Durée fixe de 2 jours (délai fournisseur)
- Peut être parallélisée avec le diagnostic approfondi
- Bloquante pour la réparation effective

## Extension

Pour ajouter un nouveau secteur de services:

1. Créer un sous-dossier `nouveau_service/`
2. Créer les 2 fichiers CSV
3. Adapter les durées (heures → fraction de jour si besoin)
4. Documenter les spécificités

**Exemples de nouveaux services**:
- Hôpital (parcours patient)
- Restauration (service repas)
- Logistique (préparation commande)
- Formation (parcours pédagogique)

---

**Retour**: [../README.md](../README.md) - Documentation CSV générale
