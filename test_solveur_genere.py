from dsl.schema import (
    InstanceTRCO,
    Tache,
    Ressource,
    CompatibiliteRessourceTache,
    Precedence,
    Echeance,
    MinimiserMakespan,
)
from solveur_candidat import resoudre


def _makespan(instance, planning):
    durees = {
        (c.tache, c.ressource): c.duree
        for c in instance.contraintes
        if isinstance(c, CompatibiliteRessourceTache)
    }
    if planning is None or not planning.operations:
        return 0
    return max(op.debut + durees[(op.tache, op.ressource)] for op in planning.operations)


def test_une_seule_tache_une_seule_ressource():
    instance = InstanceTRCO(
        taches=[Tache(id='T1')],
        ressources=[Ressource(id='R1')],
        contraintes=[
            CompatibiliteRessourceTache(tache='T1', ressource='R1', duree=10)
        ],
        objectifs=[MinimiserMakespan(poids=1)],
        unite_temps='jours',
    )
    planning = resoudre(instance)
    assert planning is not None
    assert len(planning.operations) == 1
    op = planning.operations[0]
    assert op.tache == 'T1'
    assert op.ressource == 'R1'
    assert op.debut == 0
    assert _makespan(instance, planning) == 10


def test_instance_infaisable_echeance_trop_courte():
    instance = InstanceTRCO(
        taches=[Tache(id='T1')],
        ressources=[Ressource(id='R1')],
        contraintes=[
            CompatibiliteRessourceTache(tache='T1', ressource='R1', duree=10),
            Echeance(tache='T1', echeance=5),
        ],
        objectifs=[MinimiserMakespan(poids=1)],
        unite_temps='jours',
    )
    assert resoudre(instance) is None


def test_plusieurs_ressources_choisit_la_plus_courte():
    instance = InstanceTRCO(
        taches=[Tache(id='T1')],
        ressources=[Ressource(id='R1'), Ressource(id='R2')],
        contraintes=[
            CompatibiliteRessourceTache(tache='T1', ressource='R1', duree=5),
            CompatibiliteRessourceTache(tache='T1', ressource='R2', duree=8),
        ],
        objectifs=[MinimiserMakespan(poids=1)],
        unite_temps='jours',
    )
    planning = resoudre(instance)
    assert planning is not None
    assert len(planning.operations) == 1
    op = planning.operations[0]
    assert op.ressource == 'R1'
    assert op.debut == 0
    assert _makespan(instance, planning) == 5


def test_precedence_respectee():
    instance = InstanceTRCO(
        taches=[Tache(id='T1'), Tache(id='T2')],
        ressources=[Ressource(id='R1')],
        contraintes=[
            CompatibiliteRessourceTache(tache='T1', ressource='R1', duree=3),
            CompatibiliteRessourceTache(tache='T2', ressource='R1', duree=4),
            Precedence(avant='T1', apres='T2'),
        ],
        objectifs=[MinimiserMakespan(poids=1)],
        unite_temps='jours',
    )
    planning = resoudre(instance)
    assert planning is not None
    ops = {op.tache: op for op in planning.operations}
    assert ops['T1'].debut == 0
    assert ops['T2'].debut >= 3
    assert _makespan(instance, planning) == 7


def test_determinisme_meme_makespan():
    instance = InstanceTRCO(
        taches=[Tache(id='T1'), Tache(id='T2')],
        ressources=[Ressource(id='R1'), Ressource(id='R2')],
        contraintes=[
            CompatibiliteRessourceTache(tache='T1', ressource='R1', duree=2),
            CompatibiliteRessourceTache(tache='T1', ressource='R2', duree=3),
            CompatibiliteRessourceTache(tache='T2', ressource='R1', duree=2),
            CompatibiliteRessourceTache(tache='T2', ressource='R2', duree=1),
        ],
        objectifs=[MinimiserMakespan(poids=1)],
        unite_temps='jours',
    )
    p1 = resoudre(instance)
    p2 = resoudre(instance)
    assert p1 is not None
    assert p2 is not None
    assert _makespan(instance, p1) == _makespan(instance, p2)
