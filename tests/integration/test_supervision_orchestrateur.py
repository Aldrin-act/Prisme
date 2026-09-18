"""`analyser_et_proposer` interroge `Registre` (Postgres) via les détecteurs
— testé en intégration, `registre_test` skip si Postgres injoignable. Le
modèle LLM reste toujours un faux (`ModeleFactice`), jamais un vrai appel
réseau, même en intégration. Depuis que la détection elle-même passe par un
appel LLM (`supervision/agent.py::detecter_signaux_llm`), le même modèle doit
répondre correctement aux deux schémas (détection puis rédaction) — voir
`_modele` ci-dessous, qui utilise `ModeleFactice.reponses_par_schema`."""

from __future__ import annotations

import json

from api.etat import EtatAPI
from dsl.schema import (
    CompatibiliteRessourceTache,
    InstanceTRCO,
    MinimiserMakespan,
    OperationPlanifiee,
    Planning,
    Precedence,
    Ressource,
    Tache,
)
from sandbox.runner import ResultatExecution
from scripts.enregistrer_solveur_reference import enregistrer
from solver_store.registry import Registre
from supervision import agent as agent_module
from supervision.orchestrateur import analyser_et_proposer, analyser_instance
from tests.unit.aides_test_agents import ModeleFactice
from validation_engine.feasibility_checker import ResultatFaisabilite

_INSTANCE_SANS_SOLVEUR = InstanceTRCO(
    taches=[Tache(id="T1")],
    ressources=[Ressource(id="R1")],
    contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
    objectifs=[MinimiserMakespan()],
)

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


def _modele(signaux_detection: list[dict], propositions: list[dict]) -> ModeleFactice:
    """Un seul `ModeleFactice`, une réponse par schéma — `analyser_et_proposer` invoque le même
    `modele` pour la détection (`_SchemaDetectionSupervision`) puis, si besoin, la rédaction
    (`_SchemaSupervision`)."""
    schema_detection = agent_module._SchemaDetectionSupervision(
        signaux=[agent_module._SchemaSignalDetecte(**s) for s in signaux_detection]
    )
    schema_propositions = agent_module._SchemaSupervision(
        propositions=[agent_module._SchemaPropositionUnitaire(**p) for p in propositions]
    )
    return ModeleFactice(
        raw_content=json.dumps(schema_propositions.model_dump()),
        parsed=schema_propositions,
        reponses_par_schema={
            agent_module._SchemaDetectionSupervision: (
                json.dumps(schema_detection.model_dump()),
                schema_detection,
                None,
            ),
            agent_module._SchemaSupervision: (
                json.dumps(schema_propositions.model_dump()),
                schema_propositions,
                None,
            ),
        },
    )


def test_detecte_et_persiste_une_proposition(registre_test: Registre) -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_SANS_SOLVEUR)
    modele = _modele(
        signaux_detection=[{"instance_id": instance_id, "type_signal": "signature_orpheline"}],
        propositions=[
            {
                "reference": f"signature_orpheline:{instance_id}",
                "resume": "Régénération nécessaire.",
                "priorite": "haute",
            }
        ],
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


def test_ne_rappelle_jamais_la_redaction_si_rien_de_nouveau(registre_test: Registre) -> None:
    """La détection (LLM) tourne à chaque appel — elle ne peut plus être évitée, c'est elle qui
    établit s'il y a du nouveau à proposer. La rédaction (second appel LLM), elle, reste évitée
    quand tout ce qui a été détecté est déjà couvert par une proposition en attente."""
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_SANS_SOLVEUR)
    modele = _modele(
        signaux_detection=[{"instance_id": instance_id, "type_signal": "signature_orpheline"}],
        propositions=[{"reference": f"signature_orpheline:{instance_id}", "resume": "R.", "priorite": "haute"}],
    )

    premiere_passe = analyser_et_proposer(etat, registre_test, modele, "client_test")
    assert len(premiere_passe) == 1
    assert modele.appels == 2  # détection + rédaction

    deuxieme_passe = analyser_et_proposer(etat, registre_test, modele, "client_test")

    assert deuxieme_passe == []
    assert modele.appels == 3  # + détection seule, rédaction évitée cette fois


def test_repli_sur_resume_canne_si_le_llm_omet_la_reference(registre_test: Registre) -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_SANS_SOLVEUR)
    # Le LLM de détection identifie bien le signal, mais celui de rédaction répond avec une
    # référence qui ne correspond à rien — le signal détecté ne doit jamais être perdu pour
    # autant.
    modele = _modele(
        signaux_detection=[{"instance_id": instance_id, "type_signal": "signature_orpheline"}],
        propositions=[{"reference": "reference-qui-nexiste-pas", "resume": "hors sujet", "priorite": "basse"}],
    )

    propositions = analyser_et_proposer(etat, registre_test, modele, "client_test")

    assert len(propositions) == 1
    assert propositions[0].instance_id == instance_id
    assert propositions[0].priorite == "moyenne"
    assert "régénération est nécessaire" in propositions[0].resume


