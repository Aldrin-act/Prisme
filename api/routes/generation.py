"""Déclenche le pipeline de génération de solveur multi-agents avec boucle
de réparation bornée (`generation.graph`, StateGraph LangGraph, Étape 6 —
déjà construite : analyste → benchmarker → architecte →
développeur → testeur → [Tests sandbox/Validation/Debugger, jusqu'à 10
tentatives — Reviewer désactivé, voir `generation/graph.py`] →
documentation)
depuis une instance déjà ingérée. La boucle reste bornée : après épuisement
des tentatives, l'échec est renvoyé tel quel à l'humain, jamais masqué par
un acharnement automatique (§6.5).

Trois canaux pour le même pipeline :
- `POST /{instance_id}` — bloquant, une seule réponse JSON à la fin.
- `POST /{instance_id}/demarrer` + `GET /jobs/{job_id}/stream` — le pipeline
  tourne dans un fil séparé, indépendant de toute connexion HTTP ouverte : le
  job continue même si le client se déconnecte (rechargement de page, perte
  réseau...). `stream` rejoue l'historique déjà produit puis continue en
  direct — se reconnecter après un rechargement donne la même chronologie
  que si on l'avait suivie depuis le début. C'est le canal utilisé par le
  frontend (`Front/.../solver-generator.tsx`).

Job en mémoire process (`_JOBS`), comme le reste de l'état de développement
de ce module (`api/etat.py`) — ne survit pas à un redémarrage du serveur, et
n'est jamais purgé (acceptable pour un PoC, à revoir si le volume de
générations devient significatif).

Distinct de l'agent de compréhension (`adapters/agent_comprehension/`) : ici
on génère du **code** de solveur, générique à l'ensemble du DSL — l'instance
sert à retrouver le `client_id`, la clé de matching
(`structure_contraintes` + `signature_objectifs`, utilisée pour détecter un
solveur devenu incompatible après modification de l'instance) et son propre
`instance_id`, sous lequel le résultat est enregistré : un solveur généré ne
sert que cette instance, jamais une autre même de signature identique.
L'instance n'est jamais injectée comme donnée dans le prompt (le code
produit n'est pas spécifique à son contenu, seulement à sa structure, §5.2
"generate once, re-execute many" — au sens d'une même instance rejouée dans
le temps, pas d'un partage entre instances)."""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.autorisation import client_id_pour_filtre, verifier_acces_client
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, TentativeGeneration, obtenir_etat, structure_contraintes
from api.etat import signature_objectifs as calculer_signature_objectifs
from api.routes.auth import obtenir_utilisateur_courant
from api.statistiques_generation import calculer_statistiques
from generation.graph import (
    MAX_TENTATIVES_REPARATION,
    ResultatPartiel,
    ResultatPipelineAvecBoucle,
    TentativeReparation,
    tenter_generation_avec_boucle,
    tenter_generation_avec_boucle_stream,
)
from solver_store.registry import Registre

router = APIRouter(prefix="/generation", tags=["generation"])

_INTERVALLE_POLL_SECONDES = 0.5


@dataclass
class _JobGeneration:
    """Suivi d'une génération lancée en arrière-plan — `evenements` grandit
    au fil du pipeline, `resultat`/`erreur` ne se remplissent qu'à la fin.
    `instance_id`/`client_id` permettent à une page qui n'a pas déclenché ce
    job (ex. la page Instances, ou un second onglet) de savoir qu'une
    génération tourne pour cette instance, sans dépendre du `localStorage`
    du navigateur qui l'a lancé."""

    id: str
    instance_id: str
    client_id: str
    evenements: list[dict[str, str]] = field(default_factory=list)
    resultat: dict[str, object] | None = None
    erreur: str | None = None
    termine: bool = False
    cree_le: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    # Coopératif, jamais un arrêt forcé du fil (Python ne le permet pas
    # proprement) : `_executer_job` ne consulte ce drapeau qu'entre deux
    # évènements du pipeline (chaque `yield` de `tenter_generation_avec_
    # boucle_stream` correspond à un nœud terminé) — un appel LLM déjà en
    # cours va jusqu'à son terme, l'arrêt réel intervient au yield suivant.
    annule: bool = False


_JOBS: dict[str, _JobGeneration] = {}


