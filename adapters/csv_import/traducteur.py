"""csv_import — Adaptateur pour l'ingestion T-R-C-O via trois fichiers CSV
séparés (§5.4) : Tâches, Ressources, Contraintes. Format standard pour
l'import de données tabulaires depuis un tableur (LibreOffice, Google Sheets,
etc.) ou un export ERP en CSV.

Le fichier Contraintes couvre les natures de contrainte supportées ici
(precedence, compatibilite_ressource_tache, competence_requise) via une
colonne `type` discriminante, puisqu'un CSV n'a pas d'onglets pour les
séparer comme le fait le gabarit xlsx.

Compatibilité dérivée par compétence : plutôt que de saisir à la main chaque
couple (tâche, ressource, durée), on peut déclarer qu'une ressource possède
une compétence (`ressources.csv`) et qu'une tâche l'exige (`competence_requise`
dans `contraintes.csv`) — l'adaptateur calcule alors lui-même une
`CompatibiliteRessourceTache` pour chaque ressource qualifiée, avec sa durée
comblée par apprentissage automatique (`estimateur_duree`, voir `traduire`),
appliquée telle quelle à toutes ces ressources — même principe que
`adapters/greensig/translator.py` (`equipes_compatibles_pour`/
`duree_heures_pour`). Le DSL lui-même (`dsl/schema/instance.py`,
`_competences_requises_respectees`) revérifie ensuite que chaque compatibilité
déclarée pour une tâche à compétences requises couvre bien toutes ces
compétences — un garde-fou de plus, pas remplacé ici.

Les deux mécanismes (compatibilité explicite et compatibilité dérivée par
compétence) peuvent coexister pour une même tâche : leurs résultats s'additionnent,
rien n'oblige à choisir l'un ou l'autre pour toutes les tâches d'un même fichier.

Commandes (`adapters/commande_derivation.py`) : un quatrième fichier optionnel
`commandes.csv` relie des tâches à une commande cliente et une date limite — pure
métadonnée de traçabilité d'ingestion, dérive une `Echeance` par tâche liée (sauf si déjà
explicite pour cette tâche dans `contraintes.csv`), le solveur ne voit jamais la notion de
"commande" elle-même (§5.3, vocabulaire DSL fini).

Matières (`DeclarationMateriau`/`ConsommationMatiere`, `dsl/schema/contraintes.py`) :
`contraintes.csv` gagne deux types supplémentaires — `declaration_materiau` (colonnes `materiau`,
`stock_initial`, `unite`) déclare le référentiel matière (pas de fichier séparé : un matériau
n'existe pour l'instance qu'à travers cette ligne, comme dans le DSL lui-même) et
`consommation_matiere` (colonnes `tache`, `materiau`, `quantite`) relie une tâche à sa
consommation — même granularité atomique que les autres types de contraintes de ce fichier. Aucune
dérivation depuis une nomenclature/BOM dans cet adaptateur (v1) : la consommation doit être
déclarée ligne par ligne.
"""

from __future__ import annotations

import csv
from io import StringIO
from typing import TYPE_CHECKING, Literal

from adapters.commande_derivation import Commande, deriver_echeances_par_commande
from adapters.competence_derivation import (
    CompetenceSansDureeEstimee,
    ResultatTraduction,
    completer_durees_par_estimation,
    deriver_compatibilites_par_competence,
    durees_declarees_par_tache,
)
from adapters.heures_travail import deriver_disponibilites_horaires
from dsl.schema import (
    CompatibiliteRessourceTache,
    CompetenceRequise,
    ConsommationMatiere,
    Contrainte,
    DeclarationMateriau,
    InstanceTRCO,
    MinimiserMakespan,
    Precedence,
    Ressource,
    Tache,
)

if TYPE_CHECKING:
    from estimation import EstimateurDuree

