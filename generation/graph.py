"""Pipeline multi-agents AVEC boucle de réparation (Étape 6), exprimé comme
un `StateGraph` LangGraph — seul pipeline de génération branché sur l'API
(`api/routes/generation.py`). Remplace l'ancien `pipeline_avec_boucle.py` +
`loop.py` (fonctions génératrices imbriquées) par un graphe d'états explicite
— les dataclasses `ResultatBoucleReparation`/`TentativeReparation` et le
helper `etape()`/`EvenementEtape`, auparavant dans `loop.py`, vivent ici.

Workflow complet :
1. Analyste (spécification) ‖ Benchmarker (choix de l'algorithme — toujours
   appelé, catalogue complet) — en parallèle, aucune dépendance de données
   entre les deux (l'Analyste ne lit que la mission statique, le Benchmarker
   que `instance_exemple`, déjà présent avant le premier nœud)
2. Architecte (conception, pour l'algorithme choisi) — point de jonction,
   attend les deux résultats ci-dessus
3. Développeur (code initial)
4. Testeur (tests pytest)
5. ** BOUCLE DE RÉPARATION (max 10 tentatives, `MAX_TENTATIVES_REPARATION`) **
   - Reviewer relit le code
   - Si rejeté : Debugger corrige avec les commentaires du Reviewer (la
     validation est sautée pour cette tentative), puis retour au Reviewer.
   - Si approuvé : Validation complète (statique → exécution → cascade,
     tolérance selon l'algorithme). Si elle échoue aussi, Debugger corrige
     avec le diagnostic de la validation, puis retour au Reviewer.
   - Si la validation réussit : Tests sandbox — exécute les tests de l'agent
     Testeur dans le bac à sable Docker (§6.6bis). S'ils échouent (ou si
     pytest n'a pas pu les collecter), Debugger corrige avec ce diagnostic,
     puis retour au Reviewer — traité comme n'importe quel autre échec de
     cascade. Seule l'**indisponibilité du sandbox lui-même** (Docker
     injoignable, image absente...) est meilleur-effort et ne bloque jamais
     — voir `sandbox/runner.py::executer_tests_dans_sandbox`,
     `_noeud_test_sandbox`.
   - Le nombre de tentatives est vérifié **avant** d'appeler le Debugger sur
     la toute dernière tentative — jamais de correction au-delà de la borne.
6. Documentation (meilleur-effort, après re-validation finale du code)

Pas d'Optimiseur : agent retiré du pipeline (réponse JSON trop fragile — il
embarque un code Python multi-lignes complet comme valeur de chaîne JSON, un
format que les LLM échouent régulièrement à échapper correctement — et
l'enjeu n'en valait pas la fragilité : le code est déjà validé par la
cascade à ce stade). `generation/agents/optimiseur.py` existe toujours mais
n'est plus appelé nulle part (orphelin).

Pas d'Orchestrateur non plus : il ne faisait jamais que produire un plan JSON
jamais lu par personne — l'ordre d'exécution a toujours été câblé en Python
ici (voir `_construire_graphe`), jamais décidé dynamiquement par sa réponse,
et son plan n'était même pas renvoyé par `api/routes/generation.py`.
`generation/agents/orchestrateur.py` a été supprimé (contrairement à
l'Optimiseur, laissé orphelin) — aucun code ne dépendait de sa sortie.

§6.6 : La boucle reste **bornée** (10 tentatives max), **offline** (génération),
et **diagnostique** (feedback précis de la validation).
"""

from __future__ import annotations

import operator
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from generation.agents import analyste, architecte, benchmarker, documentation, reviewer, testeur
from generation.agents.analyste import ResultatAnalyse
from generation.agents.architecte import ResultatConception
from generation.agents.client_llm import construire_modele_pour_agent
from generation.agents.debugger import corriger_code
from generation.agents.generateur import generer_code_depuis_plan
from generation.agents.reviewer import ResultatRevue
from generation.executer import ErreurExecutionGeneree, executer_code_genere
from generation.validation_statique import ResultatValidationStatique, valider_code_genere
from sandbox.runner import RapportTestsSandbox, executer_tests_dans_sandbox
from validation_engine.cascade import VerdictCascade, evaluer_cascade

