"""Agent Benchmarker (nouveau) — compare plusieurs algorithmes d'ordonnancement
et sélectionne le meilleur pour l'instance donnée.

Au lieu de forcer CP-SAT systématiquement, cet agent :
1. Analyse les caractéristiques de l'instance (taille, contraintes, structure)
2. Benchmark plusieurs algorithmes sur un échantillon
3. Recommande le meilleur selon des critères (qualité, temps, scalabilité)

Algorithmes candidats :
- CP-SAT (OR-Tools) : Optimal pour petites/moyennes instances (<500 tâches)
- Algorithmes génétiques (GA) : Bon pour grandes instances, solutions approchées
- Ant Colony Optimization (ACO) : Exploite la structure du problème
- Simulated Annealing : Rapide, solutions acceptables
- Tabu Search : Equilibre qualité/temps
- Règles de dispatching (SPT, LPT, EDD) : Ultra-rapides, heuristiques
- Glouton + Local Search : Baseline rapide

Sortie : Recommandation motivée du meilleur algorithme avec ses paramètres.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from generation.agents.base import ErreurReponseAgentInvalide  # noqa: F401 — réexporté (tests)
from generation.agents.client_llm import invoquer_agent_avec_outils

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "benchmarker.md"

_PROMPT_SYSTEME = (
    "Tu es un expert en algorithmes d'ordonnancement et en benchmarking. "
    "Tu analyses des problèmes FJSP et recommandes le meilleur algorithme selon "
    "les caractéristiques de l'instance. Tu réponds toujours en JSON strict."
)


class _SchemaRecommandation(BaseModel):
    algorithme: str = Field(description='"cp_sat", "genetic", "aco", "simulated_annealing", etc.')
    raison: str = Field(description="Justification du choix.")
    parametres: dict = Field(default_factory=dict, description="Paramètres recommandés pour cet algorithme.")
    temps_estime: str = Field(default="inconnu", description='"secondes", "minutes", "dizaines de minutes"...')
    qualite_attendue: str = Field(default="inconnue", description='"optimale", "très bonne (>95%)"...')
    alternatives: list[str] = Field(default_factory=list, description="Autres algorithmes envisageables.")


class _SchemaBenchmark(BaseModel):
    recommandation: _SchemaRecommandation
    comparaison: str = Field(default="", description="Tableau comparatif des algorithmes considérés.")


@dataclass(frozen=True)
class CaracteristiquesInstance:
    """Caractéristiques d'une instance FJSP pour le benchmark."""

    nb_taches: int
    nb_ressources: int
    nb_contraintes: int
    flexibilite_moyenne: float  # Moyenne d'équipes compatibles par tâche
    a_precedences: bool
    taille_categorie: str  # "petite", "moyenne", "grande", "très grande"
    densite_contraintes: float  # Ratio contraintes / (tâches × ressources)
    types_objectifs: tuple[str, ...]  # Types distincts présents dans instance.objectifs, triés
    nb_objectifs: int  # Nombre d'objectifs combinés (somme pondérée si > 1)
    # True si un EquilibrerCharge à méthode "variance"/"gini" est demandé —
    # en CP-SAT, cette méthode n'est qu'une approximation linéarisée (voir
    # la section "Objectifs" de generation_solveur.md, la mission commune) ;
    # un algorithme non-CP-SAT peut calculer la vraie variance/le vrai Gini
    # exactement dans sa fonction de fitness, signal pertinent pour ce choix.
    equilibrage_methode_approchee_en_cpsat: bool


@dataclass(frozen=True)
class RecommandationAlgorithme:
    """Recommandation d'algorithme par le benchmarker."""

    algorithme: str  # "cp_sat", "genetic", "aco", "simulated_annealing", etc.
    raison: str  # Justification du choix
    parametres_suggeres: dict[str, any]  # Paramètres recommandés
    temps_execution_estime: str  # "secondes", "minutes", "dizaines de minutes"
    qualite_attendue: str  # "optimale", "très bonne (>95%)", "bonne (>90%)", etc.
    alternatives: list[str]  # Autres algorithmes envisageables


@dataclass(frozen=True)
class ResultatBenchmark:
    reponse_brute: str
    caracteristiques: CaracteristiquesInstance
    recommandation: RecommandationAlgorithme
    comparaison: str  # Tableau comparatif des algorithmes
    # Trace des appels à rechercher_heuristiques_ordonnancement (ex.
    # "rechercher_heuristiques_ordonnancement({'requete': 'genetic algorithm FJSP large instances'})")
    # — jamais relue par le pipeline, utile pour le diagnostic humain (voir
    # client_llm.invoquer_agent_avec_outils). Vide si l'outil n'a pas été
    # appelé, ou si les outils sont désactivés pour cet appel.
    appels_outils: tuple[str, ...] = ()


