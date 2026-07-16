"""Couche 1 (§6.1), `integration/` : `tenter_generation_multi_agents`
exécute réellement du code Python via OR-Tools (comme `test_executer.py`),
d'où `integration/` plutôt que `unit/`.

Aucun appel LLM réel ici — un `AppelLLM` factice répond selon le prompt
système reçu (chaque agent utilise un prompt système distinct et fixe, voir
`generation/agents/*.py`), pour vérifier le câblage des 9 agents
indépendamment de toute clé d'API ou de la qualité réelle d'un LLM (voir
`scripts/mesurer_taux_succes_generation.py` pour ça).
"""

from __future__ import annotations

from generation.pipeline_multi_agents import tenter_generation_multi_agents

# Respecte l'allowlist AST (validation_statique.py) — contrairement à
# solveur_reference/solveur.py, qui importe `time` et n'y est jamais soumis
# (code permanent écrit à la main, hors du cycle « générer une fois »).
CODE_BON = """
from __future__ import annotations

from collections import defaultdict

from ortools.sat.python import cp_model

from dsl.schema import CompatibiliteMachineTache, OperationPlanifiee, Planning, Precedence


def resoudre(instance):
    modele = cp_model.CpModel()

    compat = defaultdict(set)
    duree = {}
    for contrainte in instance.contraintes:
        if isinstance(contrainte, CompatibiliteMachineTache):
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

_SYS_ORCHESTRATEUR = "Tu es un chef de projet technique qui planifie le travail d'une équipe d'agents spécialisés."
_SYS_ANALYSTE = "Tu es un analyste technique spécialisé en ordonnancement (FJSP) et en modélisation."
_SYS_ARCHITECTE = "Tu es un architecte logiciel spécialisé en modélisation de contraintes (CP-SAT, OR-Tools)."
_SYS_DEVELOPPEUR = "Tu es un générateur de code Python expert en optimisation combinatoire."
_SYS_TESTEUR = "Tu es un ingénieur qualité spécialisé en tests de solveurs d'optimisation combinatoire."
_SYS_REVIEWER = "Tu es un relecteur de code Python expert en optimisation combinatoire et en revue de sécurité."
_SYS_DEBUGGER = "Tu es un développeur Python expert en débogage de modèles d'optimisation combinatoire (CP-SAT)."
_SYS_OPTIMISEUR = "Tu es un ingénieur performance spécialisé en modèles CP-SAT et en code Python sobre."
_SYS_DOCUMENTATION = "Tu es un rédacteur technique spécialisé en documentation de modèles d'optimisation."


def _appel_factice(reponses: dict[str, str]):
    def appel(prompt_systeme: str, _prompt_utilisateur: str) -> str:
        return reponses[prompt_systeme]

    return appel


def _reponses_communes() -> dict[str, str]:
    """Les réponses des agents dont le contenu exact n'affecte pas le
    verdict (Orchestrateur, Analyste, Architecte, Testeur, Documentation) —
    du texte plausible, pas vide."""
    return {
        _SYS_ORCHESTRATEUR: "1. Analyste : ...\n2. Architecte : ...\n8. Documentation : ...",
        _SYS_ANALYSTE: "## Entrées\n...\n## Sorties\n...\n## Contraintes à couvrir\n...",
        _SYS_ARCHITECTE: "## Variables du modèle CP-SAT\n...\n## Contraintes du modèle\n...",
        _SYS_TESTEUR: "```python\ndef test_exemple():\n    assert True\n```",
        _SYS_DOCUMENTATION: "Résout le noyau minimal T-R-C-O via CP-SAT. Aucune limite connue.",
    }


def test_pipeline_reussi_quand_le_reviewer_approuve_directement() -> None:
    reponses = _reponses_communes()
    reponses[_SYS_DEVELOPPEUR] = f"```python\n{CODE_BON}\n```"
    reponses[_SYS_REVIEWER] = "VERDICT: APPROUVE\nConforme au contrat."
    reponses[_SYS_OPTIMISEUR] = "OPTIMISATION: AUCUNE\nRien à améliorer sans risque."

    resultat = tenter_generation_multi_agents(_appel_factice(reponses))

    assert resultat.reussi, (resultat.erreur_execution, resultat.verdict_cascade)
    assert resultat.revue.approuve
    assert resultat.code_corrige is None
    assert resultat.code_optimise_adopte is False
    assert resultat.documentation is not None
    assert resultat.plan_orchestrateur and resultat.specification and resultat.plan_technique


def test_pipeline_recupere_via_le_debugger_quand_le_reviewer_rejette() -> None:
    reponses = _reponses_communes()
    reponses[_SYS_DEVELOPPEUR] = f"```python\n{CODE_INVALIDE}\n```"
    reponses[_SYS_REVIEWER] = "VERDICT: A_CORRIGER\nImport `os` interdit par la mission."
    reponses[_SYS_DEBUGGER] = f"```python\n{CODE_BON}\n```"
    reponses[_SYS_OPTIMISEUR] = "OPTIMISATION: AUCUNE\nRien à améliorer sans risque."

    resultat = tenter_generation_multi_agents(_appel_factice(reponses))

    assert resultat.reussi, (resultat.erreur_execution, resultat.verdict_cascade)
    assert resultat.revue.approuve is False
    assert resultat.code_corrige is not None
    assert resultat.code_final.strip() == CODE_BON.strip()


def test_pipeline_echoue_si_le_debugger_ne_corrige_pas_non_plus() -> None:
    reponses = _reponses_communes()
    reponses[_SYS_DEVELOPPEUR] = f"```python\n{CODE_INVALIDE}\n```"
    reponses[_SYS_REVIEWER] = "VERDICT: A_CORRIGER\nImport `os` interdit par la mission."
    reponses[_SYS_DEBUGGER] = f"```python\n{CODE_INVALIDE}\n```"

    resultat = tenter_generation_multi_agents(_appel_factice(reponses))

    assert resultat.reussi is False
    assert resultat.validation_statique.valide is False
    assert resultat.optimisation is None
    assert resultat.documentation is None


def test_optimisation_rejetee_si_elle_echoue_la_validation() -> None:
    reponses = _reponses_communes()
    reponses[_SYS_DEVELOPPEUR] = f"```python\n{CODE_BON}\n```"
    reponses[_SYS_REVIEWER] = "VERDICT: APPROUVE\nConforme au contrat."
    reponses[_SYS_OPTIMISEUR] = f"OPTIMISATION: PROPOSEE\n```python\n{CODE_INVALIDE}\n```\nSimplification erronée."

    resultat = tenter_generation_multi_agents(_appel_factice(reponses))

    assert resultat.reussi, (resultat.erreur_execution, resultat.verdict_cascade)
    assert resultat.optimisation is not None
    assert resultat.optimisation.proposee is True
    assert resultat.code_optimise_adopte is False
    assert resultat.code_final.strip() == CODE_BON.strip()
