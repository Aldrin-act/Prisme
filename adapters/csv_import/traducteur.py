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
`CompatibiliteRessourceTache` pour chaque ressource qualifiée, avec la durée
estimée de la tâche (`taches.csv`, colonne `duree_estimee_jours`), appliquée
telle quelle à toutes ces ressources — même principe que
`adapters/greensig/translator.py` (`equipes_compatibles_pour`/
`duree_jours_pour`). Le DSL lui-même (`dsl/schema/instance.py`,
`_competences_requises_respectees`) revérifie ensuite que chaque compatibilité
déclarée pour une tâche à compétences requises couvre bien toutes ces
compétences — un garde-fou de plus, pas remplacé ici.

Les deux mécanismes (compatibilité explicite et compatibilité dérivée par
compétence) peuvent coexister pour une même tâche : leurs résultats s'additionnent,
rien n'oblige à choisir l'un ou l'autre pour toutes les tâches d'un même fichier.
"""

from __future__ import annotations

import csv
from io import StringIO

from adapters.competence_derivation import CompetenceSansDureeEstimee, deriver_compatibilites_par_competence
from dsl.schema import (
    CompatibiliteRessourceTache,
    CompetenceRequise,
    Contrainte,
    InstanceTRCO,
    MinimiserMakespan,
    Precedence,
    Ressource,
    Tache,
)

COLONNES_TACHES_REQUISES = ("id",)
COLONNES_TACHES_OPTIONNELLES = ("nom", "duree_estimee_jours")
COLONNES_RESSOURCES_REQUISES = ("id",)
COLONNES_RESSOURCES_OPTIONNELLES = ("nom", "competences")
COLONNES_CONTRAINTES_REQUISES = ("type",)
COLONNES_CONTRAINTES_OPTIONNELLES = (
    "tache_avant",
    "tache_apres",
    "tache",
    "ressource",
    "duree_jours",
    "competence",
)
TYPES_CONTRAINTE_SUPPORTES = ("precedence", "compatibilite_ressource_tache", "competence_requise")

# Séparateur des compétences dans une même cellule (ressources.csv) — la
# virgule est déjà le délimiteur CSV, illisible pour une liste dans une cellule.
SEPARATEUR_COMPETENCES = ";"


class ErreurFichierInvalide(Exception):
    """Fichier illisible ou colonne requise manquante — distinct d'une instance
    structurellement lue mais invalide au sens du DSL (ça, c'est une
    ValidationError Pydantic, même garde-fou que les autres canaux)."""


def _lire_lignes(
    contenu: bytes,
    nom_fichier: str,
    colonnes_requises: tuple[str, ...],
    colonnes_optionnelles: tuple[str, ...] = (),
) -> list[dict[str, str]]:
    """Décode et parse un CSV en liste de lignes (dict par en-tête de colonne).
    `utf-8-sig` tolère le BOM ajouté par certains tableurs à l'export, sans rien
    changer pour un CSV déjà en UTF-8 simple. Ignore les lignes où la première
    colonne requise est vide (ligne d'exemple laissée telle quelle, ligne vide
    en fin de fichier...). Les colonnes optionnelles absentes du fichier valent
    simplement "" partout plutôt que de faire échouer la lecture — ex.
    `competences`/`duree_estimee_jours`, inutiles tant qu'aucune compatibilité
    n'est dérivée par compétence."""
    try:
        texte = contenu.decode("utf-8-sig")
    except UnicodeDecodeError as erreur:
        raise ErreurFichierInvalide(f"{nom_fichier} : fichier illisible, encodage attendu UTF-8") from erreur

    lecteur = csv.DictReader(StringIO(texte))
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
    return [
        {c: (ligne.get(c) or "").strip() for c in toutes_colonnes}
        for ligne in lecteur
        if (ligne.get(premiere_colonne) or "").strip()
    ]


