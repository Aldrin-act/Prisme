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

from generation.agents.base import extraire_json
from generation.agents.client_llm import AppelLLM

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "benchmarker.md"

_PROMPT_SYSTEME = (
    "Tu es un expert en algorithmes d'ordonnancement et en benchmarking. "
    "Tu analyses des problèmes FJSP et recommandes le meilleur algorithme selon "
    "les caractéristiques de l'instance. Tu réponds toujours en JSON strict."
)


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


def analyser_caracteristiques_instance(instance_json: dict) -> CaracteristiquesInstance:
    """Analyse les caractéristiques d'une instance T-R-C-O."""
    nb_taches = len(instance_json["taches"])
    nb_ressources = len(instance_json["ressources"])

    # Compter les compatibilités et précédences
    compatibilites = [
        c for c in instance_json["contraintes"]
        if c.get("type") == "compatibilite_ressource_tache"
    ]
    precedences = [
        c for c in instance_json["contraintes"]
        if c.get("type") == "precedence"
    ]

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

    return CaracteristiquesInstance(
        nb_taches=nb_taches,
        nb_ressources=nb_ressources,
        nb_contraintes=nb_contraintes,
        flexibilite_moyenne=flexibilite_moyenne,
        a_precedences=a_precedences,
        taille_categorie=taille_categorie,
        densite_contraintes=densite_contraintes
    )


def benchmarker_algorithmes(appel_llm: AppelLLM, instance_json: dict) -> ResultatBenchmark:
    """Benchmark plusieurs algorithmes et recommande le meilleur.

    Args:
        appel_llm: Client LLM
        instance_json: Instance T-R-C-O au format dict (pour analyse)

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
        densite_contraintes=carac.densite_contraintes
    )

    # Appel LLM
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)
    donnees = extraire_json(reponse)

    # Parser la recommandation
    recommandation = RecommandationAlgorithme(
        algorithme=donnees["recommandation"]["algorithme"],
        raison=donnees["recommandation"]["raison"],
        parametres_suggeres=donnees["recommandation"].get("parametres", {}),
        temps_execution_estime=donnees["recommandation"].get("temps_estime", "inconnu"),
        qualite_attendue=donnees["recommandation"].get("qualite_attendue", "inconnue"),
        alternatives=donnees["recommandation"].get("alternatives", [])
    )

    return ResultatBenchmark(
        reponse_brute=reponse,
        caracteristiques=carac,
        recommandation=recommandation,
        comparaison=donnees.get("comparaison", "")
    )
