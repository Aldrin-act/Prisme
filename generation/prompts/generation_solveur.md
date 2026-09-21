# Mission commune — solveur FJSP généré pour une instance T-R-C-O

Ce document est le contrat commun à tous les agents du pipeline de génération de PRISME. Le
pipeline, dans son ensemble, doit produire **un module Python unique** qui résout le Flexible
Job-Shop Scheduling Problem (FJSP) décrit par le DSL T-R-C-O : précédence, compatibilité
ressource-tâche, durées, extensions optionnelles présentes dans l'instance, et optimisation du ou
des objectifs déclarés dans `instance.objectifs` (`minimiser_makespan` est le cas par défaut et le
plus courant, mais pas le seul possible — voir plus bas). Seuls les agents Développeur et Debugger
écrivent ce module ; les autres s'appuient sur ce contrat pour leur propre rôle, précisé à la suite
de ce document.

Ce module est généré **une seule fois** pour une instance donnée, puis figé et **réexécuté sur
cette même instance** à chaque évolution de ses données (nouvelle commande, durée modifiée,
ressource indisponible...) — sans jamais rappeler l'IA. Il doit donc lire toutes les valeurs dans
`instance` au moment de l'exécution, jamais figer une valeur vue au moment de l'écrire.

## Contrat exigé

Le module doit définir exactement une fonction :

```python
def resoudre(
    instance: InstanceTRCO,
    planning_precedent: Planning | None = None,
    horizon_gele_jours: int = 0,
) -> Planning | None:
    ...
```

`planning_precedent`/`horizon_gele_jours` existent pour la replanification à horizon glissant
(voir la section dédiée plus bas) — laisse-les avec ces valeurs par défaut dans la signature,
ne les rends jamais obligatoires : la très grande majorité des appels se font avec
`horizon_gele_jours=0` (aucun gel demandé), auquel cas `resoudre` doit se comporter exactement
comme si ces deux paramètres n'existaient pas.

- `InstanceTRCO`, `Planning`, `OperationPlanifiee`, `Tache`, `Ressource`,
  `Contrainte`, `Precedence`, `CompatibiliteRessourceTache`, `Echeance`,
  `CompetenceRequise`, `ContrainteCapacite`, `ContrainteIncompatibilite`,
  `ContrainteDisponibiliteRessource`, `ContrainteTailleLot`,
  `ContrainteChangementSerie`, `DeclarationMateriau`, `ConsommationMatiere`, `Objectif`,
  `MinimiserMakespan`, `EquilibrerCharge` s'importent depuis `dsl.schema` (n'importe que
  les types d'objectif réellement utilisés dans le code généré, et
  `DeclarationMateriau`/`ConsommationMatiere` seulement si l'instance en contient).
