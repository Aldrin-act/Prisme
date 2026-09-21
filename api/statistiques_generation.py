"""KPI d'agrégat sur les générations de solveur (page Analytique du frontend) — calcul pur,
séparé du stockage (`EtatAPI`/`EtatPostgres` ne font que lister des lignes brutes, voir
`lister_evenements_generation`/`lister_tentatives_generation`) pour rester testable sans base
de données et indépendant du backend de persistance.

Deux familles de KPI :
- généraux (déjà partiellement affichés côté frontend, recalculés ici côté serveur pour
  survivre à un redémarrage — le frontend actuel lit `_JOBS`, en mémoire process, voir
  `api/routes/generation.py`) : taux de réussite, tentatives moyennes à la convergence,
  durée moyenne ;
- non-répétition (boucles), le sujet demandé : une génération multi-agents avec boucle de
  réparation bornée (§6.6) peut « boucler » sans jamais violer sa borne de tentatives — ces
  KPI rendent ça visible même quand `nombre_tentatives < MAX_TENTATIVES_REPARATION`.
  Filtrables par agent (`calculer_statistiques(..., agent="debugger")`) — restreint aux
  générations où cet agent est intervenu, pour répondre à « lequel des agents boucle ».

Ce qui n'est PAS ici, et pourquoi (pas de champ inventé, pas de métrique qui n'a pas de sens
dans ce système) : pas de coût par tokens/appels API (LangSmith fait cette observabilité,
jamais dupliquée dans ce store — voir CLAUDE.md) ; pas de MTBF ni de CSAT (pas de service
continu ni d'utilisateur final direct de l'agent) ; pas de « taux d'échec par timeout » au
sens littéral (aucun champ ne distingue un timeout réseau/LLM d'une autre erreur — seul le
taux d'épuisement de la boucle, `taux_epuisement_boucle`, est exact et sert d'équivalent
pour « session bloquée sans résolution »).
"""

from __future__ import annotations

import re
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime

# Même règle que `agentNormalise` (Front/.../analytics.tsx) — un nom d'agent brut porte son
# numéro de tentative (`"debugger (tentative 3/10)"`) ; sans le retirer, chaque tentative
# compterait comme un "agent" différent et fausserait diversité/détection de boucle.
_SUFFIXE_TENTATIVE = re.compile(r"\s*\(tentative \d+/\d+\)$")

# Un même agent en échec au moins ce nombre de fois dans un même job est considéré comme une
# boucle détectée (répétition d'échec, pas juste une correction normale) — seuil délibérément
# bas (3) : la boucle de réparation autorise jusqu'à `MAX_TENTATIVES_REPARATION` (10) essais,
# mais un même agent qui échoue 3 fois de suite sans jamais passer est déjà un signal fort de
# non-convergence, pas besoin d'attendre l'épuisement complet pour le voir.
SEUIL_ECHECS_BOUCLE = 3

# Seuls ces nœuds de `generation/graph.py` émettent jamais `statut="echec"` (grep
# `etape(nom, "echec"` / `"termine" if ... else "echec"` dans ce fichier) — tous les autres
# (analyste, benchmarker, architecte, developpeur, testeur, debugger) rapportent toujours
# "termine" une fois qu'ils ont produit une sortie, même une correction qui ne résout rien
# (le Debugger ne "rate" jamais son propre tour, il produit toujours *une* proposition).
# `taux_boucles_detectees` serait donc trivialement 0% en filtrant sur l'un de ces agents —
# pas une vraie mesure d'absence de boucle, juste un artefact de ce que ce nœud ne peut
# structurellement pas signaler d'échec. `reviewer` reste listé bien que désactivé (§ Reviewer
# disabled) : les jobs historiques d'avant sa désactivation portent encore ses évènements.
AGENTS_CAPABLES_ECHEC = frozenset({"test_sandbox", "validation", "documentation", "reviewer"})


def agent_normalise(agent: str) -> str:
    return _SUFFIXE_TENTATIVE.sub("", agent)


@dataclass(frozen=True)
class StatistiquesGeneration:
    generations_lancees: int
    generations_terminees: int
    taux_reussite: float | None
    duree_moyenne_s: float | None

    # Non-répétition (boucles) — voir docstring module.
    tentatives_moyennes_convergence: float | None
    taux_epuisement_boucle: float | None
    taux_boucles_detectees: float | None
    diversite_actions_moyenne: float | None
    taux_stagnation: float | None

    def en_dict(self) -> dict[str, object]:
        return asdict(self)


def _duree_s(cree_le: str, termine_le: str) -> float | None:
    try:
        return (datetime.fromisoformat(termine_le) - datetime.fromisoformat(cree_le)).total_seconds()
    except ValueError:
        return None


def _moyenne(valeurs: list[float]) -> float | None:
    return statistics.fmean(valeurs) if valeurs else None


def _pourcentage(numerateur: int, denominateur: int) -> float | None:
    return (numerateur / denominateur * 100) if denominateur else None


