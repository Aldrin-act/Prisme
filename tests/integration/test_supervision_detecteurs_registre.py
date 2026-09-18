"""`detecter_signaux` interroge `Registre` (Postgres, `solver_store/registry.py`) — pas testable
en couche 1, voir `tests/integration/conftest.py::registre_test` (skip si Postgres injoignable).
Le modèle LLM reste toujours un faux (`ModeleFactice`, voir `tests/unit/aides_test_agents.py`),
jamais un vrai appel réseau, même en intégration — mêmes conventions que
`tests/integration/test_supervision_orchestrateur.py`."""

from __future__ import annotations

import json

import pytest

from api.etat import EtatAPI
from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, MinimiserMakespan, Precedence, Ressource, Tache
from sandbox.runner import ResultatExecution
from scripts.enregistrer_solveur_reference import STRUCTURE_MINIMALE, enregistrer
from solver_store.registry import Registre
from supervision import agent as agent_module
from supervision.detecteurs import (
    SignalEchecsRepetes,
    SignalInstanceAReplanifier,
    SignalSignatureOrpheline,
    SolveurHorsAtelier,
    detecter_signaux,
    detecter_signaux_instance,
)
from tests.unit.aides_test_agents import ModeleFactice

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


def _modele_avec_signaux(signaux: list[dict]) -> ModeleFactice:
    schema = agent_module._SchemaDetectionSupervision(
        signaux=[agent_module._SchemaSignalDetecte(**s) for s in signaux]
    )
    return ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)


def test_signature_orpheline_quand_aucun_solveur_ne_correspond(registre_test: Registre) -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_SANS_SOLVEUR)
    modele = _modele_avec_signaux([{"instance_id": instance_id, "type_signal": "signature_orpheline"}])

    signaux = detecter_signaux(etat, registre_test, modele, "client_test")

    assert len(signaux) == 1
    assert isinstance(signaux[0], SignalSignatureOrpheline)
    assert signaux[0].instance_id == instance_id


def test_instance_a_replanifier_quand_solveur_disponible_mais_jamais_executee(registre_test: Registre) -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_STRUCTURE_MINIMALE)
    id_solveur = enregistrer(registre_test, instance_id=instance_id, client_id="client_test")
    modele = _modele_avec_signaux(
        [
            {
                "instance_id": instance_id,
                "type_signal": "instance_a_replanifier",
                "raison": "jamais_executee",
                "id_solveur_disponible": id_solveur,
            }
        ]
    )

    signaux = detecter_signaux(etat, registre_test, modele, "client_test")

    assert len(signaux) == 1
    assert isinstance(signaux[0], SignalInstanceAReplanifier)
    assert signaux[0].instance_id == instance_id
    assert signaux[0].id_solveur_disponible == id_solveur
    assert signaux[0].structure_contraintes == STRUCTURE_MINIMALE
    assert signaux[0].raison == "jamais_executee"


def test_instance_a_replanifier_quand_modifiee_apres_sa_derniere_execution(registre_test: Registre) -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_STRUCTURE_MINIMALE)
    id_solveur = enregistrer(registre_test, instance_id=instance_id, client_id="client_test")
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur="peu importe")
    execution_id = etat.enregistrer_execution("un-solveur", instance_id, resultat)
    etat.dates_execution[execution_id] = "2026-01-01T00:00:00"
    etat.modifier_instance(instance_id, _INSTANCE_STRUCTURE_MINIMALE)
    etat.dates_modification[instance_id] = "2026-01-02T00:00:00"
    modele = _modele_avec_signaux(
        [
            {
                "instance_id": instance_id,
                "type_signal": "instance_a_replanifier",
                "raison": "modifiee_apres_derniere_execution",
                "id_solveur_disponible": id_solveur,
            }
        ]
    )

    signaux = detecter_signaux(etat, registre_test, modele, "client_test")

    assert len(signaux) == 1
    assert signaux[0].raison == "modifiee_apres_derniere_execution"


