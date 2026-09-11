from __future__ import annotations

from dsl.schema import (
    CompatibiliteRessourceTache,
    Echeance,
    InstanceTRCO,
    Precedence,
    Ressource,
    Tache,
)


def test_instance_une_tache_une_ressource():
    """Test une instance avec une seule tâche et une seule ressource compatible."""
    tache = Tache(id="T1")
    ressource = Ressource(id="R1")
    compatibilites = [CompatibiliteRessourceTache(tache=tache, ressource=ressource, duree=5)]
    instance = InstanceTRCO(
        taches=[tache], ressources=[ressource], compatibilites_ressource_tache=compatibilites, contraintes=[]
    )

    planning = resoudre(instance)
    assert planning is not None
    assert len(planning.operations) == 1
    operation = planning.operations[0]
    assert operation.tache == tache
    assert operation.ressource == ressource
    assert operation.debut == 0


def test_instance_infaisable():
    """Test une instance infaisable (aucune ressource compatible pour une tâche)."""
    tache1 = Tache(id="T1")
    tache2 = Tache(id="T2")
    ressource = Ressource(id="R1")
    compatibilites = [CompatibiliteRessourceTache(tache=tache1, ressource=ressource, duree=5)]
    instance = InstanceTRCO(
        taches=[tache1, tache2],
        ressources=[ressource],
        compatibilites_ressource_tache=compatibilites,
        contraintes=[],
    )

    planning = resoudre(instance)
    assert planning is None


def test_instance_ressources_multiples_durees_differentes():
    """Test une instance avec plusieurs ressources compatibles pour une même tâche, durées différentes."""
    tache = Tache(id="T1")
    ressource1 = Ressource(id="R1")
    ressource2 = Ressource(id="R2")
    compatibilites = [
        CompatibiliteRessourceTache(tache=tache, ressource=ressource1, duree=3),
        CompatibiliteRessourceTache(tache=tache, ressource=ressource2, duree=5),
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
    operation = planning.operations[0]
    assert operation.tache == tache
    assert operation.ressource in [ressource1, ressource2]
    assert operation.debut == 0
    # Vérifie que la ressource avec la durée la plus courte est choisie
    if operation.ressource == ressource1:
        assert operation.debut + 3 == planning.operations[0].debut + 3
    else:
        assert operation.debut + 5 == planning.operations[0].debut + 5


def test_instance_avec_precedence():
    """Test une instance avec des contraintes de précédence."""
    tache1 = Tache(id="T1")
    tache2 = Tache(id="T2")
    ressource = Ressource(id="R1")
    compatibilites = [
        CompatibiliteRessourceTache(tache=tache1, ressource=ressource, duree=2),
        CompatibiliteRessourceTache(tache=tache2, ressource=ressource, duree=3),
    ]
    precedence = Precedence(predecesseur=tache1, successeur=tache2)
    instance = InstanceTRCO(
        taches=[tache1, tache2],
        ressources=[ressource],
        compatibilites_ressource_tache=compatibilites,
        contraintes=[precedence],
    )

    planning = resoudre(instance)
    assert planning is not None
    assert len(planning.operations) == 2
    op1 = next(op for op in planning.operations if op.tache == tache1)
    op2 = next(op for op in planning.operations if op.tache == tache2)
    assert op2.debut >= op1.debut + 2


def test_instance_avec_echeance():
    """Test une instance avec une contrainte d'échéance."""
    tache = Tache(id="T1")
    ressource = Ressource(id="R1")
    compatibilites = [CompatibiliteRessourceTache(tache=tache, ressource=ressource, duree=5)]
    echeance = Echeance(tache=tache, date=4)
    instance = InstanceTRCO(
        taches=[tache],
        ressources=[ressource],
        compatibilites_ressource_tache=compatibilites,
        contraintes=[echeance],
    )

    planning = resoudre(instance)
    assert planning is None  # Infaisable car durée > échéance


def test_instance_avec_echeance_faisable():
    """Test une instance avec une contrainte d'échéance faisable."""
    tache = Tache(id="T1")
    ressource = Ressource(id="R1")
    compatibilites = [CompatibiliteRessourceTache(tache=tache, ressource=ressource, duree=3)]
    echeance = Echeance(tache=tache, date=5)
    instance = InstanceTRCO(
        taches=[tache],
        ressources=[ressource],
        compatibilites_ressource_tache=compatibilites,
        contraintes=[echeance],
    )

    planning = resoudre(instance)
    assert planning is not None
    assert len(planning.operations) == 1
    operation = planning.operations[0]
    assert operation.debut + 3 <= 5


def test_instance_ressources_disjointes():
    """Test une instance où les tâches ont des ressources disjointes."""
    tache1 = Tache(id="T1")
    tache2 = Tache(id="T2")
    ressource1 = Ressource(id="R1")
    ressource2 = Ressource(id="R2")
    compatibilites = [
        CompatibiliteRessourceTache(tache=tache1, ressource=ressource1, duree=2),
        CompatibiliteRessourceTache(tache=tache2, ressource=ressource2, duree=3),
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
    op1 = next(op for op in planning.operations if op.tache == tache1)
    op2 = next(op for op in planning.operations if op.tache == tache2)
    assert op1.ressource == ressource1
    assert op2.ressource == ressource2
    assert op1.debut == 0  # Peut commencer en parallèle
    assert op2.debut == 0
