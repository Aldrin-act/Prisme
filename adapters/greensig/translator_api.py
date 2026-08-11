"""Traduction GreenSIG (API HTTP publique) → T-R-C-O — variante alternative à `translator.py`
(base Postgres directe), sélectionnée par `GREENSIG_MODE=api` (voir `service.py`).

Limites propres à ce payload précis, différentes de celles de `translator.py` (§5.4) :

- Pas de dérivation de compatibilité par compétence : l'API publique n'expose aucune donnée de
  compétence (`competences/`/`types-tache/` inexistants, vérifié). Compatibilité dérivée
  uniquement de `taches[].equipes` (les noms d'équipe listés par la tâche elle-même) — jointure par
  **nom**, fragile si deux équipes partagent un nom, mais aucune autre clé n'est disponible côté
  API (contrairement au chemin DB qui joint par identifiant numérique).
- Pas de durée par tâche : l'API ne fournit aucun champ de charge/durée (contrairement à
  `charge_estimee_heures` côté DB) — `CompatibiliteRessourceTache.duree` vaut toujours 1 jour,
  décision explicite plutôt qu'une estimation inventée.
- Deux concepts absents du chemin DB : les jours fériés (`jours-feries/`) et les absences
  individuelles (`absences/`), toutes deux traduites en `ContrainteDisponibiliteRessource` — une
  absence rend indisponible l'**équipe entière** de l'opérateur absent (décision explicite : le DSL
  ne modélise pas la capacité réduite d'une équipe, seulement une ressource disponible ou non).
  Jours fériés et absences convergent vers **une seule** contrainte par ressource concernée (union
  des jours indisponibles), jamais une par source, pour ne jamais dépendre du nombre de
  `ContrainteDisponibiliteRessource` admissibles par ressource.
- Réclamations (`reclamations/`) jamais traduites — hors périmètre, décision explicite.

Première conversion date-calendaire → jour relatif de ce dépôt (aucun précédent ailleurs dans le
code, recherche exhaustive faite) : `jour_relatif` prend une date de référence explicite (jour 0),
`date.today()` par défaut au moment de l'appel — cohérent avec `Echeance`/`ContrainteDisponibiliteRessource`
qui exigent toutes deux des jours relatifs, jamais une date calendaire (`dsl/schema/contraintes.py`).
Les jours strictement négatifs (une date déjà passée au moment de l'appel) sont filtrés avant
émission : sans effet réel sur un horizon de planification qui démarre à aujourd'hui.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from dsl.schema import (
    CompatibiliteRessourceTache,
    Contrainte,
    ContrainteDisponibiliteRessource,
    InstanceTRCO,
    MinimiserMakespan,
    Ressource,
    Tache,
)

from .schema_greensig_api import EquipeApiGreenSIG, PayloadGreenSIGApi

_DUREE_PAR_DEFAUT_JOURS = 1  # l'API publique ne fournit aucune durée/charge estimée par tâche
_STATUT_ABSENCE_VALIDEE = "Validée"


def id_ressource(id_brut: int) -> str:
    return f"E{id_brut}"


def jour_relatif(date_iso: str, date_reference: date) -> int:
    """Convertit une date calendaire ISO (`YYYY-MM-DD`) en jour relatif à `date_reference`
    (jour 0) — même référentiel que `Echeance`/`ContrainteDisponibiliteRessource`, jamais une date
    calendaire directement dans le DSL."""
    return (date.fromisoformat(date_iso) - date_reference).days


def _jours_feries_relatifs(payload: PayloadGreenSIGApi, date_reference: date) -> set[int]:
    return {j for j in (jour_relatif(jf.date, date_reference) for jf in payload.jours_feries) if j >= 0}


def _jours_absence_par_equipe(
    payload: PayloadGreenSIGApi, equipes_actives: dict[str, EquipeApiGreenSIG], date_reference: date
) -> dict[str, set[int]]:
    """Équipe (nom) → jours relatifs où au moins un de ses opérateurs est en absence validée.
    Un opérateur absent sans équipe connue, ou dont l'équipe n'existe pas/n'est pas active, est
    ignoré (pas d'erreur — même esprit que la compatibilité tâche-équipe ci-dessous)."""
    operateurs_par_nom = {o.nom_complet: o for o in payload.operateurs}
    jours: dict[str, set[int]] = defaultdict(set)
    for absence in payload.absences:
        if absence.statut != _STATUT_ABSENCE_VALIDEE:
            continue
        operateur = operateurs_par_nom.get(absence.operateur)
        if operateur is None or operateur.equipe not in equipes_actives:
            continue
        debut = jour_relatif(absence.date_debut, date_reference)
        fin = jour_relatif(absence.date_fin, date_reference)
        jours[operateur.equipe] |= {j for j in range(debut, fin + 1) if j >= 0}
    return jours


def traduire_api(payload: PayloadGreenSIGApi, date_reference: date | None = None) -> InstanceTRCO:
    """Traduit un extrait de l'API publique GreenSIG (tâches, équipes, opérateurs, absences, jours
    fériés) en instance T-R-C-O. `date_reference` fixe le jour 0 de la conversion calendaire → jour
    relatif — paramétrable pour des tests déterministes, `date.today()` sinon."""
    date_reference = date_reference or date.today()

    equipes_actives = {e.nom_equipe: e for e in payload.equipes if e.actif}
    ressources = [
        Ressource(id=id_ressource(e.id), nom=e.nom_equipe, type="equipe") for e in equipes_actives.values()
    ]

    taches = [Tache(id=t.reference, nom=t.type_tache, priorite=t.priorite) for t in payload.taches]

    contraintes: list[Contrainte] = []
    for t in payload.taches:
        for nom_equipe in t.equipes:
            equipe = equipes_actives.get(nom_equipe)
            if equipe is None:
                continue  # équipe inconnue ou inactive référencée par la tâche — ignorée
            contraintes.append(
                CompatibiliteRessourceTache(
                    tache=t.reference, ressource=id_ressource(equipe.id), duree=_DUREE_PAR_DEFAUT_JOURS
                )
            )

    jours_feries = _jours_feries_relatifs(payload, date_reference)
    jours_absence_par_equipe = _jours_absence_par_equipe(payload, equipes_actives, date_reference)

    jours_indisponibles_par_ressource: dict[str, set[int]] = defaultdict(set)
    for nom_equipe, equipe in equipes_actives.items():
        jours_indisponibles_par_ressource[id_ressource(equipe.id)] |= jours_feries
        jours_indisponibles_par_ressource[id_ressource(equipe.id)] |= jours_absence_par_equipe.get(
            nom_equipe, set()
        )

    contraintes += [
        ContrainteDisponibiliteRessource(ressource=id_ress, jours_indisponibles=sorted(jours))
        for id_ress, jours in jours_indisponibles_par_ressource.items()
        if jours
    ]

    return InstanceTRCO(
        taches=taches, ressources=ressources, contraintes=contraintes, objectifs=[MinimiserMakespan()]
    )
