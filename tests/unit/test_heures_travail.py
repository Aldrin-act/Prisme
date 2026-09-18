"""Couche 1 (§6.1) : `adapters/heures_travail.py` — la durée de travail quotidienne d'une
ressource (`Ressource.heures_par_jour`) devient une indisponibilité récurrente ordinaire, dérivée
à l'ingestion. Aucun nouveau mécanisme côté DSL/solveur : une `ContrainteDisponibiliteRessource`
comme une autre."""

from __future__ import annotations

from adapters.heures_travail import deriver_disponibilites_horaires
from dsl.schema import ContrainteDisponibiliteRessource, Ressource


def test_journee_de_travail_rend_indisponible_le_reste_de_chaque_journee() -> None:
    derivees, avertissements = deriver_disponibilites_horaires(
        [Ressource(id="R1", heures_par_jour=8)], [], "heures"
    )

    assert len(derivees) == 1
    positions = derivees[0].jours_semaine_indisponibles
    assert len(positions) == 7 * 16  # 16 h non travaillées, sur les 7 journées du cycle
    assert all(p % 24 >= 8 for p in positions)
    assert max(positions) < 168  # jamais hors du cycle en mode heures
    assert len(avertissements) == 1


def test_journee_complete_ne_derive_rien() -> None:
    assert deriver_disponibilites_horaires([Ressource(id="R1", heures_par_jour=24)], [], "heures") == ([], [])


def test_sans_heures_par_jour_ne_derive_rien() -> None:
    assert deriver_disponibilites_horaires([Ressource(id="R1")], [], "heures") == ([], [])


def test_mode_jours_ne_derive_rien_et_previent() -> None:
    derivees, avertissements = deriver_disponibilites_horaires(
        [Ressource(id="R1", heures_par_jour=8)], [], "jours"
    )

    assert derivees == []
    assert "n'est pas appliqué" in avertissements[0]


def test_disponibilite_explicite_lemporte_et_est_signalee() -> None:
    explicite = ContrainteDisponibiliteRessource(ressource="R1", jours_indisponibles=[3])

    derivees, avertissements = deriver_disponibilites_horaires(
        [Ressource(id="R1", heures_par_jour=8)], [explicite], "heures"
    )

    assert derivees == []
    assert "l'emporte" in avertissements[0]


def test_chaque_ressource_est_traitee_independamment() -> None:
    ressources = [
        Ressource(id="R1", heures_par_jour=8),
        Ressource(id="R2"),
        Ressource(id="R3", heures_par_jour=12),
    ]

    derivees, _ = deriver_disponibilites_horaires(ressources, [], "heures")

    assert [d.ressource for d in derivees] == ["R1", "R3"]
    assert len(derivees[1].jours_semaine_indisponibles) == 7 * 12