# Constante : nombre max de tentatives de réparation. Un rejet du Reviewer
# consomme une tentative sans jamais toucher la validation cascade (fail-fast
# volontaire) — porté à 10 pour garantir en pratique plusieurs vraies
# tentatives de validation même si le Reviewer en "vole" une ou deux. La
# limite de récursion du graphe (§ `_obtenir_graphe_compile`) doit rester
# largement au-dessus de `5 + 3 * MAX_TENTATIVES_REPARATION` pour ne jamais
# couper la boucle avant qu'elle n'ait épuisé ses tentatives légitimes.
MAX_TENTATIVES_REPARATION = 10

EvenementEtape = dict[str, str]  # {"agent": ..., "statut": "en_cours"|"termine"|"echec", "resume": ...}


def etape(agent: str, statut: str, resume: str) -> EvenementEtape:
    return {"agent": agent, "statut": statut, "resume": resume}


@dataclass(frozen=True)
class ResultatPartiel:
    """Un champ de `jobs_generation` devenu disponible avant la fin du pipeline — l'appelant
    (`api/routes/generation.py::_executer_job`) le persiste immédiatement (§6.6), pour ne
    jamais perdre la sortie d'un agent si un agent suivant plante. `champ="tentative"` porte
    une `TentativeReparation` complète plutôt qu'une valeur scalaire (voir
    `_partiels_nouveaux`)."""

    champ: str
    valeur: object


@dataclass(frozen=True)
class TentativeReparation:
    """Une tentative de correction dans la boucle."""

    numero: int
    code_candidat: str
    revue: ResultatRevue
    validation_statique: ResultatValidationStatique | None
    erreur_execution: str | None
    verdict_cascade: VerdictCascade | None
    reussi: bool


@dataclass(frozen=True)
class ResultatBoucleReparation:
    """Résultat de la boucle de réparation."""

    code_initial: str
    tentatives: tuple[TentativeReparation, ...]
    code_final: str
    reussi: bool
    nombre_tentatives: int

    # Derniers résultats (pour reporting)
    derniere_revue: ResultatRevue
    derniere_validation_statique: ResultatValidationStatique | None
    derniere_erreur_execution: str | None
    dernier_verdict_cascade: VerdictCascade | None


@dataclass(frozen=True)
class ResultatPipelineAvecBoucle:
    """Résultat du pipeline multi-agents avec boucle de réparation.

    Contrat public consommé par `api/routes/generation.py` — champs stables
    depuis la version pré-LangGraph, ne pas renommer sans mettre à jour
    `_construire_reponse`/`_persister_tentatives`/`etat.terminer_job_generation`.
    """

    specification: str
    plan_technique: str

    # Choix d'algorithme — décidé par le Benchmarker avant la boucle de
    # réparation, donc toujours connu, y compris en cas d'échec.
    algorithme_recommande: str
    justification_algorithme: str
    parametres_algorithme: dict

    code_genere: str
    tests_generes: str

    boucle_reparation: ResultatBoucleReparation

    # Code final (après boucle)
    code_final: str
    validation_statique: ResultatValidationStatique | None
    erreur_execution: str | None
    verdict_cascade: VerdictCascade | None

    # Tests sandbox (§6.6bis) — `None` uniquement si le sandbox était
    # indisponible (jamais bloquant, voir `reussi` ci-dessous) ; un rapport
    # présent mais en échec (`.reussi` faux) fait déjà échouer `reussi` ici,
    # et a normalement épuisé la boucle de réparation avant d'arriver
    # jusqu'ici (voir `generation/graph.py::_route_apres_test_sandbox`).
    rapport_tests_sandbox: RapportTestsSandbox | None

    # Documentation
    documentation: str | None

    @property
    def reussi(self) -> bool:
        return (
            self.validation_statique is not None
            and self.validation_statique.valide
            and self.erreur_execution is None
            and self.verdict_cascade is not None
            and self.verdict_cascade.reussi
            and (self.rapport_tests_sandbox is None or self.rapport_tests_sandbox.reussi)
        )


def _valider_completement(
    code: str, tolerance_relative: float, comparer_affectation: bool
) -> tuple[ResultatValidationStatique, str | None, VerdictCascade | None]:
    """Valide le code en 3 passes : statique → exécution → cascade.

    Retourne (validation_statique, erreur_execution, verdict_cascade) —
    `erreur_execution` est `None` si l'exécution a réussi, `verdict_cascade`
    est `None` si on n'a pas pu l'atteindre (échec avant)."""
    validation = valider_code_genere(code)
    if not validation.valide:
        return validation, None, None

    try:
        solveur = executer_code_genere(code)
    except ErreurExecutionGeneree as erreur:
        return validation, str(erreur), None

    try:
        verdict = evaluer_cascade(solveur, tolerance_relative, comparer_affectation)
    except Exception as erreur:  # le code généré peut lever n'importe quoi
        return validation, str(erreur), None

    return validation, None, verdict


