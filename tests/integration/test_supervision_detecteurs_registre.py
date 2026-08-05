"""`detecter_signature_et_replanification` interroge `Registre` (Postgres,
`solver_store/registry.py`) — pas testable en couche 1, voir
`tests/integration/conftest.py::registre_test` (skip si Postgres injoignable).
"""

from __future__ import annotations

from api.etat import EtatAPI
from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, MinimiserMakespan, Precedence, Ressource, Tache
from sandbox.runner import ResultatExecution
from scripts.enregistrer_solveur_reference import STRUCTURE_MINIMALE, enregistrer
from solver_store.registry import Registre
from supervision.detecteurs import detecter_signature_et_replanification

_INSTANCE_STRUCTURE_MINIMALE = InstanceTRCO(
    taches=[Tache(id="T1"), Tache(id="T2")],
    ressources=[Ressource(id="R1")],
    contraintes=[
        Precedence(avant="T1", apres="T2"),
        CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
        CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=5),
    ],
    objectifs=[MinimiserMakespan()],
)

_INSTANCE_SANS_SOLVEUR = InstanceTRCO(
    taches=[Tache(id="T1")],
    ressources=[Ressource(id="R1")],
    contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
    objectifs=[MinimiserMakespan()],
)


def test_signature_orpheline_quand_aucun_solveur_ne_correspond(registre_test: Registre) -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_SANS_SOLVEUR)

    orphelines, a_replanifier = detecter_signature_et_replanification(etat, registre_test, "client_test")

    assert a_replanifier == ()
    assert len(orphelines) == 1
    assert orphelines[0].instance_id == instance_id
    assert orphelines[0].structure_contraintes == "compatibilite_ressource_tache"


def test_instance_a_replanifier_quand_solveur_disponible_mais_jamais_executee(registre_test: Registre) -> None:
    id_solveur = enregistrer(registre_test, client_id="client_test")
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_STRUCTURE_MINIMALE)

    orphelines, a_replanifier = detecter_signature_et_replanification(etat, registre_test, "client_test")

    assert orphelines == ()
    assert len(a_replanifier) == 1
    assert a_replanifier[0].instance_id == instance_id
    assert a_replanifier[0].id_solveur_disponible == id_solveur
    assert a_replanifier[0].structure_contraintes == STRUCTURE_MINIMALE


def test_instance_deja_executee_avec_solveur_disponible_nest_ni_lun_ni_lautre(registre_test: Registre) -> None:
    enregistrer(registre_test, client_id="client_test")
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_STRUCTURE_MINIMALE)
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur="peu importe")
    etat.enregistrer_execution("un-solveur", instance_id, resultat)

    orphelines, a_replanifier = detecter_signature_et_replanification(etat, registre_test, "client_test")

    assert orphelines == ()
    assert a_replanifier == ()
