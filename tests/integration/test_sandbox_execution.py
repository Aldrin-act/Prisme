"""Couche 1 (§6.1), Docker requis. Critère de validation de l'Étape 7 : un
solveur validé est stocké, réexécuté sur de nouvelles données dans un
conteneur qui meurt après, et le résultat est vérifié par le garde-fou de
faisabilité (§6.7) — les trois pièces (store, sandbox, garde-fou) bouclées
ensemble.
"""

from __future__ import annotations

from pathlib import Path

import scripts._solveur_minimal as _module_solveur_minimal
from dsl.schema import (
    CompatibiliteRessourceTache,
    InstanceTRCO,
    MinimiserMakespan,
    OperationPlanifiee,
    Planning,
    Ressource,
    Tache,
)
from sandbox.runner import executer_dans_sandbox, executer_solveur_valide
from solver_store.registry import Registre
from validation_engine.cascade import VerdictCascade
from validation_engine.synthetic_bench import generer_catalogue

# Signature à un seul paramètre — représente les 9 solveurs déjà enregistrés dans
# `solver_store/artifacts/` avant l'ajout de l'horizon gelé (Phase 2). Renvoie un planning fixe
# et légal pour l'instance à une tâche/une ressource utilisée ci-dessous.
CODE_ANCIENNE_SIGNATURE = """
from dsl.schema import OperationPlanifiee, Planning


def resoudre(instance):
    return Planning(operations=[OperationPlanifiee(tache="T1", ressource="R1", debut=0)])
"""


def _instance_triviale() -> InstanceTRCO:
    return InstanceTRCO(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
        objectifs=[MinimiserMakespan()],
    )


def _instance_choix_ressource() -> InstanceTRCO:
    """T1 est compatible avec deux ressources à des durées différentes — un solveur qui minimise
    le makespan sans contrainte de gel choisit naturellement R1 (durée 5, la plus courte)."""
    return InstanceTRCO(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1"), Ressource(id="R2")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=5),
            CompatibiliteRessourceTache(tache="T1", ressource="R2", duree=10),
        ],
        objectifs=[MinimiserMakespan()],
    )


def test_solveur_valide_stocke_puis_execute_en_sandbox(image_sandbox: str, registre_test: Registre) -> None:
    registre = registre_test
    code_source = Path(_module_solveur_minimal.__file__).read_text(encoding="utf-8")

    # Un verdict vert « à blanc » : ce test vérifie le câblage store → sandbox
    # → garde-fou, pas la cascade elle-même (déjà couverte ailleurs).
    id_solveur = registre.enregistrer_solveur(
        code_source=code_source,
        structure_contraintes="precedence,compatibilite_ressource_tache",
        verdict_cascade=VerdictCascade(diagnostics=()),
    )

    cas = next(c for c in generer_catalogue() if c.nom == "taille_2_chaine_simple")

    resultat = executer_solveur_valide(registre, id_solveur, cas.instance)

    assert resultat.reussi, resultat.erreur
    assert resultat.planning is not None
    assert resultat.verdict_faisabilite is not None
    assert resultat.verdict_faisabilite.legal


def test_solveur_ancienne_signature_continue_de_fonctionner_sans_horizon_gele(
    image_sandbox: str, registre_test: Registre
) -> None:
    """Régression : un solveur enregistré avant l'ajout de l'horizon gelé (Phase 2) doit
    continuer à s'exécuter normalement tant qu'aucun gel n'est demandé (comportement par défaut,
    `horizon_gele_jours=0`) — aucun changement pour les 9 solveurs déjà enregistrés en pratique."""
    id_solveur = registre_test.enregistrer_solveur(
        code_source=CODE_ANCIENNE_SIGNATURE,
        structure_contraintes="compatibilite_ressource_tache",
        verdict_cascade=VerdictCascade(diagnostics=()),
    )

    resultat = executer_solveur_valide(registre_test, id_solveur, _instance_triviale())

    assert resultat.reussi, resultat.erreur


def test_solveur_ancienne_signature_avec_horizon_gele_echoue_explicitement(registre_test: Registre) -> None:
    """Décision confirmée avec l'utilisateur : jamais de dégradation silencieuse. Ce test ne
    demande volontairement pas la fixture `image_sandbox` (pas de `docker build`) — si
    `executer_solveur_valide` lançait quand même un conteneur ici, ce test échouerait avec un
    message Docker (image introuvable), pas le message explicite attendu ci-dessous."""
    id_solveur = registre_test.enregistrer_solveur(
        code_source=CODE_ANCIENNE_SIGNATURE,
        structure_contraintes="compatibilite_ressource_tache",
        verdict_cascade=VerdictCascade(diagnostics=()),
    )

    resultat = executer_solveur_valide(registre_test, id_solveur, _instance_triviale(), horizon_gele_jours=5)

    assert not resultat.reussi
    assert resultat.planning is None
    assert resultat.erreur is not None
    assert "horizon_gele_jours" in resultat.erreur
    assert "régénérez" in resultat.erreur


def test_sans_gel_le_solveur_choisit_la_ressource_la_plus_rapide(image_sandbox: str) -> None:
    """Base de comparaison pour le test suivant : sans gel, `_solveur_minimal` choisit R1 (la
    ressource la moins coûteuse), jamais R2."""
    planning = executer_dans_sandbox(Path(_module_solveur_minimal.__file__), _instance_choix_ressource())

    assert planning is not None
    assert planning.operations[0].ressource == "R1"


def test_horizon_gele_force_la_ressource_et_le_debut_du_planning_precedent(image_sandbox: str) -> None:
    """`_solveur_minimal` (Phase 2, étendu de façon additive) doit figer T1 sur R2 à debut=0
    (comme dans `planning_precedent`) même si R1 serait naturellement moins coûteux — preuve que
    le gel prime sur l'optimisation, pas seulement une coïncidence de placement."""
    planning_precedent = Planning(operations=[OperationPlanifiee(tache="T1", ressource="R2", debut=0)])

    planning = executer_dans_sandbox(
        Path(_module_solveur_minimal.__file__),
        _instance_choix_ressource(),
        planning_precedent=planning_precedent,
        horizon_gele_jours=1,
    )

    assert planning is not None
    assert planning.operations[0].ressource == "R2"
    assert planning.operations[0].debut == 0
