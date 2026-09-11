"""Client LLM générique pour les agents du pipeline (§5.6).

**Fournisseur unique : Kimi (Moonshot AI)** (`KIMI_API_KEY`, jamais lue/manipulée/journalisée
directement ici, uniquement passée telle quelle à `ChatOpenAI`, voir `_construire_modele_kimi`
pour pourquoi `ChatOpenAI` plutôt qu'un package dédié). `PRISME_LLM_MODEL`
(défaut `kimi-k2.6`) et les surcharges par agent
(`PRISME_LLM_MODEL_<AGENT>`/`PRISME_LLM_TIMEOUT_SECONDES_<AGENT>`) restent disponibles ;
il n'existe plus de variable de choix de fournisseur — les autres fournisseurs
(qwen/together/nvidia/minimax/deepseek/nemotron, puis Mistral) ont été retirés du code au fil
du temps, jugés une complexité non nécessaire pour un seul fournisseur réellement utilisé en
production.

Construit sur LangChain (`langchain-core`/`langchain-openai`, `extra` optionnel
`llm` du projet) plutôt que sur le SDK brut : donne un timeout HTTP réel par appel
(absent de la version précédente — un blip réseau pouvait bloquer indéfiniment, voir
`_TIMEOUT_DEFAUT_SECONDES`) et prépare le terrain pour la sortie structurée
(`with_structured_output`). Tous les agents exposent un `BaseChatModel` LangChain
brut ; `construire_modele_pour_agent` (par agent) et `construire_modele` (générique,
sans identité d'agent) sont les seuls points d'entrée.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from generation.agents.base import ErreurReponseAgentInvalide, extraire_texte_brut

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import BaseMessage
    from pydantic import BaseModel

_TENTATIVES_MAX = 5
_TENTATIVES_MAX_SORTIE_STRUCTUREE = 3
_DELAI_BASE_SECONDES = 2.0
_DELAI_MAX_SECONDES = 30.0

# Absent de la version pré-LangChain de ce module : sans timeout, une
# connexion qui ne répond jamais bloque indéfiniment (vécu en pratique — un
# job de génération resté bloqué plus de 9 minutes sur le tout premier appel
# LLM, aucune tentative de retry jamais atteinte puisque `_avec_retry` ne
# réagit qu'à une exception, pas à un silence). Surchargeable par agent, même
# convention que `PRISME_LLM_MODEL_<AGENT>`.
_TIMEOUT_DEFAUT_SECONDES = 120.0


def _est_erreur_transitoire(erreur: Exception) -> bool:
    """5xx (surcharge/panne côté fournisseur), 429 (quota/débit dépassé, lui
    aussi transitoire par nature — le sur-débit retombe avec le temps), ou
    timeout/coupure réseau. Jamais les autres 4xx (clé invalide, prompt
    rejeté...) qui échoueraient de façon identique à chaque nouvelle
    tentative, retenter ne ferait que perdre du temps."""
    code_statut = getattr(erreur, "status_code", None)
    if isinstance(code_statut, int):
        return code_statut >= 500 or code_statut == 429
    nom_type = type(erreur).__name__
    return "Timeout" in nom_type or "Connection" in nom_type


def _avec_retry(appel: Callable) -> Callable:
    """Réessaie un appel en cas d'erreur transitoire côté fournisseur (ex. 504
    Gateway Timeout) avec backoff exponentiel, pour qu'un blip réseau ne fasse
    pas échouer toute une tentative de génération (§5.6).

    Générique sur la signature de `appel` : sert aussi bien à envelopper
    `modele.invoke(messages)` en sortie brute qu'un appel `.invoke(messages)`
    sur un `Runnable` de sortie structurée — le prédicat de retry
    (`_est_erreur_transitoire`) ne dépend que de l'exception levée, jamais
    de la forme de `appel`.
    """

    def appel_avec_retry(*args, **kwargs):
        for tentative in range(_TENTATIVES_MAX):
            try:
                return appel(*args, **kwargs)
            except Exception as erreur:
                derniere_est_transitoire = _est_erreur_transitoire(erreur)
                if not derniere_est_transitoire or tentative == _TENTATIVES_MAX - 1:
                    raise
                time.sleep(min(_DELAI_BASE_SECONDES * (2**tentative), _DELAI_MAX_SECONDES))
        raise AssertionError("inatteignable")  # la boucle retourne ou lève à chaque itération

    return appel_avec_retry


def invoquer_agent_structure(
    modele: BaseChatModel,
    schema: type[BaseModel],
    messages: list[BaseMessage],
    *,
    tentatives_max: int = _TENTATIVES_MAX_SORTIE_STRUCTUREE,
) -> tuple[BaseModel, str]:
    """Invoque `modele` en sortie structurée (`with_structured_output`) et valide la réponse
    contre `schema`, avec jusqu'à `tentatives_max` appels LLM indépendants si le modèle renvoie
    un JSON syntaxiquement valide mais non conforme au schéma (vu en pratique sur l'agent
    Architecte : `fonctions_internes` structuré comme un objet imbriqué au lieu de la chaîne de
    texte attendue, avec `finish_reason="stop"` — pas une troncature, le modèle produit juste
    autre chose que demandé).

    Distinct de `_avec_retry`, appliqué ici à chaque tentative : celui-ci retente le *même* appel
    réseau sur une erreur transitoire (5xx/429/timeout) sans jamais avoir reçu de réponse ;
    celui-ci retente un *nouvel* appel LLM complet quand une réponse a bien été reçue mais ne
    respecte pas le schéma — `include_raw=True` fait que LangChain ne lève jamais dans ce cas,
    l'erreur revient dans `sortie["parsing_error"]`, jamais retentée par ailleurs.

    Lève `ErreurReponseAgentInvalide` seulement si `tentatives_max` tentatives échouent toutes —
    laisser la tentative de génération échouer à ce stade reste le comportement voulu du pipeline
    (voir `generation/graph.py`, chaque nœud sauf Documentation) : un agent qui ne produit jamais
    de sortie conforme après plusieurs essais indépendants est un vrai problème (fournisseur
    cassé, prompt qui a dérivé), pas un aléa à absorber silencieusement.

    Renvoie `(donnees_validees, reponse_brute_de_la_derniere_tentative)`."""
    structure = modele.with_structured_output(schema, include_raw=True, method=methode_sortie_structuree(modele))
    derniere_erreur: Exception | None = None
    reponse_brute = ""
    for _ in range(tentatives_max):
        sortie = _avec_retry(structure.invoke)(messages)
        reponse_brute = extraire_texte_brut(sortie["raw"])
        if sortie["parsing_error"] is None:
            return sortie["parsed"], reponse_brute
        derniere_erreur = sortie["parsing_error"]
    raise ErreurReponseAgentInvalide(
        f"réponse non conforme au schéma reçue de l'agent après {tentatives_max} tentative(s) : "
        f"{reponse_brute[:200]!r}"
    ) from derniere_erreur


def invoquer_agent_avec_outils(
    modele: BaseChatModel,
    schema: type[BaseModel],
    outils: list,
    messages: list[BaseMessage],
    *,
    max_appels_outils: int = 3,
    tentatives_max: int = _TENTATIVES_MAX_SORTIE_STRUCTUREE,
) -> tuple[BaseModel, str, list[str]]:
    """Variante d'`invoquer_agent_structure` qui laisse le modèle appeler des
    outils Python (`langchain_core.tools`, décorés `@tool`) avant de produire
    sa réponse structurée finale — premier mécanisme de ce type dans le
    projet, jusqu'ici tous les agents étaient de purs appels sans outil (voir
    `generation/agents/analyste.py`/`benchmarker.py` pour les deux premiers
    outils réels).

    Deux phases distinctes, jamais combinées en un seul appel : la boucle
    d'outils tourne sur `modele.bind_tools(outils)` en sortie libre (le
    tool-calling natif et la sortie structurée stricte ne sont pas garantis
    compatibles selon le fournisseur) ; une fois la boucle terminée (plus
    d'appel d'outil demandé, ou `max_appels_outils` atteint), un dernier
    appel classique via `invoquer_agent_structure` extrait la réponse finale
    conforme au schéma, à partir de la conversation enrichie des résultats
    d'outils déjà obtenus.

    `outils` vide : équivalent strict à `invoquer_agent_structure` (aucune
    étape supplémentaire), pour que les agents existants n'aient rien à
    changer tant qu'aucun outil ne leur est fourni.

    Renvoie `(donnees_validees, reponse_brute_finale, appels_effectues)` —
    `appels_effectues` (ex. `["rechercher_instances_similaires({})"]`) sert
    de trace, jamais relue par le pipeline, utile pour le diagnostic humain."""
    if not outils:
        donnees, reponse_brute = invoquer_agent_structure(modele, schema, messages, tentatives_max=tentatives_max)
        return donnees, reponse_brute, []

    from langchain_core.messages import HumanMessage, ToolMessage

    outils_par_nom = {outil.name: outil for outil in outils}
    modele_avec_outils = modele.bind_tools(outils)
    conversation = list(messages)
    appels_effectues: list[str] = []

    for _ in range(max_appels_outils):
        reponse = _avec_retry(modele_avec_outils.invoke)(conversation)
        conversation.append(reponse)
        if not reponse.tool_calls:
            break
        for appel in reponse.tool_calls:
            outil = outils_par_nom.get(appel["name"])
            resultat = outil.invoke(appel["args"]) if outil is not None else f"outil inconnu : {appel['name']!r}"
            appels_effectues.append(f"{appel['name']}({appel['args']})")
            conversation.append(ToolMessage(content=str(resultat), tool_call_id=appel["id"]))
    else:
        conversation.append(
            HumanMessage(
                content="Nombre maximal d'appels d'outils atteint — réponds maintenant "
                "directement avec le JSON demandé, sans outil supplémentaire."
            )
        )

    donnees, reponse_brute = invoquer_agent_structure(modele, schema, conversation, tentatives_max=tentatives_max)
    return donnees, reponse_brute, appels_effectues


_MODELE_KIMI_PAR_DEFAUT = "kimi-k2.6"
_KIMI_API_BASE_URL_PAR_DEFAUT = "https://api.moonshot.ai/v1"


def _timeout_pour_agent(nom_agent: str | None) -> float:
    if nom_agent:
        valeur = os.environ.get(f"PRISME_LLM_TIMEOUT_SECONDES_{nom_agent.upper()}")
        if valeur:
            return float(valeur)
    return float(os.environ.get("PRISME_LLM_TIMEOUT_SECONDES") or _TIMEOUT_DEFAUT_SECONDES)


def _construire_modele_kimi(modele: str, timeout: float) -> BaseChatModel:
    """Kimi (Moonshot AI) est compatible OpenAI — `ChatOpenAI` avec un `base_url` personnalisé
    est le patron officiellement recommandé par LangChain pour tout fournisseur compatible,
    plutôt qu'un package tiers dédié (`langchain-moonshot`, communautaire, pas un partner
    package LangChain officiel à ce jour) — même logique que le retrait des autres fournisseurs
    (qwen/together/nvidia/minimax/deepseek) : une seule dépendance fiable plutôt que plusieurs."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=modele,
        api_key=os.environ.get("KIMI_API_KEY"),
        base_url=os.environ.get("KIMI_API_BASE_URL") or _KIMI_API_BASE_URL_PAR_DEFAUT,
        timeout=timeout,
    )


