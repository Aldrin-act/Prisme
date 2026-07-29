"""Couche 1 (§6.1) : `generation.graph` exécute réellement du code Python
via OR-Tools (comme `test_executer.py`), d'où `integration/` plutôt que
`unit/`. Aucun appel LLM réel — un faux modèle par agent (voir
`tests/unit/aides_test_agents.py`), injecté via `config["configurable"]
["fabrique_modele"]` (voir `generation.graph._modele`), remplace
`construire_modele_pour_agent` sans reconstruire le graphe."""

from __future__ import annotations

import json

import generation.graph as g
from generation.agents import (
    analyste,
    architecte,
    benchmarker,
    debugger,
    documentation,
    generateur,
    testeur,
)
from generation.agents import (
    reviewer as reviewer_agent,
)
from tests.unit.aides_test_agents import ModeleFactice

# Respecte l'allowlist AST (generation/validation_statique.py) et résout
# réellement le FJSP (CP-SAT) — un stub qui renverrait juste un Planning
# vide échouerait légitimement la cascade réelle contre le banc synthétique.
# Même fixture que tests/integration/test_pipeline_multi_agents.py (fichier
# supprimé avec cette migration).
CODE_BON = """
from __future__ import annotations

from collections import defaultdict

from ortools.sat.python import cp_model

from dsl.schema import CompatibiliteRessourceTache, OperationPlanifiee, Planning, Precedence


def resoudre(instance):
    modele = cp_model.CpModel()

    compat = defaultdict(set)
    duree = {}
    for contrainte in instance.contraintes:
        if isinstance(contrainte, CompatibiliteRessourceTache):
            compat[contrainte.tache].add(contrainte.ressource)
            duree[(contrainte.tache, contrainte.ressource)] = contrainte.duree

    horizon = sum(max(duree[(tache.id, r)] for r in compat[tache.id]) for tache in instance.taches)

    debut = {}
    fin = {}
    presence = {}
    intervalles = defaultdict(list)

    for tache in instance.taches:
        candidats = compat[tache.id]
        d_var = modele.NewIntVar(0, horizon, f"debut_{tache.id}")
        f_var = modele.NewIntVar(0, horizon, f"fin_{tache.id}")
        debut[tache.id] = d_var
        fin[tache.id] = f_var

        presences_tache = []
        for ressource_id in candidats:
            d = duree[(tache.id, ressource_id)]
            p = modele.NewBoolVar(f"presence_{tache.id}_{ressource_id}")
            intervalle = modele.NewOptionalIntervalVar(d_var, d, f_var, p, f"iv_{tache.id}_{ressource_id}")
            intervalles[ressource_id].append(intervalle)
            presence[(tache.id, ressource_id)] = p
            presences_tache.append(p)
        modele.AddExactlyOne(presences_tache)

    for ressource in instance.ressources:
        modele.AddNoOverlap(intervalles[ressource.id])

    for contrainte in instance.contraintes:
        if isinstance(contrainte, Precedence):
            modele.Add(fin[contrainte.avant] <= debut[contrainte.apres])

    makespan = modele.NewIntVar(0, horizon, "makespan")
    modele.AddMaxEquality(makespan, list(fin.values()))
    modele.Minimize(makespan)

    solveur = cp_model.CpSolver()
    statut = solveur.Solve(modele)
    if statut not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    operations = []
    for tache in instance.taches:
        candidats = compat[tache.id]
        ressource_choisie = next(r for r in candidats if solveur.Value(presence[(tache.id, r)]))
        operations.append(
            OperationPlanifiee(tache=tache.id, ressource=ressource_choisie, debut=solveur.Value(debut[tache.id]))
        )
    return Planning(operations=operations)
"""

CODE_INVALIDE = "import os\n\n\ndef resoudre(instance):\n    return None\n"


def _modele_revue(*, verdict: str | None, problemes: list[str] | None) -> ModeleFactice:
    schema = reviewer_agent._SchemaRevue(verdict=verdict, problemes=problemes)
    return ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)


