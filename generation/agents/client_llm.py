"""Client LLM générique pour les agents du pipeline (§5.6).

**Fournisseur : Kimi en direct**, dès que `KIMI_API_KEY` est renseignée — l'API Kimi est
compatible OpenAI (`_construire_modele_kimi`), modèle par défaut `kimi-k2.6`, clés créées
depuis la console Kimi (`platform.kimi.ai`).
**OpenRouter** (`OPENROUTER_API_KEY`) reste le repli quand aucune clé Kimi n'est configurée.
`PRISME_LLM_FOURNISSEUR` (`kimi` / `openrouter`) force l'un ou l'autre ; absente, la présence de
la clé Kimi tranche (`fournisseur_llm`). Aucune clé n'est jamais lue ailleurs, manipulée ni
journalisée ici : elle est passée telle quelle à `ChatOpenAI`.

`PRISME_LLM_MODEL` et les surcharges par agent (`PRISME_LLM_MODEL_<AGENT>`/
`PRISME_LLM_TIMEOUT_SECONDES_<AGENT>`) valent pour les deux fournisseurs. Un nom de modèle au
format du catalogue OpenRouter (`moonshotai/kimi-k2.6`, nommage imposé par ce catalogue) est
accepté tel quel en mode Kimi : le préfixe d'éditeur est retiré (`_nom_modele_kimi`), ce qui
laisse `kimi-k2.6`, le seul nommage utilisé côté Kimi. Les autres fournisseurs historiques
(qwen/together/nvidia/minimax/deepseek/nemotron, Mistral) restent retirés.

Construit sur LangChain (`langchain-core`/`langchain-openai`, `extra` optionnel
`llm` du projet) plutôt que sur le SDK brut : donne un timeout HTTP réel par appel
(absent de la version précédente — un blip réseau pouvait bloquer indéfiniment, voir
`_TIMEOUT_DEFAUT_SECONDES`) et prépare le terrain pour la sortie structurée
(`with_structured_output`). Tous les agents exposent un `BaseChatModel` LangChain
brut ; `construire_modele_pour_agent` (par agent) et `construire_modele` (générique,
sans identité d'agent) sont les seuls points d'entrée.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
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


# Un sémaphore par valeur de `PRISME_LLM_CONCURRENCE_MAX` — recréé si la valeur change, ce qui
# permet aux tests de faire varier la limite sans état résiduel d'un test à l'autre.
_VERROU_LIMITEURS = threading.Lock()
_LIMITEURS: dict[int, threading.BoundedSemaphore] = {}


def _limiteur_concurrence() -> threading.BoundedSemaphore | None:
    """Borne le nombre d'appels LLM simultanés de tout le processus, d'après
    `PRISME_LLM_CONCURRENCE_MAX` — absente ou 0 : aucune limite (comportement historique).

    Nécessaire quand le compte du fournisseur plafonne la concurrence (vu en pratique : compte
    Kimi limité à **une** requête simultanée, erreur 429 « max organization concurrency: 1 »).
    Le graphe de génération lance l'Analyste et le Benchmarker en parallèle : l'un occupe
    l'unique place pendant toute sa réponse (souvent plus d'une minute), l'autre reçoit un 429,
    et ses cinq tentatives de `_avec_retry` (environ 30 s d'attente cumulée) s'épuisent avant que
    la place se libère — toute la génération échoue. Faire attendre l'appel en file ici, avant
    même de l'envoyer, supprime le 429 au lieu de compter sur des tentatives. Lu à chaque appel
    (pas à l'import) : `.env` peut être chargé après l'import de ce module.

    Une valeur non entière lève une erreur explicite plutôt que de désactiver la limite en
    silence — une faute de frappe reproduirait sinon le 429 sans explication visible."""
    valeur = (os.environ.get("PRISME_LLM_CONCURRENCE_MAX") or "").strip()
    if not valeur:
        return None
    try:
        maximum = int(valeur)
    except ValueError:
        raise ValueError(f"PRISME_LLM_CONCURRENCE_MAX doit être un entier, reçu : {valeur!r}") from None
    if maximum <= 0:
        return None
    with _VERROU_LIMITEURS:
        if maximum not in _LIMITEURS:
            _LIMITEURS[maximum] = threading.BoundedSemaphore(maximum)
        return _LIMITEURS[maximum]


@dataclass(frozen=True)
class MesureAppelLLM:
    """Ce qu'a coûté un appel logique au modèle — tentatives et attentes comprises — pour qu'un
    humain puisse voir **pourquoi** une génération est lente, sans aller fouiller LangSmith.

    Les trois causes de latence réellement observées sur ce projet y sont chacune visibles :
    la réflexion du modèle (`tokens_reflexion`, jusqu'à 92 % de la sortie sur `kimi-k2.6`),
    l'attente d'une place quand le compte est limité à une requête simultanée
    (`attente_file_s`), et les refus du fournisseur rattrapés par de nouvelles tentatives
    (`refus_429`, `tentatives`). `reponse_conforme` vaut `None` hors sortie structurée, `False`
    quand le modèle a répondu mais pas au format demandé (l'agent relancera un appel)."""

    reussi: bool
    duree_s: float
    attente_file_s: float
    tentatives: int
    refus_429: int
    modele: str | None = None
    tokens_entree: int | None = None
    tokens_sortie: int | None = None
    tokens_reflexion: int | None = None
    reponse_conforme: bool | None = None
    erreur: str | None = None
    # Réponse coupée : le modèle a atteint sa limite de tokens de sortie avant d'avoir fini — vu en
    # pratique sur le Développeur avec réflexion (31 099 tokens de réflexion sur 32 768 permis).
    limite_sortie_atteinte: bool = False

    def cause_dominante(self) -> str | None:
        """Ce qui explique surtout la durée de cet appel : `"refus"` (le fournisseur a refusé,
        l'appel a échoué), `"attente"` (plus de la moitié du temps passée à attendre une place),
        `"reflexion"` (plus de la moitié de la sortie consacrée à la réflexion, sur un appel
        d'au moins 30 s), `"refus"` encore si des refus ont été rattrapés, sinon `None` — un
        appel court ou sans cause marquante n'a rien à expliquer. `"longueur"` passe avant tout le
        reste : une réponse coupée est un échec, quelle que soit la durée de l'appel."""
        if self.limite_sortie_atteinte:
            return "longueur"
        if self.refus_429 and not self.reussi:
            return "refus"
        if self.attente_file_s >= 5 and self.attente_file_s >= 0.5 * self.duree_s:
            return "attente"
        if (
            self.duree_s >= 30
            and self.tokens_reflexion
            and self.tokens_sortie
            and self.tokens_reflexion >= 0.5 * self.tokens_sortie
        ):
            return "reflexion"
        if self.refus_429:
            return "refus"
        return None

    def en_dict(self) -> dict[str, object]:
        return asdict(self) | {"cause": self.cause_dominante()}


# Un seul observateur pour tout le processus — posé par `generation/graph.py`, qui fait remonter
# chaque mesure dans le flux de la génération en cours. Il retrouve lui-même le contexte de
# l'appel (quel job, quel agent) : ce module ne connaît ni les jobs ni LangGraph.
_observateur_appels: Callable[[MesureAppelLLM], None] | None = None


def definir_observateur_appels(observateur: Callable[[MesureAppelLLM], None] | None) -> None:
    """Pose (ou retire, avec `None`) la fonction appelée après chaque appel au modèle."""
    global _observateur_appels
    _observateur_appels = observateur


def _message_de_reponse(reponse: object) -> object:
    """`with_structured_output(..., include_raw=True)` renvoie `{"raw": AIMessage, ...}` ; un
    appel brut renvoie directement l'`AIMessage` — l'usage de tokens vit sur ce dernier."""
    return reponse.get("raw") if isinstance(reponse, dict) else reponse


def _mesure_depuis_reponse(reponse: object) -> dict[str, object]:
    message = _message_de_reponse(reponse)
    usage = getattr(message, "usage_metadata", None) or {}
    metadonnees = getattr(message, "response_metadata", None) or {}
    details_sortie = usage.get("output_token_details") or {}
    conforme = None
    if isinstance(reponse, dict) and "parsing_error" in reponse:
        conforme = reponse["parsing_error"] is None
    return {
        "modele": metadonnees.get("model_name"),
        "tokens_entree": usage.get("input_tokens"),
        "tokens_sortie": usage.get("output_tokens"),
        "tokens_reflexion": details_sortie.get("reasoning"),
        "reponse_conforme": conforme,
    }


def _est_limite_de_sortie(erreur: BaseException | None) -> bool:
    """`openai.LengthFinishReasonError` : la réponse a été coupée à la limite de tokens de sortie.
    Reconnue par son nom plutôt qu'importée — ce module n'importe jamais le SDK au chargement."""
    return erreur is not None and type(erreur).__name__ == "LengthFinishReasonError"


def _mesure_depuis_erreur(erreur: BaseException | None) -> dict[str, object]:
    """Une réponse coupée porte quand même son usage (`erreur.completion.usage`) : c'est lui qui
    montre que la réflexion a mangé le budget de sortie — l'information clé pour comprendre."""
    if not _est_limite_de_sortie(erreur):
        return {}
    completion = getattr(erreur, "completion", None)
    usage = getattr(completion, "usage", None)
    details = getattr(usage, "completion_tokens_details", None)
    return {
        "limite_sortie_atteinte": True,
        "modele": getattr(completion, "model", None),
        "tokens_entree": getattr(usage, "prompt_tokens", None),
        "tokens_sortie": getattr(usage, "completion_tokens", None),
        "tokens_reflexion": getattr(details, "reasoning_tokens", None),
    }


def _notifier_observateur(mesure: MesureAppelLLM) -> None:
    """Une mesure ne doit jamais faire échouer l'appel qu'elle décrit."""
    observateur = _observateur_appels
    if observateur is None:
        return
    try:
        observateur(mesure)
    except Exception:  # noqa: BLE001 — observation pure, jamais bloquante
        logging.getLogger(__name__).warning("observateur des appels LLM en échec", exc_info=True)


def _avec_retry(appel: Callable) -> Callable:
    """Réessaie un appel en cas d'erreur transitoire côté fournisseur (ex. 504
    Gateway Timeout) avec backoff exponentiel, pour qu'un blip réseau ne fasse
    pas échouer toute une tentative de génération (§5.6).

    Générique sur la signature de `appel` : sert aussi bien à envelopper
    `modele.invoke(messages)` en sortie brute qu'un appel `.invoke(messages)`
    sur un `Runnable` de sortie structurée — le prédicat de retry
    (`_est_erreur_transitoire`) ne dépend que de l'exception levée, jamais
    de la forme de `appel`.

    Chaque tentative prend une place du limiteur de concurrence (`_limiteur_concurrence`) et
    la rend avant l'attente de backoff : un appel qui patiente entre deux tentatives ne bloque
    jamais les autres.

    Chaque appel logique produit une `MesureAppelLLM` (réussi ou non), transmise à
    l'observateur s'il y en a un — c'est le seul point par où passent tous les appels au
    modèle du projet, donc le seul endroit où la mesure est complète.
    """

    def appel_avec_retry(*args, **kwargs):
        limiteur = _limiteur_concurrence()
        debut = time.monotonic()
        attente_file_s = 0.0
        tentatives = 0
        refus_429 = 0
        reponse: object = None
        erreur_finale: BaseException | None = None
        try:
            for tentative in range(_TENTATIVES_MAX):
                tentatives += 1
                try:
                    if limiteur is None:
                        reponse = appel(*args, **kwargs)
                        return reponse
                    debut_attente = time.monotonic()
                    with limiteur:
                        attente_file_s += time.monotonic() - debut_attente
                        reponse = appel(*args, **kwargs)
                        return reponse
                except Exception as erreur:
                    if getattr(erreur, "status_code", None) == 429:
                        refus_429 += 1
                    derniere_est_transitoire = _est_erreur_transitoire(erreur)
                    if not derniere_est_transitoire or tentative == _TENTATIVES_MAX - 1:
                        erreur_finale = erreur
                        raise
                    time.sleep(min(_DELAI_BASE_SECONDES * (2**tentative), _DELAI_MAX_SECONDES))
            raise AssertionError("inatteignable")  # la boucle retourne ou lève à chaque itération
        finally:
            reussi = erreur_finale is None and reponse is not None
            _notifier_observateur(
                MesureAppelLLM(
                    reussi=reussi,
                    duree_s=time.monotonic() - debut,
                    attente_file_s=attente_file_s,
                    tentatives=tentatives,
                    refus_429=refus_429,
                    erreur=None
                    if erreur_finale is None
                    else f"{type(erreur_finale).__name__}: {erreur_finale}"[:300],
                    **(_mesure_depuis_reponse(reponse) if reussi else _mesure_depuis_erreur(erreur_finale)),
                )
            )

    return appel_avec_retry


def _message_limite_de_sortie(erreur: BaseException) -> str:
    """Message affiché à l'humain à la place du message brut du SDK, qui ne dit pas quoi faire.
    Pas de nouvelle tentative : le même prompt avec les mêmes réglages recoupe au même endroit."""
    mesure = _mesure_depuis_erreur(erreur)
    sortie, reflexion = mesure.get("tokens_sortie"), mesure.get("tokens_reflexion")
    detail = ""
    if isinstance(sortie, int):
        detail = f" de {sortie} tokens"
        if isinstance(reflexion, int) and reflexion:
            detail += f", dont {reflexion} de réflexion ({round(100 * reflexion / sortie)} %)"
    return (
        f"réponse coupée : le modèle a atteint sa limite de sortie{detail} avant d'avoir terminé sa "
        "réponse. Si la réflexion occupe l'essentiel de ce budget, coupez-la pour cet agent "
        "(PRISME_LLM_REFLEXION_<AGENT>=desactivee) ; sinon, réduisez la taille du prompt."
    )


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
        try:
            sortie = _avec_retry(structure.invoke)(messages)
        except Exception as erreur:
            if _est_limite_de_sortie(erreur):
                raise ErreurReponseAgentInvalide(_message_limite_de_sortie(erreur)) from erreur
            raise
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
            # Certains fournisseurs compatibles OpenAI exigent que le dernier message envoyé
            # ait role=user — sans ce message de relance, la conversation se terminerait sur
            # cet AIMessage juste ajouté, rejetée par ces fournisseurs avant même d'atteindre
            # `invoquer_agent_structure` (vu en pratique, erreur 400 "last message must have
            # role=user"). Même message que le cas `max_appels_outils` atteint ci-dessous.
            conversation.append(
                HumanMessage(
                    content="Réponds maintenant directement avec le JSON demandé, sans outil supplémentaire."
                )
            )
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


_MODELE_PAR_DEFAUT = "moonshotai/kimi-k2.6"
_OPENROUTER_API_BASE_URL_PAR_DEFAUT = "https://openrouter.ai/api/v1"
# Hôte d'API de la plateforme Kimi internationale — vérifié comme étant celui qui répond
# (`api.kimi.ai` existe mais ne sert aucune API sur `/v1`). Les clés de la plateforme chinoise
# (`api.moonshot.cn`) sont distinctes et refusées ici (« Invalid Authentication ») : dans ce cas,
# surcharger `KIMI_API_BASE_URL`.
_KIMI_API_BASE_URL_PAR_DEFAUT = "https://api.moonshot.ai/v1"
# Préfixe d'éditeur du catalogue OpenRouter, retiré pour l'appel direct — voir `_nom_modele_kimi`.
_PREFIXE_MODELE_KIMI_OPENROUTER = "moonshotai/"


def fournisseur_llm() -> str:
    """`"kimi"` ou `"openrouter"`. `PRISME_LLM_FOURNISSEUR` force le choix ; absente (ou
    inconnue), Kimi en direct dès que `KIMI_API_KEY` est renseignée, OpenRouter sinon."""
    choix = (os.environ.get("PRISME_LLM_FOURNISSEUR") or "").strip().lower()
    if choix in ("kimi", "openrouter"):
        return choix
    return "kimi" if os.environ.get("KIMI_API_KEY") else "openrouter"


def _nom_modele_kimi(modele: str) -> str:
    """`moonshotai/kimi-k2.6` (nommage du catalogue OpenRouter) → `kimi-k2.6` (nommage de l'API
    Kimi) : un même `PRISME_LLM_MODEL` sert les deux fournisseurs."""
    if modele.startswith(_PREFIXE_MODELE_KIMI_OPENROUTER):
        return modele[len(_PREFIXE_MODELE_KIMI_OPENROUTER) :]
    return modele


def _timeout_pour_agent(nom_agent: str | None) -> float:
    if nom_agent:
        valeur = os.environ.get(f"PRISME_LLM_TIMEOUT_SECONDES_{nom_agent.upper()}")
        if valeur:
            return float(valeur)
    return float(os.environ.get("PRISME_LLM_TIMEOUT_SECONDES") or _TIMEOUT_DEFAUT_SECONDES)


_VALEURS_REFLEXION_DESACTIVEE = frozenset({"desactivee", "désactivée", "non", "off", "0", "false"})
_VALEURS_REFLEXION_ACTIVEE = frozenset({"activee", "activée", "oui", "on", "1", "true"})


def _reflexion_desactivee(nom_agent: str | None) -> bool:
    """Faut-il couper la phase de réflexion du modèle Kimi pour cet agent ?
    `PRISME_LLM_REFLEXION_<AGENT>` l'emporte sur `PRISME_LLM_REFLEXION` ; les deux absentes (ou
    vides) : réflexion laissée active, le comportement par défaut du modèle.

    Mesuré sur les traces LangSmith de l'agent de compréhension (`cellule_usinage_export`,
    `kimi-k2.6`) : avec la réflexion, 85 à 92 % des tokens de sortie sont de la réflexion, et un
    appel dure 5 à 16 minutes — assez pour monopoliser la seule place d'un compte limité à une
    requête simultanée. Sans réflexion : 1 630 tokens de sortie au lieu de 12 000 à 19 000, en
    39 secondes. À réserver aux agents dont la tâche n'en tire pas profit (extraction vers un
    format imposé, rédaction) ; les agents qui écrivent du code peuvent la garder.

    Une valeur inconnue lève une erreur explicite plutôt que d'être ignorée en silence."""
    valeur = ""
    if nom_agent:
        valeur = os.environ.get(f"PRISME_LLM_REFLEXION_{nom_agent.upper()}") or ""
    valeur = (valeur or os.environ.get("PRISME_LLM_REFLEXION") or "").strip().lower()
    if not valeur or valeur in _VALEURS_REFLEXION_ACTIVEE:
        return False
    if valeur in _VALEURS_REFLEXION_DESACTIVEE:
        return True
    raise ValueError(f"PRISME_LLM_REFLEXION doit valoir « activee » ou « desactivee », reçu : {valeur!r}")


def _construire_modele_openrouter(modele: str, timeout: float) -> BaseChatModel:
    """OpenRouter est compatible OpenAI — `ChatOpenAI` avec un `base_url` personnalisé
    est le patron officiellement recommandé par LangChain pour tout fournisseur compatible,
    plutôt qu'un package tiers dédié (`langchain-openrouter`, communautaire, pas un partner
    package LangChain officiel à ce jour) — même logique que le retrait des autres fournisseurs
    (qwen/together/nvidia/minimax/deepseek) : une seule dépendance fiable plutôt que plusieurs."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=modele,
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        base_url=os.environ.get("OPENROUTER_API_BASE_URL") or _OPENROUTER_API_BASE_URL_PAR_DEFAUT,
        timeout=timeout,
    )


def _construire_modele_kimi(modele: str, timeout: float, *, reflexion_desactivee: bool = False) -> BaseChatModel:
    """Kimi en direct — API compatible OpenAI, même patron `ChatOpenAI` + `base_url` qu'OpenRouter,
    sans intermédiaire (une passerelle de moins, donc une source de panne et de latence de
    moins).

    `reflexion_desactivee` : envoie `{"thinking": {"type": "disabled"}}` dans le corps de la
    requête, le paramètre de l'API Kimi qui coupe la phase de réflexion — voir
    `_reflexion_desactivee` pour la mesure qui justifie ce réglage."""
    from langchain_openai import ChatOpenAI

    options = {"extra_body": {"thinking": {"type": "disabled"}}} if reflexion_desactivee else {}
    return ChatOpenAI(
        model=_nom_modele_kimi(modele),
        api_key=os.environ.get("KIMI_API_KEY"),
        base_url=os.environ.get("KIMI_API_BASE_URL") or _KIMI_API_BASE_URL_PAR_DEFAUT,
        timeout=timeout,
        **options,
    )


def _construire_modele_fournisseur(
    modele: str, timeout: float, *, reflexion_desactivee: bool = False
) -> BaseChatModel:
    """`reflexion_desactivee` n'a d'effet qu'en mode Kimi : OpenRouter ne reconnaît pas ce
    paramètre sous ce nom, il n'y est donc jamais transmis."""
    if fournisseur_llm() == "kimi":
        return _construire_modele_kimi(modele, timeout, reflexion_desactivee=reflexion_desactivee)
    return _construire_modele_openrouter(modele, timeout)


def methode_sortie_structuree(modele: BaseChatModel) -> str:
    """`method=` à passer à `modele.with_structured_output(schema, method=...)`.

    `"json_mode"` plutôt que le défaut LangChain (`method="function_calling"`, tool-calling
    natif) ou le mode schéma strict (`"json_schema"`) : mode JSON basique, le plus largement
    supporté chez les fournisseurs compatibles OpenAI. **Validé par des appels réels contre
    l'API Kimi en direct** (`kimi-k2.6`, 2026-09-21) : sortie conforme au schéma dès la première
    tentative, y compris sur le schéma de l'agent Benchmarker et son champ `Literal`."""
    return "json_mode"


def construire_modele() -> BaseChatModel:
    """Construit le `BaseChatModel` générique, d'après `PRISME_LLM_MODEL` — sans identité
    d'agent, pour les chemins qui n'en ont pas (Étape 4 historique, scripts de connectivité).
    Voir `construire_modele_pour_agent` pour le routage par agent."""
    # `.get(..., defaut)` ne renvoie le défaut que si la variable est absente — or `.env` la
    # déclare toujours, vide par défaut (`PRISME_LLM_MODEL=`), ce qui donnerait `modele = ""`
    # sans le `or` : le fournisseur rejette alors l'appel avec une erreur "modèle manquant"
    # plutôt que d'utiliser son propre défaut, l'erreur n'a rien d'évident depuis l'appelant.
    modele_nom = os.environ.get("PRISME_LLM_MODEL") or _MODELE_PAR_DEFAUT
    return _construire_modele_fournisseur(
        modele_nom, _timeout_pour_agent(None), reflexion_desactivee=_reflexion_desactivee(None)
    )


def construire_modele_pour_agent(nom_agent: str) -> BaseChatModel:
    """Construit le `BaseChatModel` LangChain (Kimi ou OpenRouter, voir `fournisseur_llm`) pour
    un agent spécifique. Le retry
    (`_avec_retry` pour les erreurs réseau transitoires, `invoquer_agent_structure` pour une
    sortie structurée non conforme) reste à la charge de l'appelant, qui l'applique au point
    d'appel réel (`.invoke(...)` sur le `Runnable` structuré ou brut), puisque le modèle
    renvoyé ici n'est pas encore l'objet invoqué.

    Permet une surcharge par variable d'environnement `PRISME_LLM_MODEL_<AGENT>` /
    `PRISME_LLM_TIMEOUT_SECONDES_<AGENT>` / `PRISME_LLM_REFLEXION_<AGENT>` — le fournisseur, lui,
    est le même pour tous les agents.
    """
    var_modele = f"PRISME_LLM_MODEL_{nom_agent.upper()}"
    modele_nom = os.environ.get(var_modele) or os.environ.get("PRISME_LLM_MODEL") or _MODELE_PAR_DEFAUT
    return _construire_modele_fournisseur(
        modele_nom, _timeout_pour_agent(nom_agent), reflexion_desactivee=_reflexion_desactivee(nom_agent)
    )


def construire_modele_comprehension() -> BaseChatModel:
    """Dépendance FastAPI zero-arg (`Depends(...)`) pour l'agent de
    compréhension ERP (`adapters/agent_comprehension/`, §5.4 bis) — routé
    comme n'importe quel agent du pipeline via `construire_modele_pour_agent`
    (clé `"comprehension"`), pas un client LLM à part."""
    return construire_modele_pour_agent("comprehension")


def construire_modele_comprehension_optionnel() -> BaseChatModel | None:
    """Variante de `construire_modele_comprehension` ci-dessus pour un usage **best-effort**
    (ex. description métier automatique sur un import CSV/JSON déterministe,
    `api/routes/adapters.py::_description_metier_optionnelle`) — un chemin qui doit rester
    utilisable sans `.[llm]` installé, contrairement aux routes de compréhension elles-mêmes qui
    en dépendent entièrement. Ne fait *que* couvrir l'absence de la dépendance (`ImportError`,
    `langchain_openai` non installé) : une clé API absente/invalide construit quand même le
    client (`ChatOpenAI` ne valide rien à la construction) et échoue seulement au premier appel
    réel, à la charge de l'appelant."""
    try:
        return construire_modele_comprehension()
    except ImportError:
        return None


def construire_modele_supervision() -> BaseChatModel:
    """Dépendance FastAPI zero-arg (`Depends(...)`) pour l'agent de
    supervision (`supervision/agent.py`, §2, MT7) — même raison d'être que
    `construire_modele_comprehension` : `Depends()` n'accepte pas
    `construire_modele_pour_agent` directement (paramètre `nom_agent` requis)."""
    return construire_modele_pour_agent("supervision")