COLONNES_TACHES_REQUISES = ("id",)
# Colonne de durée : son nom déclare l'unité du fichier, jamais une conversion — l'entier est
# repris tel quel, c'est `unite_temps` (paramètre de `traduire`, repris dans
# `InstanceTRCO.unite_temps`) qui dit ce qu'il signifie. `duree_jours` est le nom historique,
# `duree_heures` son équivalent pour un fichier en heures, `duree` la forme neutre. Un fichier
# n'en déclare qu'une seule à la fois (voir `_colonne_duree`).
COLONNE_DUREE_PAR_UNITE = {"jours": "duree_jours", "heures": "duree_heures"}
COLONNES_DUREE_ACCEPTEES = ("duree_jours", "duree_heures", "duree")
# Aucun fichier d'ingestion ne déclare de durée : elle se fixe **à la commande**, tâche par tâche
# (`POST /ingestion/{instance_id}/commandes`, champ `durees_taches`) — l'atelier décrit ce qui peut
# s'exécuter où, la commande dit combien de temps ça prend. Les colonnes de durée restent lues si
# elles sont présentes, pour les fichiers déjà écrits dans l'ancien format (taches.csv comme
# contraintes.csv), jamais exigées.
COLONNES_TACHES_OPTIONNELLES = ("nom", *COLONNES_DUREE_ACCEPTEES)

# Durée d'attente d'une compatibilité dont aucune durée n'est déclarée nulle part. `duree` est
# obligatoire côté DSL (`CompatibiliteRessourceTache`) : il faut bien une valeur pour que
# l'instance existe avant sa première commande. 1 (la plus petite valeur valide) est une valeur
# d'attente reconnaissable, jamais une estimation — chaque tâche concernée ressort dans les
# avertissements, et la première commande qui la référence fixe sa vraie durée.
DUREE_EN_ATTENTE_DE_COMMANDE = 1
COLONNES_RESSOURCES_REQUISES = ("id",)
COLONNES_RESSOURCES_OPTIONNELLES = ("nom", "competences", "heures_par_jour")
COLONNES_CONTRAINTES_REQUISES = ("type",)
COLONNES_CONTRAINTES_OPTIONNELLES = (
    "tache_avant",
    "tache_apres",
    "tache",
    "ressource",
    *COLONNES_DUREE_ACCEPTEES,
    "competence",
    "materiau",
    "quantite",
    "stock_initial",
    "unite",
)
TYPES_CONTRAINTE_SUPPORTES = (
    "precedence",
    "compatibilite_ressource_tache",
    "competence_requise",
    "declaration_materiau",
    "consommation_matiere",
)
COLONNES_COMMANDES_REQUISES = ("id", "taches")
COLONNES_COMMANDES_OPTIONNELLES = ("client", "date_limite")

# Séparateur des compétences dans une même cellule (ressources.csv) — la
# virgule est déjà le délimiteur CSV, illisible pour une liste dans une cellule.
SEPARATEUR_COMPETENCES = ";"

# Même motif pour la liste de tâches d'une commande (commandes.csv, colonne `taches`).
SEPARATEUR_TACHES = ";"


class ErreurFichierInvalide(Exception):
    """Fichier illisible ou colonne requise manquante — distinct d'une instance
    structurellement lue mais invalide au sens du DSL (ça, c'est une
    ValidationError Pydantic, même garde-fou que les autres canaux)."""


def _lire_lignes_et_entetes(
    contenu: bytes,
    nom_fichier: str,
    colonnes_requises: tuple[str, ...],
    colonnes_optionnelles: tuple[str, ...] = (),
    delimiteur: str = ",",
) -> tuple[list[dict[str, str]], tuple[str, ...]]:
    """Décode et parse un CSV en liste de lignes (dict par en-tête de colonne).
    `utf-8-sig` tolère le BOM ajouté par certains tableurs à l'export, sans rien
    changer pour un CSV déjà en UTF-8 simple. Ignore les lignes où la première
    colonne requise est vide (ligne d'exemple laissée telle quelle, ligne vide
    en fin de fichier...). Les colonnes optionnelles absentes du fichier valent
    simplement "" partout plutôt que de faire échouer la lecture — ex.
    `competences`, inutile tant qu'aucune compatibilité n'est dérivée par
    compétence. `delimiteur` (un seul caractère, `,` par
    défaut) : certains exports européens (Excel FR notamment) utilisent `;`,
    la virgule étant déjà le séparateur décimal — jamais deviné automatiquement,
    l'appelant (ex. la page Données) le déclare explicitement."""
    try:
        texte = contenu.decode("utf-8-sig")
    except UnicodeDecodeError as erreur:
        raise ErreurFichierInvalide(f"{nom_fichier} : fichier illisible, encodage attendu UTF-8") from erreur

    lecteur = csv.DictReader(StringIO(texte), delimiter=delimiteur)
    if lecteur.fieldnames is None:
        raise ErreurFichierInvalide(f"{nom_fichier} : fichier vide")

    manquantes = [c for c in colonnes_requises if c not in lecteur.fieldnames]
    if manquantes:
        raise ErreurFichierInvalide(
            f"{nom_fichier} : colonne(s) manquante(s) : {', '.join(manquantes)} "
            f"(attendues : {', '.join(colonnes_requises)})"
        )

    toutes_colonnes = (*colonnes_requises, *colonnes_optionnelles)
    premiere_colonne = colonnes_requises[0]
    lignes = [
        {c: (ligne.get(c) or "").strip() for c in toutes_colonnes}
        for ligne in lecteur
        if (ligne.get(premiere_colonne) or "").strip()
    ]
    # Les en-têtes réels du fichier (pas les colonnes attendues) : seul `_lire_contraintes` s'en
    # sert, pour savoir laquelle des colonnes de durée acceptées le fichier déclare.
    return lignes, tuple(n.strip() for n in lecteur.fieldnames if n)