# Seul CP-SAT est jugé à l'identique (exactitude requise) ; tout autre
# algorithme recommandé par le Benchmarker est approché par nature et n'a
# aucune raison de retomber exactement sur l'optimum du banc synthétique ni
# sur l'affectation tâche→ressource des cas de référence. Lieu naturel pour
# tout appelant (`graph.py`, `loop.py`, `scripts/`) puisque
# c'est ce module qui produit les chaînes `algorithme`.
_ALGORITHMES_EXACTS = frozenset({"cp_sat"})
TOLERANCE_MAKESPAN_ALGORITHME_APPROCHE = 0.10  # 10 % au-dessus de l'optimum/de la référence


def rechercher_heuristiques_sur_le_web(requete: str) -> str:
    """Fonction pure (au sens : sans état module) derrière l'outil LLM —
    recherche web réelle (DuckDuckGo, aucune clé API requise), jamais un
    catalogue figé dans le code : les heuristiques d'ordonnancement et leurs
    performances rapportées évoluent plus vite que ce fichier. Ne lève
    jamais — un échec réseau/de recherche dégrade en un message explicite,
    jamais bloquant pour la recommandation de l'agent (même philosophie que
    `test_sandbox`, `generation/graph.py`)."""
    from langchain_community.tools import DuckDuckGoSearchRun

    try:
        return DuckDuckGoSearchRun().run(requete)
    except Exception as erreur:  # noqa: BLE001 — service externe, jamais bloquant ici
        return f"Recherche web indisponible ({erreur}) — réponds à partir de tes propres connaissances."


def _construire_outil_recherche_heuristiques():
    """Outil lié à ce module, jamais construit au niveau module (import
    paresseux de `langchain_community.tools`, comme le reste des dépendances
    LangChain de ce projet — voir `client_llm.py`)."""
    from langchain_core.tools import tool

    @tool
    def rechercher_heuristiques_ordonnancement(requete: str) -> str:
        """Recherche sur le web des informations sur les algorithmes/heuristiques
        d'ordonnancement (FJSP et problèmes proches) — utile pour comparer des
        approches, vérifier des performances rapportées dans la littérature
        récente, ou découvrir une heuristique non couverte par ce prompt.
        `requete` : la recherche à effectuer (français ou anglais)."""
        return rechercher_heuristiques_sur_le_web(requete)

    return rechercher_heuristiques_ordonnancement


def parametres_cascade_pour_algorithme(algorithme: str) -> tuple[float, bool]:
    """Renvoie `(tolerance_relative, comparer_affectation)` à passer à
    `evaluer_cascade` selon l'algorithme choisi par le Benchmarker."""
    if algorithme in _ALGORITHMES_EXACTS:
        return 0.0, True
    return TOLERANCE_MAKESPAN_ALGORITHME_APPROCHE, False