def _message_echec_validation(
    validation: ResultatValidationStatique, erreur_execution: str | None, verdict: VerdictCascade | None
) -> str:
    """Message de diagnostic pour le Debugger — trois branches, selon quelle
    passe a échoué (statique / exécution / cascade)."""
    if not validation.valide:
        return "Validation statique échouée : " + "; ".join(validation.violations)
    if erreur_execution is not None:
        return f"Erreur d'exécution : {erreur_execution}"
    if verdict is None:
        return "La validation cascade n'a pas pu être exécutée"
    details_echecs = "; ".join(f"[{d.brique_en_echec}] {d.nom} : {'; '.join(d.details)}" for d in verdict.echecs)
    return f"Validation cascade échouée : {details_echecs}"


def _message_echec_tests_sandbox(rapport: RapportTestsSandbox) -> str:
    """Message de diagnostic pour le Debugger quand les tests générés par
    l'agent Testeur échouent en sandbox — traité comme un signal de bug réel
    dans `resoudre()` (ces tests la ciblent directement, voir
    `generation/prompts/testeur.md`), au même titre qu'un échec de cascade."""
    if rapport.erreur is not None:
        return f"Les tests générés n'ont pas pu être collectés/exécutés en sandbox : {rapport.erreur}"
    details_echecs = "; ".join(f"{t.nom} : {t.message}" for t in rapport.tests if not t.reussi)
    return f"Tests générés en échec dans le sandbox : {details_echecs}"


class EtatGeneration(TypedDict, total=False):
    instance_exemple: dict | None

    analyse: ResultatAnalyse

    algo: str
    raison_algo: str
    parametres_algo: dict

    conception: ResultatConception

    code_genere: str
    tests_generes: str

    tolerance_relative: float
    comparer_affectation: bool

    # Boucle de réparation
    code_candidat: str
    numero_tentative: int
    tentatives: Annotated[list[TentativeReparation], operator.add]
    derniere_revue: ResultatRevue
    derniere_validation_statique: ResultatValidationStatique | None
    derniere_erreur_execution: str | None
    dernier_verdict_cascade: VerdictCascade | None
    message_pour_debugger: str | None
    boucle_reussie: bool

    rapport_tests_sandbox: RapportTestsSandbox | None

    resultat_final: ResultatPipelineAvecBoucle


def _modele(config: RunnableConfig, nom_agent: str):
    """Résout le `BaseChatModel` pour un agent — `construire_modele_pour_agent`
    par défaut, ou la fabrique injectée via
    `config["configurable"]["fabrique_modele"]` (tests : voir
    `tests/integration/test_graph_pipeline.py` — un faux modèle par agent,
    sans appel LLM réel, sans reconstruire le graphe)."""
    fabrique = (config.get("configurable") or {}).get("fabrique_modele", construire_modele_pour_agent)
    return fabrique(nom_agent)


# --- Nœuds du pipeline (avant la boucle) -----------------------------------


def _noeud_analyste(etat: EtatGeneration, config: RunnableConfig) -> dict:
    """Lit `instance_exemple` comme le Benchmarker (même fallback) — les deux
    nœuds partent en parallèle depuis `START` sans dépendance croisée l'un
    envers l'autre, cette clé est déjà présente dans `etat_initial` avant que
    l'un ou l'autre ne démarre. Seule la *structure* de l'instance (types de
    contraintes/objectifs, compteurs) atteint l'Analyste, jamais ses valeurs
    — voir `analyste.py::extraire_structure_instance`."""
    writer = get_stream_writer()
    writer(etape("analyste", "en_cours", "Analyse de la mission..."))
    instance = etat.get("instance_exemple") or benchmarker.creer_instance_exemple_defaut()
    resultat = analyste.analyser_mission(_modele(config, "analyste"), instance)
    writer(etape("analyste", "termine", "Spécification technique produite"))
    return {"analyse": resultat}