def _lire_lignes(
    contenu: bytes,
    nom_fichier: str,
    colonnes_requises: tuple[str, ...],
    colonnes_optionnelles: tuple[str, ...] = (),
    delimiteur: str = ",",
) -> list[dict[str, str]]:
    """Cas courant : les lignes seules, sans les en-têtes bruts."""
    lignes, _ = _lire_lignes_et_entetes(contenu, nom_fichier, colonnes_requises, colonnes_optionnelles, delimiteur)
    return lignes


def _lire_taches(
    contenu: bytes, delimiteur: str = ",", unite_temps: Literal["jours", "heures"] = "jours"
) -> tuple[list[Tache], dict[str, int]]:
    """Renvoie `(tâches, durée par tâche)`. La durée n'est pas un champ de `Tache` (`dsl/schema` n'en
    a délibérément aucun, §4.2 — en FJSP flexible elle appartient au couple tâche-ressource) :
    elle est lue ici puis reportée sur chaque `CompatibiliteRessourceTache` de cette tâche (voir
    `traduire`). Une tâche sans durée déclarée reste possible tant que ses compatibilités en
    portent une (ancien format) ; sinon l'instance est rejetée explicitement."""
    lignes, entetes = _lire_lignes_et_entetes(
        contenu, "taches.csv", COLONNES_TACHES_REQUISES, COLONNES_TACHES_OPTIONNELLES, delimiteur
    )
    colonne_duree, _ = _colonne_duree(entetes, unite_temps, "taches.csv")

    taches: list[Tache] = []
    durees: dict[str, int] = {}
    for ligne in lignes:
        taches.append(Tache(id=ligne["id"], **({"nom": ligne["nom"]} if ligne["nom"] else {})))
        brut = ligne[colonne_duree]
        if not brut:
            continue
        try:
            durees[ligne["id"]] = int(float(brut))
        except ValueError as erreur:
            raise ErreurFichierInvalide(
                f"taches.csv : durée invalide « {brut} » pour {ligne['id']} — doit être un nombre "
                f"entier de {unite_temps}, colonne « {colonne_duree} »."
            ) from erreur
    return taches, durees


def _lire_ressources(contenu: bytes, delimiteur: str = ",") -> list[Ressource]:
    """`competences` (séparées par `;`) va directement sur `Ressource` — c'est
    déjà un champ réel du DSL, utilisé tel quel par la dérivation partagée
    (`adapters/competence_derivation.py`). `heures_par_jour` (durée de travail
    quotidienne, 1 à 24) de même : champ réel du DSL, d'où `adapters/heures_travail.py`
    dérive une indisponibilité récurrente (voir `traduire`)."""
    lignes = _lire_lignes(
        contenu, "ressources.csv", COLONNES_RESSOURCES_REQUISES, COLONNES_RESSOURCES_OPTIONNELLES, delimiteur
    )
    ressources: list[Ressource] = []
    for ligne in lignes:
        heures_par_jour: int | None = None
        if ligne["heures_par_jour"]:
            try:
                heures_par_jour = int(float(ligne["heures_par_jour"]))
            except ValueError as erreur:
                raise ErreurFichierInvalide(
                    f"ressources.csv : durée de travail quotidienne invalide "
                    f"« {ligne['heures_par_jour']} » pour {ligne['id']} — doit être un nombre entier "
                    f"d'heures entre 1 et 24."
                ) from erreur
        ressources.append(
            Ressource(
                id=ligne["id"],
                **({"nom": ligne["nom"]} if ligne["nom"] else {}),
                competences=sorted(
                    {c.strip() for c in ligne["competences"].split(SEPARATEUR_COMPETENCES) if c.strip()}
                ),
                **({"heures_par_jour": heures_par_jour} if heures_par_jour is not None else {}),
            )
        )
    return ressources


