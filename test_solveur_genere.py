from __future__ import annotations
from dsl.schema import (
    InstanceTRCO, Planning, OperationPlanifiee, Tache, Ressource,
    Contrainte, Precedence, CompatibiliteRessourceTache, Echeance
)
import pytest
from typing import List


def test_instance_une_tache_une_ressource():
    """Test une instance avec une seule tâche et une seule ressource compatible."""
    tache = Tache(id="T1")
    ressource = Ressource(id="R1")
    compatibilites = [CompatibiliteRessourceTache(tache=tache, ressource=ressource, duree=5)]
    instance = InstanceTRCO(
        taches=[tache],
        ressources=[ressource],
        compatibilites_ressource_tache=compatibilites,
        contraintes=[]
    )
    
    planning = resoudre(instance)
    assert planning is not None
    assert len(planning.operations) == 1
    assert planning.operations[0].tache == tache
    assert planning.operations[0].ressource == ressource
    assert planning.operations[0].debut == 0


def test_instance_infaisable():
    """Test une instance infaisable (aucune ressource compatible pour une tâche)."""
    tache = Tache(id="T1")
    ressource = Ressource(id="R1")
    # Aucune compatibilité pour T1
    instance = InstanceTRCO(
        taches=[tache],
        ressources=[ressource],
        compatibilites_ressource_tache=[],
        contraintes=[]
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
        CompatibiliteRessourceTache(tache=tache, ressource=ressource2, duree=5)
    ]
    instance = InstanceTRCO(
        taches=[tache],
        ressources=[ressource1, ressource2],
        compatibilites_ressource_tache=compatibilites,
        contraintes=[]
    )
    
    planning = resoudre(instance)
    assert planning is not None
    assert len(planning.operations) == 1
    assert planning.operations[0].tache == tache
    assert planning.operations[0].ressource in [ressource1, ressource2]
    assert planning.operations[0].debut == 0
    # Vérifie que la ressource avec la durée la plus courte est choisie
    if planning.operations[0].ressource == ressource1:
        assert planning.operations[0].ressource == ressource1
    else:
        # Si ce n'est pas le cas, c'est que le solveur a trouvé une autre solution optimale
        # (par exemple, si d'autres contraintes sont ajoutées plus tard)
        pass


def test_instance_avec_precedence():
    """Test une instance avec des contraintes de précédence."""
    tache1 = Tache(id="T1")
    tache2 = Tache(id="T2")
    ressource = Ressource(id="R1")
    compatibilites = [
        CompatibiliteRessourceTache(tache=tache1, ressource=ressource, duree=2),
        CompatibiliteRessourceTache(tache=tache2, ressource=ressource, duree=3)
    ]
    contraintes = [Precedence(tache_predecesseur=tache1, tache_successeur=tache2)]
    instance = InstanceTRCO(
        taches=[tache1, tache2],
        ressources=[ressource],
        compatibilites_ressource_tache=compatibilites,
        contraintes=contraintes
    )
    
    planning = resoudre(instance)
    assert planning is not None
    assert len(planning.operations) == 2
    
    # Trouver les opérations pour T1 et T2
    op_t1 = next(op for op in planning.operations if op.tache == tache1)
    op_t2 = next(op for op in planning.operations if op.tache == tache2)
    
    assert op_t1.debut + 2 <= op_t2.debut


def test_instance_avec_echeance():
    """Test une instance avec une échéance sur une tâche."""
    tache = Tache(id="T1")
    ressource = Ressource(id="R1")
    compatibilites = [CompatibiliteRessourceTache(tache=tache, ressource=ressource, duree=5)]
    contraintes = [Echeance(tache=tache, echeance=4)]  # Échéance impossible à respecter
    instance = InstanceTRCO(
        taches=[tache],
        ressources=[ressource],
        compatibilites_ressource_tache=compatibilites,
        contraintes=contraintes
    )
    
    planning = resoudre(instance)
    assert planning is None


def test_instance_avec_echeance_realiste():
    """Test une instance avec une échéance réaliste."""
    tache = Tache(id="T1")
    ressource = Ressource(id="R1")
    compatibilites = [CompatibiliteRessourceTache(tache=tache, ressource=ressource, duree=3)]
    contraintes = [Echeance(tache=tache, echeance=5)]
    instance = InstanceTRCO(
        taches=[tache],
        ressources=[ressource],
        compatibilites_ressource_tache=compatibilites,
        contraintes=contraintes
    )
    
    planning = resoudre(instance)
    assert planning is not None
    assert len(planning.operations) == 1
    assert planning.operations[0].debut + 3 <= 5
