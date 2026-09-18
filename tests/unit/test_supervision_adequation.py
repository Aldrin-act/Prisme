"""Couche 1 (§6.1) : `supervision/adequation.py` — faut-il régénérer le solveur d'un atelier ?
Jamais par règle mécanique : chaque changement devient un constat argumenté, et seul un constat
« bloquant » (preuve à l'appui) recommande une régénération.

Aucun service externe : l'artefact solveur est construit à la main (pas de `Registre`), l'essai en
bac à sable est simulé (`executer` injecté), le Benchmarker répond via `ModeleFactice`."""

from __future__ import annotations

import json
from pathlib import Path

from api.etat import EtatAPI
from dsl.schema import (
    CompatibiliteRessourceTache,
    ContrainteTailleLot,
    Echeance,
    EquilibrerCharge,
    InstanceTRCO,
    MinimiserMakespan,
    OperationPlanifiee,
    Planning,
    Precedence,
    Ressource,
    Tache,
)
from generation.agents import benchmarker
from sandbox.runner import ResultatExecution
from solver_store.registry import ArtefactSolveur
from supervision.adequation import EvaluationSolveur, evaluer_solveur
from tests.unit.aides_test_agents import ModeleFactice
from validation_engine.feasibility_checker import ResultatFaisabilite, Violation

_INSTANCE = InstanceTRCO(
    taches=[Tache(id="T1", quantite=5), Tache(id="T2")],
    ressources=[Ressource(id="R1")],
    contraintes=[
        Precedence(avant="T1", apres="T2"),
        CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
        CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=5),
    ],
    objectifs=[MinimiserMakespan()],
)
_STRUCTURE_INITIALE = "compatibilite_ressource_tache,precedence"
_PLANNING = Planning(
    operations=[
        OperationPlanifiee(tache="T1", ressource="R1", debut=0),
        OperationPlanifiee(tache="T2", ressource="R1", debut=10),
    ]
)


def _solveur(
    structure: str = _STRUCTURE_INITIALE,
    objectifs: str = "minimiser_makespan",
    algorithme: str | None = "cp_sat",
    code: str = "def resoudre(instance):\n    ...\n",
) -> ArtefactSolveur:
    return ArtefactSolveur(
        id="solveur-1",
        client_id="client_test",
        instance_id="ignore-ici",
        structure_contraintes=structure,
        signature_objectifs=objectifs,
        chemin_code=Path("inutile.py"),
        empreinte_sha256="0" * 64,
        date_validation="2026-09-01T00:00:00+00:00",
        code_source=code,
        actif=True,
        algorithme=algorithme,
        algorithme_raison=None,
    )


def _modele(algorithme: str = "cp_sat", alternatives: list[str] | None = None) -> ModeleFactice:
    schema = benchmarker._SchemaBenchmark(
        recommandation=benchmarker._SchemaRecommandation(
            algorithme=algorithme, raison="raison de test", alternatives=alternatives or []
        )
    )
    return ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)


def _essai_legal(*_: object) -> ResultatExecution:
    return ResultatExecution(_PLANNING, ResultatFaisabilite(violations=()), None)


def _essai_avec_violation(type_violation: str, message: str):
    def executer(*_: object) -> ResultatExecution:
        violation = Violation(type=type_violation, message=message, tache="T2")
        return ResultatExecution(_PLANNING, ResultatFaisabilite(violations=(violation,)), None)

    return executer


def _essai_en_erreur(erreur: str):
    def executer(*_: object) -> ResultatExecution:
        return ResultatExecution(None, None, erreur)

    return executer


def _evaluer(
    instance: InstanceTRCO,
    solveur: ArtefactSolveur,
    modele: ModeleFactice | None = None,
    executer=_essai_legal,
    bac_a_sable: bool = True,
) -> EvaluationSolveur:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client_test", instance)
    return evaluer_solveur(
        etat,
        None,  # registre : jamais utilisé directement, `executer` est simulé
        modele or _modele(),
        instance_id,
        solveur,
        executer=executer,
        bac_a_sable_disponible=lambda: bac_a_sable,
    )