def _instance_et_cle(instance_id: str, etat: EtatAPI, utilisateur: dict) -> tuple[str, dict, str, str]:
    """Résout l'instance et sa clé de matching, avec le contrôle d'accès —
    partagé par les routes ci-dessous, appelé avant tout streaming/job pour
    qu'une instance inconnue ou interdite renvoie un vrai 404/403 immédiat.

    Renvoie désormais aussi l'instance elle-même (dict JSON,
    `InstanceTRCO.model_dump(mode="json")`) — jusqu'ici jetée après
    extraction de la clé de matching, elle alimente maintenant l'agent
    Benchmarker (voir `generation/graph.py`, `instance_exemple`). Toujours
    pas injectée dans un prompt de génération de code : seule l'analyse de
    taille/structure/flexibilité du Benchmarker
    la consomme."""
    try:
        client_id, instance = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)
    instance_dict = instance.model_dump(mode="json")
    return client_id, instance_dict, structure_contraintes(instance), calculer_signature_objectifs(instance)


def _construire_reponse(
    resultat: ResultatPipelineAvecBoucle,
    registre: Registre,
    client_id: str,
    instance_id: str,
    structure: str,
    signature_obj: str,
) -> dict[str, object]:
    """Le résultat final, sous la même forme pour tous les canaux — enregistre
    le solveur si la cascade est au vert, sinon renvoie le diagnostic tel quel."""
    nombre_tentatives = resultat.boucle_reparation.nombre_tentatives
    # Visible directement sur le résultat (succès ou échec), pas seulement via
    # `/historique` — dernier passage des tests générés par l'agent Testeur
    # réellement exécutés en sandbox (§6.6bis), `None` uniquement si le
    # sandbox était indisponible (jamais bloquant, voir `ResultatPipelineAvecBoucle.reussi`).
    rapport_tests_sandbox = resultat.rapport_tests_sandbox.en_dict() if resultat.rapport_tests_sandbox else None

    if not resultat.reussi:
        erreur: str | None = None
        if resultat.validation_statique is not None and not resultat.validation_statique.valide:
            erreur = "code rejeté par la validation statique : " + "; ".join(
                resultat.validation_statique.violations
            )
        elif resultat.erreur_execution is not None:
            erreur = f"erreur à l'exécution du code : {resultat.erreur_execution}"
        elif (
            resultat.verdict_cascade is not None
            and resultat.verdict_cascade.reussi
            and resultat.rapport_tests_sandbox is not None
            and not resultat.rapport_tests_sandbox.reussi
        ):
            # Cascade au vert, mais tests générés par l'agent Testeur en échec en
            # sandbox après épuisement des tentatives (§6.6bis) — seul cas où la
            # cascade seule ne suffit pas à expliquer l'échec global.
            detail = resultat.rapport_tests_sandbox.erreur or "; ".join(
                t.nom for t in resultat.rapport_tests_sandbox.tests if not t.reussi
            )
            erreur = f"cascade de validation réussie, mais tests générés en échec en sandbox : {detail}"

        echecs_cascade = list(resultat.verdict_cascade.echecs) if resultat.verdict_cascade else []
        return {
            "reussi": False,
            "id_solveur": None,
            "structure_contraintes": structure,
            "signature_objectifs": signature_obj,
            "algorithme": resultat.algorithme_recommande,
            "algorithme_raison": resultat.justification_algorithme,
            "nombre_tentatives": nombre_tentatives,
            "erreur": erreur,
            "echecs_cascade": [
                {"nom": d.nom, "brique_en_echec": d.brique_en_echec, "details": list(d.details)}
                for d in echecs_cascade
            ],
            "rapport_tests_sandbox": rapport_tests_sandbox,
        }

    assert resultat.verdict_cascade is not None  # garanti par ResultatPipelineAvecBoucle.reussi
    id_solveur = registre.enregistrer_solveur(
        resultat.code_final,
        structure,
        resultat.verdict_cascade,
        instance_id=instance_id,
        client_id=client_id,
        signature_objectifs=signature_obj,
        algorithme=resultat.algorithme_recommande,
        algorithme_raison=resultat.justification_algorithme,
    )
    return {
        "reussi": True,
        "id_solveur": id_solveur,
        "structure_contraintes": structure,
        "signature_objectifs": signature_obj,
        "algorithme": resultat.algorithme_recommande,
        "algorithme_raison": resultat.justification_algorithme,
        "nombre_tentatives": nombre_tentatives,
        "erreur": None,
        "echecs_cascade": [],
        "rapport_tests_sandbox": rapport_tests_sandbox,
    }