def _noeud_benchmarker(etat: EtatGeneration, config: RunnableConfig) -> dict:
    """Toujours appelé, jamais dans un try/except (comme tous les nœuds sauf
    Documentation) : le choix d'algorithme est structurant pour l'Architecte
    et le Développeur qui suivent, un échec ici doit interrompre la
    tentative comme n'importe quel autre agent du chemin principal."""
    writer = get_stream_writer()
    instance = etat.get("instance_exemple") or benchmarker.creer_instance_exemple_defaut()
    writer(etape("benchmarker", "en_cours", "Analyse de l'instance et sélection de l'algorithme..."))
    resultat = benchmarker.benchmarker_algorithmes(_modele(config, "benchmarker"), instance)
    algo = resultat.recommandation.algorithme
    writer(etape("benchmarker", "termine", f"Algorithme recommandé : {algo}"))
    return {
        "algo": algo,
        "raison_algo": resultat.recommandation.raison,
        "parametres_algo": resultat.recommandation.parametres_suggeres,
    }


def _noeud_architecte(etat: EtatGeneration, config: RunnableConfig) -> dict:
    writer = get_stream_writer()
    writer(etape("architecte", "en_cours", "Conception du modèle..."))
    conception = architecte.concevoir_modele(
        _modele(config, "architecte"), etat["analyse"], algorithme=etat["algo"], parametres=etat["parametres_algo"]
    )
    writer(etape("architecte", "termine", "Plan technique produit"))
    return {"conception": conception}


def _noeud_developpeur(etat: EtatGeneration, config: RunnableConfig) -> dict:
    writer = get_stream_writer()
    writer(etape("developpeur", "en_cours", "Rédaction du code du solveur..."))
    brut = generer_code_depuis_plan(
        _modele(config, "generateur"),
        etat["conception"].en_texte(),
        algorithme=etat["algo"],
        parametres=etat["parametres_algo"],
    )
    writer(etape("developpeur", "termine", f"{len(brut.code_source.splitlines())} ligne(s) de code générées"))
    tolerance_relative, comparer_affectation = benchmarker.parametres_cascade_pour_algorithme(etat["algo"])
    return {
        "code_genere": brut.code_source,
        "code_candidat": brut.code_source,
        "tolerance_relative": tolerance_relative,
        "comparer_affectation": comparer_affectation,
    }


def _noeud_testeur(etat: EtatGeneration, config: RunnableConfig) -> dict:
    writer = get_stream_writer()
    writer(etape("testeur", "en_cours", "Génération des tests..."))
    tests = testeur.generer_tests(_modele(config, "testeur"), etat["code_candidat"])
    writer(etape("testeur", "termine", "Tests générés"))
    return {"tests_generes": tests.code_tests, "numero_tentative": 1, "tentatives": []}


# --- Boucle de réparation ----------------------------------------------


def _noeud_reviewer(etat: EtatGeneration, config: RunnableConfig) -> dict:
    writer = get_stream_writer()
    n = etat["numero_tentative"]
    nom = f"reviewer (tentative {n}/{MAX_TENTATIVES_REPARATION})"
    writer(etape(nom, "en_cours", "Relecture critique du code..."))
    revue = reviewer.relire_code(_modele(config, "reviewer"), etat["code_candidat"])
    writer(
        etape(
            nom,
            "termine" if revue.approuve else "echec",
            "Code approuvé" if revue.approuve else f"{len(revue.problemes)} problème(s) relevé(s) par le reviewer",
        )
    )

    maj: dict = {"derniere_revue": revue}
    if not revue.approuve:
        maj["tentatives"] = [
            TentativeReparation(
                numero=n,
                code_candidat=etat["code_candidat"],
                revue=revue,
                validation_statique=None,
                erreur_execution=None,
                verdict_cascade=None,
                reussi=False,
            )
        ]
        maj["message_pour_debugger"] = revue.commentaires
    return maj


def _route_apres_reviewer(etat: EtatGeneration) -> Literal["validation", "debugger", "fin_boucle"]:
    if etat["derniere_revue"].approuve:
        return "validation"
    if etat["numero_tentative"] >= MAX_TENTATIVES_REPARATION:
        return "fin_boucle"
    return "debugger"