def _constat(evaluation: EvaluationSolveur, debut_sujet: str):
    return next(c for c in evaluation.constats if c.sujet.startswith(debut_sujet))


def _avec_echeance(instance: InstanceTRCO = _INSTANCE) -> InstanceTRCO:
    return instance.model_copy(update={"contraintes": [*instance.contraintes, Echeance(tache="T2", echeance=12)]})


# --- Rien n'a changé ---


def test_rien_n_a_change_aucune_regeneration() -> None:
    evaluation = _evaluer(_INSTANCE, _solveur())

    assert evaluation.a_regenerer is False
    assert evaluation.essai is None  # aucun essai lancé : les contraintes n'ont pas changé
    assert all(c.verdict == "sans_impact" for c in evaluation.constats)


# --- Contrainte ajoutée : décidé par l'essai réel et le code, jamais par le seul ajout ---


def test_contrainte_ajoutee_et_violee_par_l_essai_reel_est_bloquante() -> None:
    evaluation = _evaluer(
        _avec_echeance(),
        _solveur(),
        executer=_essai_avec_violation("echeance_depassee", "T2 finit à 15, échéance 12"),
    )

    constat = _constat(evaluation, "Contrainte ajoutée : echeance")
    assert constat.verdict == "bloquant"
    assert "essai réel" in constat.argument
    assert constat.preuves == ("T2 finit à 15, échéance 12",)
    assert evaluation.a_regenerer is True


def test_contrainte_ajoutee_respectee_et_traitee_par_le_code_est_sans_impact() -> None:
    code = "for c in instance.contraintes:\n    if c.type == 'echeance':\n        ...\n"
    evaluation = _evaluer(_avec_echeance(), _solveur(code=code))

    assert _constat(evaluation, "Contrainte ajoutée : echeance").verdict == "sans_impact"
    assert evaluation.a_regenerer is False


def test_contrainte_ajoutee_respectee_par_hasard_est_a_surveiller_sans_regenerer() -> None:
    evaluation = _evaluer(_avec_echeance(), _solveur())

    constat = _constat(evaluation, "Contrainte ajoutée : echeance")
    assert constat.verdict == "a_surveiller"
    assert "ne mentionne jamais" in constat.argument
    assert evaluation.a_regenerer is False


def test_sans_bac_a_sable_la_lecture_du_code_tranche() -> None:
    ignoree = _evaluer(_avec_echeance(), _solveur(), bac_a_sable=False)
    assert _constat(ignoree, "Contrainte ajoutée : echeance").verdict == "bloquant"

    code = "from dsl.schema import Echeance\n"
    mentionnee = _evaluer(_avec_echeance(), _solveur(code=code), bac_a_sable=False)
    assert _constat(mentionnee, "Contrainte ajoutée : echeance").verdict == "non_verifie"
    assert mentionnee.a_regenerer is False


def test_contrainte_jamais_lue_par_un_solveur_est_sans_impact() -> None:
    instance = _INSTANCE.model_copy(
        update={"contraintes": [*_INSTANCE.contraintes, ContrainteTailleLot(tache="T1", lot_min=1, lot_max=10)]}
    )
    evaluation = _evaluer(instance, _solveur(), bac_a_sable=False)

    assert _constat(evaluation, "Contrainte ajoutée : taille_lot").verdict == "sans_impact"
    assert evaluation.a_regenerer is False


# --- Contrainte retirée : jamais une raison de régénérer à elle seule ---


def test_contrainte_retiree_n_impose_pas_de_regeneration() -> None:
    solveur = _solveur(structure="compatibilite_ressource_tache,echeance,precedence")

    evaluation = _evaluer(_INSTANCE, solveur)

    assert _constat(evaluation, "Contrainte retirée : echeance").verdict == "sans_impact"
    assert evaluation.a_regenerer is False


