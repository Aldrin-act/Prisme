"""Couche 1 (§6.1) : calendrier ouvré (`dsl/calendrier.py`) — une opération travaille jusqu'à la
fermeture, s'arrête, reprend à l'ouverture (nuit et week-end) — et ses trois consommateurs :
garde-fou de faisabilité, correction post-solveur, makespan.

Conventions : mode heures, ouvré = 8h-22h hors samedi/dimanche. `position_zero_semaine` = position de
l'instant 0 dans la semaine (0 = dimanche 00h) : lundi 00h = 24, vendredi 00h = 120.
"""

from __future__ import annotations

from datetime import UTC, datetime

from dsl.calendrier import (
    avec_calendrier,
    est_instant_ouvre,
    fin_calendaire,
    premier_instant_ouvert,
    segments_travailles,
)
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
from validation_engine.makespan import calculer_makespan

LUNDI_00H = 24
VENDREDI_00H = 120


def _instance(position: int | None, duree_a: int = 5, duree_b: int = 2, precedence: bool = True) -> InstanceTRCO:
    contraintes: list = [
        CompatibiliteRessourceTache(tache="A", ressource="R1", duree=duree_a),
        CompatibiliteRessourceTache(tache="B", ressource="R1", duree=duree_b),
    ]
    if precedence:
        contraintes.append(Precedence(avant="A", apres="B"))
    return InstanceTRCO(
        taches=[Tache(id="A"), Tache(id="B")],
        ressources=[Ressource(id="R1")],
        contraintes=contraintes,
        objectifs=[MinimiserMakespan()],
        unite_temps="heures",
        position_zero_semaine=position,
    )


def _planning(**debuts: int) -> Planning:
    return Planning(operations=[OperationPlanifiee(tache=t, ressource="R1", debut=d) for t, d in debuts.items()])


def test_sans_calendrier_la_fin_reste_debut_plus_duree() -> None:
    instance = _instance(None)

    assert fin_calendaire(instance, 19, 5) == 24
    assert est_instant_ouvre(instance, 3) is True


def test_mode_jours_ignore_le_calendrier_meme_avec_une_position() -> None:
    instance = _instance(LUNDI_00H).model_copy(update={"unite_temps": "jours"})

    assert fin_calendaire(instance, 19, 5) == 24


def test_operation_qui_traverse_la_nuit_s_arrete_a_22h_et_reprend_a_8h() -> None:
    """Lundi 19h, 5 h de travail : 19h-22h (3 h), pause, mardi 8h-10h (2 h) — fin mardi 10h."""
    instance = _instance(LUNDI_00H)

    assert fin_calendaire(instance, 19, 5) == 34  # mardi 10h = 24 + 10
    assert segments_travailles(instance, 19, 5) == [(19, 22), (32, 34)]


def test_operation_demarrant_a_une_heure_fermee_commence_a_l_ouverture() -> None:
    instance = _instance(LUNDI_00H)

    assert premier_instant_ouvert(instance, 3) == 8
    assert fin_calendaire(instance, 3, 2) == 10


def test_le_week_end_est_traverse_comme_la_nuit() -> None:
    """Vendredi 20h, 4 h : 20h-22h (2 h), samedi/dimanche fermés, lundi 8h-10h (2 h)."""
    instance = _instance(VENDREDI_00H)

    assert fin_calendaire(instance, 20, 4) == 82  # lundi 10h = 72 + 10
    assert segments_travailles(instance, 20, 4) == [(20, 22), (80, 82)]


def test_avec_calendrier_ancre_l_instant_zero_sur_l_heure_du_moment() -> None:
    instance = _instance(None)
    lundi_10h44 = datetime(2026, 9, 21, 10, 44, tzinfo=UTC)  # 2026-09-21 est un lundi

    assert avec_calendrier(instance, lundi_10h44).position_zero_semaine == LUNDI_00H + 10


def test_garde_fou_refuse_un_demarrage_hors_heures_ouvrees() -> None:
    instance = _instance(LUNDI_00H, precedence=False)

    verdict = verifier_faisabilite(instance, _planning(A=3, B=100))

    assert "debut_hors_heures_ouvrees" in {v.type for v in verdict.violations}


def test_garde_fou_utilise_la_fin_calendaire_pour_les_precedences() -> None:
    """A finit mardi 10h (instant 34) : B ne peut pas démarrer mardi 9h (33), même si
    `debut + duree` (19 + 5 = 24) laisserait croire le contraire."""
    instance = _instance(LUNDI_00H)

    trop_tot = verifier_faisabilite(instance, _planning(A=19, B=33))
    a_temps = verifier_faisabilite(instance, _planning(A=19, B=34))

    assert "precedence_violee" in {v.type for v in trop_tot.violations}
    assert a_temps.legal


def test_correction_rend_legal_un_planning_qui_ignore_le_calendrier() -> None:
    """Un solveur qui ne connaît pas le calendrier place A à 3h (nuit) et B juste après `debut+duree`."""
    instance = _instance(LUNDI_00H)
    planning = _planning(A=3, B=8)  # B « juste après » A (3 + 5) en ignorant la nuit

    corrige = repousser_hors_jours_non_ouvres(instance, planning, datetime(2026, 9, 21, tzinfo=UTC))

    debuts = {op.tache: op.debut for op in corrige.operations}
    assert debuts["A"] == 8  # première heure ouvrée
    assert debuts["B"] == 13  # après la fin calendaire de A (8 + 5)
    assert verifier_faisabilite(instance, corrige).legal


def test_correction_laisse_inchange_un_planning_deja_conforme() -> None:
    instance = _instance(LUNDI_00H)
    planning = _planning(A=19, B=34)

    corrige = repousser_hors_jours_non_ouvres(instance, planning, datetime(2026, 9, 21, tzinfo=UTC))

    assert {op.tache: op.debut for op in corrige.operations} == {"A": 19, "B": 34}


def test_makespan_est_la_fin_calendaire_de_la_derniere_operation() -> None:
    instance = _instance(LUNDI_00H)

    assert calculer_makespan(instance, _planning(A=19, B=34)) == 36  # B : mardi 10h + 2 h = 12h
    assert calculer_makespan(_instance(None), _planning(A=19, B=34)) == 36
