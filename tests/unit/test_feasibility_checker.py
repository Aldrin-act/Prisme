"""Couche 1 (§6.1) : le vérificateur de faisabilité est du code écrit à la
main, déterministe. Batterie exhaustive (§6.2 brique 1) — chaque type de
violation qu'il sait diagnostiquer est couvert par au moins un cas légal
voisin et un cas illégal qui le déclenche, en isolation des autres.
"""

from __future__ import annotations

from dsl.schema import (
    CompatibiliteMachineTache,
    InstanceTRCO,
    MinimiserMakespan,
    OperationPlanifiee,
    Planning,
    Precedence,
    Ressource,
    Tache,
)
from validation_engine.feasibility_checker import verifier_faisabilite


def _instance(taches, ressources, contraintes=()) -> InstanceTRCO:
    return InstanceTRCO(
        taches=taches,
        ressources=ressources,
        contraintes=list(contraintes),
        objectifs=[MinimiserMakespan()],
    )


def _planning(*operations: OperationPlanifiee) -> Planning:
    return Planning(operations=list(operations))


def _op(tache: str, ressource: str, debut: int) -> OperationPlanifiee:
    return OperationPlanifiee(tache=tache, ressource=ressource, debut=debut)


def test_planning_legal_est_accepte() -> None:
    instance = _instance(
        taches=[Tache(id="T1", duree=30), Tache(id="T2", duree=45), Tache(id="T3", duree=15)],
        ressources=[Ressource(id="M1"), Ressource(id="M2")],
        contraintes=[
            Precedence(avant="T1", apres="T2"),
            Precedence(avant="T2", apres="T3"),
            CompatibiliteMachineTache(tache="T1", ressource="M1"),
            CompatibiliteMachineTache(tache="T2", ressource="M1"),
            CompatibiliteMachineTache(tache="T2", ressource="M2"),
            CompatibiliteMachineTache(tache="T3", ressource="M2"),
        ],
    )
    planning = _planning(
        _op("T1", "M1", 0),
        _op("T2", "M2", 30),
        _op("T3", "M2", 75),
    )

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal
    assert resultat.violations == ()


def test_operations_bout_a_bout_sur_la_meme_ressource_sont_legales() -> None:
    instance = _instance(
        taches=[Tache(id="T1", duree=10), Tache(id="T2", duree=10)],
        ressources=[Ressource(id="M1")],
    )
    planning = _planning(_op("T1", "M1", 0), _op("T2", "M1", 10))

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_precedence_violee_est_detectee() -> None:
    # Deux ressources distinctes pour isoler la violation de précédence de
    # toute violation de chevauchement (même ressource + mêmes instants
    # déclencherait aussi un chevauchement_ressource).
    instance = _instance(
        taches=[Tache(id="T1", duree=30), Tache(id="T2", duree=10)],
        ressources=[Ressource(id="M1"), Ressource(id="M2")],
        contraintes=[Precedence(avant="T1", apres="T2")],
    )
    planning = _planning(_op("T1", "M1", 0), _op("T2", "M2", 20))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["precedence_violee"]
    assert resultat.violations[0].tache == "T1"
    assert resultat.violations[0].tache_secondaire == "T2"


def test_chevauchement_ressource_est_detecte() -> None:
    instance = _instance(
        taches=[Tache(id="T1", duree=10), Tache(id="T2", duree=10)],
        ressources=[Ressource(id="M1")],
    )
    planning = _planning(_op("T1", "M1", 0), _op("T2", "M1", 5))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["chevauchement_ressource"]
    violation = resultat.violations[0]
    assert violation.ressource == "M1"
    assert {violation.tache, violation.tache_secondaire} == {"T1", "T2"}


def test_incompatibilite_machine_tache_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1", duree=10)],
        ressources=[Ressource(id="M1"), Ressource(id="M2")],
        contraintes=[CompatibiliteMachineTache(tache="T1", ressource="M1")],
    )
    planning = _planning(_op("T1", "M2", 0))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["incompatibilite_machine_tache"]
    assert resultat.violations[0].tache == "T1"
    assert resultat.violations[0].ressource == "M2"


def test_tache_sans_contrainte_de_compatibilite_est_libre() -> None:
    """Absence de contrainte = absence de restriction (voir docstring du module)."""
    instance = _instance(
        taches=[Tache(id="T1", duree=10)],
        ressources=[Ressource(id="M1"), Ressource(id="M2")],
    )
    planning = _planning(_op("T1", "M2", 0))

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_tache_non_planifiee_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1", duree=10), Tache(id="T2", duree=10)],
        ressources=[Ressource(id="M1")],
    )
    planning = _planning(_op("T1", "M1", 0))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["tache_non_planifiee"]
    assert resultat.violations[0].tache == "T2"


def test_tache_planifiee_plusieurs_fois_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1", duree=10)],
        ressources=[Ressource(id="M1"), Ressource(id="M2")],
    )
    planning = _planning(_op("T1", "M1", 0), _op("T1", "M2", 0))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["tache_planifiee_plusieurs_fois"]
    assert resultat.violations[0].tache == "T1"


def test_tache_inconnue_dans_planning_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1", duree=10)],
        ressources=[Ressource(id="M1")],
    )
    planning = _planning(_op("T1", "M1", 0), _op("T99", "M1", 10))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["tache_inconnue_dans_planning"]
    assert resultat.violations[0].tache == "T99"


def test_ressource_inconnue_dans_planning_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1", duree=10)],
        ressources=[Ressource(id="M1")],
        contraintes=[CompatibiliteMachineTache(tache="T1", ressource="M1")],
    )
    planning = _planning(_op("T1", "M99", 0))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["ressource_inconnue_dans_planning"]
    assert resultat.violations[0].ressource == "M99"