def methode_sortie_structuree(modele: BaseChatModel) -> str:
    """`method=` à passer à `modele.with_structured_output(schema, method=...)`.

    `"json_mode"` plutôt que le défaut LangChain (`method="function_calling"`, tool-calling
    natif) ou le mode schéma strict (`"json_schema"`) : mode JSON basique, le plus largement
    supporté chez les fournisseurs compatibles OpenAI — choisi par prudence, pas encore
    revalidé par un appel réel contre Kimi (contrairement au choix précédent pour Mistral, qui
    l'avait été — voir l'historique de ce fichier)."""
    return "json_mode"


def construire_modele() -> BaseChatModel:
    """Construit le `BaseChatModel` générique, d'après `PRISME_LLM_MODEL` — sans identité
    d'agent, pour les chemins qui n'en ont pas (Étape 4 historique, scripts de connectivité).
    Voir `construire_modele_pour_agent` pour le routage par agent."""
    # `.get(..., defaut)` ne renvoie le défaut que si la variable est absente — or `.env` la
    # déclare toujours, vide par défaut (`PRISME_LLM_MODEL=`), ce qui donnerait `modele = ""`
    # sans le `or` : le fournisseur rejette alors l'appel avec une erreur "modèle manquant"
    # plutôt que d'utiliser son propre défaut, l'erreur n'a rien d'évident depuis l'appelant.
    modele_nom = os.environ.get("PRISME_LLM_MODEL") or _MODELE_KIMI_PAR_DEFAUT
    return _construire_modele_kimi(modele_nom, _timeout_pour_agent(None))