def calculer_statistiques(
    jobs: list[dict[str, object]],
    evenements: list[dict[str, object]],
    tentatives: list[dict[str, object]],
    max_tentatives_reparation: int,
    agent: str | None = None,
) -> StatistiquesGeneration:
    """`agent` (déjà normalisé, ex. `"debugger"` sans suffixe de tentative) restreint TOUT le
    calcul aux générations où cet agent est intervenu au moins une fois — un seul filtre
    cohérent plutôt que de ne filtrer qu'une partie des KPI. `taux_boucles_detectees` change
    aussi de définition sous ce filtre : « cet agent précis a-t-il échoué ≥ le seuil de fois »
    plutôt que « un agent quelconque » — et devient `None` (non applicable, pas 0%) si `agent`
    ne peut structurellement jamais échouer (voir `AGENTS_CAPABLES_ECHEC`) : filtrer un KPI de
    boucle sur un agent qui ne peut pas être en boucle casserait la cohérence de la mesure."""
    evenements_par_job: dict[str, list[dict[str, object]]] = {}
    for e in evenements:
        evenements_par_job.setdefault(str(e["job_id"]), []).append(e)

    if agent is not None:
        ids_jobs_avec_agent = {
            job_id
            for job_id, evs in evenements_par_job.items()
            if any(agent_normalise(str(e["agent"])) == agent for e in evs)
        }
        jobs = [j for j in jobs if str(j["job_id"]) in ids_jobs_avec_agent]
        tentatives = [t for t in tentatives if str(t["job_id"]) in ids_jobs_avec_agent]

    jobs_termines = [j for j in jobs if j["termine"]]
    jobs_reussis = [j for j in jobs_termines if j["reussi"]]
    ids_jobs_termines = {str(j["job_id"]) for j in jobs_termines}

    durees = [
        d
        for j in jobs_termines
        if j["termine_le"] is not None and (d := _duree_s(str(j["cree_le"]), str(j["termine_le"]))) is not None
    ]

    tentatives_convergence = [
        float(j["nombre_tentatives"]) for j in jobs_reussis if j["nombre_tentatives"] is not None
    ]

    jobs_epuises = [
        j for j in jobs_termines if not j["reussi"] and (j["nombre_tentatives"] or 0) >= max_tentatives_reparation
    ]

    # Regroupe par agent normalisé au sein de chaque job (parmi les jobs terminés retenus),
    # pour la détection de boucle et la diversité des actions.
    echecs_par_job_agent: dict[str, dict[str, int]] = {}
    agents_uniques_par_job: dict[str, set[str]] = {}
    nb_evenements_par_job: dict[str, int] = {}
    for job_id in ids_jobs_termines:
        for e in evenements_par_job.get(job_id, []):
            # Une mesure d'appel au modèle n'est pas une action d'agent : la compter fausserait la
            # diversité des actions (nombre d'évènements au dénominateur).
            if e["statut"] == "mesure":
                continue
            nom_agent = agent_normalise(str(e["agent"]))
            nb_evenements_par_job[job_id] = nb_evenements_par_job.get(job_id, 0) + 1
            agents_uniques_par_job.setdefault(job_id, set()).add(nom_agent)
            if e["statut"] == "echec":
                par_agent = echecs_par_job_agent.setdefault(job_id, {})
                par_agent[nom_agent] = par_agent.get(nom_agent, 0) + 1

    def _boucle_detectee(par_agent: dict[str, int]) -> bool:
        if agent is not None:
            return par_agent.get(agent, 0) >= SEUIL_ECHECS_BOUCLE
        return max(par_agent.values(), default=0) >= SEUIL_ECHECS_BOUCLE

    # Cohérence : un filtre sur un agent qui ne peut structurellement pas échouer rendrait ce
    # KPI trivialement 0% (voir `AGENTS_CAPABLES_ECHEC`) — `None` (non applicable) plutôt qu'un
    # 0% qui se lirait à tort comme « pas de boucle détectée pour cet agent ».
    boucles_non_applicable = agent is not None and agent not in AGENTS_CAPABLES_ECHEC
    jobs_avec_boucle = (
        set()
        if boucles_non_applicable
        else {job_id for job_id, par_agent in echecs_par_job_agent.items() if _boucle_detectee(par_agent)}
    )
    diversites = [
        len(agents_uniques_par_job[job_id]) / nb_evenements_par_job[job_id]
        for job_id in ids_jobs_termines
        if nb_evenements_par_job.get(job_id)
    ]

    # Stagnation : parmi les tentatives consécutives d'un même job (déjà triées par `numero`,
    # voir les deux implémentations de `lister_tentatives_generation`), code candidat identique
    # au précédent = le Debugger a "corrigé" sans rien changer. Ne couvre que les tentatives
    # qui atteignent la Validation (seules à être persistées ici, voir
    # `generation/graph.py::_noeud_validation`) — un cycle test_sandbox/Debugger qui échoue
    # avant la Validation n'apparaît pas individuellement, seul `nombre_tentatives` le reflète.
    # Jamais spécifique à `agent` : une tentative n'est pas attribuable à un agent unique
    # (solveur ET tests, potentiellement corrigés par le Debugger sur la base d'un diagnostic
    # de Validation ou de test_sandbox).
    tentatives_par_job: dict[str, list[str]] = {}
    for t in tentatives:
        tentatives_par_job.setdefault(str(t["job_id"]), []).append(str(t["code_candidat"]))
    transitions_stagnantes = 0
    transitions_totales = 0
    for codes in tentatives_par_job.values():
        for precedent, suivant in zip(codes, codes[1:]):
            transitions_totales += 1
            if precedent == suivant:
                transitions_stagnantes += 1

    return StatistiquesGeneration(
        generations_lancees=len(jobs),
        generations_terminees=len(jobs_termines),
        taux_reussite=_pourcentage(len(jobs_reussis), len(jobs_termines)),
        duree_moyenne_s=_moyenne(durees),
        tentatives_moyennes_convergence=_moyenne(tentatives_convergence),
        taux_epuisement_boucle=_pourcentage(len(jobs_epuises), len(jobs_termines)),
        taux_boucles_detectees=(
            None if boucles_non_applicable else _pourcentage(len(jobs_avec_boucle), len(jobs_termines))
        ),
        diversite_actions_moyenne=_moyenne(diversites),
        taux_stagnation=_pourcentage(transitions_stagnantes, transitions_totales),
    )
