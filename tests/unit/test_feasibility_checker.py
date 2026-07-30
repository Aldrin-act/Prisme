"""Couche 1 (§6.1) : le vérificateur de faisabilité est du code écrit à la
main, déterministe. Batterie exhaustive (§6.2 brique 1) — chaque type de
violation qu'il sait diagnostiquer est couvert par au moins un cas légal
voisin et un cas illégal qui le déclenche, en isolation des autres.
"""

from __future__ import annotations

from dsl.schema import (
    CompatibiliteRessourceTache,
    ContrainteCapacite,
    ContrainteIncompatibilite,
    Echeance,
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
        taches=[Tache(id="T1"), Tache(id="T2"), Tache(id="T3")],
        ressources=[Ressource(id="R1"), Ressource(id="R2")],
        contraintes=[
            Precedence(avant="T1", apres="T2"),
            Precedence(avant="T2", apres="T3"),
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=30),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=45),
            CompatibiliteRessourceTache(tache="T2", ressource="R2", duree=45),
            CompatibiliteRessourceTache(tache="T3", ressource="R2", duree=15),
        ],
    )
    planning = _planning(
        _op("T1", "R1", 0),
        _op("T2", "R2", 30),
        _op("T3", "R2", 75),
    )

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal
    assert resultat.violations == ()


def test_operations_bout_a_bout_sur_la_meme_ressource_sont_legales() -> None:
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=10),
        ],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R1", 10))

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_precedence_violee_est_detectee() -> None:
    # Deux ressources distinctes pour isoler la violation de précédence de
    # toute violation de chevauchement (même ressource + mêmes instants
    # déclencherait aussi un chevauchement_ressource).
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1"), Ressource(id="R2")],
        contraintes=[
            Precedence(avant="T1", apres="T2"),
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=30),
            CompatibiliteRessourceTache(tache="T2", ressource="R2", duree=10),
        ],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R2", 20))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["precedence_violee"]
    assert resultat.violations[0].tache == "T1"
    assert resultat.violations[0].tache_secondaire == "T2"


def test_chevauchement_ressource_est_detecte() -> None:
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=10),
        ],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R1", 5))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["chevauchement_ressource"]
    violation = resultat.violations[0]
    assert violation.ressource == "R1"
    assert {violation.tache, violation.tache_secondaire} == {"T1", "T2"}


def test_incompatibilite_ressource_tache_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1"), Ressource(id="R2")],
        contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
    )
    planning = _planning(_op("T1", "R2", 0))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["incompatibilite_ressource_tache"]
    assert resultat.violations[0].tache == "T1"
    assert resultat.violations[0].ressource == "R2"


def test_tache_non_planifiee_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=10),
        ],
    )
    planning = _planning(_op("T1", "R1", 0))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["tache_non_planifiee"]
    assert resultat.violations[0].tache == "T2"


def test_tache_planifiee_plusieurs_fois_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1"), Ressource(id="R2")],
        contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T1", "R2", 0))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["tache_planifiee_plusieurs_fois"]
    assert resultat.violations[0].tache == "T1"


def test_tache_inconnue_dans_planning_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T99", "R1", 10))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["tache_inconnue_dans_planning"]
    assert resultat.violations[0].tache == "T99"


def test_ressource_inconnue_dans_planning_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
    )
    planning = _planning(_op("T1", "R99", 0))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["ressource_inconnue_dans_planning"]
    assert resultat.violations[0].ressource == "R99"


def test_echeance_respectee_est_legale() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            Echeance(tache="T1", echeance=10),
        ],
    )
    planning = _planning(_op("T1", "R1", 0))  # finit à 10 : échéance respectée pile

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_echeance_depassee_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            Echeance(tache="T1", echeance=5),
        ],
    )
    planning = _planning(_op("T1", "R1", 0))  # finit à 10, échéance à 5

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["echeance_depassee"]
    assert resultat.violations[0].tache == "T1"


def test_capacite_respectee_est_legale() -> None:
    """Deux tâches simultanées sur une ressource de capacité 2 : légal — le
    chevauchement seul (`chevauchement_ressource`, capacité implicite de 1)
    ne s'applique plus dès qu'une `ContrainteCapacite` couvre la ressource."""
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=10),
            ContrainteCapacite(ressource="R1", capacite=2),
        ],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R1", 5))

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_capacite_depassee_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2"), Tache(id="T3")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T3", ressource="R1", duree=10),
            ContrainteCapacite(ressource="R1", capacite=2),
        ],
    )
    # T1 [0,10), T2 [0,10), T3 [5,15) : 3 tâches actives à l'instant 5 > capacité 2.
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R1", 0), _op("T3", "R1", 5))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["capacite_depassee"]
    assert resultat.violations[0].ressource == "R1"


def test_capacite_bout_a_bout_reste_legale() -> None:
    """Une ressource de capacité 2 qui ne voit jamais plus de 2 tâches
    simultanées reste légale même avec plusieurs tâches au total."""
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2"), Tache(id="T3")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T3", ressource="R1", duree=10),
            ContrainteCapacite(ressource="R1", capacite=2),
        ],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R1", 0), _op("T3", "R1", 10))

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_incompatibilite_taches_respectee_est_legale() -> None:
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1"), Ressource(id="R2")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T2", ressource="R2", duree=10),
            ContrainteIncompatibilite(tache="T1", tache_incompatible="T2"),
        ],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R2", 0))

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_incompatibilite_taches_violee_est_detectee() -> None:
    """Même sans chevauchement temporel : deux tâches incompatibles sur la
    même ressource sont illégales quelle que soit l'heure."""
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=10),
            ContrainteIncompatibilite(tache="T1", tache_incompatible="T2"),
        ],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R1", 10))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert "incompatibilite_taches_violee" in [v.type for v in resultat.violations]
    violation = next(v for v in resultat.violations if v.type == "incompatibilite_taches_violee")
    assert {violation.tache, violation.tache_secondaire} == {"T1", "T2"}
    assert violation.ressource == "R1"