def construire_modele_pour_agent(nom_agent: str) -> BaseChatModel:
    """Construit le `BaseChatModel` LangChain (Kimi) pour un agent spécifique. Le retry
    (`_avec_retry` pour les erreurs réseau transitoires, `invoquer_agent_structure` pour une
    sortie structurée non conforme) reste à la charge de l'appelant, qui l'applique au point
    d'appel réel (`.invoke(...)` sur le `Runnable` structuré ou brut), puisque le modèle
    renvoyé ici n'est pas encore l'objet invoqué.

    Permet une surcharge par variable d'environnement `PRISME_LLM_MODEL_<AGENT>` /
    `PRISME_LLM_TIMEOUT_SECONDES_<AGENT>` — jamais de choix de fournisseur, il n'y en a qu'un.
    """
    var_modele = f"PRISME_LLM_MODEL_{nom_agent.upper()}"
    modele_nom = os.environ.get(var_modele) or _MODELE_KIMI_PAR_DEFAUT
    return _construire_modele_kimi(modele_nom, _timeout_pour_agent(nom_agent))


def construire_modele_comprehension() -> BaseChatModel:
    """Dépendance FastAPI zero-arg (`Depends(...)`) pour l'agent de
    compréhension ERP (`adapters/agent_comprehension/`, §5.4 bis) — routé
    comme n'importe quel agent du pipeline via `construire_modele_pour_agent`
    (clé `"comprehension"`), pas un client LLM à part."""
    return construire_modele_pour_agent("comprehension")


def construire_modele_supervision() -> BaseChatModel:
    """Dépendance FastAPI zero-arg (`Depends(...)`) pour l'agent de
    supervision (`supervision/agent.py`, §2, MT7) — même raison d'être que
    `construire_modele_comprehension` : `Depends()` n'accepte pas
    `construire_modele_pour_agent` directement (paramètre `nom_agent` requis)."""
    return construire_modele_pour_agent("supervision")