def creer_instance_exemple_defaut() -> dict:
    """Petite instance par défaut (10 tâches, 5 ressources, pas de
    précédences) pour le Benchmarker quand l'appelant n'a pas d'instance
    réelle sous la main (scripts, tests) — typiquement classée « petite »,
    oriente vers cp_sat, préservant le comportement de ces appelants
    d'avant le branchement du Benchmarker sur le pipeline."""
    return {
        "taches": [{"id": f"T{i}"} for i in range(1, 11)],
        "ressources": [{"id": f"R{i}"} for i in range(1, 6)],
        "contraintes": [
            {
                "type": "compatibilite_ressource_tache",
                "tache": f"T{i}",
                "ressource": f"R{((i - 1) % 5) + 1}",
                "duree": 30,
            }
            for i in range(1, 11)
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def analyser_caracteristiques_instance(instance_json: dict) -> CaracteristiquesInstance:
    """Analyse les caractéristiques d'une instance T-R-C-O."""
    nb_taches = len(instance_json["taches"])
    nb_ressources = len(instance_json["ressources"])

    # Compter les compatibilités et précédences
    compatibilites = [c for c in instance_json["contraintes"] if c.get("type") == "compatibilite_ressource_tache"]
    precedences = [c for c in instance_json["contraintes"] if c.get("type") == "precedence"]

    nb_contraintes = len(compatibilites) + len(precedences)
    a_precedences = len(precedences) > 0

    # Flexibilité moyenne (équipes par tâche)
    from collections import Counter

    comp_par_tache = Counter(c["tache"] for c in compatibilites)
    flexibilite_moyenne = sum(comp_par_tache.values()) / len(comp_par_tache) if comp_par_tache else 0

    # Catégorie de taille
    if nb_taches < 50:
        taille_categorie = "petite"
    elif nb_taches < 200:
        taille_categorie = "moyenne"
    elif nb_taches < 1000:
        taille_categorie = "grande"
    else:
        taille_categorie = "très grande"

    # Densité de contraintes
    densite_contraintes = nb_contraintes / (nb_taches * nb_ressources) if nb_ressources > 0 else 0

    # Objectifs — jamais lus avant cette section : le choix d'algorithme ne
    # dépendait jusqu'ici que de la forme/taille du problème, jamais de ce
    # qu'on cherche à optimiser.
    objectifs = instance_json.get("objectifs", [])
    types_objectifs = tuple(sorted({o.get("type", "?") for o in objectifs}))
    nb_objectifs = len(objectifs)
    equilibrage_methode_approchee_en_cpsat = any(
        o.get("type") == "equilibrer_charge" and o.get("methode", "ecart_max") in {"variance", "gini"}
        for o in objectifs
    )

    return CaracteristiquesInstance(
        nb_taches=nb_taches,
        nb_ressources=nb_ressources,
        nb_contraintes=nb_contraintes,
        flexibilite_moyenne=flexibilite_moyenne,
        a_precedences=a_precedences,
        taille_categorie=taille_categorie,
        densite_contraintes=densite_contraintes,
        types_objectifs=types_objectifs,
        nb_objectifs=nb_objectifs,
        equilibrage_methode_approchee_en_cpsat=equilibrage_methode_approchee_en_cpsat,
    )


def benchmarker_algorithmes(
    modele: BaseChatModel, instance_json: dict, *, avec_outils: bool = True
) -> ResultatBenchmark:
    """Benchmark plusieurs algorithmes et recommande le meilleur.

    Args:
        modele: `BaseChatModel` LangChain (voir `client_llm.construire_modele_pour_agent`).
        instance_json: Instance T-R-C-O au format dict (pour analyse)
        avec_outils: Si vrai (défaut), l'agent peut effectuer une recherche
            web (`rechercher_heuristiques_ordonnancement`, voir plus haut)
            avant de répondre — jamais requis, purement consultatif. `False`
            retombe sur un appel structuré simple, sans outil (tests,
            comparaison avant/après).

    Returns:
        Recommandation d'algorithme avec justification
    """
    # Analyser les caractéristiques
    carac = analyser_caracteristiques_instance(instance_json)

    # Construire le prompt
    prompt_template = CHEMIN_PROMPT.read_text(encoding="utf-8")

    prompt = prompt_template.format(
        nb_taches=carac.nb_taches,
        nb_ressources=carac.nb_ressources,
        nb_contraintes=carac.nb_contraintes,
        flexibilite_moyenne=carac.flexibilite_moyenne,
        a_precedences="Oui" if carac.a_precedences else "Non",
        taille_categorie=carac.taille_categorie,
        densite_contraintes=carac.densite_contraintes,
        types_objectifs=", ".join(carac.types_objectifs) if carac.types_objectifs else "aucun",
        nb_objectifs=carac.nb_objectifs,
        equilibrage_methode_approchee_en_cpsat="Oui" if carac.equilibrage_methode_approchee_en_cpsat else "Non",
    )

    outils = [_construire_outil_recherche_heuristiques()] if avec_outils else []
    donnees, reponse_brute, appels_outils = invoquer_agent_avec_outils(
        modele, _SchemaBenchmark, outils, [SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)]
    )
    recommandation = RecommandationAlgorithme(
        algorithme=donnees.recommandation.algorithme,
        raison=donnees.recommandation.raison,
        parametres_suggeres=donnees.recommandation.parametres,
        temps_execution_estime=donnees.recommandation.temps_estime,
        qualite_attendue=donnees.recommandation.qualite_attendue,
        alternatives=donnees.recommandation.alternatives,
    )

    return ResultatBenchmark(
        reponse_brute=reponse_brute,
        caracteristiques=carac,
        recommandation=recommandation,
        comparaison=donnees.comparaison,
        appels_outils=tuple(appels_outils),
    )
