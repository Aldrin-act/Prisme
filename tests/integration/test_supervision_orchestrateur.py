"""`analyser_et_proposer` interroge `Registre` (Postgres) via les détecteurs
— testé en intégration, `registre_test` skip si Postgres injoignable. Le
modèle LLM reste toujours un faux (`ModeleFactice`), jamais un vrai appel
réseau, même en intégration."""

from __future__ import annotations

import json

from api.etat import EtatAPI
from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, MinimiserMakespan, Ressource, Tache
from solver_store.registry import Registre
from supervision import agent as agent_module
from supervision.orchestrateur import analyser_et_proposer
from tests.unit.aides_test_agents import ModeleFactice

_INSTANCE_SANS_SOLVEUR = InstanceTRCO(
    taches=[Tache(id="T1")],
    ressources=[Ressource(id="R1")],
    contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
    objectifs=[MinimiserMakespan()],
)


def _modele_avec_propositions(propositions: list[dict]) -> ModeleFactice:
    schema = agent_module._SchemaSupervision(
        propositions=[agent_module._SchemaPropositionUnitaire(**p) for p in propositions]
    )
    return ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)


def test_detecte_et_persiste_une_proposition(registre_test: Registre) -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_SANS_SOLVEUR)
    reference = f"signature_orpheline:{instance_id}"
    modele = _modele_avec_propositions(
        [{"reference": reference, "resume": "Régénération nécessaire.", "priorite": "haute"}]
    )

    propositions = analyser_et_proposer(etat, registre_test, modele, "client_test")

    assert len(propositions) == 1
    assert propositions[0].type_signal == "signature_orpheline"
    assert propositions[0].instance_id == instance_id
    assert propositions[0].resume == "Régénération nécessaire."
    assert propositions[0].priorite == "haute"
    assert propositions[0].action_suggeree == "regenerer_solveur"

    en_base = etat.lister_propositions(client_id="client_test")
    assert len(en_base) == 1


def test_ne_rappelle_jamais_le_llm_si_rien_de_nouveau(registre_test: Registre) -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_SANS_SOLVEUR)
    reference = f"signature_orpheline:{instance_id}"
    modele = _modele_avec_propositions([{"reference": reference, "resume": "R.", "priorite": "haute"}])
    premiere_passe = analyser_et_proposer(etat, registre_test, modele, "client_test")
    assert len(premiere_passe) == 1

    # `modele=None` : si l'orchestrateur touchait encore le modèle ici, ça
    # planterait — la même signature reste couverte par la proposition en
    # attente déjà enregistrée, donc aucun appel LLM ne doit avoir lieu.
    deuxieme_passe = analyser_et_proposer(etat, registre_test, None, "client_test")

    assert deuxieme_passe == []


def test_repli_sur_resume_canne_si_le_llm_omet_la_reference(registre_test: Registre) -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_SANS_SOLVEUR)
    # Le modèle répond, mais avec une référence qui ne correspond à rien —
    # le signal détecté par Python ne doit jamais être perdu pour autant.
    modele = _modele_avec_propositions(
        [{"reference": "reference-qui-nexiste-pas", "resume": "hors sujet", "priorite": "basse"}]
    )

    propositions = analyser_et_proposer(etat, registre_test, modele, "client_test")

    assert len(propositions) == 1
    assert propositions[0].instance_id == instance_id
    assert propositions[0].priorite == "moyenne"
    assert "régénération est nécessaire" in propositions[0].resume
