"""`detecter_commandes_en_retard` (supervision/detecteurs.py) — aucun appel LLM, aucune
dépendance Postgres (contrairement à `detecter_signaux`, voir
`tests/integration/test_supervision_detecteurs_registre.py`) : testable en couche 1, réutilise
directement `calculer_statut_commande` déjà couverte par ses propres tests
(`tests/unit/test_comparaison_scenarios.py` s'il existe, sinon la fonction elle-même)."""

from __future__ import annotations

from api.etat import EtatAPI
from dsl.schema import (
    CompatibiliteRessourceTache,
    InstanceTRCO,
    MinimiserMakespan,
    OperationPlanifiee,
    Planning,
    Ressource,
    Tache,
)
from sandbox.runner import ResultatExecution
from supervision.detecteurs import SignalCommandeEnRetard, detecter_commandes_en_retard
from validation_engine.feasibility_checker import ResultatFaisabilite

_INSTANCE_UNE_TACHE = InstanceTRCO(
    taches=[Tache(id="T1")],
    ressources=[Ressource(id="R1")],
    contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
    objectifs=[MinimiserMakespan()],
)


def _executer_avec_succes(etat: EtatAPI, instance_id: str) -> None:
    """Enregistre une exécution réussie de `_INSTANCE_UNE_TACHE` : T1 sur R1, débute au jour 0,
    finit au jour 10 (durée déclarée par la seule `CompatibiliteRessourceTache` de l'instance)."""
    planning = Planning(operations=[OperationPlanifiee(tache="T1", ressource="R1", debut=0)])
    resultat = ResultatExecution(
        planning=planning, verdict_faisabilite=ResultatFaisabilite(violations=()), erreur=None
    )
    assert resultat.reussi
    etat.enregistrer_execution("solveur-quelconque", instance_id, resultat)


def test_commande_planifiee_en_retard_est_detectee() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_UNE_TACHE)
    _executer_avec_succes(etat, instance_id)
    etat.enregistrer_commande("cmd_1", instance_id, "client_test", date_limite=5, taches=("T1",))

    signaux = detecter_commandes_en_retard(etat, "client_test")

    assert len(signaux) == 1
    assert isinstance(signaux[0], SignalCommandeEnRetard)
    assert signaux[0].commande_id == "cmd_1"
    assert signaux[0].instance_id == instance_id
    assert signaux[0].date_fin_prevue == 10
    assert signaux[0].date_limite == 5


def test_commande_a_temps_nest_pas_detectee() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_UNE_TACHE)
    _executer_avec_succes(etat, instance_id)
    etat.enregistrer_commande("cmd_1", instance_id, "client_test", date_limite=20, taches=("T1",))

    assert detecter_commandes_en_retard(etat, "client_test") == ()


def test_commande_jamais_planifiee_nest_jamais_en_retard() -> None:
    """`en_retard=None` (aucune exécution réussie pour l'instance) n'est jamais confondu avec
    "en retard" — jamais de signal tant qu'aucun jugement n'est possible."""
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_UNE_TACHE)
    etat.enregistrer_commande("cmd_1", instance_id, "client_test", date_limite=0, taches=("T1",))

    assert detecter_commandes_en_retard(etat, "client_test") == ()


def test_commande_sans_date_limite_nest_jamais_en_retard() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_UNE_TACHE)
    _executer_avec_succes(etat, instance_id)
    etat.enregistrer_commande("cmd_1", instance_id, "client_test", date_limite=None, taches=("T1",))

    assert detecter_commandes_en_retard(etat, "client_test") == ()


def test_deux_commandes_en_retard_meme_instance_donnent_deux_signaux() -> None:
    """Deux commandes en retard sur la même instance produisent bien deux signaux distincts,
    chacun avec son propre commande_id — pas un seul signal qui en écraserait un autre."""
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_UNE_TACHE)
    _executer_avec_succes(etat, instance_id)
    etat.enregistrer_commande("cmd_1", instance_id, "client_test", date_limite=5, taches=("T1",))
    etat.enregistrer_commande("cmd_2", instance_id, "client_test", date_limite=2, taches=("T1",))

    signaux = detecter_commandes_en_retard(etat, "client_test")

    assert len(signaux) == 2
    assert {s.commande_id for s in signaux} == {"cmd_1", "cmd_2"}


def test_aucune_commande_pour_le_client_ne_declenche_rien() -> None:
    etat = EtatAPI()
    assert detecter_commandes_en_retard(etat, "client_sans_commande") == ()


def test_commande_dun_autre_client_est_ignoree() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_a", _INSTANCE_UNE_TACHE)
    _executer_avec_succes(etat, instance_id)
    etat.enregistrer_commande("cmd_1", instance_id, "client_a", date_limite=5, taches=("T1",))

    assert detecter_commandes_en_retard(etat, "client_b") == ()
