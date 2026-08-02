"""Couche 1 (§6.1) : l'adaptateur ERP est du code écrit à la main,
déterministe — pure traduction, aucune dépendance externe (ni OR-Tools ni
Docker)."""

from __future__ import annotations

from adapters.erp_reference import OperationERP, PayloadERP, PosteERP, traduire
from dsl.schema import CompatibiliteRessourceTache, CompetenceRequise, InstanceTRCO, Precedence


def test_traduction_produit_les_bonnes_taches_et_ressources() -> None:
    payload = PayloadERP(
        operations=[
            OperationERP(code_operation="OP10", duree_jours=2, poste_id="POSTE_A"),
            OperationERP(
                code_operation="OP20",
                duree_jours=3,
                poste_id="POSTE_B",
                operation_precedente="OP10",
            ),
        ],
        postes=[PosteERP(code_poste="POSTE_A"), PosteERP(code_poste="POSTE_B")],
    )

    instance = traduire(payload)

    assert isinstance(instance, InstanceTRCO)
    assert {tache.id for tache in instance.taches} == {"OP10", "OP20"}
    assert {c.tache: c.duree for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)} == {
        "OP10": 2,
        "OP20": 3,
    }
    assert {ressource.id for ressource in instance.ressources} == {"POSTE_A", "POSTE_B"}


def test_traduction_produit_une_compatibilite_unique_par_tache() -> None:
    payload = PayloadERP(
        operations=[OperationERP(code_operation="OP10", duree_jours=1, poste_id="POSTE_A")],
        postes=[PosteERP(code_poste="POSTE_A")],
    )

    instance = traduire(payload)

    compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)]
    assert len(compatibilites) == 1
    assert compatibilites[0].tache == "OP10"
    assert compatibilites[0].ressource == "POSTE_A"


def test_traduction_reporte_la_precedence_uniquement_si_declaree() -> None:
    payload = PayloadERP(
        operations=[
            OperationERP(code_operation="OP10", duree_jours=1, poste_id="POSTE_A"),
            OperationERP(
                code_operation="OP20",
                duree_jours=1,
                poste_id="POSTE_A",
                operation_precedente="OP10",
            ),
        ],
        postes=[PosteERP(code_poste="POSTE_A")],
    )

    instance = traduire(payload)

    precedences = [c for c in instance.contraintes if isinstance(c, Precedence)]
    assert len(precedences) == 1
    assert precedences[0].avant == "OP10"
    assert precedences[0].apres == "OP20"


def test_traduction_sans_operation_precedente_ne_produit_aucune_precedence() -> None:
    payload = PayloadERP(
        operations=[OperationERP(code_operation="OP10", duree_jours=1, poste_id="POSTE_A")],
        postes=[PosteERP(code_poste="POSTE_A")],
    )

    instance = traduire(payload)

    assert not [c for c in instance.contraintes if isinstance(c, Precedence)]


def test_traduction_derive_une_competence_requise_si_declaree() -> None:
    payload = PayloadERP(
        operations=[
            OperationERP(
                code_operation="OP10",
                duree_jours=1,
                poste_id="POSTE_A",
                competence_requise="soudure",
            ),
            OperationERP(code_operation="OP20", duree_jours=1, poste_id="POSTE_A"),
        ],
        postes=[PosteERP(code_poste="POSTE_A", competences=["soudure"])],
    )

    instance = traduire(payload)

    competences_requises = [c for c in instance.contraintes if isinstance(c, CompetenceRequise)]
    assert len(competences_requises) == 1
    assert competences_requises[0].tache == "OP10"
    assert competences_requises[0].competence == "soudure"


def test_traduction_sans_competence_requise_ne_produit_aucune_contrainte() -> None:
    payload = PayloadERP(
        operations=[OperationERP(code_operation="OP10", duree_jours=1, poste_id="POSTE_A")],
        postes=[PosteERP(code_poste="POSTE_A")],
    )

    instance = traduire(payload)

    assert not [c for c in instance.contraintes if isinstance(c, CompetenceRequise)]
    assert instance.ressources[0].competences == []


def test_traduction_reporte_les_competences_du_poste_sur_la_ressource() -> None:
    payload = PayloadERP(
        operations=[OperationERP(code_operation="OP10", duree_jours=1, poste_id="POSTE_A")],
        postes=[PosteERP(code_poste="POSTE_A", competences=["soudure", "controle_qualite"])],
    )

    instance = traduire(payload)

    assert instance.ressources[0].competences == ["soudure", "controle_qualite"]


def test_instance_produite_est_valide_par_construction() -> None:
    """La traduction doit toujours produire un InstanceTRCO qui passe ses
    propres garde-fous (§6.7) — sinon l'adaptateur laisserait passer des
    données incohérentes vers le solveur."""
    payload = PayloadERP(
        operations=[
            OperationERP(code_operation="OP10", duree_jours=2, poste_id="POSTE_A"),
            OperationERP(
                code_operation="OP20",
                duree_jours=1,
                poste_id="POSTE_B",
                operation_precedente="OP10",
            ),
        ],
        postes=[PosteERP(code_poste="POSTE_A"), PosteERP(code_poste="POSTE_B")],
    )

    instance = traduire(payload)

    # Ne lève pas : model_validate revalide un InstanceTRCO déjà construit.
    InstanceTRCO.model_validate(instance.model_dump())