def _noeud_validation(etat: EtatGeneration, config: RunnableConfig) -> dict:
    writer = get_stream_writer()
    n = etat["numero_tentative"]
    nom = f"validation (tentative {n}/{MAX_TENTATIVES_REPARATION})"
    writer(etape(nom, "en_cours", "Validation statique → exécution → cascade complète..."))
    validation, erreur_exec, verdict = _valider_completement(
        etat["code_candidat"], etat["tolerance_relative"], etat["comparer_affectation"]
    )
    reussi = validation.valide and erreur_exec is None and verdict is not None and verdict.reussi
    writer(
        etape(
            nom,
            "termine" if reussi else "echec",
            "Cascade de validation au vert" if reussi else "Cascade de validation en échec",
        )
    )

    tentative = TentativeReparation(
        numero=n,
        code_candidat=etat["code_candidat"],
        revue=etat["derniere_revue"],
        validation_statique=validation,
        erreur_execution=erreur_exec,
        verdict_cascade=verdict,
        reussi=reussi,
    )
    maj: dict = {
        "tentatives": [tentative],
        "boucle_reussie": reussi,
        "derniere_validation_statique": validation,
        "derniere_erreur_execution": erreur_exec,
        "dernier_verdict_cascade": verdict,
    }
    if not reussi:
        maj["message_pour_debugger"] = _message_echec_validation(validation, erreur_exec, verdict)
    return maj


def _route_apres_validation(etat: EtatGeneration) -> Literal["test_sandbox", "debugger", "fin_boucle"]:
    if etat["boucle_reussie"]:
        return "test_sandbox"
    if etat["numero_tentative"] >= MAX_TENTATIVES_REPARATION:
        return "fin_boucle"
    return "debugger"


def _noeud_test_sandbox(etat: EtatGeneration) -> dict:
    """Exécute les tests de l'agent Testeur dans le bac à sable, une fois par
    tentative de validation réussie. Un échec des tests générés (ou une
    collecte pytest impossible) renvoie au Debugger comme n'importe quel
    échec de cascade (§6.6bis) — ces tests ciblent `resoudre()` directement
    (voir `generation/prompts/testeur.md`), donc leur échec est traité comme
    un signal de bug réel dans le solveur, plus un simple avertissement pour
    lecture humaine.

    Seule l'indisponibilité de l'infrastructure d'audit elle-même (Docker
    injoignable, image non construite, délai dépassé...) dégrade en silence
    vers `rapport_tests_sandbox=None`, sans jamais bloquer l'acceptation —
    un environnement sans Docker ne doit jamais rendre la génération
    impossible, contrairement à un vrai échec de tests."""
    writer = get_stream_writer()
    writer(etape("test_sandbox", "en_cours", "Exécution des tests générés dans le sandbox..."))

    try:
        rapport = executer_tests_dans_sandbox(etat["code_candidat"], etat["tests_generes"])
    except Exception as erreur:  # noqa: BLE001 — infrastructure d'audit indisponible, jamais bloquant
        writer(etape("test_sandbox", "echec", f"Tests sandbox ignorés ({type(erreur).__name__}) : {erreur}"))
        return {"rapport_tests_sandbox": None}

    if rapport.reussi:
        nb_reussis = sum(t.reussi for t in rapport.tests)
        writer(etape("test_sandbox", "termine", f"{nb_reussis}/{len(rapport.tests)} test(s) généré(s) réussi(s)"))
        return {"rapport_tests_sandbox": rapport}

    message = _message_echec_tests_sandbox(rapport)
    writer(etape("test_sandbox", "echec", message))
    return {"rapport_tests_sandbox": rapport, "message_pour_debugger": message}


def _route_apres_test_sandbox(etat: EtatGeneration) -> Literal["documentation", "debugger", "fin_boucle"]:
    """Indisponibilité du sandbox (`rapport_tests_sandbox is None`) : jamais
    bloquant, direction Documentation comme avant §6.6bis. Un rapport
    présent mais en échec (`.reussi` faux) est traité exactement comme un
    échec de cascade — même borne `MAX_TENTATIVES_REPARATION`, retour au
    Debugger."""
    rapport = etat.get("rapport_tests_sandbox")
    if rapport is None or rapport.reussi:
        return "documentation"
    if etat["numero_tentative"] >= MAX_TENTATIVES_REPARATION:
        return "fin_boucle"
    return "debugger"


def _noeud_debugger(etat: EtatGeneration, config: RunnableConfig) -> dict:
    writer = get_stream_writer()
    n = etat["numero_tentative"]
    nom = f"debugger (tentative {n}/{MAX_TENTATIVES_REPARATION})"
    writer(etape(nom, "en_cours", "Correction du code d'après le diagnostic..."))
    correction = corriger_code(
        _modele(config, "debugger"), etat["code_candidat"], etat["message_pour_debugger"] or ""
    )
    writer(etape(nom, "termine", "Code corrigé"))
    return {"code_candidat": correction.code_source, "numero_tentative": n + 1}


