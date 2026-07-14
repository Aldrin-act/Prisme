# Règles de correspondance — ERP de référence → T-R-C-O (§5.4)

| Format ERP (propriétaire)              | T-R-C-O (canonique)                                              |
|-----------------------------------------|-------------------------------------------------------------------|
| `OperationERP.code_operation`            | `Tache.id`                                                        |
| `OperationERP.duree_minutes`             | `CompatibiliteMachineTache.duree`                                 |
| `OperationERP.poste_id`                  | `CompatibiliteMachineTache.ressource` (une seule, forcée)          |
| `OperationERP.operation_precedente`      | `Precedence.avant` (si non nul) → `Precedence.apres = code_operation` |
| `PosteERP.code_poste`                    | `Ressource.id`                                                    |
| *(aucun champ ERP)*                      | `Objectif` → toujours `MinimiserMakespan()` (l'ERP n'a pas la notion) |

Perte d'expressivité assumée dans un sens (ERP → T-R-C-O) : l'ERP ne connaît
qu'un poste par opération, jamais plusieurs postes compatibles. La
traduction produit donc une `CompatibiliteMachineTache` unique par tâche —
un cas particulier valide du noyau T-R-C-O, qui sait représenter des
compatibilités multiples même si cet ERP précis ne les fournit jamais.