def test_instance_modifiee_apres_execution_propose_bien_une_reexecution(registre_test: Registre) -> None:
    """Bout en bout : une instance exécutée puis modifiée en place (même
    instance_id) doit produire une proposition `instance_a_replanifier` dont
    le résumé de repli mentionne la modification — pas "jamais exécutée"."""
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_STRUCTURE_MINIMALE)
    id_solveur = enregistrer(registre_test, instance_id=instance_id, client_id="client_test")
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur="peu importe")
    execution_id = etat.enregistrer_execution("un-solveur", instance_id, resultat)
    etat.dates_execution[execution_id] = "2026-01-01T00:00:00"
    etat.modifier_instance(instance_id, _INSTANCE_STRUCTURE_MINIMALE)
    etat.dates_modification[instance_id] = "2026-01-02T00:00:00"

    modele = _modele(
        signaux_detection=[
            {
                "instance_id": instance_id,
                "type_signal": "instance_a_replanifier",
                "raison": "modifiee_apres_derniere_execution",
                "id_solveur_disponible": id_solveur,
            }
        ],
        # Le LLM de rédaction ne répond rien d'utilisable pour ce signal — le résumé de repli fait foi.
        propositions=[],
    )

    propositions = analyser_et_proposer(etat, registre_test, modele, "client_test")

    assert len(propositions) == 1
    assert propositions[0].type_signal == "instance_a_replanifier"
    assert propositions[0].instance_id == instance_id
    assert propositions[0].action_suggeree == "executer"
    assert "modifiée depuis sa dernière exécution" in propositions[0].resume


def test_commande_en_retard_dedoublonnee_par_commande_id(registre_test: Registre) -> None:
    """Deux commandes en retard sur la même instance, détectées à deux passes différentes : la
    seconde passe doit proposer la nouvelle commande sans jamais reproposer la première déjà en
    attente — la clé de dédoublonnage doit inclure commande_id, pas seulement
    (type_signal, instance_id), sans quoi la seconde commande serait silencieusement engloutie
    par la proposition déjà pendante de la première."""
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_SANS_SOLVEUR)
    resultat = ResultatExecution(
        planning=Planning(operations=[OperationPlanifiee(tache="T1", ressource="R1", debut=0)]),
        verdict_faisabilite=ResultatFaisabilite(violations=()),
        erreur=None,
    )
    assert resultat.reussi
    etat.enregistrer_execution("solveur-quelconque", instance_id, resultat)
    etat.enregistrer_commande("cmd_1", instance_id, "client_test", date_limite=5, taches=("T1",))

    modele_vide = _modele(signaux_detection=[], propositions=[])
    premiere_passe = analyser_et_proposer(etat, registre_test, modele_vide, "client_test")
    assert len(premiere_passe) == 1
    assert premiere_passe[0].type_signal == "commande_en_retard"
    assert premiere_passe[0].commande_id == "cmd_1"
    assert premiere_passe[0].action_suggeree == "aucune"

    # Une deuxième commande devient en retard sur la MÊME instance.
    etat.enregistrer_commande("cmd_2", instance_id, "client_test", date_limite=2, taches=("T1",))

    deuxieme_passe = analyser_et_proposer(etat, registre_test, modele_vide, "client_test")

    assert len(deuxieme_passe) == 1
    assert deuxieme_passe[0].type_signal == "commande_en_retard"
    assert deuxieme_passe[0].commande_id == "cmd_2"


def test_solveur_dont_l_algorithme_n_est_plus_le_meilleur_propose_une_regeneration(
    registre_test: Registre,
) -> None:
    """Le Benchmarker, rejoué sur l'instance actuelle, recommande un autre algorithme que celui du
    solveur : la supervision doit proposer de régénérer, et ne plus proposer de simplement
    ré-exécuter ce même solveur (deux actions contradictoires)."""
    from pathlib import Path

    import scripts._solveur_minimal as module_solveur
    from generation.agents import benchmarker
    from scripts._solveur_minimal import resoudre
    from scripts.enregistrer_solveur_reference import STRUCTURE_MINIMALE
    from validation_engine.cascade import evaluer_cascade

    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_STRUCTURE_MINIMALE)
    id_solveur = registre_test.enregistrer_solveur(
        code_source=Path(module_solveur.__file__).read_text(encoding="utf-8"),
        structure_contraintes=STRUCTURE_MINIMALE,
        verdict_cascade=evaluer_cascade(resoudre),
        instance_id=instance_id,
        client_id="client_test",
        algorithme="cp_sat",
        algorithme_raison="petite instance",
    )

    modele = _modele(
        signaux_detection=[
            {
                "instance_id": instance_id,
                "type_signal": "instance_a_replanifier",
                "raison": "jamais_executee",
                "id_solveur_disponible": id_solveur,
            }
        ],
        propositions=[],
    )
    schema_benchmark = benchmarker._SchemaBenchmark(
        recommandation=benchmarker._SchemaRecommandation(
            algorithme="genetic", raison="instance devenue très grande"
        )
    )
    modele._reponses_par_schema[benchmarker._SchemaBenchmark] = (
        json.dumps(schema_benchmark.model_dump()),
        schema_benchmark,
        None,
    )

    propositions = analyser_instance(etat, registre_test, modele, instance_id, id_solveur)

    assert [p.type_signal for p in propositions] == ["solveur_a_regenerer"]
    assert propositions[0].action_suggeree == "regenerer_solveur"
    assert f"solveur={id_solveur}" in propositions[0].details
    # Le détail porte l'argument bloquant et ses preuves, pas un simple champ.
    argument = next(d for d in propositions[0].details if d.startswith("Algorithme :"))
    assert "genetic" in argument
    assert any("instance devenue très grande" in d for d in propositions[0].details)


