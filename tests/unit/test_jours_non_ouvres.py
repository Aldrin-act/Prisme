"""Couche 1 (§6.1) : `validation_engine/jours_non_ouvres.py` est du code écrit à la main,
déterministe — pure correction post-solveur, jamais un changement de sémantique du DSL.

Référence commune à tous les tests : jour 0 = vendredi 2024-01-05 (UTC), jours 1-2 = samedi/
dimanche (bloqués), jour 3 = lundi — vérifié une fois pour toutes (voir shell history de
conception), jamais recalculé par magie ici.
"""

from __future__ import annotations

from datetime import UTC, datetime

from dsl.schema import (
    CompatibiliteRessourceTache,
    InstanceTRCO,
    MinimiserMakespan,
    OperationPlanifiee,
    Planning,
    Precedence,
    Ressource,
    Tache,
)
from validation_engine.feasibility_checker import verifier_faisabilite
from validation_engine.jours_non_ouvres import repousser_hors_jours_non_ouvres

REFERENCE = datetime(2024, 1, 5, tzinfo=UTC)  # vendredi ; +1/+2 = samedi/dimanche ; +3 = lundi


def _instance(taches, ressources, contraintes=(), unite_temps="jours", jours_fermes=None) -> InstanceTRCO:
    kwargs = {} if jours_fermes is None else {"jours_fermes": jours_fermes}
    return InstanceTRCO(
        taches=taches,
        ressources=ressources,
        contraintes=list(contraintes),
        objectifs=[MinimiserMakespan()],
        unite_temps=unite_temps,
        **kwargs,
    )


def _planning(*operations: OperationPlanifiee) -> Planning:
    return Planning(operations=list(operations))


def _op(tache: str, ressource: str, debut: int) -> OperationPlanifiee:
    return OperationPlanifiee(tache=tache, ressource=ressource, debut=debut)


def test_planning_qui_ne_touche_jamais_le_week_end_est_inchange() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=1)],
    )
    planning = _planning(_op("T1", "R1", 0))  # vendredi, ne chevauche rien

    resultat = repousser_hors_jours_non_ouvres(instance, planning, REFERENCE)

    assert resultat.operations[0].debut == 0


def test_operation_demarrant_le_week_end_est_repoussee_au_lundi() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=1)],
    )
    planning = _planning(_op("T1", "R1", 1))  # samedi

    resultat = repousser_hors_jours_non_ouvres(instance, planning, REFERENCE)

    assert resultat.operations[0].debut == 3  # lundi


def test_operation_chevauchant_vendredi_samedi_est_repoussee_en_bloc() -> None:
    """Durée 2 démarrant vendredi (jour 0) chevauche samedi (jour 1) — jamais coupée en deux,
    repoussée entièrement après le week-end."""
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=2)],
    )
    planning = _planning(_op("T1", "R1", 0))

    resultat = repousser_hors_jours_non_ouvres(instance, planning, REFERENCE)

    assert resultat.operations[0].debut == 3  # lundi, jamais vendredi+samedi coupé


def test_ecart_original_entre_deux_operations_de_la_meme_ressource_est_preserve() -> None:
    """T1 (jour 1, durée 1, fin originale=2) puis T2 démarre au jour 5 dans le planning
    d'origine — un écart délibéré de 3 jours (ex. temps de changement de série) après la fin
    originale de T1. Si T1 est repoussé après le week-end, cet écart de 3 doit être préservé,
    jamais comprimé à 0."""
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=1),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=1),
        ],
    )
    planning = _planning(_op("T1", "R1", 1), _op("T2", "R1", 5))

    resultat = repousser_hors_jours_non_ouvres(instance, planning, REFERENCE)

    debuts = {op.tache: op.debut for op in resultat.operations}
    assert debuts["T1"] == 3  # lundi
    assert debuts["T2"] == 7  # fin décalée de T1 (4) + écart original préservé (3)


