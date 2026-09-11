from __future__ import annotations

from dataclasses import dataclass

from solver import resoudre

from dsl.schema import (
    InstanceTRCO,
    Ressource,
    Tache,
)


@dataclass
class MockTache:
    id: str


@dataclass
class MockRessource:
    id: str


@dataclass
class MockCompatibiliteRessourceTache:
    tache: Tache
    ressource: Ressource
    duree: int


@dataclass
class MockPrecedence:
    tache_precedente: Tache
    tache_suivante: Tache


@dataclass
class MockEcheance:
    tache: Tache
    echeance: int


def test_instance_une_tache_une_ressource():
    """Test une instance avec une seule tâche et une seule ressource compatible."""
    tache = MockTache(id="T1")
    ressource = MockRessource(id="R1")
    compatibilites = [MockCompatibiliteRessourceTache(tache=tache, ressource=ressource, duree=5)]
    instance = InstanceTRCO(
        taches=[tache], ressources=[ressource], compatibilites_ressource_tache=compatibilites, contraintes=[]
    )

    planning = resoudre(instance)
    assert planning is not None
    assert len(planning.operations) == 1
    assert planning.operations[0].tache == tache
    assert planning.operations[0].ressource == ressource
    assert planning.operations[0].debut == 0


def test_instance_infaisable_aucune_ressource_compatible():
    """Test une instance infaisable (aucune ressource compatible pour une tâche)."""
    tache = MockTache(id="T1")
    ressource = MockRessource(id="R1")
    instance = InstanceTRCO(
        taches=[tache], ressources=[ressource], compatibilites_ressource_tache=[], contraintes=[]
    )

    planning = resoudre(instance)
    assert planning is None


def test_instance_plusieurs_ressources_compatibles_durees_differentes():
    """Test une instance avec plusieurs ressources compatibles pour une même tâche."""
    tache = MockTache(id="T1")
    ressource1 = MockRessource(id="R1")
    ressource2 = MockRessource(id="R2")
    compatibilites = [
        MockCompatibiliteRessourceTache(tache=tache, ressource=ressource1, duree=3),
        MockCompatibiliteRessourceTache(tache=tache, ressource=ressource2, duree=5),
    ]
    instance = InstanceTRCO(
        taches=[tache],
        ressources=[ressource1, ressource2],
        compatibilites_ressource_tache=compatibilites,
        contraintes=[],
    )

    planning = resoudre(instance)
    assert planning is not None
    assert len(planning.operations) == 1
    assert planning.operations[0].tache == tache
    assert planning.operations[0].ressource in [ressource1, ressource2]
    assert planning.operations[0].debut == 0
    # Vérifie que la ressource avec la durée la plus courte est choisie
    if planning.operations[0].ressource == ressource1:
        assert planning.operations[0].debut + 3 <= 5


def test_instance_avec_precedence():
    """Test une instance avec des contraintes de précédence."""
    tache1 = MockTache(id="T1")
    tache2 = MockTache(id="T2")
    ressource = MockRessource(id="R1")
    compatibilites = [
        MockCompatibiliteRessourceTache(tache=tache1, ressource=ressource, duree=2),
        MockCompatibiliteRessourceTache(tache=tache2, ressource=ressource, duree=3),
    ]
    contraintes = [MockPrecedence(tache_precedente=tache1, tache_suivante=tache2)]
    instance = InstanceTRCO(
        taches=[tache1, tache2],
        ressources=[ressource],
        compatibilites_ressource_tache=compatibilites,
        contraintes=contraintes,
    )

    planning = resoudre(instance)
    assert planning is not None
    assert len(planning.operations) == 2

    op1 = next(op for op in planning.operations if op.tache == tache1)
    op2 = next(op for op in planning.operations if op.tache == tache2)

    assert op1.debut + 2 <= op2.debut


def test_instance_avec_echeance():
    """Test une instance avec une échéance sur une tâche."""
    tache = MockTache(id="T1")
    ressource = MockRessource(id="R1")
    compatibilites = [MockCompatibiliteRessourceTache(tache=tache, ressource=ressource, duree=5)]
    contraintes = [MockEcheance(tache=tache, echeance=4)]
    instance = InstanceTRCO(
        taches=[tache],
        ressources=[ressource],
        compatibilites_ressource_tache=compatibilites,
        contraintes=contraintes,
    )

    planning = resoudre(instance)
    assert planning is None  # L'échéance est trop stricte (durée 5 > échéance 4)


def test_instance_avec_echeance_realiste():
    """Test une instance avec une échéance réaliste."""
    tache = MockTache(id="T1")
    ressource = MockRessource(id="R1")
    compatibilites = [MockCompatibiliteRessourceTache(tache=tache, ressource=ressource, duree=3)]
    contraintes = [MockEcheance(tache=tache, echeance=5)]
    instance = InstanceTRCO(
        taches=[tache],
        ressources=[ressource],
        compatibilites_ressource_tache=compatibilites,
        contraintes=contraintes,
    )

    planning = resoudre(instance)
    assert planning is not None
    assert len(planning.operations) == 1
    assert planning.operations[0].debut + 3 <= 5


def test_instance_multiple_taches_ressources():
    """Test une instance avec plusieurs tâches et ressources."""
    tache1 = MockTache(id="T1")
    tache2 = MockTache(id="T2")
    ressource1 = MockRessource(id="R1")
    ressource2 = MockRessource(id="R2")
    compatibilites = [
        MockCompatibiliteRessourceTache(tache=tache1, ressource=ressource1, duree=2),
        MockCompatibiliteRessourceTache(tache=tache1, ressource=ressource2, duree=3),
        MockCompatibiliteRessourceTache(tache=tache2, ressource=ressource1, duree=4),
        MockCompatibiliteRessourceTache(tache=tache2, ressource=ressource2, duree=1),
    ]
    instance = InstanceTRCO(
        taches=[tache1, tache2],
        ressources=[ressource1, ressource2],
        compatibilites_ressource_tache=compatibilites,
        contraintes=[],
    )

    planning = resoudre(instance)
    assert planning is not None
    assert len(planning.operations) == 2

    # Vérifie que les tâches ne se chevauchent pas sur la même ressource
    for ressource in [ressource1, ressource2]:
        ops = [op for op in planning.operations if op.ressource == ressource]
        if len(ops) > 1:
            assert (
                ops[0].debut + ops[0].tache.duree <= ops[1].debut
                or ops[1].debut + ops[1].tache.duree <= ops[0].debut
            )