def _colonne_duree(
    entetes: tuple[str, ...], unite_temps: Literal["jours", "heures"], nom_fichier: str = "contraintes.csv"
) -> tuple[str, list[str]]:
    """Choisit la colonne de durée déclarée par `nom_fichier` parmi
    `COLONNES_DUREE_ACCEPTEES`, et avertit si son nom contredit `unite_temps`.

    Aucune conversion n'a lieu ici : un fichier en heures se lit en déclarant
    `unite_temps="heures"` à l'ingestion, ses entiers partent tels quels dans
    `CompatibiliteRessourceTache.duree`. Le nom de colonne n'est qu'une étiquette — d'où
    l'avertissement (§FC4, jamais une correction silencieuse) plutôt qu'une erreur quand
    `duree_heures` arrive avec `unite_temps="jours"` : c'est très probablement une unité mal
    choisie à l'import, mais seul un humain peut trancher. Deux colonnes de durée à la fois
    est en revanche une vraie ambiguïté, refusée."""
    presentes = [c for c in COLONNES_DUREE_ACCEPTEES if c in entetes]
    attendue = COLONNE_DUREE_PAR_UNITE[unite_temps]
    if len(presentes) > 1:
        raise ErreurFichierInvalide(
            f"{nom_fichier} : colonnes de durée multiples ({', '.join(presentes)}) — "
            f"n'en garder qu'une seule ({attendue} pour une instance en {unite_temps})."
        )
    if not presentes:
        return attendue, []
    colonne = presentes[0]
    autre_unite = COLONNE_DUREE_PAR_UNITE["heures" if unite_temps == "jours" else "jours"]
    avertissements = (
        [
            f"{nom_fichier} déclare la colonne « {colonne} » alors que l'instance est ingérée "
            f"en {unite_temps} : les durées sont reprises telles quelles, sans conversion. "
            f"Renommer la colonne en « {attendue} », ou ré-importer en "
            f"{'heures' if unite_temps == 'jours' else 'jours'}."
        ]
        if colonne == autre_unite
        else []
    )
    return colonne, avertissements