def _lire_taches(contenu: bytes) -> tuple[list[Tache], dict[str, int | None]]:
    """Renvoie les tâches ainsi que, par id, leur durée estimée (colonne
    `duree_estimee_jours`) — `None` si absente, seulement nécessaire pour
    les tâches dont la compatibilité est dérivée par compétence. Même
    structure que dans les autres adaptateurs pour cohérence."""
    lignes = _lire_lignes(contenu, "taches.csv", COLONNES_TACHES_REQUISES, COLONNES_TACHES_OPTIONNELLES)
    taches = [Tache(id=ligne["id"], **({"nom": ligne["nom"]} if ligne["nom"] else {})) for ligne in lignes]
    durees_estimees: dict[str, int | None] = {}
    for ligne in lignes:
        if not ligne["duree_estimee_jours"]:
            durees_estimees[ligne["id"]] = None
            continue
        try:
            durees_estimees[ligne["id"]] = int(float(ligne["duree_estimee_jours"]))
        except ValueError as erreur:
            raise ErreurFichierInvalide(
                f"taches.csv : durée estimée invalide « {ligne['duree_estimee_jours']} » pour {ligne['id']}"
            ) from erreur
    return taches, durees_estimees


def _lire_ressources(contenu: bytes) -> list[Ressource]:
    """`competences` (séparées par `;`) va directement sur `Ressource` — c'est
    déjà un champ réel du DSL, utilisé tel quel par la dérivation partagée
    (`adapters/competence_derivation.py`)."""
    lignes = _lire_lignes(
        contenu, "ressources.csv", COLONNES_RESSOURCES_REQUISES, COLONNES_RESSOURCES_OPTIONNELLES
    )
    return [
        Ressource(
            id=ligne["id"],
            **({"nom": ligne["nom"]} if ligne["nom"] else {}),
            competences=sorted(
                {c.strip() for c in ligne["competences"].split(SEPARATEUR_COMPETENCES) if c.strip()}
            ),
        )
        for ligne in lignes
    ]


def _lire_contraintes(contenu: bytes) -> list[Contrainte]:
    """Renvoie les contraintes explicites (precedence, compatibilite_ressource_tache
    et competence_requise, ces dernières incluses telles quelles — la
    dérivation partagée les relit directement depuis cette liste, voir
    `traduire`)."""
    lignes = _lire_lignes(
        contenu, "contraintes.csv", COLONNES_CONTRAINTES_REQUISES, COLONNES_CONTRAINTES_OPTIONNELLES
    )
    contraintes: list[Contrainte] = []
    for ligne in lignes:
        type_ = ligne["type"]
        if type_ == "precedence":
            contraintes.append(Precedence(avant=ligne["tache_avant"], apres=ligne["tache_apres"]))
        elif type_ == "compatibilite_ressource_tache":
            try:
                duree_jours = int(float(ligne["duree_jours"]))
            except ValueError as erreur:
                raise ErreurFichierInvalide(
                    f"contraintes.csv : durée invalide « {ligne['duree_jours']} » pour "
                    f"{ligne['tache']}/{ligne['ressource']} — doit être un nombre entier de jours."
                ) from erreur
            contraintes.append(
                CompatibiliteRessourceTache(tache=ligne["tache"], ressource=ligne["ressource"], duree=duree_jours)
            )
        elif type_ == "competence_requise":
            contraintes.append(CompetenceRequise(tache=ligne["tache"], competence=ligne["competence"]))
        else:
            raise ErreurFichierInvalide(
                f"contraintes.csv : type de contrainte inconnu « {type_} » "
                f"(attendu : {', '.join(TYPES_CONTRAINTE_SUPPORTES)})"
            )
    return contraintes


def traduire(taches_csv: bytes, ressources_csv: bytes, contraintes_csv: bytes) -> InstanceTRCO:
    """Traduit trois fichiers CSV (Tâches, Ressources, Contraintes) en une
    instance T-R-C-O. Lève `ErreurFichierInvalide` si un fichier est illisible,
    vide, ou qu'une colonne requise manque (y compris une durée estimée
    manquante pour une dérivation par compétence) ; `pydantic.ValidationError`
    si les données une fois lues ne forment pas une instance valide (id
    dupliqué, référence inconnue, tâche sans compatibilité...)."""
    taches, durees_estimees = _lire_taches(taches_csv)
    ressources = _lire_ressources(ressources_csv)
    contraintes = _lire_contraintes(contraintes_csv)
    durees_estimees_connues = {t: d for t, d in durees_estimees.items() if d is not None}

    try:
        compatibilites_derivees = deriver_compatibilites_par_competence(
            contraintes, ressources, durees_estimees_connues
        )
    except CompetenceSansDureeEstimee as erreur:
        raise ErreurFichierInvalide(f"taches.csv : {erreur} (colonne duree_estimee_jours)") from erreur

    return InstanceTRCO(
        taches=taches,
        ressources=ressources,
        contraintes=[*contraintes, *compatibilites_derivees],
        objectifs=[MinimiserMakespan()],
    )
