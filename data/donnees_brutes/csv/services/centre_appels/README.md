# Centre d'Appels - CSV

Données CSV pour un centre de support client avec escalade N1/N2.

## Fichiers

- **centre_appels_operations.csv** - 8 opérations de traitement
- **centre_appels_postes.csv** - 4 postes de travail

## Processus de traitement

```
Réception → Qualification → Diagnostic → Escalade N2 → Résolution → Suivi → Clôture → Confirmation
```

### Détail des opérations

| Code | Opération | Poste | Durée (jours) | Durée (heures) |
|------|-----------|-------|---------------|----------------|
| OP_REC | Réception appel | Téléphonique N1 | 0.02 | ~30min |
| OP_QUA | Qualification demande | CRM | 0.05 | ~1h12 |
| OP_DIA | Diagnostic technique | Support N1 | 0.1 | ~2h24 |
| OP_ESC | Escalade niveau 2 | Support N2 | 0.15 | ~3h36 |
| OP_RES | Résolution | Support N2 | 0.2 | ~4h48 |
| OP_SUI | Suivi post-résolution | CRM | 0.05 | ~1h12 |
| OP_CLO | Clôture ticket | CRM | 0.03 | ~45min |
| OP_CNF | Confirmation client | Téléphonique N2 | 0.05 | ~1h12 |

**Durée totale**: ~0.67 jour (~16 heures)

## Particularités

### Durées fractionnaires
Les durées sont exprimées en **fraction de jour** car les opérations sont courtes (minutes/heures):
- 0.02 jour ≈ 30 minutes
- 0.1 jour ≈ 2h24

### Escalade hiérarchique
Workflow typique:
1. **N1** (téléphonique) → Réception + Qualification + Diagnostic simple
2. **Escalade N2** si problème complexe
3. **N2** (expert) → Résolution + Confirmation

### Utilisation du CRM
Le CRM (Customer Relationship Management) est utilisé à 3 moments:
- Qualification (création fiche client)
- Suivi (mise à jour statut)
- Clôture (archivage ticket)

## Cas d'usage

✅ **Tests durées courtes** - Opérations en heures/minutes
✅ **Workflows services** - Processus métier non-industriel
✅ **Escalade** - Flux hiérarchique N1 → N2
✅ **SLA** - Temps de résolution à respecter

## Import

```python
from adapters.csv_import.adapter import AdapterCSV

adapter = AdapterCSV()
instance = adapter.adapter_depuis_fichiers(
    "services/centre_appels/centre_appels_operations.csv",
    "services/centre_appels/centre_appels_postes.csv"
)
```

## Notes

- Les durées courtes peuvent nécessiter une précision supplémentaire lors de la planification
- Le parallélisme est possible (traiter plusieurs tickets en même temps)
- Le CRM est une ressource partagée critique
