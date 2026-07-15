"""Couche 1 (§6.1) : le banc synthétique est un générateur écrit à la main,
déterministe. Critère de validation de l'Étape 3 (§6.4) : chaque planning
« optimal » produit par construction inverse est confirmé faisable par le
vérificateur de l'Étape 2, et son optimum annoncé résiste à un recalcul
indépendant fondé sur la seule précédence — pas seulement à la comptabilité
interne du générateur.
"""

from __future__ import annotations

from dsl.schema import CompatibiliteMachineTache, InstanceTRCO, Planning, Precedence
from validation_engine.feasibility_checker import verifier_faisabilite
from validation_engine.synthetic_bench import generer_catalogue, generer_catalogue_faisabilite_seule
from validation_engine.synthetic_bench.catalogue import DOSSIER_INSTANCES
from validation_engine.synthetic_bench.stockage import charger


def _optimum_attendu(instance: InstanceTRCO) -> int:
    """Recalcule l'optimum indépendamment de `construction_inverse.py` : la
    précédence impose, à elle seule, qu'une chaîne de tâches liées ne peut
    pas durer moins que la somme de leurs durées (§6.4).
    """
    durees = {c.tache: c.duree for c in instance.contraintes if isinstance(c, CompatibiliteMachineTache)}
    suivant: dict[str, str] = {}
    a_un_predecesseur: set[str] = set()
    for contrainte in instance.contraintes:
        if isinstance(contrainte, Precedence):
            suivant[contrainte.avant] = contrainte.apres
            a_un_predecesseur.add(contrainte.apres)

    departs_de_chaine = [tache_id for tache_id in durees if tache_id not in a_un_predecesseur]

    optimum = 0
    for depart in departs_de_chaine:
        total = 0
        tache_id = depart
        while True:
            total += durees[tache_id]
            if tache_id not in suivant:
                break
            tache_id = suivant[tache_id]
        optimum = max(optimum, total)
    return optimum


def _ensemble_taches(instance: InstanceTRCO) -> set[tuple[str, int]]:
    """La durée vit sur `CompatibiliteMachineTache`, pas sur `Tache` — mais le banc
    synthétique garantit une seule ressource compatible par tâche, donc la paire
    (tâche, durée) reste bien définie ici."""
    return {(c.tache, c.duree) for c in instance.contraintes if isinstance(c, CompatibiliteMachineTache)}


def _ensemble_ressources(instance: InstanceTRCO) -> set[str]:
    return {ressource.id for ressource in instance.ressources}


def _ensemble_contraintes(instance: InstanceTRCO) -> set[tuple[str, str, str]]:
    resultat: set[tuple[str, str, str]] = set()
    for contrainte in instance.contraintes:
        if isinstance(contrainte, Precedence):
            resultat.add(("precedence", contrainte.avant, contrainte.apres))
        elif isinstance(contrainte, CompatibiliteMachineTache):
            resultat.add(("compatibilite_machine_tache", contrainte.tache, contrainte.ressource))
    return resultat


def _ensemble_operations(planning: Planning) -> set[tuple[str, str, int]]:
    return {(op.tache, op.ressource, op.debut) for op in planning.operations}


def test_chaque_planning_optimal_est_faisable() -> None:
    for cas in generer_catalogue():
        resultat = verifier_faisabilite(cas.instance, cas.planning_optimal)
        assert resultat.legal, (cas.nom, resultat.violations)


def test_optimum_resiste_a_un_recalcul_independant() -> None:
    for cas in generer_catalogue():
        assert cas.optimum == _optimum_attendu(cas.instance), cas.nom


def test_tailles_croissantes() -> None:
    tailles = [len(cas.instance.taches) for cas in generer_catalogue()]
    assert tailles == sorted(tailles)
    assert len(set(tailles)) == len(tailles)


def test_catalogue_verse_sur_disque_est_a_jour() -> None:
    """Le catalogue versionné (`instances/*.json`) ne doit pas avoir dérivé
    du générateur : sinon un futur consommateur (Étape 4+) validerait contre
    des données obsolètes."""
    for cas in generer_catalogue():
        cas_disque = charger(cas.nom, DOSSIER_INSTANCES)

        assert cas_disque.optimum == cas.optimum
        assert _ensemble_taches(cas_disque.instance) == _ensemble_taches(cas.instance)
        assert _ensemble_ressources(cas_disque.instance) == _ensemble_ressources(cas.instance)
        assert _ensemble_contraintes(cas_disque.instance) == _ensemble_contraintes(cas.instance)
        assert _ensemble_operations(cas_disque.planning_optimal) == _ensemble_operations(cas.planning_optimal)


def test_niveau_faisabilite_seule_produit_des_instances_valides() -> None:
    """PH3-T3 : le second niveau n'a pas d'optimum connu — seule sa validité
    structurelle (schéma T-R-C-O) est vérifiable à ce stade ; sa faisabilité
    une fois résolue est exercée par
    `tests/integration/test_synthetic_bench_faisabilite_seule.py` (a besoin
    d'un vrai solveur OR-Tools, donc hors de `unit/`)."""
    cas_generes = generer_catalogue_faisabilite_seule()
    assert cas_generes
    for cas in cas_generes:
        assert isinstance(cas.instance, InstanceTRCO)


def test_niveau_faisabilite_seule_exerce_une_vraie_contention_partagee() -> None:
    """Contrairement au niveau 1 (une ressource dédiée par job), chaque tâche
    ici est compatible avec toutes les ressources partagées de l'instance —
    une vraie contention entre jobs, jamais produite par `construction_inverse.py`."""
    for cas in generer_catalogue_faisabilite_seule():
        ressources = {r.id for r in cas.instance.ressources}
        for tache in cas.instance.taches:
            compatibles = {
                c.ressource
                for c in cas.instance.contraintes
                if isinstance(c, CompatibiliteMachineTache) and c.tache == tache.id
            }
            assert compatibles == ressources, (cas.nom, tache.id)