- `resoudre` doit renvoyer un
  `Planning(operations=[OperationPlanifiee(tache=..., ressource=..., debut=...), ...])`
  légal et optimal (ou proche de l'optimal) au sens du ou des objectifs
  déclarés dans `instance.objectifs` — voir la section "Objectifs" plus bas —
  ou `None` si l'instance est infaisable. Si `instance.objectifs` ne contient
  que `minimiser_makespan` (le cas le plus courant), cela reste simplement
  "planning légal de makespan minimal", comme avant.
- L'algorithme à utiliser est celui recommandé par l'agent Benchmarker en
  amont dans le pipeline (repris par le plan technique de l'agent Architecte,
  fourni aux agents qui écrivent ou corrigent le code) : une **heuristique**
  parmi tabou, recuit simulé, génétique, ACO, glouton + recherche locale,
  règles de dispatching. PRISME n'utilise aucun moteur exact : `ortools` n'est
  ni disponible ni autorisé. N'utilise jamais un autre algorithme que celui
  indiqué dans le plan technique. Le contrat de sortie ne change pas :
  `resoudre` renvoie le meilleur planning légal trouvé au sens des objectifs de
  l'instance, ou `None` si aucun planning légal n'a été trouvé.
- **Déterminisme obligatoire** (§6.5) : `resoudre` doit renvoyer le même
  makespan à chaque appel sur la même instance. Si l'algorithme utilise du
  hasard (génétique, ACO, recuit simulé, tabou avec départage aléatoire...),
  instancie un générateur local avec une graine fixe (`random.Random(<graine>)`),
  jamais l'état global du module `random`. Borne les itérations par un nombre
  fixe (générations, itérations...), jamais par une limite de temps écoulé —
  non reproductible d'une machine à l'autre, et de toute façon appliquée par le
  bac à sable d'exécution (Étape 7, limites CPU/mémoire, kill au dépassement).
  **Ordre de parcours** : n'itère jamais directement sur un `set` (ou un
  `frozenset`) d'identifiants — l'ordre d'une chaîne dans un `set` change d'un
  processus Python à l'autre (`PYTHONHASHSEED`) et rendrait le résultat non
  reproductible même avec une graine fixe. Parcours des listes, des `dict`
  (ordre d'insertion garanti) ou `sorted(...)` ; réserve les `set` aux tests
  d'appartenance (`x in ensemble`). Départage toujours les égalités de façon
  déterministe (par exemple par identifiant trié), jamais par l'ordre
  d'itération d'une structure non ordonnée.
- **Budget d'exécution** : chaque exécution tourne dans un conteneur tué au
  bout de **30 secondes** (réelles, 1 vCPU, 512 Mo). Tout algorithme doit rendre
  la main bien avant — un nombre fixe d'itérations/générations dimensionné
  pour une instance de plusieurs centaines de tâches, pas seulement pour le
  petit banc de validation.
- **Contraintes dures = construction, jamais pénalité** : une contrainte dure
  (précédence, compatibilité ressource-tâche, non-chevauchement d'une
  ressource) doit être **impossible à violer par construction** du planning —
  jamais un terme de pénalité dans une fonction de fitness/coût qu'un individu
  pourrait quand même faire gagner malgré la violation. Cela veut dire un
  décodeur qui construit le planning en respectant ces règles au moment même
  où il place chaque tâche (schéma *serial schedule generation scheme* détaillé
  dans le plan technique de l'agent Architecte) — la recherche (tabou, recuit,
  génétique, ACO...) n'optimise alors que l'objectif du planning déjà légal,
  jamais un score composite mêlant faisabilité et qualité. Seule exception
  encadrée : `Echeance`, voir la section dédiée plus bas.
- `CompetenceRequise`/`ContrainteCapacite`/`ContrainteIncompatibilite`/
  `ContrainteDisponibiliteRessource`/`ContrainteTailleLot`/`ContrainteChangementSerie`
  sont des extensions optionnelles du noyau minimal : si l'instance n'en
  contient pas, ignore-les, elles n'existent pas. `Echeance` a sa propre
  section plus bas (fréquente depuis que les commandes en dérivent). `CompetenceRequise`
  ne demande aucun traitement côté solveur : `InstanceTRCO` garantit déjà,
  avant que `resoudre` ne soit appelé, que toute `CompatibiliteRessourceTache`
  respecte les compétences requises — `CompatibiliteRessourceTache` reste la
  seule source de compatibilité et de durée à utiliser. `ContrainteTailleLot`
  non plus : elle borne `Tache.quantite` (une donnée d'entrée, pas une durée
  ni une date) entre `lot_min`/`lot_max`, entièrement vérifiée par
  `validation_engine/feasibility_checker.py` avant même que le planning
  existe — `Tache.quantite`/`ContrainteTailleLot` ne doivent jamais
  apparaître dans le solveur, ni comme borne de décision, ni comme poids
  d'objectif.
- `ContrainteCapacite(ressource, capacite)` : sans elle, une ressource a une
  capacité implicite de **1** (jamais deux opérations en même temps — le
  décodeur refuse tout chevauchement). Pour une ressource couverte par une
  `ContrainteCapacite`, jusqu'à `capacite` opérations peuvent s'y chevaucher :
  remplace la disponibilité "libre/occupée" par un compteur d'opérations
  actives sur la ressource à l'instant considéré, autorisant un nouveau départ
  tant que ce compteur est strictement inférieur à `capacite`.
- `ContrainteIncompatibilite(tache, tache_incompatible)` : les deux tâches
  citées ne peuvent **jamais** être affectées à la même ressource, quelle que
  soit l'heure — indépendant de tout chevauchement temporel. Le décodeur exclut
  simplement toute ressource déjà occupée (à n'importe quel instant) par la
  tâche incompatible au moment de choisir une ressource pour l'autre tâche.
- `ContrainteDisponibiliteRessource(ressource, jours_indisponibles,
  jours_semaine_indisponibles)` : la ressource citée est indisponible durant
  chacun des instants (relatifs) listés dans `jours_indisponibles`, **et/ou**
  durant chaque occurrence du motif récurrent `jours_semaine_indisponibles`
  (positions d'un cycle depuis l'instant 0 de l'instance, répété sur tout
  l'horizon — ex. `[5, 6]` bloque les instants 5, 6, 12, 13, 19, 20... pour
  un cycle de 7). **La longueur du cycle dépend de `InstanceTRCO.unite_temps`
  de l'instance que tu génères : 7 en mode `"jours"`, 168 en mode
  `"heures"`** — lis toujours cette valeur sur l'instance plutôt que de
  supposer 7, le code généré doit fonctionner pour les deux modes séparément
  (une instance donnée n'utilise qu'un seul mode, jamais les deux à la fois).
  Aucune opération ne peut démarrer ni se poursuivre ces instants-là. Les
  deux champs se combinent (jamais l'un remplace l'autre), y compris entre
  plusieurs `ContrainteDisponibiliteRessource` distinctes pour la **même**
  ressource (additionne, ne prends jamais seulement la dernière rencontrée).
  Un calendrier global d'atelier (jours fériés/repos hebdomadaire communs à
  toutes les ressources) n'est pas un mécanisme séparé : c'est la même
  contrainte déclarée identiquement pour chaque ressource de l'instance. Le
  décodeur matérialise d'abord `jours_semaine_indisponibles` en instants
  concrets sur tout l'horizon (`longueur_cycle = 7 if instance.unite_temps ==
  "jours" else 168` puis `{instant for instant in range(horizon) if instant %
  longueur_cycle in motif}`), fusionne avec `jours_indisponibles` dans le
  **même** ensemble par ressource (une seule fois, jamais recalculé par appel),
  puis, au moment de choisir un instant de début sur cette ressource, rejette
  tout choix dont l'intervalle `[debut, fin)` intersecte les instants
  indisponibles de la ressource (table précalculée, jamais une recherche
  dans `instance.contraintes` à l'intérieur du décodeur — voir "Précalcule
  tout" plus bas). Une ressource qui a aussi une `ContrainteCapacite`
  combine naturellement les deux règles : indisponible = capacité nulle à cet
  instant.
- `ContrainteChangementSerie(ressource, tache_avant, tache_apres, duree_setup)` :
  contrainte **dirigée**, propre à `ressource` — si le solveur affecte à la
  fois `tache_avant` et `tache_apres` à `ressource` **et** que `tache_avant`
  finit avant que `tache_apres` ne commence, impose `debut[tache_apres] >=
  fin[tache_avant] + duree_setup`. Le vérificateur de faisabilité n'exige le
  délai que si les deux tâches sont *directement* consécutives sur la ressource
  (sans tâche intercalée). Pour respecter exactement cette règle avec un
  décodeur : **sur une ressource qui porte au moins une
  `ContrainteChangementSerie`, place les tâches en ajout seulement** (jamais
  dans un trou antérieur à la dernière tâche déjà placée — le décodeur reste
  alors dans l'ordre chronologique de la ressource). Au moment d'ajouter une
  tâche à la fin de la liste déjà placée sur cette ressource, si la dernière
  tâche placée et la nouvelle forment une paire déclarée
  (`(ressource, tache_avant, tache_apres)` précalculé en dictionnaire
  `duree_setup_par_paire`, jamais recherché dans `instance.contraintes`), impose
  `debut >= fin_derniere + duree_setup` avant de fixer le début. Sur une
  ressource sans changement de série, l'insertion dans les trous reste permise.

## Instance vivante : les commandes font grossir l'instance entre deux exécutions

Le module est réexécuté sur la même instance à chaque commande client ajoutée. La notion de
« commande » n'existe pas dans le DSL — tu ne la vois jamais comme telle — mais chaque commande
modifie l'instance avant la réexécution suivante :

- elle ajoute des `Tache` neuves, dont l'identifiant est généré (ex. `cmd-1a2b3c4d_0_DECOUPE`)
  et dont `produit`/`quantite` sont renseignés quand elles viennent du processus de l'atelier ;
- elle ajoute les `Precedence` qui enchaînent les étapes du processus — y compris **plusieurs
  prédécesseurs pour une même tâche** (sous-produits qui convergent vers un assemblage), et des
  tâches sans aucune précédence ;
- elle ajoute des `CompetenceRequise` et les `CompatibiliteRessourceTache` qui en sont dérivées ;
- si la commande a une date limite, elle ajoute **une `Echeance` identique pour chacune de ses
  tâches** ;
- elle peut remplacer la durée d'une tâche existante sur toutes ses ressources compatibles.

Conséquences pour le code :

- ne suppose jamais un nombre de tâches, un format ou un préfixe d'identifiant, un nombre de
  produits ou une forme de graphe de précédence (chaînes simples, arbres convergents et tâches
  isolées coexistent dans la même instance) — parcours toujours ce qui est présent ;
- `Tache.produit`, `Tache.quantite`, `Tache.statut` et `Tache.nom` sont purement informatifs :
  jamais lus pour décider d'une affectation, d'un ordre, d'une durée ou d'un objectif ;
- l'instance peut compter plusieurs fois plus de tâches à une exécution future qu'au moment de la
  génération : la complexité doit rester maîtrisée (voir « Précalcule tout » et « Budget
  d'exécution »).

## Échéances (`Echeance`)

`Echeance(tache, echeance)` : la tâche doit **finir** au plus tard à l'instant `echeance` (même
unité que les durées). C'est une contrainte **dure**, vérifiée comme telle par le garde-fou de
faisabilité en aval : un planning qui en dépasse une est rejeté. Si aucune `Echeance` n'est
présente, ignore cette section.

Une échéance ne peut pas être garantie au moment où l'on place une tâche (la placer au plus tôt
est déjà le mieux possible pour elle). Procède ainsi :

1. le décodeur place les tâches comme d'habitude, puis compte `nb_echeances_depassees` sur le
   planning obtenu ;
2. la fitness renvoie un **tuple** `(nb_echeances_depassees, objectif_principal,
   terme_priorite)` — la comparaison lexicographique des tuples Python fait qu'un planning qui
   respecte toutes les échéances bat toujours un planning qui en dépasse une, quel que soit son
   objectif ;
3. oriente la recherche vers les échéances : au moins une solution initiale triée par échéance
   croissante (règle EDD, tâches sans échéance en dernier, départage par identifiant) ;
4. à la fin, si la meilleure solution trouvée a `nb_echeances_depassees > 0`, renvoie `None` —
   jamais un planning qui dépasse une échéance ; l'humain décide ensuite, ne relâche jamais une
   échéance toi-même.

## Calendrier ouvré (`instance.position_zero_semaine`, mode heures)

Quand `instance.unite_temps == "heures"` **et** `instance.position_zero_semaine is not None`, l'atelier
n'est ouvert que certaines heures (`instance.heure_ouverture` à `instance.heure_fermeture`, jours de
`instance.jours_fermes` exclus — week-end par défaut). **Une opération ne travaille que pendant les
heures ouvrées** : démarrée à 19h avec 5 h de travail, elle travaille jusqu'à 22h, s'arrête, puis
reprend le lendemain à 8h et finit à 10h. Sa `duree` compte les heures *travaillées*, jamais les
heures fermées traversées. Sinon (jours, ou `position_zero_semaine is None`), ignore toute cette
section : `fin = debut + duree`, comme partout ailleurs.

Le module `dsl.calendrier` fournit la règle exacte — **utilise-la telle quelle, ne la réécris jamais** :

```python
from dsl.calendrier import fin_calendaire, premier_instant_ouvert

debut = premier_instant_ouvert(instance, plus_tot)      # une opération ne démarre qu'à une heure ouvrée
fin = fin_calendaire(instance, debut, duree)            # fin réelle, pauses (nuit, week-end) comprises
```

Ces deux fonctions valent `debut` et `debut + duree` quand aucun calendrier n'est actif : appelle-les
donc **toujours**, sans test `if` de ta part. Partout où tu écrirais `debut + duree`, écris
`fin_calendaire(instance, debut, duree)` :

- fin d'un prédécesseur (la tâche suivante démarre à `premier_instant_ouvert(instance, fin_avant)`) ;
- libération de la ressource (la tâche suivante sur la même ressource attend la fin calendaire) ;
- comparaison à une `Echeance`, calcul du makespan, occupation d'une ressource à capacité > 1 ;
- calcul de l'horizon : après l'avoir calculé comme d'habitude, prends
  `horizon = fin_calendaire(instance, 0, horizon) + 168` (une semaine de marge).

Le garde-fou de faisabilité utilise exactement la même règle et rejette un planning dont une
opération démarre hors des heures ouvrées (`debut_hors_heures_ouvrees`), ou dont la fin réelle
chevauche la suivante. Un temps de changement de série (`duree_setup`) reste un écart en heures
écoulées entre la fin calendaire d'une tâche et le début de la suivante.

## Matières (`DeclarationMateriau` + `ConsommationMatiere`)

Aucune `DeclarationMateriau` dans `instance.contraintes` sur la très grande majorité des
instances — dans ce cas, ignore complètement cette section, aucun code lié aux matières à
générer. Contrairement à `Tache`/`Ressource`, un matériau n'a pas de liste top-level dédiée : sa
seule existence est sa `DeclarationMateriau(materiau, stock_initial, ...)`, une contrainte parmi
les autres. Quand une ou plusieurs sont présentes, une ou plusieurs `ConsommationMatiere(tache,
materiau, quantite)` décrivent la quantité prélevée par chaque tâche sur le stock d'un matériau,
**au moment où la tâche commence** (`debut` de son opération). C'est une contrainte **dure** : le
stock d'un matériau ne doit **jamais** passer sous zéro à aucun instant du planning produit — pas
un objectif, pas une pénalité, aucune notion de "pénurie tolérée" à ce stade. Aucun
réapprovisionnement à modéliser : `stock_initial` couvre tout l'horizon de planification.

- **Décodeur** : maintiens un compteur de stock courant par matériau (initialisé à
  `stock_initial`), précalculé une seule fois en table `consommations_par_tache` (jamais une
  recherche dans `instance.contraintes` à l'intérieur de la boucle de décision — voir
  "Précalcule tout" plus bas). Au moment de fixer le `debut` d'une tâche, si elle consomme un ou
  plusieurs matériaux, vérifie que chaque stock concerné a assez de marge une fois la
  consommation appliquée ; si un stock manquerait, ce placement est **rejeté par construction**
  (retente un autre `debut`/une autre ressource, jamais une solution "illégale" gardée avec une
  pénalité de fitness — même principe que "contraintes dures = construction, jamais pénalité"
  plus haut). Une fois un placement accepté, décrémente réellement le compteur de stock du
  matériau concerné avant de continuer le décodage des tâches suivantes. Le stock ne peut que
  décroître : le décodage suit l'ordre chronologique des `debut` des tâches consommatrices, pas
  l'ordre de placement — si le décodeur peut placer une tâche à un `debut` antérieur à une
  consommation déjà appliquée, revérifie le stock sur la chronologie complète.

## Replanification à horizon glissant (`planning_precedent`, `horizon_gele_jours`)

Quand `horizon_gele_jours > 0` **et** `planning_precedent is not None` : toute opération de
`planning_precedent` dont `debut < horizon_gele_jours` doit être **fixée** dans le nouveau
planning — même `ressource`, même `debut`, jamais une simple suggestion — à condition que le
couple `(tache, ressource)` de cette opération soit toujours une `CompatibiliteRessourceTache`
valide de l'instance courante (sinon ignore cette opération : la tâche ou la ressource a disparu
entre les deux exécutions, ce n'est pas une erreur à signaler). Si `planning_precedent is None` ou
`horizon_gele_jours == 0`, ignore complètement ces deux paramètres — solve normal, sans aucune
opération fixée.

Objectif métier : un atelier qui a déjà commencé à exécuter le planning précédent ne doit pas voir
les prochains jours perturbés par une replanification ; seul le reste de l'horizon (au-delà de
`horizon_gele_jours`) reste librement optimisable.

Avant de lancer le décodeur normal, place d'abord toutes les opérations gelées (dans leur
`(ressource, debut)` fixe, en marquant la ressource occupée jusqu'à `debut + duree`), puis laisse le
décodeur traiter les tâches restantes normalement — le mécanisme "contraintes dures = construction,
jamais pénalité" (voir plus haut) s'applique ici aussi : une opération gelée n'est jamais un simple
biais de coût, c'est une donnée d'entrée déjà décidée. La recherche (tabou, recuit...) ne doit
jamais déplacer une opération gelée.

## Objectifs (`instance.objectifs`, liste polymorphe — jamais un seul supposé)

`instance.objectifs` se parcourt comme `instance.contraintes`, jamais un seul
élément supposé présent ni son type deviné : filtre par `isinstance`.

```python
objectifs_makespan = [o for o in instance.objectifs if isinstance(o, MinimiserMakespan)]
objectifs_equilibrage = [o for o in instance.objectifs if isinstance(o, EquilibrerCharge)]
```

Si plusieurs objectifs sont présents, combine-les par **somme pondérée** (chaque
`Objectif` porte un `poids`) dans la fonction de fitness — jamais un seul objectif choisi en
ignorant les autres. `objectif.poids`, `objectif.methode`,
`objectif.ressources_cibles` sont des **valeurs lues à l'exécution**, jamais
des constantes que tu figerais toi-même au moment d'écrire le code : le
même module est réexécuté sur la même instance à chaque évolution de ses
données (principe « générer une fois, réexécuter souvent »), et un
utilisateur peut modifier un poids ou une méthode sans que le solveur soit
régénéré.

- `MinimiserMakespan(poids, makespan_cible, penalite_depassement)` : le cas
  par défaut. `makespan_cible`/`penalite_depassement` sont optionnels
  (souvent absents) — si absents, minimise simplement le makespan
  (`max(fins)` du planning décodé), sans traitement spécial.
- `EquilibrerCharge(poids, methode, ressources_cibles)` : équilibre la charge
  de travail entre ressources. Calcule d'abord une **charge par ressource** —
  somme des `duree` des tâches qui lui sont affectées dans le planning décodé
  (dict ressource→charge accumulé en construisant le planning) — restreinte
  aux ressources listées dans `ressources_cibles` si fourni, sinon toutes les
  ressources qui apparaissent dans au moins une `CompatibiliteRessourceTache`.
  Puis, selon `methode`, la fitness calcule la valeur **exacte** (Python pur,
  aucun nouvel import requis — pas de module `statistics`) :
  - `"ecart_max"` (valeur par défaut du schéma) : `poids * (max(charges.values()) -
    min(charges.values()))`.
  - `"variance"` : `poids * sum((c - moyenne) ** 2 for c in charges.values()) /
    len(charges)` avec `moyenne = sum(charges.values()) / len(charges)`.
  - `"gini"` : `poids * sum(abs(a - b) for a in charges.values() for b in
    charges.values()) / (2 * len(charges) * sum(charges.values()))` (ou 0 si la
    somme des charges est nulle).

## Priorité des tâches (`Tache.priorite`, départage uniquement)

`Tache.priorite` (1 = critique, 5 = faible, optionnelle) **ne fait jamais
perdre à l'objectif principal la moindre unité** — elle ne départage
qu'entre plusieurs plannings de même valeur d'objectif (celui ou ceux de
`instance.objectifs`, voir ci-dessus). Jamais un poids ajouté à l'objectif
principal, jamais une contrainte.

- Fais renvoyer à la fitness un **tuple** `(objectif_principal, terme_priorite)` plutôt qu'un
  seul nombre, avec `terme_priorite = somme((6 - t.priorite) * fin_tache)` sur les seules tâches
  ayant une `priorite` déclarée (poids 5 pour priorité 1/critique, poids 1 pour priorité 5/faible ;
  tâches sans `priorite` exclues de la somme) — la comparaison lexicographique native des tuples
  Python fait exactement ce départage, sans aucune échelle à calculer ni risque de dépassement.
  Quand des échéances sont présentes, le tuple complet est celui de la section « Échéances » :
  `(nb_echeances_depassees, objectif_principal, terme_priorite)`.

## Accès aux données de l'instance (noms de champs exacts — ne pas en deviner d'autres)

`InstanceTRCO` a exactement ces champs : `taches`, `ressources`, `contraintes`, `objectifs`,
`unite_temps` (`"jours"` ou `"heures"`, lu uniquement pour la longueur du cycle hebdomadaire des
indisponibilités) et `jours_fermes` (**jamais lu par le solveur** — les jours fermés sont
appliqués après coup, hors du module généré). Il n'existe **aucun** raccourci du type
`instance.precedences`, `instance.compatibilite_ressource_tache` ou `instance.commandes` —
`contraintes` est une **liste polymorphe unique** (`Precedence |
CompatibiliteRessourceTache | Echeance | CompetenceRequise |
ContrainteCapacite | ContrainteIncompatibilite |
ContrainteDisponibiliteRessource | ContrainteTailleLot |
ContrainteChangementSerie | DeclarationMateriau | ConsommationMatiere`), à filtrer par type avec `isinstance` :

```python
compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)]
precedences = [c for c in instance.contraintes if isinstance(c, Precedence)]
echeances = [c for c in instance.contraintes if isinstance(c, Echeance)]
capacites = [c for c in instance.contraintes if isinstance(c, ContrainteCapacite)]
incompatibilites = [c for c in instance.contraintes if isinstance(c, ContrainteIncompatibilite)]
disponibilites = [c for c in instance.contraintes if isinstance(c, ContrainteDisponibiliteRessource)]
tailles_lot = [c for c in instance.contraintes if isinstance(c, ContrainteTailleLot)]  # jamais lue par le solveur
changements_serie = [c for c in instance.contraintes if isinstance(c, ContrainteChangementSerie)]
```

Champs exacts de chaque type — vérifie-les avant d'écrire du code qui y
accède, ne les devine jamais par analogie avec un autre projet :

- `Precedence.avant`, `Precedence.apres` (pas `tache_amont`/`tache_aval`) :
  la tâche `avant` doit être terminée avant que `apres` ne commence.
- `CompatibiliteRessourceTache.tache`, `.ressource`, `.duree`.
- `Echeance.tache`, `.echeance` (pas `date_limite`) : instant limite de fin
  de la tâche, dans l'unité de temps déclarée par `InstanceTRCO.unite_temps`
  (jours ou heures).
- `ContrainteCapacite.ressource`, `.capacite` : nombre d'opérations que
  cette ressource peut traiter simultanément (jamais 0, jamais négatif).
- `ContrainteIncompatibilite.tache`, `.tache_incompatible` (pas
  `tache_1`/`tache_2`) : relation symétrique, l'ordre des deux champs n'a
  aucun sens métier.
- `ContrainteDisponibiliteRessource.ressource`, `.jours_indisponibles`
  (liste d'instants relatifs, jamais une date calendaire),
  `.jours_semaine_indisponibles` (`list[int] | None`, positions d'un motif
  récurrent sur un cycle de 7 ou 168 selon `InstanceTRCO.unite_temps` — voir
  plus haut ; les deux champs se combinent, aucun des deux n'est garanti
  non-vide seul).
- `ContrainteTailleLot.tache`, `.lot_min`, `.lot_max` : validation statique
  uniquement (voir plus haut) — jamais lue dans le code généré.
- `ContrainteChangementSerie.ressource`, `.tache_avant`, `.tache_apres`,
  `.duree_setup` (unité de `InstanceTRCO.unite_temps`) : contrainte dirigée,
  `tache_avant` → `tache_apres` uniquement dans ce sens — voir plus haut
  pour l'encodage.
- `Tache.priorite` (`int | None`, 1 à 5) : départage uniquement, voir
  "Priorité des tâches" plus haut — jamais un champ de contrainte/objectif.
- `Tache.quantite` (`int | None`) : donnée d'entrée pour `ContrainteTailleLot`
  uniquement (déjà vérifiée en amont) — jamais lue dans le code généré, ni
  comme durée, ni comme poids, ni comme borne de décision. Renseignée par les
  commandes issues du processus de l'atelier : ce n'est **pas** un multiplicateur de durée
  (la durée à utiliser est déjà dans `CompatibiliteRessourceTache.duree`).
- `Tache.produit`, `Tache.statut` (`str | None`) : purement informatifs, jamais lus.
- `DeclarationMateriau.materiau`, `.stock_initial` (`float`), `.unite` (informatif) ;
  `ConsommationMatiere.tache`, `.materiau`, `.quantite` (`float`) — voir « Matières ».
- `Tache.id`, `Ressource.id` (type `Identifiant`, une chaîne) sont les
  **seuls** identifiants stables à utiliser partout où une tâche/ressource
  doit être référencée : clé de dictionnaire, gène de chromosome,
  `OperationPlanifiee.tache`/`.ressource`. `Tache.nom`/`Ressource.nom`
  sont **optionnels** (`str | None`, souvent absents) et pas garantis
  uniques — ne jamais les utiliser comme identifiant, seulement pour de
  l'affichage.

## Horizon (borne supérieure du temps)

`horizon` borne le temps, en particulier la matérialisation des indisponibilités récurrentes.
Trop court, il rend infaisable une instance qui ne l'est pas (le solveur renvoie `None` à tort) ; la « somme des durées » seule ne suffit **pas** dès qu'il
y a des jours d'indisponibilité, des temps de changement de série ou des opérations gelées.
Calcule-le une fois, au début de `resoudre`, ainsi :

```python
duree_max_par_tache: dict[str, int] = {}
for c in instance.contraintes:
    if isinstance(c, CompatibiliteRessourceTache):
        duree_max_par_tache[c.tache] = max(duree_max_par_tache.get(c.tache, 0), c.duree)
