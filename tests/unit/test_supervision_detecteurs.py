"""Couche 1 (§6.1) : `detecter_echecs_repetes` est pur et ne touche qu'à
`EtatAPI` — pas de `Registre` (Postgres) requis, donc pas de skip Docker/DB
possible ici. Les détecteurs qui interrogent `Registre`
(`detecter_signature_et_replanification`) sont testés en intégration
(`tests/integration/test_supervision_detecteurs_registre.py`)."""

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
from supervision.detecteurs import detecter_echecs_repetes
from validation_engine.feasibility_checker import ResultatFaisabilite

_INSTANCE = InstanceTRCO(
    taches=[Tache(id="T1")],
    ressources=[Ressource(id="R1")],
    contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
    objectifs=[MinimiserMakespan()],
)

_ECHEC = ResultatExecution(planning=None, verdict_faisabilite=None, erreur="boom")
_SUCCES = ResultatExecution(
    planning=Planning(operations=[OperationPlanifiee(tache="T1", ressource="R1", debut=0)]),
    verdict_faisabilite=ResultatFaisabilite(violations=()),
    erreur=None,
)


def _executer(
    etat: EtatAPI, instance_id: str, resultat: ResultatExecution, date_execution: str, id_solveur: str = "s1"
) -> str:
    execution_id = etat.enregistrer_execution(id_solveur, instance_id, resultat)
    etat.dates_execution[execution_id] = date_execution
    return execution_id


def test_signale_apres_seuil_echecs_consecutifs() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE)
    for i in range(3):
        _executer(etat, instance_id, _ECHEC, date_execution=f"2026-01-0{i + 1}T00:00:00")

    signaux = detecter_echecs_repetes(etat, "client_test", seuil=3)

    assert len(signaux) == 1
    assert signaux[0].instance_id == instance_id
    assert signaux[0].client_id == "client_test"
    assert len(signaux[0].execution_ids) == 3


def test_ignore_sous_le_seuil() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE)
    _executer(etat, instance_id, _ECHEC, date_execution="2026-01-01T00:00:00")
    _executer(etat, instance_id, _ECHEC, date_execution="2026-01-02T00:00:00")

    assert detecter_echecs_repetes(etat, "client_test", seuil=3) == ()


def test_ignore_si_le_plus_recent_a_reussi() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE)
    _executer(etat, instance_id, _ECHEC, date_execution="2026-01-01T00:00:00")
    _executer(etat, instance_id, _ECHEC, date_execution="2026-01-02T00:00:00")
    _executer(etat, instance_id, _SUCCES, date_execution="2026-01-03T00:00:00")

    assert detecter_echecs_repetes(etat, "client_test", seuil=3) == ()


def test_trie_par_date_execution_pas_par_ordre_dinsertion() -> None:
    """`EtatAPI.lister_executions` préserve l'ordre d'insertion,
    `EtatPostgres` renvoie `ORDER BY date_execution DESC` — le détecteur ne
    doit dépendre d'aucun des deux, seulement de `date_execution`."""
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE)
    # Insérées dans le désordre chronologique : la plus récente en premier.
    _executer(etat, instance_id, _SUCCES, date_execution="2026-01-03T00:00:00")
    _executer(etat, instance_id, _ECHEC, date_execution="2026-01-01T00:00:00")
    _executer(etat, instance_id, _ECHEC, date_execution="2026-01-02T00:00:00")

    # Le plus récent (2026-01-03) a réussi malgré son insertion en premier.
    assert detecter_echecs_repetes(etat, "client_test", seuil=3) == ()


def test_scope_par_client_id() -> None:
    etat = EtatAPI()
    instance_a = etat.enregistrer_instance("client_a", _INSTANCE)
    etat.enregistrer_instance("client_b", _INSTANCE)
    for i in range(3):
        _executer(etat, instance_a, _ECHEC, date_execution=f"2026-01-0{i + 1}T00:00:00")

    assert detecter_echecs_repetes(etat, "client_b", seuil=3) == ()
    assert len(detecter_echecs_repetes(etat, "client_a", seuil=3)) == 1
