# Atelier Mécanique - CSV

Données CSV pour un atelier de fabrication métallique.

## Fichiers

- **atelier_mecanique_operations.csv** - 8 opérations de fabrication
- **atelier_mecanique_postes.csv** - 8 postes/machines

## Processus de fabrication

```
Découpe → Perçage → Pliage → Soudure → Peinture → Contrôle
```

### Détail des opérations

| Code | Opération | Poste | Durée | Précédente |
|------|-----------|-------|-------|------------|
| OP_DEC | Découpe | Découpeuse laser | 1j | - |
| OP_PER | Perçage | Perceuse CNC | 1j | OP_DEC |
| OP_PLI | Pliage | Presse plieuse | 1j | OP_PER |
| OP_SOU_MIG | Soudure MIG | Poste soudure MIG | 2j | OP_PLI |
| OP_SOU_TIG | Soudure TIG (alternative) | Poste soudure TIG | 2.5j | OP_PLI |
| OP_PEI | Peinture | Cabine peinture | 1j | OP_SOU_* |
| OP_SEC | Séchage | Tunnel séchage | 2j | OP_PEI |
| OP_CTR | Contrôle qualité | Station contrôle | 1j | OP_SEC |

**Durée totale**: ~12 jours (chemin critique: découpe → perçage → pliage → soudure TIG → peinture → séchage → contrôle)

## Particularités

### Soudure avec alternatives
L'opération de soudure offre **2 alternatives**:
- **MIG** (Metal Inert Gas): Plus rapide (2j)
- **TIG** (Tungsten Inert Gas): Plus lent mais meilleure qualité (2.5j)

Le choix dépend des exigences qualité du produit.

### Ressources partagées
- **Tunnel de séchage**: Utilisé après peinture, peut créer un goulot d'étranglement si plusieurs pièces

## Cas d'usage

✅ **Formation** - Exemple classique de fabrication métallique
✅ **Démonstration** - Flux linéaire simple à comprendre
✅ **Tests** - Alternatives de soudure, choix de ressource

## Import

```python
from adapters.csv_import.adapter import AdapterCSV

adapter = AdapterCSV()
instance = adapter.adapter_depuis_fichiers(
    "industrie_manufacturiere/atelier_mecanique/atelier_mecanique_operations.csv",
    "industrie_manufacturiere/atelier_mecanique/atelier_mecanique_postes.csv"
)
```