horizon = sum(duree_max_par_tache.values())
horizon += sum(c.duree_setup for c in instance.contraintes if isinstance(c, ContrainteChangementSerie))
if planning_precedent is not None and horizon_gele_jours > 0:
    horizon += max((op.debut for op in planning_precedent.operations), default=0)

disponibilites = [c for c in instance.contraintes if isinstance(c, ContrainteDisponibiliteRessource)]
if disponibilites:
    longueur_cycle = 7 if instance.unite_temps == "jours" else 168
    motif_par_ressource: dict[str, set[int]] = {}
    for c in disponibilites:
        motif_par_ressource.setdefault(c.ressource, set()).update(c.jours_semaine_indisponibles or [])
    positions_bloquees = max(len(motif) for motif in motif_par_ressource.values())
    positions_libres = max(1, longueur_cycle - positions_bloquees)
    dernier_instant_bloque = max((j for c in disponibilites for j in c.jours_indisponibles), default=0)
    # Étire l'horizon au prorata des positions bloquées du cycle, puis ajoute la dernière
    # indisponibilité explicite et une marge d'un cycle + la plus longue tâche.
    horizon = -(-horizon * longueur_cycle // positions_libres) + dernier_instant_bloque + longueur_cycle
    horizon += max(duree_max_par_tache.values(), default=0)
```

Une tâche plus longue que la plus longue plage libre de sa ressource ne pourra jamais être placée :
c'est une vraie infaisabilité (renvoie `None`), pas un problème d'horizon.

## Précalcule tout, jamais de recherche répétée dans `instance.contraintes`

**Parcourir
`instance.contraintes` (ou toute liste de taille proportionnelle à
l'instance) à l'intérieur d'une fonction appelée par tâche, par opération,
ou par évaluation est interdit** — ça transforme un algorithme censé être
rapide en un algorithme quadratique (ou pire), invisible sur le petit banc
de validation (1 à 80 tâches, quelques secondes) mais qui explose sur une
instance réelle de quelques centaines ou milliers de tâches (minutes à
heures) et dépasse le délai du bac à sable (30 s). C'est exactement ce qui arrive quand des
commandes s'accumulent sur une instance générée à petite taille.

Construis chaque table de correspondance **une seule fois**, avant toute
boucle de recherche/génération, jamais à l'intérieur :

```python
# Une seule fois, avant la recherche — jamais recalculé ensuite
duree_par_tache_ressource = {
    (c.tache, c.ressource): c.duree
    for c in instance.contraintes
    if isinstance(c, CompatibiliteRessourceTache)
}
compatibilites_par_tache: dict[str, list[tuple[str, int]]] = {}
for c in instance.contraintes:
    if isinstance(c, CompatibiliteRessourceTache):
        compatibilites_par_tache.setdefault(c.tache, []).append((c.ressource, c.duree))

# Capacité implicite de 1 si absente de cette table. Ces `set` ne servent qu'à des tests
# d'appartenance (`x in ...`) — jamais itérés directement (voir « Déterminisme obligatoire »).
capacite_par_ressource = {
    c.ressource: c.capacite for c in instance.contraintes if isinstance(c, ContrainteCapacite)
}
taches_incompatibles: dict[str, set[str]] = {}
for c in instance.contraintes:
    if isinstance(c, ContrainteIncompatibilite):
        taches_incompatibles.setdefault(c.tache, set()).add(c.tache_incompatible)
        taches_incompatibles.setdefault(c.tache_incompatible, set()).add(c.tache)

# `.update(...)`, jamais une écriture directe `c.ressource: set(...)` dans un dict comprehension
# — plusieurs ContrainteDisponibiliteRessource pour la MÊME ressource (jours explicites + motif
# récurrent, ou deux contraintes distinctes) doivent s'additionner, jamais que la dernière
# rencontrée écrase les précédentes.
jours_indisponibles_par_ressource: dict[str, set[int]] = {}
# 7 en mode jours, 168 en mode heures — jamais 7 codé en dur, lis toujours unite_temps.
longueur_cycle = 7 if instance.unite_temps == "jours" else 168
for c in instance.contraintes:
    if not isinstance(c, ContrainteDisponibiliteRessource):
        continue
    jours = jours_indisponibles_par_ressource.setdefault(c.ressource, set())
    jours.update(c.jours_indisponibles)
    if c.jours_semaine_indisponibles:
        # Matérialise le motif récurrent en instants concrets sur tout l'horizon (`horizon`,
        # calculé juste avant, voir la section « Horizon ») — une seule fois ici, jamais
        # recalculé à chaque intervalle créé.
        jours.update(jour for jour in range(horizon) if jour % longueur_cycle in c.jours_semaine_indisponibles)
```

Le décodeur/la fitness est appelé des dizaines ou centaines de milliers de
fois (population × générations, itérations...) : toute recherche de durée, de compatibilité ou de
précédence dans cette fonction doit être un accès de dictionnaire `O(1)`
sur une table construite en dehors de la boucle — jamais un `for c in
instance.contraintes: ...` réévalué à chaque appel.

## Contraintes de sécurité (impératives — le code est exécuté automatiquement)

- Imports autorisés, et seulement ceux-là : `dsl.schema`, `dsl.calendrier`, `collections`,
  `collections.abc`, `dataclasses`, `typing`, `__future__`, `random`, `math`,
  `heapq`, `itertools`, `bisect`, `functools`, `copy` (`random` et `math` pour la
  génération/mutation, le recuit ; `heapq`/`bisect` pour les files d'événements et
  l'insertion dans les trous ; `time` reste interdit — jamais de limite en temps
  réel).
- Interdit, sans exception : `eval`, `exec`, `compile`, `__import__`,
  `open`, `input`, tout accès réseau ou fichier, tout import hors de la
  liste ci-dessus (notamment `os`, `sys`, `subprocess`, `socket`, `shutil`,
  `importlib`).

Ceci est le contrat commun ; le format de réponse exact (bloc de code,
JSON...) est précisé séparément selon qui te le demande.