# --- Nœuds terminaux ---------------------------------------------------


def _construire_boucle_reparation(etat: EtatGeneration, *, reussi: bool) -> ResultatBoucleReparation:
    tentatives = tuple(etat["tentatives"])
    nombre_tentatives = etat["numero_tentative"] if reussi else len(tentatives)
    return ResultatBoucleReparation(
        code_initial=etat["code_genere"],
        tentatives=tentatives,
        code_final=etat["code_candidat"],
        reussi=reussi,
        nombre_tentatives=nombre_tentatives,
        derniere_revue=etat["derniere_revue"],
        derniere_validation_statique=etat.get("derniere_validation_statique"),
        derniere_erreur_execution=etat.get("derniere_erreur_execution"),
        dernier_verdict_cascade=etat.get("dernier_verdict_cascade"),
    )


def _noeud_fin_boucle(etat: EtatGeneration) -> dict:
    """Échec après épuisement des tentatives — retour honnête à l'humain
    (§6.6), jamais masqué par un acharnement automatique. Documentation
    sautée : pas de code retenu à documenter.

    Atteint soit avant `test_sandbox` (reviewer/validation jamais résolus),
    soit après (validation réussie mais tests sandbox jamais résolus, voir
    `_route_apres_test_sandbox`) — dans ce second cas, `derniere_validation_
    statique`/`dernier_verdict_cascade` reflètent une validation qui a
    pourtant réussi ; `rapport_tests_sandbox` doit donc être propagé tel
    quel (jamais figé à `None`) pour que `ResultatPipelineAvecBoucle.reussi`
    reste correctement `False`."""
    boucle = _construire_boucle_reparation(etat, reussi=False)
    resultat = ResultatPipelineAvecBoucle(
        specification=etat["analyse"].en_texte(),
        plan_technique=etat["conception"].en_texte(),
        algorithme_recommande=etat["algo"],
        justification_algorithme=etat["raison_algo"],
        parametres_algorithme=etat["parametres_algo"],
        code_genere=etat["code_genere"],
        tests_generes=etat["tests_generes"],
        boucle_reparation=boucle,
        code_final=boucle.code_final,
        validation_statique=boucle.derniere_validation_statique,
        erreur_execution=boucle.derniere_erreur_execution,
        verdict_cascade=boucle.dernier_verdict_cascade,
        rapport_tests_sandbox=etat.get("rapport_tests_sandbox"),
        documentation=None,
    )
    return {"resultat_final": resultat}


def _noeud_documentation(etat: EtatGeneration, config: RunnableConfig) -> dict:
    """Succès après boucle → re-validation du code final (résultat qui
    compte vraiment pour la réponse), puis documentation meilleur-effort :
    un texte descriptif manqué ne doit jamais faire perdre un solveur déjà
    validé."""
    writer = get_stream_writer()
    boucle = _construire_boucle_reparation(etat, reussi=True)
    code_final = boucle.code_final
    validation, erreur_exec, verdict = _valider_completement(
        code_final, etat["tolerance_relative"], etat["comparer_affectation"]
    )

    writer(etape("documentation", "en_cours", "Rédaction de la documentation..."))
    documentation_texte: str | None = None
    try:
        doc = documentation.documenter_code(_modele(config, "documentation"), code_final)
    except Exception as erreur:  # noqa: BLE001 — meilleur-effort, ne doit jamais faire échouer la génération
        writer(etape("documentation", "echec", f"Documentation ignorée ({type(erreur).__name__}) : {erreur}"))
    else:
        documentation_texte = doc.en_texte()
        writer(etape("documentation", "termine", "Documentation produite"))

    resultat = ResultatPipelineAvecBoucle(
        specification=etat["analyse"].en_texte(),
        plan_technique=etat["conception"].en_texte(),
        algorithme_recommande=etat["algo"],
        justification_algorithme=etat["raison_algo"],
        parametres_algorithme=etat["parametres_algo"],
        code_genere=etat["code_genere"],
        tests_generes=etat["tests_generes"],
        boucle_reparation=boucle,
        code_final=code_final,
        validation_statique=validation,
        erreur_execution=erreur_exec,
        verdict_cascade=verdict,
        rapport_tests_sandbox=etat.get("rapport_tests_sandbox"),
        documentation=documentation_texte,
    )
    return {"resultat_final": resultat}