def _reponses_communes() -> dict[str, object]:
    """Une réponse par agent, suffisante pour amener le pipeline jusqu'au
    Reviewer sans jamais échouer avant — chaque test surcharge ensuite
    `reviewer`/`debugger` selon le scénario."""
    return {
        "analyste": ModeleFactice(
            raw_content="{}",
            parsed=analyste._SchemaAnalyse(entrees="I", sorties="P", contraintes_a_couvrir=["c1"]),
        ),
        "benchmarker": ModeleFactice(
            raw_content="{}",
            parsed=benchmarker._SchemaBenchmark(
                recommandation=benchmarker._SchemaRecommandation(algorithme="cp_sat", raison="petite instance")
            ),
        ),
        "architecte": ModeleFactice(
            raw_content="{}",
            parsed=architecte._SchemaConception(variables="v", contraintes_modele="c", objectif="o"),
        ),
        "generateur": ModeleFactice(raw_content="{}", parsed=generateur._SchemaGenerationCode(code=CODE_BON)),
        "testeur": ModeleFactice(
            raw_content="{}", parsed=testeur._SchemaTests(code_tests="def test_x(): assert True")
        ),
        "documentation": ModeleFactice(
            raw_content="{}",
            parsed=documentation._SchemaDocumentation(resume="r", limites_connues="l"),
        ),
    }


def _fabrique(specs: dict[str, object | list[object]]):
    files = {nom: iter(v if isinstance(v, list) else [v] * 100) for nom, v in specs.items()}

    def fabrique_modele(nom_agent: str):
        return next(files[nom_agent])

    return fabrique_modele


def _invoquer(specs: dict[str, object | list[object]]) -> g.ResultatPipelineAvecBoucle:
    graphe = g._construire_graphe().compile()
    etat_final = graphe.invoke(
        {"instance_exemple": None},
        config={"configurable": {"fabrique_modele": _fabrique(specs)}, "recursion_limit": 60},
    )
    resultat = etat_final["resultat_final"]
    assert resultat is not None
    return resultat


def test_pipeline_reussi_quand_le_reviewer_approuve_directement() -> None:
    specs = _reponses_communes()
    specs["reviewer"] = _modele_revue(verdict="APPROUVE", problemes=None)

    resultat = _invoquer(specs)

    assert resultat.reussi is True
    assert resultat.code_final.strip() == CODE_BON.strip()
    assert resultat.boucle_reparation.nombre_tentatives == 1
    assert len(resultat.boucle_reparation.tentatives) == 1
    assert resultat.boucle_reparation.tentatives[0].reussi is True
    assert resultat.documentation is not None


def test_pipeline_recupere_via_le_debugger_quand_le_reviewer_rejette() -> None:
    specs = _reponses_communes()
    # 1re tentative : Reviewer rejette. Debugger corrige (renvoie CODE_BON).
    # 2e tentative : Reviewer approuve, la validation passe.
    specs["reviewer"] = [
        _modele_revue(verdict="A_CORRIGER", problemes=["import os interdit"]),
        _modele_revue(verdict="APPROUVE", problemes=None),
    ]
    specs["debugger"] = ModeleFactice(
        raw_content="{}", parsed=debugger._SchemaCorrection(code=CODE_BON, cause="import interdit retiré")
    )

    resultat = _invoquer(specs)

    assert resultat.reussi is True
    assert resultat.code_final.strip() == CODE_BON.strip()
    assert resultat.boucle_reparation.nombre_tentatives == 2
    assert len(resultat.boucle_reparation.tentatives) == 2
    assert resultat.boucle_reparation.tentatives[0].reussi is False
    assert resultat.boucle_reparation.tentatives[0].validation_statique is None  # sauté, reviewer a rejeté
    assert resultat.boucle_reparation.tentatives[1].reussi is True


