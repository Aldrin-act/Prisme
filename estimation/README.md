# estimation — Estimation de durée par apprentissage supervisé

Implémente MT3 du plan directeur initial (écarté puis reformulé, `docs/
contexte_general.md` §3.3.2) : un modèle prédit la durée d'une opération à
partir de traits tâche/ressource, pour combler les cas où aucune durée n'a
été déclarée ni dérivée par compétence — jamais pour remplacer une donnée
déjà déclarée.

- `donnees_historique.py` — `ObservationDuree`, `historique_synthetique()` :
  données d'entraînement **synthétiques**, dérivées du banc de l'Étape 3
  (`validation_engine/synthetic_bench/`). Aucune donnée de durée réellement
  observée n'existe nulle part dans PRISME aujourd'hui (ni en base, ni dans
  l'ERP réel GreenSIG — voir `docs/perspective_estimation_charge.md`) ; ce
  module ne prétend pas le contraire. Il calcule une « durée observée »
  comme une fonction connue des traits (quantité, priorité, type de
  ressource, compétences) plus un petit résidu déterministe — un signal
  vérifiable, dans le même esprit que `construction_inverse.py`, qui prouve
  l'optimalité d'un planning synthétique sans jamais faire tourner de
  solveur.
- `modele.py` — `EstimateurDuree` (`entrainer`/`estimer`, un
  `GradientBoostingRegressor` scikit-learn), `EstimationDuree` (résultat,
  jamais directement un `CompatibiliteRessourceTache`), et
  `vers_durees_estimees_par_tache` (convertit vers la forme attendue par
  `adapters/competence_derivation.py::deriver_compatibilites_par_competence`,
  ne retient que les estimations dont la confiance dépasse un seuil).

## Pourquoi scikit-learn plutôt que XGBoost

Le plan directeur initial citait les deux. `scikit-learn` évite une
dépendance à une toolchain compilée séparée en plus de `numpy` (extra
`estimation` de `pyproject.toml`) pour la même famille de méthode (boosting
de gradient) — un choix pragmatique, pas une limite du modèle retenu.

## Pourquoi le modèle n'utilise pas la durée déjà déclarée comme trait

Une première version faisait apprendre au modèle une « correction » d'une
durée déjà déclarée. Ce cadrage ne tient pas dans le cas d'usage réel de ce
module — combler une durée *manquante* (`adapters/csv_import/`,
`adapters/json_import/`) — puisqu'il n'y a alors justement aucune durée
déclarée à corriger. Le modèle apprend donc uniquement à partir des traits
tâche/ressource (`quantite`, `priorite`, `type`, nombre de compétences),
un problème plus honnête et directement applicable au cas réel où
l'estimation est sollicitée.

## Garde-fou : décision humaine préservée (FC4, §1.6)

`adapters/csv_import/traducteur.py` et `adapters/json_import/traducteur.py`
acceptent un paramètre optionnel `estimateur_duree`. Quand il est fourni et
qu'une tâche à compétence requise n'a aucune durée connue,
`adapters/competence_derivation.py::completer_durees_par_estimation` comble
le trou — mais `traduire()` retourne désormais un
`ResultatTraduction(instance, avertissements)` plutôt qu'une `InstanceTRCO`
nue : chaque durée comblée par le modèle ajoute un avertissement explicite,
visible par l'appelant (dashboard/API), jamais une estimation qui se fait
passer pour un fait déclaré.

## Limite assumée

Sans mécanisme de capture de durée réellement observée (voir
`docs/perspective_estimation_charge.md`), ce module s'entraîne et se valide
sur du synthétique — la `confiance` qu'il rapporte mesure un ajustement à ce
synthétique, pas une garantie sur des données réelles jamais vues. Il reste
branchable tel quel le jour où un historique réel existera : seule la source
des `ObservationDuree` changerait (`historique_synthetique()` remplacée par
une lecture de l'historique réel), jamais l'API du module.