def _tentative_persistee(tentative: TentativeReparation) -> TentativeGeneration:
    """Convertit une tentative interne du pipeline (§6.6) en sa forme persistée — réutilisée
    pour la capture incrémentale (`ResultatPartiel(champ="tentative", ...)`, voir
    `_executer_job`), pour ne jamais perdre une tentative déjà accumulée si le pipeline
    plante avant la fin de la boucle de réparation."""
    return TentativeGeneration(
        numero=tentative.numero,
        code_candidat=tentative.code_candidat,
        reussi=tentative.reussi,
        erreur_execution=tentative.erreur_execution,
        revue_approuve=tentative.revue.approuve if tentative.revue else None,
        revue_reponse_brute=tentative.revue.reponse_brute if tentative.revue else None,
        revue_problemes=tentative.revue.problemes if tentative.revue else (),
        validation_statique_valide=(
            tentative.validation_statique.valide if tentative.validation_statique else None
        ),
        validation_statique_violations=(
            tentative.validation_statique.violations if tentative.validation_statique else ()
        ),
    )


def _executer_job(
    job: _JobGeneration,
    registre: Registre,
    etat: EtatAPI,
    client_id: str,
    structure: str,
    signature_obj: str,
    instance_dict: dict,
) -> None:
    """Corps du fil d'exécution — jamais laissé mourir en silence (§6.6 : le
    pipeline peut échouer, la mesure/le suivi doit survivre). Persiste en
    base au fil de l'eau (`etat`), en plus du suivi en mémoire process
    (`job`) déjà utilisé par le flux SSE — les deux coexistent, le premier
    survit à un redémarrage du serveur, le second reste la source du direct.

    Chaque sortie d'agent (`ResultatPartiel`) est persistée dès qu'elle est connue, pas
    seulement à la toute fin — un plantage en cours de route (pas l'échec « propre » après
    épuisement des tentatives) ne perd donc plus ce que les agents précédents ont déjà
    produit."""
    resultat_pipeline: ResultatPipelineAvecBoucle | None = None
    try:
        for item in tenter_generation_avec_boucle_stream(instance_dict, client_id=client_id):
            if isinstance(item, ResultatPipelineAvecBoucle):
                resultat_pipeline = item
                job.resultat = _construire_reponse(
                    item, registre, client_id, job.instance_id, structure, signature_obj
                )
            elif isinstance(item, ResultatPartiel):
                if item.champ == "tentative":
                    etat.ajouter_tentative_generation(job.id, _tentative_persistee(item.valeur))
                else:
                    etat.mettre_a_jour_job_generation(job.id, **{item.champ: item.valeur})
            else:
                job.evenements.append(item)
                etat.ajouter_evenement_generation(job.id, item["agent"], item["statut"], item["resume"])
            if job.annule:
                job.erreur = "Génération annulée par l'utilisateur"
                break
    except Exception as erreur:  # noqa: BLE001 — le pipeline peut lever n'importe quoi (appel LLM, réseau...)
        job.erreur = str(erreur)
    finally:
        job.termine = True

        if job.resultat is not None:
            reussi = job.resultat.get("reussi")
            id_solveur = job.resultat.get("id_solveur")
            nombre_tentatives = job.resultat.get("nombre_tentatives")
        else:
            reussi = False if job.erreur is not None else None
            id_solveur = None
            nombre_tentatives = None

        # `champs_contenu` reste vide si le pipeline a planté avant d'atteindre un nœud
        # terminal (`resultat_pipeline is None`) — `terminer_job_generation` traite alors
        # l'absence de ces kwargs comme « ne pas toucher », jamais comme un effacement de ce
        # que `mettre_a_jour_job_generation` a déjà persisté ci-dessus au fil de l'eau.
        champs_contenu: dict[str, object] = {}
        if resultat_pipeline is not None:
            champs_contenu = {
                "specification": resultat_pipeline.specification,
                "plan_technique": resultat_pipeline.plan_technique,
                "algorithme": resultat_pipeline.algorithme_recommande,
                "algorithme_raison": resultat_pipeline.justification_algorithme,
                "algorithme_parametres": resultat_pipeline.parametres_algorithme,
                "code_genere": resultat_pipeline.code_genere,
                "tests_generes": resultat_pipeline.tests_generes,
                "code_final": resultat_pipeline.code_final,
                "rapport_tests_sandbox": (
                    resultat_pipeline.rapport_tests_sandbox.en_dict()
                    if resultat_pipeline.rapport_tests_sandbox is not None
                    else None
                ),
                "documentation": resultat_pipeline.documentation,
            }

        etat.terminer_job_generation(
            job.id,
            reussi=reussi,
            id_solveur=id_solveur,
            nombre_tentatives=nombre_tentatives,
            erreur=job.erreur,
            **champs_contenu,
        )