def test_echecs_repetes(registre_test: Registre) -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_SANS_SOLVEUR)
    echec = ResultatExecution(planning=None, verdict_faisabilite=None, erreur="boom")
    execution_ids = tuple(etat.enregistrer_execution("s1", instance_id, echec) for _ in range(3))
    for i, execution_id in enumerate(execution_ids):
        etat.dates_execution[execution_id] = f"2026-01-0{i + 1}T00:00:00"
    modele = _modele_avec_signaux(
        [
            {
                "instance_id": instance_id,
                "type_signal": "echecs_repetes",
                "id_solveur": "s1",
                "execution_ids": list(execution_ids),
            }
        ]
    )

    signaux = detecter_signaux(etat, registre_test, modele, "client_test")

    # Aussi signature_orpheline (aucun solveur enregistré) : le LLM n'a ici renvoyé que
    # echecs_repetes, ce qui suffit à prouver que ce signal est bien transporté indépendamment.
    echecs = [s for s in signaux if isinstance(s, SignalEchecsRepetes)]
    assert len(echecs) == 1
    assert echecs[0].id_solveur == "s1"
    assert set(echecs[0].execution_ids) == set(execution_ids)


def test_aucune_instance_nappelle_jamais_le_llm(registre_test: Registre) -> None:
    etat = EtatAPI()
    # `modele=None` : si detecter_signaux appelait le LLM malgré l'absence
    # totale d'instance pour ce client, ça planterait.
    assert detecter_signaux(etat, registre_test, None, "client_sans_instance") == ()


def test_instance_id_halluciné_est_ignore(registre_test: Registre) -> None:
    etat = EtatAPI()
    etat.enregistrer_instance("client_test", _INSTANCE_SANS_SOLVEUR)
    modele = _modele_avec_signaux(
        [{"instance_id": "instance-qui-nexiste-pas", "type_signal": "signature_orpheline"}]
    )

    assert detecter_signaux(etat, registre_test, modele, "client_test") == ()


def test_id_solveur_disponible_halluciné_est_ignore(registre_test: Registre) -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_STRUCTURE_MINIMALE)
    # Aucun solveur réellement enregistré, mais le LLM en invente un.
    modele = _modele_avec_signaux(
        [
            {
                "instance_id": instance_id,
                "type_signal": "instance_a_replanifier",
                "raison": "jamais_executee",
                "id_solveur_disponible": "solveur-invente",
            }
        ]
    )

    assert detecter_signaux(etat, registre_test, modele, "client_test") == ()


def test_solveur_dune_autre_instance_nest_jamais_propose(registre_test: Registre) -> None:
    """Un solveur ne sert que l'instance qui l'a fait générer — même si le LLM (par erreur ou
    hallucination) propose un `id_solveur_disponible` réel, appartenant à une AUTRE instance de
    structure identique, `detecter_signaux` doit l'écarter plutôt que le propager."""
    etat = EtatAPI()
    instance_id_1 = etat.enregistrer_instance("client_test", _INSTANCE_STRUCTURE_MINIMALE)
    instance_id_2 = etat.enregistrer_instance("client_test", _INSTANCE_STRUCTURE_MINIMALE)
    id_solveur_1 = enregistrer(registre_test, instance_id=instance_id_1, client_id="client_test")

    modele = _modele_avec_signaux(
        [
            {
                "instance_id": instance_id_2,
                "type_signal": "instance_a_replanifier",
                "raison": "jamais_executee",
                "id_solveur_disponible": id_solveur_1,
            }
        ]
    )

    assert detecter_signaux(etat, registre_test, modele, "client_test") == ()


def test_deux_instances_meme_structure_solveur_ne_se_partage_pas(registre_test: Registre) -> None:
    """Deux instances de structure/objectifs identiques, un solveur enregistré pour l'une
    seulement : l'autre doit être `signature_orpheline`, jamais `instance_a_replanifier` — fin du
    partage par signature entre instances d'un même client."""
    etat = EtatAPI()
    instance_avec_solveur = etat.enregistrer_instance("client_test", _INSTANCE_STRUCTURE_MINIMALE)
    instance_sans_solveur = etat.enregistrer_instance("client_test", _INSTANCE_STRUCTURE_MINIMALE)
    id_solveur = enregistrer(registre_test, instance_id=instance_avec_solveur, client_id="client_test")

    modele = _modele_avec_signaux(
        [
            {
                "instance_id": instance_sans_solveur,
                "type_signal": "signature_orpheline",
            }
        ]
    )

    signaux = detecter_signaux(etat, registre_test, modele, "client_test")

    assert len(signaux) == 1
    assert isinstance(signaux[0], SignalSignatureOrpheline)
    assert signaux[0].instance_id == instance_sans_solveur
    assert id_solveur  # le solveur existe bien, juste jamais proposé pour l'autre instance


