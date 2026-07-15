"""Couche 1 (§6.1) : la mécanique de stabilité (§6.5) est écrite à la main et
déterministe, même si ce qu'elle mesure — un solveur — ne l'est pas
forcément. Démontre qu'un solveur déterministe et légal est jugé stable, et
qu'un solveur dont le makespan varie d'un essai à l'autre est jugé instable.
"""

from __future__ import annotations

from dsl.schema import InstanceTRCO, OperationPlanifiee, Planning
from validation_engine.stability_test import tester_stabilite
from validation_engine.synthetic_bench import generer_catalogue

# pytest collecte par défaut toute fonction préfixée par "test" (sans exiger
# l'underscore) ; sans ce garde-fou, `tester_stabilite` importée ci-dessus est
# elle-même prise pour un test et échoue faute de fixture `solveur`.
tester_stabilite.__test__ = False

_CAS = next(cas for cas in generer_catalogue() if cas.nom == "taille_2_chaine_simple")


def _solveur_deterministe(instance: InstanceTRCO) -> Planning:
    return _CAS.planning_optimal


def _fabriquer_solveur_instable():
    """Un solveur qui décale artificiellement son planning un essai sur deux —
    même structure légale, makespan différent : le genre d'instabilité que
    §6.5 veut détecter."""
    compteur = {"n": 0}

    def solveur(instance: InstanceTRCO) -> Planning:
        compteur["n"] += 1
        decalage = 5 if compteur["n"] % 2 == 0 else 0
        return Planning(
            operations=[
                OperationPlanifiee(
                    tache=operation.tache, ressource=operation.ressource, debut=operation.debut + decalage
                )
                for operation in _CAS.planning_optimal.operations
            ]
        )

    return solveur


def _fabriquer_solveur_partiellement_illegal():
    """Un solveur illégal un essai sur cinq (précédence violée) — légal et
    stable le reste du temps : sert à vérifier que `taux_generations_valides`
    est bien une mesure quantifiable, distincte du verdict tout-ou-rien `stable`."""
    compteur = {"n": 0}

    def solveur(instance: InstanceTRCO) -> Planning:
        compteur["n"] += 1
        if compteur["n"] == 1:
            return Planning(
                operations=[
                    OperationPlanifiee(tache=operation.tache, ressource=operation.ressource, debut=0)
                    for operation in _CAS.planning_optimal.operations
                ]
            )
        return _CAS.planning_optimal

    return solveur


def test_solveur_deterministe_est_stable() -> None:
    resultat = tester_stabilite(_solveur_deterministe, _CAS.instance, n_essais=5)

    assert resultat.stable
    assert resultat.taux_generations_valides == 1.0
    assert len(set(resultat.makespans)) == 1
    assert resultat.diagnostics == ()


def test_solveur_a_makespan_variable_est_instable() -> None:
    resultat = tester_stabilite(_fabriquer_solveur_instable(), _CAS.instance, n_essais=5)

    assert not resultat.stable
    assert resultat.taux_generations_valides == 1.0
    assert len(set(resultat.makespans)) > 1


def test_taux_generations_valides_reflete_les_essais_illegaux() -> None:
    resultat = tester_stabilite(_fabriquer_solveur_partiellement_illegal(), _CAS.instance, n_essais=5)

    assert not resultat.stable
    assert resultat.taux_generations_valides == 0.8
    assert len(resultat.diagnostics) == 1