# --- Essai en échec ---


def test_solveur_qui_plante_sur_l_instance_actuelle_est_bloquant() -> None:
    evaluation = _evaluer(_avec_echeance(), _solveur(), executer=_essai_en_erreur("délai dépassé (60 s)"))

    constat = _constat(evaluation, "Exécution sur l'instance actuelle")
    assert constat.verdict == "bloquant"
    assert evaluation.a_regenerer is True


def test_instance_jugee_infaisable_est_a_surveiller_pas_une_preuve_contre_le_solveur() -> None:
    """Des données impossibles ne justifient jamais de régénérer un solveur sain."""
    evaluation = _evaluer(
        _avec_echeance(),
        _solveur(code="Echeance"),
        executer=_essai_en_erreur("le solveur a jugé l'instance infaisable"),
    )

    assert _constat(evaluation, "Exécution sur l'instance actuelle").verdict == "a_surveiller"
    assert evaluation.a_regenerer is False


# --- Objectifs ---


def test_objectif_ajoute_jamais_lu_par_le_code_est_bloquant() -> None:
    instance = _INSTANCE.model_copy(update={"objectifs": [MinimiserMakespan(), EquilibrerCharge()]})

    evaluation = _evaluer(instance, _solveur())

    constat = _constat(evaluation, "Objectif ajouté : equilibrer_charge")
    assert constat.verdict == "bloquant"
    assert "ne l'optimise pas" in constat.argument
    assert evaluation.a_regenerer is True


def test_objectif_ajoute_deja_traite_par_le_code_est_sans_impact() -> None:
    instance = _INSTANCE.model_copy(update={"objectifs": [MinimiserMakespan(), EquilibrerCharge()]})
    code = "if objectif.type == 'equilibrer_charge':\n    ...\n"

    evaluation = _evaluer(instance, _solveur(code=code))

    assert _constat(evaluation, "Objectif ajouté : equilibrer_charge").verdict == "sans_impact"
    assert evaluation.a_regenerer is False


def test_objectif_retire_encore_code_est_a_surveiller_sans_regenerer() -> None:
    solveur = _solveur(objectifs="equilibrer_charge,minimiser_makespan", code="EquilibrerCharge")

    evaluation = _evaluer(_INSTANCE, solveur)

    assert _constat(evaluation, "Objectif retiré : equilibrer_charge").verdict == "a_surveiller"
    assert evaluation.a_regenerer is False


# --- Algorithme ---


def test_autre_algorithme_prefere_mais_actuel_encore_valable_ne_regenere_pas() -> None:
    evaluation = _evaluer(_INSTANCE, _solveur(algorithme="cp_sat"), modele=_modele("genetic", ["cp_sat"]))

    constat = _constat(evaluation, "Algorithme")
    assert constat.verdict == "sans_impact"
    assert "alternatives" in constat.argument
    assert evaluation.a_regenerer is False


def test_algorithme_ni_recommande_ni_alternative_est_bloquant_avec_les_faits() -> None:
    evaluation = _evaluer(
        _INSTANCE, _solveur(algorithme="greedy_local"), modele=_modele("cp_sat", ["tabu_search"])
    )

    constat = _constat(evaluation, "Algorithme")
    assert constat.verdict == "bloquant"
    assert any("2 tâches" in preuve for preuve in constat.preuves)
    assert any("raison de test" in preuve for preuve in constat.preuves)
    assert evaluation.a_regenerer is True


def test_algorithme_inconnu_n_appelle_pas_le_benchmarker() -> None:
    modele = _modele("genetic")

    evaluation = _evaluer(_INSTANCE, _solveur(algorithme=None), modele=modele)

    assert modele.appels == 0
    assert _constat(evaluation, "Algorithme").verdict == "non_verifie"
    assert evaluation.a_regenerer is False