def test_precedence_propage_le_decalage_au_successeur() -> None:
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1"), Ressource(id="R2")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=1),
            CompatibiliteRessourceTache(tache="T2", ressource="R2", duree=1),
            Precedence(avant="T1", apres="T2"),
        ],
    )
    # T1 au jour 1 (samedi) ; T2 au jour 2 dans l'original (démarre juste à la fin de T1, écart 0).
    planning = _planning(_op("T1", "R1", 1), _op("T2", "R2", 2))

    resultat = repousser_hors_jours_non_ouvres(instance, planning, REFERENCE)

    debuts = {op.tache: op.debut for op in resultat.operations}
    assert debuts["T1"] == 3  # lundi
    assert debuts["T2"] == 4  # juste après la fin décalée de T1, même écart (0) préservé


def test_operation_gelee_nest_jamais_decalee() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=1)],
    )
    planning = _planning(_op("T1", "R1", 1))  # samedi

    resultat = repousser_hors_jours_non_ouvres(
        instance, planning, REFERENCE, operations_gelees=frozenset({("T1", "R1")})
    )

    assert resultat.operations[0].debut == 1  # inchangé malgré le week-end


def test_mode_heures_utilise_un_cycle_de_168() -> None:
    """Même référence (vendredi) mais en mode heures : le week-end commence à l'heure 24
    (samedi 00:00) et dure 48 heures, jusqu'à l'heure 72 (lundi 00:00)."""
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=1)],
        unite_temps="heures",
    )
    planning = _planning(_op("T1", "R1", 30))  # samedi 06:00

    resultat = repousser_hors_jours_non_ouvres(instance, planning, REFERENCE)

    assert resultat.operations[0].debut == 72  # lundi 00:00


def test_operation_plus_longue_que_la_plus_longue_plage_ouvree_ne_boucle_pas_indefiniment() -> None:
    """Une opération de durée 10 (> 5, la plus longue plage continue de jours non bloqués entre
    deux week-ends) ne peut *par construction* jamais éviter tout instant bloqué, quel que soit
    son point de départ — régression : observée en conditions réelles (solveur `_solveur_minimal`,
    instance à une tâche de durée 10 jours) provoquant plusieurs millions d'itérations jusqu'à
    `OverflowError` sur l'arithmétique de dates avant le correctif. Doit maintenant se terminer
    immédiatement, sans lever d'exception."""
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
    )
    planning = _planning(_op("T1", "R1", 0))

    resultat = repousser_hors_jours_non_ouvres(instance, planning, REFERENCE)

    # Aucune exception levée (c'était le bug) ; le résultat reste borné et déterministe.
    assert 0 <= resultat.operations[0].debut < 100


def test_jours_fermes_personnalises_remplacent_le_week_end_par_defaut() -> None:
    """`jours_fermes=[5]` (vendredi seul, convention 0=dimanche..6=samedi) : le jour 0 (vendredi,
    normalement ouvert) devient fermé, mais samedi/dimanche (jours 1-2) redeviennent ouverts —
    confirme que la configuration remplace bien le week-end codé en dur, pas un ajout."""
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=1)],
        jours_fermes=[5],
    )
    planning = _planning(_op("T1", "R1", 0))  # vendredi, désormais fermé

    resultat = repousser_hors_jours_non_ouvres(instance, planning, REFERENCE)

    assert resultat.operations[0].debut == 1  # samedi, désormais ouvert


def test_jours_fermes_vide_ne_decale_jamais_rien() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=1)],
        jours_fermes=[],
    )
    planning = _planning(_op("T1", "R1", 1))  # samedi, mais plus aucun jour fermé déclaré

    resultat = repousser_hors_jours_non_ouvres(instance, planning, REFERENCE)

    assert resultat.operations[0].debut == 1


def test_resultat_reste_legal_apres_correction() -> None:
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=1),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=2),
        ],
    )
    planning = _planning(_op("T1", "R1", 1), _op("T2", "R1", 2))

    resultat = repousser_hors_jours_non_ouvres(instance, planning, REFERENCE)

    assert verifier_faisabilite(instance, resultat).legal
