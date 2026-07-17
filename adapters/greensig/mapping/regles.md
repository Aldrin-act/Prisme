# Règles de correspondance — GreenSIG → T-R-C-O (§5.4)

| Format GreenSIG (propriétaire)                                          | T-R-C-O (canonique)                                                        |
|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `api_planification_tache.id` (`deleted_at IS NULL`)                       | `Tache.id` (préfixé `T` — ex. `id=1` → `"T1"`)                              |
| `api_users_equipe.id` (`actif = true`)                                    | `Ressource.id` (préfixé `E` — ex. `id=100` → `"E100"`)                      |
| `api_users_competenceoperateur`/`api_users_operateur.equipe_id`, via `mapping/competences_types_tache.py` (type de tâche mappé) | `CompatibiliteRessourceTache` — une par équipe ayant ≥1 opérateur qualifié (voir "Compatibilité par compétence" ci-dessous) |
| `api_planification_tache_equipes` (type de tâche **non** mappé — fallback) | `CompatibiliteRessourceTache` — une par couple (tâche, équipe affectée)       |
| `api_planification_tache.charge_estimee_heures × 60`                      | `CompatibiliteRessourceTache.duree` (identique pour chaque équipe compatible) |
| *(absent si `charge_estimee_heures` est `NULL` ou `0`)*                   | `CompatibiliteRessourceTache.duree = 30` (valeur par défaut, `_DUREE_PAR_DEFAUT_MINUTES`) |
| *(`charge_estimee_heures` non nulle mais arrondissant à 0 minute)*        | `CompatibiliteRessourceTache.duree = 1` (plancher, `_DUREE_MINIMALE_MINUTES` — observé sur données réelles : ex. `0.00064h`, quelques secondes) |
| *(aucune colonne)*                                                        | `Precedence` → jamais produite (voir limite 1 ci-dessous)                   |
| *(aucun champ GreenSIG)*                                                  | `Objectif` → toujours `MinimiserMakespan()` (GreenSIG n'a pas la notion)    |

## Champs GreenSIG délibérément ignorés

Aucun équivalent en T-R-C-O aujourd'hui (§4.1 "Minimal viable core") :
`priorite`, `date_echeance`, `date_debut_planifiee`/`date_fin_planifiee`,
`statut`, `note_qualite`, `etat_validation`. `id_type_tache_id` influence
toujours la durée seulement à travers `charge_estimee_heures`, pas
directement — mais il pilote désormais aussi la compatibilité quand un
mapping existe (voir ci-dessous). `api_users_operateur` n'est plus ignoré
en bloc : les opérateurs ne deviennent jamais des `Ressource` individuelles
(seule l'équipe l'est), mais leurs compétences déterminent quelle équipe est
compatible avec quel type de tâche.

## Compatibilité par compétence, pas par affectation historique

**Principe :** la compatibilité tâche-ressource doit refléter qui **sait
faire** un travail, pas qui l'a fait par le passé. Une affectation
historique (`api_planification_tache_equipes`) ne prouve pas la compétence
(l'équipe a pu être affectée par défaut, en dépannage...) et son absence ne
prouve pas l'incompétence (le type de tâche n'a peut-être simplement jamais
été confié à personne dans la fenêtre de données extraite).

**Mise en œuvre :** `adapters/greensig/mapping/competences_types_tache.py`
définit `COMPETENCES_PAR_TYPE_TACHE : dict[id_type_tache, frozenset[id_competence]]`.
Pour un type de tâche présent dans ce mapping, `translator.traduire`
détermine la compatibilité **exclusivement** par compétence (une équipe est
compatible si ≥1 de ses opérateurs actifs détient une des compétences
mappées) — l'affectation historique est ignorée pour ce type, même si une
équipe non qualifiée a été affectée par le passé.

**Table actuelle (7 types sur 41 — le reste n'a pas de correspondance
compétence évidente dans le catalogue GreenSIG et retombe sur l'affectation
historique, comportement inchangé pour eux) :**

| `id_type_tache` | nom_tache | compétence(s) GreenSIG (traitées comme synonymes) |
|---|---|---|
| 1 | Nettoyage | 23 "Nettoyage général", 11 "Nettoyage general" (doublon accent/typo) |
| 2 | Binage | 21 "Binage", 5 "Binage des sols" |
| 3 | Confection des cuvettes | 6 "Confection des cuvettes" |
| 5 | Arrosage | 9 "Arrosage" |
| 18 | Tonte | 17 "Tondeuse", 1 "Utilisation de tondeuse" |
| 20 | Désherbage | 20 "Désherbage", 4 "Desherbage manuel et mecanique" |
| 136 | Taille de décoration | 22 "Taille de décoration", 8 "Taille de decoration" (doublon accent) |

Curatée à la main sur `backup_20260503.sql`, **pas un matching automatique
par similarité de nom** — un rapprochement par texte serait le même risque
d'hallucination que celui diagnostiqué côté `agent_comprehension`, juste
déplacé en Python. Traiter les paires "doublon" ci-dessus comme des
synonymes d'une même compétence réelle est une hypothèse, à confirmer avec
l'équipe GreenSIG, pas une certitude métier — documentée telle quelle dans
le module de mapping. Les ~34 types restants (Élagage, Fertilisation
chimique, Taille de formation, Terreautage, Tuteurage, Sablage...) n'ont pas
de correspondance évidente dans le catalogue de 30 compétences actuel ; à
compléter par un futur retour métier, jamais par une supposition de ma part.

## Filtrage en amont de la traduction

- Tâches avec `deleted_at` renseigné → exclues (suppression logique GreenSIG,
  aucun sens côté canonique).
- Équipes avec `actif = false` → exclues ; toute association vers une équipe
  inactive dans `api_planification_tache_equipes` est silencieusement ignorée.
- Opérateurs avec `statut != 'ACTIF'` → exclus dès `extraction.py` (côté SQL).
- Compétences avec `niveau = 'NON'` → exclues dès `extraction.py` : ce
  niveau signifie explicitement "n'a pas cette compétence", pas une absence
  de donnée à ignorer par défaut.

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
3. **Tâche sans ressource compatible identifiée → rejet, pas d'invention.**
   Si aucune équipe compétente (type mappé) ni aucune équipe active affectée
   (type non mappé, fallback) n'est trouvée pour une tâche non supprimée,
   `traduire()` produit quand même la `Tache` mais aucune
   `CompatibiliteRessourceTache` associée ; `InstanceTRCO` la rejette alors via
   le garde-fou §6.7 ("chaque tâche doit avoir ≥1 compatibilité"). C'est
   volontaire — mieux vaut un rejet explicite côté appelant qu'une
   compatibilité fictive, que le signal manquant soit une compétence ou une
   affectation historique.
