# Rapport — données GreenSIG à travers le DSL T-R-C-O

Généré le 2026-07-17 09:52 UTC depuis `db_greensig` (`adapters/greensig/extraction.py` → `adapters/greensig/translator.py`). Détail par tâche : [`rapport_dsl.csv`](rapport_dsl.csv).

## Résumé

| | |
|---|---:|
| Tâches actives extraites | 1007 |
| Traduisibles (≥1 ressource compatible) | 997 |
| &nbsp;&nbsp;dont par compétence (type de tâche mappé) | 707 |
| &nbsp;&nbsp;dont par affectation historique (fallback, type non mappé) | 290 |
| Rejetées (aucune ressource compatible) | 10 |
| Taux de rejet | 1% |

## Traduction du lot brut complet (comportement réel du système)

`api/routes/adapters.py` (`POST /adapters/greensig/ingerer`) tente exactement cette traduction, sans filtrage — une seule tâche sans compatibilité suffit à faire rejeter tout le lot par `InstanceTRCO` (garde-fou §6.7, `adapters/greensig/mapping/regles.md` limite 3). Décision explicite : ne jamais ingérer un sous-ensemble silencieusement tronqué.

**Résultat : rejetée — 1 violation(s), voir détail dans le rapport.**

<details><summary>Détail de l'erreur de validation</summary>

```
1 validation error for InstanceTRCO
  Value error, tâche(s) sans aucune contrainte de compatibilité ressource-tâche déclarée : ['T1407', 'T1409', 'T1410', 'T1419', 'T1458', 'T1465', 'T268', 'T287', 'T3040', 'T741'] [type=value_error, input_value={'taches': [Tache(id='T25...='minimiser_makespan')]}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/value_error
```

</details>

## Rejets par type de tâche

| Type de tâche | Tâches rejetées |
|---|---:|
| Fertilisation chimique | 2 |
| Arrachage des plantes mortes | 1 |
| Taille de formation | 1 |
| Taille d'entretien des arbustes | 1 |
| Désherbage chimique | 1 |
| Élagage | 1 |
| Terreautage | 1 |
| Traitement | 1 |
| Taille d'entretien | 1 |

## Instance T-R-C-O illustrative (sous-ensemble traduisible)

**Jamais ce que le système ingère réellement** — construite ici uniquement pour montrer la forme de l'InstanceTRCO obtenue une fois les tâches sans ressource compatible écartées.

| | |
|---|---:|
| Tâches | 997 |
| Ressources (équipes) | 26 |
| Contraintes de compatibilité ressource-tâche | 10713 |
| Contraintes de précédence | 0 (GreenSIG n'en produit jamais, voir regles.md) |
| Objectif | minimiser_makespan |