# --- Analyse atelier par atelier, entrée (instance_id, id_solveur) ---


def test_un_appel_llm_par_atelier_jamais_un_seul_pour_tout_le_client(registre_test: Registre) -> None:
    """Deux ateliers du même client : la détection doit interroger le LLM une fois par atelier, et
    un signal renvoyé pour l'autre atelier dans la réponse d'un atelier ne doit jamais être propagé
    deux fois."""
    etat = EtatAPI()
    instance_a = etat.enregistrer_instance("client_test", _INSTANCE_SANS_SOLVEUR)
    instance_b = etat.enregistrer_instance("client_test", _INSTANCE_SANS_SOLVEUR)
    # Le faux modèle renvoie la même réponse à chaque appel, citant les deux ateliers : chaque
    # analyse ne doit garder que le signal de son propre atelier.
    modele = _modele_avec_signaux(
        [
            {"instance_id": instance_a, "type_signal": "signature_orpheline"},
            {"instance_id": instance_b, "type_signal": "signature_orpheline"},
        ]
    )

    signaux = detecter_signaux(etat, registre_test, modele, "client_test")

    assert modele.appels == 2
    assert sorted(s.instance_id for s in signaux) == sorted([instance_a, instance_b])


def test_detection_d_un_seul_atelier_ignore_les_autres(registre_test: Registre) -> None:
    etat = EtatAPI()
    instance_a = etat.enregistrer_instance("client_test", _INSTANCE_SANS_SOLVEUR)
    instance_b = etat.enregistrer_instance("client_test", _INSTANCE_SANS_SOLVEUR)
    modele = _modele_avec_signaux(
        [
            {"instance_id": instance_a, "type_signal": "signature_orpheline"},
            {"instance_id": instance_b, "type_signal": "signature_orpheline"},
        ]
    )

    signaux = detecter_signaux_instance(etat, registre_test, modele, instance_a)

    assert modele.appels == 1
    assert [s.instance_id for s in signaux] == [instance_a]


def test_solveur_d_un_autre_atelier_refuse_en_entree(registre_test: Registre) -> None:
    etat = EtatAPI()
    instance_a = etat.enregistrer_instance("client_test", _INSTANCE_STRUCTURE_MINIMALE)
    instance_b = etat.enregistrer_instance("client_test", _INSTANCE_STRUCTURE_MINIMALE)
    id_solveur_b = enregistrer(registre_test, instance_id=instance_b, client_id="client_test")

    # `modele=None` : le refus doit arriver avant tout appel LLM.
    with pytest.raises(SolveurHorsAtelier):
        detecter_signaux_instance(etat, registre_test, None, instance_a, id_solveur_b)


def test_id_solveur_limite_les_executions_a_ce_solveur(registre_test: Registre) -> None:
    """Échecs répétés d'un ancien solveur, puis un nouveau solveur analysé : les exécutions de
    l'ancien ne sont jamais montrées au LLM ni acceptées en retour."""
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_STRUCTURE_MINIMALE)
    id_solveur = enregistrer(registre_test, instance_id=instance_id, client_id="client_test")
    echec = ResultatExecution(planning=None, verdict_faisabilite=None, erreur="boom")
    anciennes = tuple(etat.enregistrer_execution("ancien-solveur", instance_id, echec) for _ in range(3))
    modele = _modele_avec_signaux(
        [
            {
                "instance_id": instance_id,
                "type_signal": "echecs_repetes",
                "id_solveur": "ancien-solveur",
                "execution_ids": list(anciennes),
            },
            # Signal impossible : l'atelier a justement le solveur analysé.
            {"instance_id": instance_id, "type_signal": "signature_orpheline"},
        ]
    )

    signaux = detecter_signaux_instance(etat, registre_test, modele, instance_id, id_solveur)

    assert signaux == ()
