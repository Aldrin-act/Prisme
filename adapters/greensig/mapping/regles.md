# Règles de correspondance — GreenSIG → T-R-C-O (§5.4)

| Format GreenSIG (propriétaire)                                          | T-R-C-O (canonique)                                                        |
|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `api_planification_tache.id` (`deleted_at IS NULL`)                       | `Tache.id` (préfixé `T` — ex. `id=1` → `"T1"`)                              |
| `api_users_equipe.id` (`actif = true`)                                    | `Ressource.id` (préfixé `E` — ex. `id=100` → `"E100"`)                      |
| `api_planification_tache_equipes` (association tâche↔équipe)              | `CompatibiliteMachineTache` — une par couple (tâche, équipe affectée)       |
| `api_planification_tache.charge_estimee_heures × 60`                      | `CompatibiliteMachineTache.duree` (identique pour chaque équipe compatible) |
| *(absent si `charge_estimee_heures` est `NULL`)*                          | `CompatibiliteMachineTache.duree = 30` (valeur par défaut, `_DUREE_PAR_DEFAUT_MINUTES`) |
| *(aucune colonne)*                                                        | `Precedence` → jamais produite (voir limite 1 ci-dessous)                   |
| *(aucun champ GreenSIG)*                                                  | `Objectif` → toujours `MinimiserMakespan()` (GreenSIG n'a pas la notion)    |

## Champs GreenSIG délibérément ignorés

Aucun équivalent en T-R-C-O aujourd'hui (§4.1 "Minimal viable core") :
`priorite`, `date_echeance`, `date_debut_planifiee`/`date_fin_planifiee`,
`statut`, `note_qualite`, `etat_validation`, `id_type_tache_id` (le type de
tâche influence la durée seulement à travers `charge_estimee_heures`, pas
directement), et tout ce qui touche aux opérateurs individuels (`api_users_operateur`) —
seule l'équipe (`api_users_equipe`) est traitée comme ressource planifiable.

## Filtrage en amont de la traduction

- Tâches avec `deleted_at` renseigné → exclues (suppression logique GreenSIG,
  aucun sens côté canonique).
- Équipes avec `actif = false` → exclues ; toute association vers une équipe
  inactive dans `api_planification_tache_equipes` est silencieusement ignorée.

## Pertes d'expressivité assumées (GreenSIG → T-R-C-O)

1. **Pas de précédence entre tâches.** Le schéma ne porte aucune colonne de
   ce type sur `api_planification_tache` : `chaine_report_id`/
   `ordre_dans_chaine` (sur `api_planification_distributioncharge`)
   modélisent les *reports* d'une même distribution de charge dans le temps,
   pas un ordre d'exécution entre deux tâches distinctes — utiliser ces
   champs comme `Precedence` serait une fausse équivalence. Un ERP plus
   riche pourrait fournir cet axe ; celui-ci ne le peut pas.
2. **Durée uniforme par tâche, pas par couple (tâche, équipe).**
   `charge_estimee_heures` est une charge globale sur la tâche ; GreenSIG ne
   stocke aucune productivité par équipe (`api_planification_ratioproductivite`
   est indexée par `type_objet`, pas par équipe). La traduction applique donc
   la même durée à chaque équipe compatible — un cas particulier valide du
   noyau T-R-C-O (qui sait représenter des durées différentes par ressource),
   mais que cet ERP précis ne peut pas exploiter pleinement.
3. **Tâche sans équipe active affectée → rejet, pas d'invention.** Si
   `api_planification_tache_equipes` ne référence aucune équipe active pour
   une tâche non supprimée, `traduire()` produit quand même la `Tache` mais
   aucune `CompatibiliteMachineTache` associée ; `InstanceTRCO` la rejette
   alors via le garde-fou §6.7 ("chaque tâche doit avoir ≥1 compatibilité").
   C'est volontaire — mieux vaut un rejet explicite côté appelant qu'une
   compatibilité fictive.