def test_solveur_adapte_ne_propose_aucune_regeneration(registre_test: Registre) -> None:
    from pathlib import Path

    import scripts._solveur_minimal as module_solveur
    from generation.agents import benchmarker
    from scripts._solveur_minimal import resoudre
    from scripts.enregistrer_solveur_reference import STRUCTURE_MINIMALE
    from validation_engine.cascade import evaluer_cascade

    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", _INSTANCE_STRUCTURE_MINIMALE)
    id_solveur = registre_test.enregistrer_solveur(
        code_source=Path(module_solveur.__file__).read_text(encoding="utf-8"),
        structure_contraintes=STRUCTURE_MINIMALE,
        verdict_cascade=evaluer_cascade(resoudre),
        instance_id=instance_id,
        client_id="client_test",
        algorithme="cp_sat",
    )
    modele = _modele(signaux_detection=[], propositions=[])
    schema_benchmark = benchmarker._SchemaBenchmark(
        recommandation=benchmarker._SchemaRecommandation(algorithme="cp_sat", raison="petite instance")
    )
    modele._reponses_par_schema[benchmarker._SchemaBenchmark] = (
        json.dumps(schema_benchmark.model_dump()),
        schema_benchmark,
        None,
    )

    assert analyser_instance(etat, registre_test, modele, instance_id, id_solveur) == []


def test_instance_jugee_infaisable_est_signalee_sans_regeneration(registre_test: Registre, monkeypatch) -> None:
    """Une échéance ajoutée depuis la génération, et l'essai réel répond « aucune solution » : la
    supervision le signale (données à vérifier), sans jamais proposer de régénérer le solveur."""
    from pathlib import Path

    import scripts._solveur_minimal as module_solveur
    from dsl.schema import Echeance
    from generation.agents import benchmarker
    from scripts._solveur_minimal import resoudre
    from scripts.enregistrer_solveur_reference import STRUCTURE_MINIMALE
    from supervision import adequation
    from validation_engine.cascade import evaluer_cascade

    etat = EtatAPI()
    instance = _INSTANCE_STRUCTURE_MINIMALE.model_copy(
        update={"contraintes": [*_INSTANCE_STRUCTURE_MINIMALE.contraintes, Echeance(tache="T2", echeance=1)]}
    )
    instance_id = etat.enregistrer_instance("client_test", instance)
    id_solveur = registre_test.enregistrer_solveur(
        code_source=Path(module_solveur.__file__).read_text(encoding="utf-8") + "\n# Echeance\n",
        structure_contraintes=STRUCTURE_MINIMALE,
        verdict_cascade=evaluer_cascade(resoudre),
        instance_id=instance_id,
        client_id="client_test",
        algorithme="cp_sat",
    )
    monkeypatch.setattr(adequation, "sandbox_disponible", lambda: True)
    monkeypatch.setattr(
        adequation,
        "executer_solveur_valide",
        lambda *_: ResultatExecution(None, None, adequation.MESSAGE_INFAISABLE),
    )

    modele = _modele(signaux_detection=[], propositions=[])
    schema_benchmark = benchmarker._SchemaBenchmark(
        recommandation=benchmarker._SchemaRecommandation(algorithme="cp_sat", raison="petite instance")
    )
    modele._reponses_par_schema[benchmarker._SchemaBenchmark] = (
        json.dumps(schema_benchmark.model_dump()),
        schema_benchmark,
        None,
    )

    propositions = analyser_instance(etat, registre_test, modele, instance_id, id_solveur)

    assert [p.type_signal for p in propositions] == ["instance_jugee_infaisable"]
    assert propositions[0].action_suggeree == "aucune"
    assert "données" in propositions[0].resume