def test_pipeline_echoue_apres_epuisement_des_tentatives() -> None:
    specs = _reponses_communes()
    specs["generateur"] = ModeleFactice(
        raw_content="{}", parsed=generateur._SchemaGenerationCode(code=CODE_INVALIDE)
    )
    # Reviewer approuve toujours, mais le code reste invalide (import os) —
    # la validation échoue à chaque tentative, le Debugger ne corrige jamais
    # vraiment (renvoie le même code invalide).
    specs["reviewer"] = _modele_revue(verdict="APPROUVE", problemes=None)
    specs["debugger"] = ModeleFactice(
        raw_content="{}", parsed=debugger._SchemaCorrection(code=CODE_INVALIDE, cause="tentative infructueuse")
    )

    resultat = _invoquer(specs)

    assert resultat.reussi is False
    assert resultat.boucle_reparation.reussi is False
    assert resultat.boucle_reparation.nombre_tentatives == g.MAX_TENTATIVES_REPARATION
    assert len(resultat.boucle_reparation.tentatives) == g.MAX_TENTATIVES_REPARATION
    assert resultat.documentation is None  # sautée en cas d'échec


def test_debugger_jamais_appele_sur_la_derniere_tentative_epuisee() -> None:
    """Le Debugger ne doit jamais être invoqué pour une 11e tentative — le
    contrôle de la borne se fait dans le routeur, avant l'arête vers lui."""
    specs = _reponses_communes()
    specs["generateur"] = ModeleFactice(
        raw_content="{}", parsed=generateur._SchemaGenerationCode(code=CODE_INVALIDE)
    )
    specs["reviewer"] = _modele_revue(verdict="APPROUVE", problemes=None)

    appels_debugger = 0
    modele_debugger = ModeleFactice(
        raw_content="{}", parsed=debugger._SchemaCorrection(code=CODE_INVALIDE, cause="c")
    )
    original_invoke = modele_debugger.with_structured_output

    def with_structured_output_compte(*args, **kwargs):
        nonlocal appels_debugger
        appels_debugger += 1
        return original_invoke(*args, **kwargs)

    modele_debugger.with_structured_output = with_structured_output_compte
    specs["debugger"] = modele_debugger

    resultat = _invoquer(specs)

    assert resultat.boucle_reparation.nombre_tentatives == g.MAX_TENTATIVES_REPARATION
    # Le Debugger corrige après les tentatives 1..9 (jamais après la 10e).
    assert appels_debugger == g.MAX_TENTATIVES_REPARATION - 1


def test_boucle_epuisee_ne_leve_pas_graphrecursionerror() -> None:
    """Couvre le risque de limite de récursion : 5 nœuds de mise en place +
    10 × (reviewer + validation + debugger) doit rester sous la limite
    passée à `.invoke()` (voir `generation.graph._LIMITE_RECURSION`)."""
    specs = _reponses_communes()
    specs["generateur"] = ModeleFactice(
        raw_content="{}", parsed=generateur._SchemaGenerationCode(code=CODE_INVALIDE)
    )
    specs["reviewer"] = _modele_revue(verdict="APPROUVE", problemes=None)
    specs["debugger"] = ModeleFactice(
        raw_content="{}", parsed=debugger._SchemaCorrection(code=CODE_INVALIDE, cause="c")
    )

    resultat = _invoquer(specs)  # ne doit lever aucune exception

    assert resultat.boucle_reparation.nombre_tentatives == g.MAX_TENTATIVES_REPARATION


def test_stream_produit_des_evenements_etape_puis_le_resultat_final() -> None:
    specs = _reponses_communes()
    specs["reviewer"] = _modele_revue(verdict="APPROUVE", problemes=None)

    graphe = g._construire_graphe().compile()
    elements: list = []
    for mode, payload in graphe.stream(
        {"instance_exemple": None},
        stream_mode=["custom", "values"],
        config={"configurable": {"fabrique_modele": _fabrique(specs)}, "recursion_limit": 60},
    ):
        if mode == "custom":
            elements.append(payload)

    noms_agents = [e["agent"] for e in elements]
    assert "benchmarker" in noms_agents
    assert "documentation" in noms_agents
    assert all(e["statut"] in ("en_cours", "termine", "echec") for e in elements)
