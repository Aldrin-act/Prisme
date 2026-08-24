"""Couche 1 (§6.1) : `estimation/` — nécessite l'extra optionnel `estimation`
(`uv sync --extra estimation`) ; s'auto-ignore sinon, même esprit que les
tests Docker/Postgres qui s'auto-ignorent si le service est injoignable
(voir CLAUDE.md)."""

from __future__ import annotations

import pytest

pytest.importorskip("sklearn")

from adapters.competence_derivation import deriver_compatibilites_par_competence  # noqa: E402
from dsl.schema import CompetenceRequise, Ressource, Tache  # noqa: E402
from estimation import EstimateurDuree, historique_synthetique, vers_durees_estimees_par_tache  # noqa: E402


def _ressource_depuis_observation(observation) -> Ressource:  # type: ignore[no-untyped-def]
    type_ressource = ["machine", "humain", "equipe"][observation.ressource_type_index]
    return Ressource(
        id=observation.ressource_id,
        type=type_ressource,
        competences=[f"c{i}" for i in range(observation.ressource_nb_competences)],
    )


def test_historique_synthetique_produit_des_observations() -> None:
    observations = historique_synthetique()
    # 5 cas du banc synthétique (Étape 3), 1+3+9+25+80 compatibilités déclarées.
    assert len(observations) == 1 + 3 + 9 + 25 + 80
    assert all(o.duree_observee_jours >= 1 for o in observations)


def test_entrainer_exige_un_minimum_d_observations() -> None:
    with pytest.raises(ValueError, match="au moins"):
        EstimateurDuree.entrainer(historique_synthetique()[:2])


def test_estimateur_retrouve_le_signal_synthetique_connu() -> None:
    """`duree_observee_jours` est une fonction connue des traits
    (`donnees_historique.py::_duree_observee`) — un modèle qui l'a appris
    doit s'en approcher, pas juste « faire au mieux »."""
    observations = historique_synthetique()
    estimateur = EstimateurDuree.entrainer(observations)

    erreurs = []
    for o in observations:
        tache = Tache(id=o.tache_id, quantite=o.tache_quantite, priorite=o.tache_priorite)
        ressource = _ressource_depuis_observation(o)
        estimation = estimateur.estimer(tache, ressource)
        erreurs.append(abs(estimation.duree_estimee_jours - o.duree_observee_jours))

    mae = sum(erreurs) / len(erreurs)
    assert mae < 2.5  # le résidu synthétique lui-même est borné à [-2, +2] jours


def test_vers_durees_estimees_par_tache_filtre_sous_le_seuil_de_confiance() -> None:
    estimateur = EstimateurDuree.entrainer(historique_synthetique())
    tache = Tache(id="T_NOUVELLE", quantite=5, priorite=2)
    ressource = Ressource(id="R_NOUVELLE", type="machine", competences=["x"])
    estimation = estimateur.estimer(tache, ressource)

    assert vers_durees_estimees_par_tache([estimation], seuil_confiance=0.0) == {
        "T_NOUVELLE": estimation.duree_estimee_jours
    }
    assert vers_durees_estimees_par_tache([estimation], seuil_confiance=1.1) == {}


def test_estimation_branchable_dans_la_derivation_par_competence() -> None:
    """Preuve bout en bout du point d'intégration existant
    (`adapters/competence_derivation.py`) : le dict produit par
    `vers_durees_estimees_par_tache` doit être directement acceptable par
    `deriver_compatibilites_par_competence`, sans aucune adaptation."""
    estimateur = EstimateurDuree.entrainer(historique_synthetique())
    tache = Tache(id="T1", quantite=5, priorite=2)
    ressource = Ressource(id="R1", type="machine", competences=["decoupe"])
    estimation = estimateur.estimer(tache, ressource)
    durees = vers_durees_estimees_par_tache([estimation], seuil_confiance=0.0)

    derivees = deriver_compatibilites_par_competence(
        [CompetenceRequise(tache="T1", competence="decoupe")], [ressource], durees
    )

    assert len(derivees) == 1
    assert derivees[0].duree == durees["T1"]