@router.post("/{instance_id}")
def generer_solveur(
    instance_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    registre: Registre = Depends(obtenir_registre),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Synchrone et bloquant (plusieurs appels LLM — 8 agents, jusqu'à 10
    tentatives de réparation — plus exécution sandboxée et cascade complète
    à chaque tentative : potentiellement plusieurs minutes). Voir
    `/{instance_id}/demarrer` pour suivre la progression agent par agent,
    de façon résistante à un rechargement de page."""
    client_id, instance_dict, structure, signature_obj = _instance_et_cle(instance_id, etat, utilisateur)

    job_id = str(uuid.uuid4())
    etat.enregistrer_job_generation(job_id, instance_id, client_id)

    resultat = tenter_generation_avec_boucle(instance_exemple=instance_dict, client_id=client_id)
    reponse = _construire_reponse(resultat, registre, client_id, instance_id, structure, signature_obj)

    for tentative in resultat.boucle_reparation.tentatives:
        etat.ajouter_tentative_generation(job_id, _tentative_persistee(tentative))
    etat.terminer_job_generation(
        job_id,
        reussi=reponse["reussi"],
        id_solveur=reponse["id_solveur"],
        specification=resultat.specification,
        plan_technique=resultat.plan_technique,
        algorithme=resultat.algorithme_recommande,
        algorithme_raison=resultat.justification_algorithme,
        algorithme_parametres=resultat.parametres_algorithme,
        code_genere=resultat.code_genere,
        tests_generes=resultat.tests_generes,
        code_final=resultat.code_final,
        rapport_tests_sandbox=(
            resultat.rapport_tests_sandbox.en_dict() if resultat.rapport_tests_sandbox is not None else None
        ),
        documentation=resultat.documentation,
        nombre_tentatives=reponse["nombre_tentatives"],
        erreur=reponse["erreur"],
    )
    return reponse


@router.post("/{instance_id}/demarrer")
def demarrer_generation_solveur(
    instance_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    registre: Registre = Depends(obtenir_registre),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, str]:
    """Démarre le pipeline dans un fil séparé et renvoie immédiatement un
    `job_id` : la génération continue même si le client se déconnecte
    (rechargement de page, perte réseau...). Suivre la progression via
    `GET /jobs/{job_id}/stream`, qui peut être rejoint ou rejoué à tout
    moment — c'est ce qui permet à la page de survivre à un F5."""
    client_id, instance_dict, structure, signature_obj = _instance_et_cle(instance_id, etat, utilisateur)

    job_id = str(uuid.uuid4())
    job = _JobGeneration(id=job_id, instance_id=instance_id, client_id=client_id)
    _JOBS[job_id] = job
    etat.enregistrer_job_generation(job_id, instance_id, client_id)

    fil = threading.Thread(
        target=_executer_job,
        args=(job, registre, etat, client_id, structure, signature_obj, instance_dict),
        daemon=True,
    )
    fil.start()

    return {"job_id": job_id}


@router.post("/jobs/{job_id}/annuler")
def annuler_generation_solveur(
    job_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, bool]:
    """Demande d'arrêt coopérative — voir `_JobGeneration.annule`. Un job
    déjà terminé (succès, échec, ou déjà annulé) est un no-op, jamais une
    erreur : annuler deux fois, ou annuler après la fin naturelle, reste
    sans effet plutôt que de faire échouer l'appelant sur une course
    inoffensive (double-clic, requête réseau en retard...)."""
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job de génération inconnu")

    verifier_acces_client(utilisateur, job.client_id)

    if not job.termine:
        job.annule = True

    return {"annule": job.annule}


@router.get("/jobs")
def lister_jobs_generation(
    instance_id: str | None = None,
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> list[dict[str, object]]:
    """Jobs de génération connus (mémoire process), filtrables par instance —
    pour qu'une page qui n'a pas déclenché le job (Instances, un autre
    onglet...) sache qu'une génération tourne en arrière-plan pour telle
    instance. Mêmes règles de visibilité que le reste de l'API : un compte
    non-admin ne voit que les jobs de son propre client.

    Inclut `evenements` (l'historique agent par agent) et `nombre_tentatives`
    — pas seulement `reussi`/`termine` — pour que la page Analytique puisse
    calculer de vraies statistiques par agent (taux d'échec, fréquence...)
    sans qu'un canal dédié soit nécessaire."""
    filtre_client = client_id_pour_filtre(utilisateur)
    return [
        {
            "job_id": job.id,
            "instance_id": job.instance_id,
            "client_id": job.client_id,
            "termine": job.termine,
            "reussi": job.resultat.get("reussi") if job.resultat else None,
            "nombre_tentatives": job.resultat.get("nombre_tentatives") if job.resultat else None,
            "cree_le": job.cree_le,
            "evenements": job.evenements,
        }
        for job in _JOBS.values()
        if (filtre_client is None or job.client_id == filtre_client)
        and (instance_id is None or job.instance_id == instance_id)
    ]


@router.get("/statistiques")
def obtenir_statistiques_generation(
    agent: str | None = None,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """KPI d'agrégat pour la page Analytique (§ non-répétition/boucles, voir
    `api/statistiques_generation.py`) — lit le stockage **persisté**
    (`jobs_generation`/`evenements_generation`/`tentatives_generation`),
    contrairement à `GET /jobs` qui lit `_JOBS` en mémoire process et perd
    tout à un redémarrage. Même règle de visibilité que le reste de l'API.

    `agent` (déjà normalisé côté frontend, ex. `"debugger"`) restreint tout le
    calcul aux générations où cet agent est intervenu — voir la docstring de
    `calculer_statistiques` pour ce qui change précisément sous ce filtre."""
    filtre_client = client_id_pour_filtre(utilisateur)
    jobs = etat.lister_jobs_generation_persistes(client_id=filtre_client)
    evenements = etat.lister_evenements_generation(client_id=filtre_client)
    tentatives = etat.lister_tentatives_generation(client_id=filtre_client)
    return calculer_statistiques(jobs, evenements, tentatives, MAX_TENTATIVES_REPARATION, agent=agent).en_dict()


@router.get("/jobs/{job_id}/stream")
def suivre_job_generation(job_id: str) -> StreamingResponse:
    """Rejoue l'historique des évènements déjà produits par le job, puis
    continue à streamer les suivants au fur et à mesure (scrutation toutes
    les 500ms — le job tourne dans un autre fil, rien d'autre à écouter).
    Un job déjà terminé renvoie immédiatement son historique complet suivi
    du résultat final : rouvrir ce flux après un rechargement de page donne
    donc exactement la même chronologie que si on l'avait suivie en direct."""
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job de génération inconnu")

    def flux() -> Iterator[str]:
        index = 0
        while True:
            while index < len(job.evenements):
                yield f"event: etape\ndata: {json.dumps(job.evenements[index])}\n\n"
                index += 1

            if job.termine:
                if job.erreur is not None:
                    yield f"event: erreur\ndata: {json.dumps({'message': job.erreur})}\n\n"
                elif job.resultat is not None:
                    yield f"event: resultat\ndata: {json.dumps(job.resultat)}\n\n"
                return

            time.sleep(_INTERVALLE_POLL_SECONDES)

    return StreamingResponse(flux(), media_type="text/event-stream")


@router.get("/jobs/{job_id}/historique")
def obtenir_historique_job_generation(
    job_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Historique complet et durable d'un job (§6.6) : survit à un
    redémarrage du serveur, contrairement à `_JOBS`/`GET .../stream`
    (mémoire process). Inclut le code candidat de **chaque** tentative de la
    boucle de réparation, y compris les rejetées — pas seulement le code
    final retenu — pour permettre l'audit complet du raisonnement des
    agents, un choix explicite plutôt qu'un historique tronqué."""
    try:
        job = etat.recuperer_job_generation(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job de génération inconnu") from None

    verifier_acces_client(utilisateur, job.client_id)

    return {
        "job_id": job.id,
        "instance_id": job.instance_id,
        "client_id": job.client_id,
        "cree_le": job.cree_le,
        "termine": job.termine,
        "reussi": job.reussi,
        "id_solveur": job.id_solveur,
        "specification": job.specification,
        "plan_technique": job.plan_technique,
        "algorithme": job.algorithme,
        "algorithme_raison": job.algorithme_raison,
        "algorithme_parametres": job.algorithme_parametres,
        "code_genere": job.code_genere,
        "tests_generes": job.tests_generes,
        "code_final": job.code_final,
        "rapport_tests_sandbox": job.rapport_tests_sandbox,
        "documentation": job.documentation,
        "nombre_tentatives": job.nombre_tentatives,
        "erreur": job.erreur,
        "termine_le": job.termine_le,
        "evenements": [
            {"ordre": e.ordre, "agent": e.agent, "statut": e.statut, "resume": e.resume} for e in job.evenements
        ],
        "tentatives": [
            {
                "numero": t.numero,
                "code_candidat": t.code_candidat,
                "reussi": t.reussi,
                "erreur_execution": t.erreur_execution,
                "revue_approuve": t.revue_approuve,
                "revue_reponse_brute": t.revue_reponse_brute,
                "revue_problemes": list(t.revue_problemes),
                "validation_statique_valide": t.validation_statique_valide,
                "validation_statique_violations": list(t.validation_statique_violations),
            }
            for t in job.tentatives
        ],
    }