def _lire_contraintes(
    contenu: bytes,
    delimiteur: str = ",",
    unite_temps: Literal["jours", "heures"] = "jours",
    durees_par_tache: dict[str, int] | None = None,
) -> tuple[list[Contrainte], list[str]]:
    """Renvoie les contraintes explicites (precedence, compatibilite_ressource_tache
    et competence_requise, ces dernières incluses telles quelles — la
    dérivation partagée les relit directement depuis cette liste, voir
    `traduire`), plus les avertissements de lecture (voir `_colonne_duree`)."""
    lignes, entetes = _lire_lignes_et_entetes(
        contenu, "contraintes.csv", COLONNES_CONTRAINTES_REQUISES, COLONNES_CONTRAINTES_OPTIONNELLES, delimiteur
    )
    colonne_duree, avertissements = _colonne_duree(entetes, unite_temps)
    durees_par_tache = durees_par_tache or {}
    taches_sans_duree: set[str] = set()
    contraintes: list[Contrainte] = []
    for ligne in lignes:
        type_ = ligne["type"]
        if type_ == "precedence":
            contraintes.append(Precedence(avant=ligne["tache_avant"], apres=ligne["tache_apres"]))
        elif type_ == "compatibilite_ressource_tache":
            # La durée vient de la tâche (`taches.csv`). Une durée encore présente sur la ligne
            # (ancien format) l'emporte pour ce couple précis, et la divergence est signalée.
            brut = ligne[colonne_duree]
            if brut:
                try:
                    duree = int(float(brut))
                except ValueError as erreur:
                    raise ErreurFichierInvalide(
                        f"contraintes.csv : durée invalide « {brut} » pour "
                        f"{ligne['tache']}/{ligne['ressource']} — doit être un nombre entier de "
                        f"{unite_temps}, colonne « {colonne_duree} »."
                    ) from erreur
                if ligne["tache"] in durees_par_tache and durees_par_tache[ligne["tache"]] != duree:
                    avertissements.append(
                        f"contraintes.csv : durée {duree} déclarée pour {ligne['tache']}/"
                        f"{ligne['ressource']} — elle l'emporte sur la durée {durees_par_tache[ligne['tache']]} "
                        f"déclarée pour cette tâche dans taches.csv."
                    )
            elif ligne["tache"] in durees_par_tache:
                duree = durees_par_tache[ligne["tache"]]
            else:
                duree = DUREE_EN_ATTENTE_DE_COMMANDE
                taches_sans_duree.add(ligne["tache"])
            contraintes.append(
                CompatibiliteRessourceTache(tache=ligne["tache"], ressource=ligne["ressource"], duree=duree)
            )
        elif type_ == "competence_requise":
            contraintes.append(CompetenceRequise(tache=ligne["tache"], competence=ligne["competence"]))
        elif type_ == "declaration_materiau":
            try:
                stock_initial = float(ligne["stock_initial"])
            except ValueError as erreur:
                raise ErreurFichierInvalide(
                    f"contraintes.csv : stock initial invalide « {ligne['stock_initial']} » pour "
                    f"{ligne['materiau']!r}"
                ) from erreur
            contraintes.append(
                DeclarationMateriau(
                    materiau=ligne["materiau"],
                    stock_initial=stock_initial,
                    **({"unite": ligne["unite"]} if ligne["unite"] else {}),
                )
            )
        elif type_ == "consommation_matiere":
            try:
                quantite = float(ligne["quantite"])
            except ValueError as erreur:
                raise ErreurFichierInvalide(
                    f"contraintes.csv : quantité invalide « {ligne['quantite']} » pour "
                    f"{ligne['tache']}/{ligne['materiau']}"
                ) from erreur
            contraintes.append(
                ConsommationMatiere(tache=ligne["tache"], materiau=ligne["materiau"], quantite=quantite)
            )
        else:
            raise ErreurFichierInvalide(
                f"contraintes.csv : type de contrainte inconnu « {type_} » "
                f"(attendu : {', '.join(TYPES_CONTRAINTE_SUPPORTES)})"
            )
    if taches_sans_duree:
        avertissements.append(
            f"aucune durée déclarée pour {', '.join(sorted(taches_sans_duree))} : "
            f"{DUREE_EN_ATTENTE_DE_COMMANDE} {unite_temps} par défaut en attendant qu'une commande "
            f"fixe la durée de ces tâches — le planning produit d'ici là ne veut rien dire."
        )
    return contraintes, avertissements


def _lire_commandes(contenu: bytes, delimiteur: str = ",") -> list[Commande]:
    """`taches` (séparées par `;`, même convention que `competences` sur
    ressources.csv) — voir `adapters/commande_derivation.py::Commande`."""
    lignes = _lire_lignes(
        contenu, "commandes.csv", COLONNES_COMMANDES_REQUISES, COLONNES_COMMANDES_OPTIONNELLES, delimiteur
    )
    commandes: list[Commande] = []
    for ligne in lignes:
        taches_liees = tuple(t.strip() for t in ligne["taches"].split(SEPARATEUR_TACHES) if t.strip())
        if not taches_liees:
            raise ErreurFichierInvalide(f"commandes.csv : commande {ligne['id']!r} sans aucune tâche liée")
        date_limite: int | None = None
        if ligne["date_limite"]:
            try:
                date_limite = int(float(ligne["date_limite"]))
            except ValueError as erreur:
                raise ErreurFichierInvalide(
                    f"commandes.csv : date limite invalide « {ligne['date_limite']} » pour {ligne['id']!r}"
                ) from erreur
        commandes.append(
            Commande(id=ligne["id"], taches=taches_liees, client=ligne["client"] or None, date_limite=date_limite)
        )
    return commandes


