# Assemblage Électronique - CSV

Données CSV pour la fabrication de cartes électroniques (PCB).

## Fichiers

- **assemblage_electronique_operations.csv** - 10 opérations de production
- **assemblage_electronique_postes.csv** - 9 postes/machines

## Processus de fabrication

```
Pose CMS Face A → Soudure Refusion → AOI →
Retournement →
Pose CMS Face B → Soudure Refusion → AOI →
Tests → Conditionnement
```

### Détail des opérations

| Code | Opération | Poste | Durée | Phase |
|------|-----------|-------|-------|-------|
| OP_CMS_A | Pose composants CMS face A | Pick & Place | 1j | Face A |
| OP_REF_A | Soudure refusion face A | Four refusion | 0.5j | Face A |
| OP_AOI_A | Inspection optique face A | AOI automatique | 0.3j | Face A |
| OP_RET | Retournement PCB | Poste retournement | 0.1j | Transition |
| OP_CMS_B | Pose composants CMS face B | Pick & Place | 1j | Face B |
| OP_REF_B | Soudure refusion face B | Four refusion | 0.5j | Face B |
| OP_AOI_B | Inspection optique face B | AOI automatique | 0.3j | Face B |
| OP_TST | Tests fonctionnels | Banc de test | 0.5j | Validation |
| OP_EMB | Emballage | Poste emballage | 0.2j | Finition |

**Durée totale**: ~6 jours

## Particularités

### Production double face
Les PCB modernes ont des composants des **deux côtés**:
1. **Face A** (composants principaux): Pose → Soudure → Inspection
2. **Retournement** obligatoire
3. **Face B** (composants secondaires): Même processus

### Inspection automatique (AOI)
L'AOI (Automatic Optical Inspection) détecte les défauts automatiquement:
- Composants manquants
- Mauvaise orientation
- Soudures défectueuses
- Pas d'intervention humaine

### Tests fonctionnels
Après assemblage complet, un banc de test vérifie:
- Alimentation électrique
- Signaux I/O
- Fonctionnalités principales

## Cas d'usage

✅ **Benchmark performance** - 10 opérations, graphe riche
✅ **Tests qualité** - Inspection automatique + tests
✅ **Industrie 4.0** - Automatisation poussée

## Import

```python
from adapters.csv_import.adapter import AdapterCSV

adapter = AdapterCSV()
instance = adapter.adapter_depuis_fichiers(
    "industrie_manufacturiere/assemblage_electronique/assemblage_electronique_operations.csv",
    "industrie_manufacturiere/assemblage_electronique/assemblage_electronique_postes.csv"
)
```