def _construire_graphe() -> StateGraph:
    graphe = StateGraph(EtatGeneration)
    graphe.add_node("analyste", _noeud_analyste)
    graphe.add_node("benchmarker", _noeud_benchmarker)
    graphe.add_node("architecte", _noeud_architecte)
    graphe.add_node("developpeur", _noeud_developpeur)
    graphe.add_node("testeur", _noeud_testeur)
    graphe.add_node("reviewer", _noeud_reviewer)
    graphe.add_node("validation", _noeud_validation)
    graphe.add_node("debugger", _noeud_debugger)
    graphe.add_node("fin_boucle", _noeud_fin_boucle)
    graphe.add_node("test_sandbox", _noeud_test_sandbox)
    graphe.add_node("documentation", _noeud_documentation)

    # Analyste et Benchmarker n'ont aucune dépendance de données l'un envers
    # l'autre — l'Analyste ne lit que la mission statique, le Benchmarker que
    # `instance_exemple` (déjà dans `etat_initial` avant le premier nœud) —
    # donc fan-out depuis START puis fan-in sur l'Architecte (le vrai point
    # de jonction, qui a besoin des deux) plutôt qu'un enchaînement séquentiel.
    # Clés d'état disjointes (`analyse` vs `algo`/`raison_algo`/`parametres_algo`)
    # : pas de reducer nécessaire, LangGraph attend simplement que les deux
    # branches soient terminées avant d'exécuter l'Architecte.
    graphe.add_edge(START, "analyste")
    graphe.add_edge(START, "benchmarker")
    graphe.add_edge("analyste", "architecte")
    graphe.add_edge("benchmarker", "architecte")
    graphe.add_edge("architecte", "developpeur")
    graphe.add_edge("developpeur", "testeur")
    graphe.add_edge("testeur", "reviewer")
    graphe.add_conditional_edges(
        "reviewer",
        _route_apres_reviewer,
        {"validation": "validation", "debugger": "debugger", "fin_boucle": "fin_boucle"},
    )
    graphe.add_conditional_edges(
        "validation",
        _route_apres_validation,
        {"test_sandbox": "test_sandbox", "debugger": "debugger", "fin_boucle": "fin_boucle"},
    )
    graphe.add_edge("debugger", "reviewer")
    graphe.add_edge("fin_boucle", END)
    graphe.add_conditional_edges(
        "test_sandbox",
        _route_apres_test_sandbox,
        {"documentation": "documentation", "debugger": "debugger", "fin_boucle": "fin_boucle"},
    )
    graphe.add_edge("documentation", END)
    return graphe


_GRAPHE_COMPILE = None


def _obtenir_graphe_compile():
    """Instanciation paresseuse — construire le graphe importe déjà tous les
    agents, pas besoin de le refaire à chaque appel."""
    global _GRAPHE_COMPILE
    if _GRAPHE_COMPILE is None:
        _GRAPHE_COMPILE = _construire_graphe().compile()
    return _GRAPHE_COMPILE


# 5 nœuds de mise en place + jusqu'à 10 × (reviewer + validation + test_sandbox
# + debugger) ≈ 45 super-steps dans le pire cas — grande marge au-dessus de la limite par
# défaut de LangGraph (25) pour ne jamais couper la boucle avant qu'elle
# n'épuise légitimement ses tentatives (`GraphRecursionError` silencieux
# sinon, voir tests/integration/test_graph_pipeline.py).
_LIMITE_RECURSION = 60