def traduire(
    taches_csv: bytes,
    ressources_csv: bytes,
    contraintes_csv: bytes,
    commandes_csv: bytes | None = None,
    estimateur_duree: EstimateurDuree | None = None,
    delimiteur: str = ",",
    unite_temps: Literal["jours", "heures"] = "jours",
) -> ResultatTraduction:
    """Traduit trois fichiers CSV (Tâches, Ressources, Contraintes), plus un quatrième optionnel
        (Commandes), en une instance T-R-C-O. Lève `ErreurFichierInvalide` si un fichier est
        illisible, vide, qu'une colonne requise manque, ou qu'une tâche à compétence requise reste
        sans durée dérivable (`estimateur_duree` absent ou n'ayant rien pu estimer) ;
        `pydantic.ValidationError` si les données une fois lues ne forment pas une
        instance valide (id dupliqué, référence inconnue, tâche sans compatibilité...).

        `estimateur_duree` (optionnel, `estimation.EstimateurDuree`) comble, via apprentissage
        automatique (`estimation/`), la durée des tâches à compétence requise qui n'en ont
        aucune de connue — jamais silencieusement : chaque durée ainsi comblée ajoute un
        avertissement au `ResultatTraduction` renvoyé (§FC4, décision humaine préservée). Ignoré
        (comme si absent) si `unite_temps == "heures"` : entraîné sur une échelle jours
        (`estimation/donnees_historique.py`), une estimation à cette échelle serait fausse pour des
        durées en heures — limitation documentée, pas un ré-entraînement dans ce chantier.

        `delimiteur` (un seul caractère, `,` par défaut) s'applique identiquement aux quatre
        fichiers — un export cohérent utilise toujours le même séparateur partout.

    Aucun fichier ne déclare de durée : elle se fixe à la commande, tâche par tâche (voir
    `DUREE_EN_ATTENTE_DE_COMMANDE`). Une durée encore présente dans un fichier (`taches.csv` ou
    `contraintes.csv`, ancien format) reste lue et appliquée telle quelle, jamais exigée.

    `Ressource.heures_par_jour` (colonne optionnelle `heures_par_jour` de ressources.csv) devient
        une indisponibilité récurrente dérivée (`adapters/heures_travail.py`), signalée elle aussi par
        un avertissement — appliquée uniquement à une instance en heures.

        `unite_temps` ("jours" par défaut) devient `InstanceTRCO.unite_temps` tel quel — voir
        `dsl/schema/instance.py` pour ce que ça change (cycle de `ContrainteDisponibiliteRessource.
        jours_semaine_indisponibles`, affichage frontend). Il fixe aussi la colonne de durée attendue
        dans `contraintes.csv` (`duree_jours` ou `duree_heures`, voir `_colonne_duree`) : les entiers
        lus ne sont jamais convertis, c'est cette unité qui dit ce qu'ils valent."""
    if unite_temps == "heures":
        estimateur_duree = None
    taches, durees_par_tache = _lire_taches(taches_csv, delimiteur, unite_temps)
    ressources = _lire_ressources(ressources_csv, delimiteur)
    contraintes, avertissements_lecture = _lire_contraintes(
        contraintes_csv, delimiteur, unite_temps, durees_par_tache
    )
    # Durées déjà déclarées à la main : seule source de durée d'une compatibilité dérivée par
    # compétence depuis le retrait de l'estimation automatique de l'ingestion.
    durees_estimees_connues: dict[str, int] = {**durees_declarees_par_tache(contraintes), **durees_par_tache}

    avertissements: list[str] = list(avertissements_lecture)
    if estimateur_duree is not None:
        durees_estimees_connues, avertissements_estimation = completer_durees_par_estimation(
            contraintes, ressources, taches, durees_estimees_connues, estimateur_duree
        )
        avertissements += avertissements_estimation

    try:
        compatibilites_derivees = deriver_compatibilites_par_competence(
            contraintes, ressources, durees_estimees_connues
        )
    except CompetenceSansDureeEstimee as erreur:
        raise ErreurFichierInvalide(f"taches.csv : {erreur} (fournir un estimateur_duree)") from erreur

    commandes = _lire_commandes(commandes_csv, delimiteur) if commandes_csv is not None else []
    echeances_derivees = deriver_echeances_par_commande(commandes, contraintes)

    disponibilites_derivees, avertissements_horaires = deriver_disponibilites_horaires(
        ressources, contraintes, unite_temps
    )
    avertissements += avertissements_horaires

    instance = InstanceTRCO(
        taches=taches,
        ressources=ressources,
        contraintes=[*contraintes, *compatibilites_derivees, *echeances_derivees, *disponibilites_derivees],
        objectifs=[MinimiserMakespan()],
        unite_temps=unite_temps,
    )
    return ResultatTraduction(instance=instance, avertissements=tuple(avertissements))
