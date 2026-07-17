# Rapport — données GreenSIG à travers le DSL T-R-C-O

Généré le 2026-07-16 12:49 UTC depuis `db_greensig` (`adapters/greensig/extraction.py` → `adapters/greensig/translator.py`). Détail par tâche : [`rapport_dsl.csv`](rapport_dsl.csv).

## Résumé

| | |
|---|---:|
| Tâches actives extraites | 1007 |
| Traduisibles (≥1 équipe active) | 779 |
| Rejetées (aucune équipe active) | 228 |
| Taux de rejet | 23% |

## Traduction du lot brut complet (comportement réel du système)

`api/routes/adapters.py` (`POST /adapters/greensig/ingerer`) tente exactement cette traduction, sans filtrage — une seule tâche sans compatibilité suffit à faire rejeter tout le lot par `InstanceTRCO` (garde-fou §6.7, `adapters/greensig/mapping/regles.md` limite 3). Décision explicite : ne jamais ingérer un sous-ensemble silencieusement tronqué.

**Résultat : rejetée — 1 violation(s), voir détail dans le rapport.**

<details><summary>Détail de l'erreur de validation</summary>

```
1 validation error for InstanceTRCO
  Value error, tâche(s) sans aucune contrainte de compatibilité ressource-tâche déclarée : ['T1197', 'T1216', 'T1217', 'T1218', 'T1219', 'T1220', 'T1221', 'T1222', 'T1223', 'T1224', 'T1225', 'T1226', 'T1227', 'T1228', 'T1229', 'T1230', 'T1231', 'T1232', 'T1233', 'T1234', 'T1235', 'T1236', 'T1237', 'T1238', 'T1239', 'T1240', 'T1241', 'T1242', 'T1243', 'T1244', 'T1245', 'T1246', 'T1249', 'T1250', 'T1251', 'T1272', 'T1273', 'T1274', 'T1275', 'T1276', 'T1277', 'T1278', 'T1279', 'T1280', 'T1281', 'T1282', 'T1283', 'T1284', 'T1285', 'T1286', 'T1287', 'T1288', 'T1289', 'T1290', 'T1291', 'T1292', 'T1293', 'T1294', 'T1295', 'T1296', 'T1297', 'T1298', 'T1407', 'T1409', 'T1410', 'T1418', 'T1419', 'T1420', 'T1421', 'T1422', 'T1423', 'T1424', 'T1434', 'T1439', 'T1444', 'T1445', 'T1446', 'T1447', 'T1454', 'T1458', 'T1459', 'T1465', 'T1467', 'T1526', 'T163', 'T176', 'T1874', 'T1875', 'T1877', 'T1878', 'T1879', 'T1887', 'T194', 'T203', 'T204', 'T205', 'T206', 'T207', 'T208', 'T209', 'T211', 'T212', 'T215', 'T216', 'T217', 'T218', 'T219', 'T220', 'T221', 'T222', 'T223', 'T263', 'T264', 'T265', 'T268', 'T287', 'T296', 'T304', 'T3040', 'T305', 'T307', 'T308', 'T458', 'T459', 'T460', 'T461', 'T462', 'T463', 'T464', 'T465', 'T466', 'T467', 'T468', 'T604', 'T605', 'T606', 'T607', 'T608', 'T609', 'T610', 'T611', 'T612', 'T613', 'T614', 'T615', 'T616', 'T617', 'T618', 'T619', 'T620', 'T621', 'T622', 'T623', 'T624', 'T625', 'T626', 'T627', 'T628', 'T629', 'T630', 'T631', 'T632', 'T633', 'T634', 'T635', 'T636', 'T637', 'T638', 'T639', 'T640', 'T641', 'T642', 'T643', 'T644', 'T645', 'T646', 'T647', 'T648', 'T649', 'T650', 'T651', 'T652', 'T653', 'T654', 'T655', 'T656', 'T657', 'T658', 'T659', 'T660', 'T661', 'T662', 'T663', 'T664', 'T665', 'T666', 'T667', 'T668', 'T669', 'T670', 'T671', 'T672', 'T673', 'T674', 'T675', 'T676', 'T677', 'T678', 'T679', 'T680', 'T681', 'T682', 'T683', 'T684', 'T685', 'T686', 'T687', 'T688', 'T689', 'T690', 'T691', 'T692', 'T693', 'T723', 'T724', 'T725', 'T741', 'T743'] [type=value_error, input_value={'taches': [Tache(id='T25...='minimiser_makespan')]}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/value_error
```

</details>

## Rejets par type de tâche

| Type de tâche | Tâches rejetées |
|---|---:|
| Nettoyage | 113 |
| Désherbage | 43 |
| Tonte | 31 |
| Confection des cuvettes | 23 |
| Binage | 8 |
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

**Jamais ce que le système ingère réellement** — construite ici uniquement pour montrer la forme de l'InstanceTRCO obtenue une fois les tâches sans équipe active écartées.

| | |
|---|---:|
| Tâches | 779 |
| Ressources (équipes) | 26 |
| Contraintes de compatibilité ressource-tâche | 779 |
| Contraintes de précédence | 0 (GreenSIG n'en produit jamais, voir regles.md) |
| Objectif | minimiser_makespan |