def _partiels_nouveaux(ancien: dict, nouveau: dict) -> Iterator[ResultatPartiel]:
    """Compare deux instantanés successifs de l'état LangGraph (`stream_mode="values"`) et
    yield ce qui vient d'apparaître — détection par présence de clé, pas par égalité de
    valeur : chaque champ n'apparaît qu'une fois dans l'état, jamais réécrit par un nœud
    suivant, donc « apparaît pour la première fois » suffit sans comparer du texte long.
    `tentatives` (liste qui grandit via le réducteur `operator.add`) traité à part : slicing
    par longueur pour ne yield que les entrées nouvelles depuis le dernier passage.
    `code_final`/`documentation` n'ont pas besoin de capture partielle : ils n'existent que
    dans `resultat_final`, construit uniquement aux nœuds terminaux."""
    if "analyse" in nouveau and "analyse" not in ancien:
        yield ResultatPartiel("specification", nouveau["analyse"].en_texte())
    if "algo" in nouveau and "algo" not in ancien:
        yield ResultatPartiel("algorithme", nouveau["algo"])
        yield ResultatPartiel("algorithme_raison", nouveau["raison_algo"])
        yield ResultatPartiel("algorithme_parametres", nouveau["parametres_algo"])
    if "conception" in nouveau and "conception" not in ancien:
        yield ResultatPartiel("plan_technique", nouveau["conception"].en_texte())
    if "code_genere" in nouveau and "code_genere" not in ancien:
        yield ResultatPartiel("code_genere", nouveau["code_genere"])
    if "tests_generes" in nouveau and "tests_generes" not in ancien:
        yield ResultatPartiel("tests_generes", nouveau["tests_generes"])
    if "rapport_tests_sandbox" in nouveau and "rapport_tests_sandbox" not in ancien:
        rapport = nouveau["rapport_tests_sandbox"]
        yield ResultatPartiel("rapport_tests_sandbox", rapport.en_dict() if rapport is not None else None)
    for tentative in nouveau.get("tentatives", [])[len(ancien.get("tentatives", [])) :]:
        yield ResultatPartiel("tentative", tentative)


def tenter_generation_avec_boucle_stream(
    instance_exemple: dict | None = None,
) -> Iterator[EvenementEtape | ResultatPartiel | ResultatPipelineAvecBoucle]:
    """Version streaming du pipeline complet — yield un `EvenementEtape`
    après chaque agent (et chaque sous-étape de la boucle de réparation) ;
    le tout dernier élément produit est toujours le `ResultatPipelineAvecBoucle`
    final. Consommée par `api/routes/generation.py` pour le streaming SSE —
    un pipeline à 7 agents + jusqu'à 10 tentatives de réparation peut prendre
    plusieurs minutes, une attente aveugle n'est pas acceptable.

    `instance_exemple` : instance T-R-C-O (dict JSON, ex.
    `InstanceTRCO.model_dump(mode="json")`) transmise à l'agent Benchmarker,
    désormais **toujours appelé** — aucun seuil de taille, aucun raccourci
    déterministe : il choisit le meilleur algorithme de son catalogue entier
    (cp_sat, genetic, aco, simulated_annealing, tabu_search, dispatching,
    greedy_local), quel que soit le nombre de tâches. Si `None` (appelants
    historiques sans instance sous la main — scripts, tests), une petite
    instance par défaut est utilisée
    (`generation.agents.benchmarker.creer_instance_exemple_defaut`),
    orientant presque toujours vers cp_sat et préservant leur comportement
    d'avant cette fonctionnalité. Le solveur figé produit sera ensuite
    réexécuté (§5.2, « generate once ») sur d'autres instances de la même clé
    (client + structure_contraintes + signature_objectifs) potentiellement de
    taille très différente — accepté, pas quelque chose à corriger ici.

    Chaque agent construit son propre modèle LangChain via
    `construire_modele_pour_agent(nom)` (§5.6, `config_fournisseurs.py`) —
    le fournisseur optimal par agent, jamais un client partagé imposé par
    l'appelant.
    """
    graphe = _obtenir_graphe_compile()
    etat_initial: EtatGeneration = {"instance_exemple": instance_exemple}
    resultat_final: ResultatPipelineAvecBoucle | None = None
    dernier_etat: dict = {}

    for mode, payload in graphe.stream(
        etat_initial, stream_mode=["custom", "values"], config={"recursion_limit": _LIMITE_RECURSION}
    ):
        if mode == "custom":
            yield payload
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("resultat_final") is not None:
            resultat_final = payload["resultat_final"]
            continue
        yield from _partiels_nouveaux(dernier_etat, payload)
        dernier_etat = payload

    assert resultat_final is not None  # le graphe atteint toujours fin_boucle ou documentation
    yield resultat_final


def tenter_generation_avec_boucle(
    instance_exemple: dict | None = None,
) -> ResultatPipelineAvecBoucle:
    """Version bloquante — ne renvoie que le résultat final, sans les
    évènements intermédiaires. `instance_exemple` : voir
    `tenter_generation_avec_boucle_stream`. Voir cette dernière pour le
    streaming SSE (`api/routes/generation.py`)."""
    resultat: ResultatPipelineAvecBoucle | None = None
    for item in tenter_generation_avec_boucle_stream(instance_exemple):
        if isinstance(item, ResultatPipelineAvecBoucle):
            resultat = item
    assert resultat is not None  # tenter_generation_avec_boucle_stream yield toujours un résultat final
    return resultat
