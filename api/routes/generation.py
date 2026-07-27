"""Déclenche le pipeline de génération de solveur multi-agents avec boucle
de réparation bornée (`generation.pipeline_avec_boucle`, Étape 6 — déjà
construite : orchestrateur → analyste → architecte → développeur → testeur
→ [Reviewer/Debugger, jusqu'à 10 tentatives] → documentation)
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
ne sert qu'à retrouver le `client_id` et la clé de matching
(`structure_contraintes` + `signature_objectifs`) sous laquelle enregistrer
le résultat, jamais comme donnée injectée dans le prompt (le code produit
n'est pas spécifique à cette instance, §5.2 "generate once, re-execute
many")."""

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
from generation.loop import ResultatBoucleReparation
from generation.pipeline_avec_boucle import (
    ResultatPipelineAvecBoucle,
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


_JOBS: dict[str, _JobGeneration] = {}


def _instance_et_cle(instance_id: str, etat: EtatAPI, utilisateur: dict) -> tuple[str, str, str]:
    """Résout l'instance et sa clé de matching, avec le contrôle d'accès —
    partagé par les routes ci-dessous, appelé avant tout streaming/job pour
    qu'une instance inconnue ou interdite renvoie un vrai 404/403 immédiat."""
    try:
        client_id, instance = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)
    return client_id, structure_contraintes(instance), calculer_signature_objectifs(instance)


def _construire_reponse(
    resultat: ResultatPipelineAvecBoucle,
    registre: Registre,
    client_id: str,
    structure: str,
    signature_obj: str,
) -> dict[str, object]:
    """Le résultat final, sous la même forme pour tous les canaux — enregistre
    le solveur si la cascade est au vert, sinon renvoie le diagnostic tel quel."""
    nombre_tentatives = resultat.boucle_reparation.nombre_tentatives

    if not resultat.reussi:
        erreur: str | None = None
        if resultat.validation_statique is not None and not resultat.validation_statique.valide:
            erreur = "code rejeté par la validation statique : " + "; ".join(
                resultat.validation_statique.violations
            )
        elif resultat.erreur_execution is not None:
            erreur = f"erreur à l'exécution du code : {resultat.erreur_execution}"

        echecs_cascade = list(resultat.verdict_cascade.echecs) if resultat.verdict_cascade else []
        return {
            "reussi": False,
            "id_solveur": None,
            "structure_contraintes": structure,
            "signature_objectifs": signature_obj,
            "nombre_tentatives": nombre_tentatives,
            "erreur": erreur,
            "echecs_cascade": [
                {"nom": d.nom, "brique_en_echec": d.brique_en_echec, "details": list(d.details)}
                for d in echecs_cascade
            ],
        }

    assert resultat.verdict_cascade is not None  # garanti par ResultatPipelineAvecBoucle.reussi
    id_solveur = registre.enregistrer_solveur(
        resultat.code_final, structure, resultat.verdict_cascade, client_id, signature_obj
    )
    return {
        "reussi": True,
        "id_solveur": id_solveur,
        "structure_contraintes": structure,
        "signature_objectifs": signature_obj,
        "nombre_tentatives": nombre_tentatives,
        "erreur": None,
        "echecs_cascade": [],
    }


def _persister_tentatives(etat: EtatAPI, job_id: str, boucle: ResultatBoucleReparation) -> None:
    """Écrit chaque tentative de la boucle de réparation (§6.6), y compris
    celles rejetées — le code candidat de chacune est conservé, pas
    seulement celui de la tentative finale (choix explicite : « historique
    complet »)."""
    for tentative in boucle.tentatives:
        etat.ajouter_tentative_generation(
            job_id,
            TentativeGeneration(
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
            ),
        )


def _executer_job(
    job: _JobGeneration, registre: Registre, etat: EtatAPI, client_id: str, structure: str, signature_obj: str
) -> None:
    """Corps du fil d'exécution — jamais laissé mourir en silence (§6.6 : le
    pipeline peut échouer, la mesure/le suivi doit survivre). Persiste en
    base au fil de l'eau (`etat`), en plus du suivi en mémoire process
    (`job`) déjà utilisé par le flux SSE — les deux coexistent, le premier
    survit à un redémarrage du serveur, le second reste la source du direct."""
    resultat_pipeline: ResultatPipelineAvecBoucle | None = None
    try:
        for item in tenter_generation_avec_boucle_stream():
            if isinstance(item, ResultatPipelineAvecBoucle):
                resultat_pipeline = item
                job.resultat = _construire_reponse(item, registre, client_id, structure, signature_obj)
            else:
                job.evenements.append(item)
                etat.ajouter_evenement_generation(job.id, item["agent"], item["statut"], item["resume"])
    except Exception as erreur:  # noqa: BLE001 — le pipeline peut lever n'importe quoi (appel LLM, réseau...)
        job.erreur = str(erreur)
    finally:
        job.termine = True
        if resultat_pipeline is not None:
            _persister_tentatives(etat, job.id, resultat_pipeline.boucle_reparation)

        if job.resultat is not None:
            reussi = job.resultat.get("reussi")
            id_solveur = job.resultat.get("id_solveur")
            nombre_tentatives = job.resultat.get("nombre_tentatives")
        else:
            reussi = False if job.erreur is not None else None
            id_solveur = None
            nombre_tentatives = None

        etat.terminer_job_generation(
            job.id,
            reussi=reussi,
            id_solveur=id_solveur,
            specification=resultat_pipeline.specification if resultat_pipeline else None,
            plan_technique=resultat_pipeline.plan_technique if resultat_pipeline else None,
            code_genere=resultat_pipeline.code_genere if resultat_pipeline else None,
            tests_generes=resultat_pipeline.tests_generes if resultat_pipeline else None,
            code_final=resultat_pipeline.code_final if resultat_pipeline else None,
            nombre_tentatives=nombre_tentatives,
            erreur=job.erreur,
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
    client_id, structure, signature_obj = _instance_et_cle(instance_id, etat, utilisateur)

    job_id = str(uuid.uuid4())
    etat.enregistrer_job_generation(job_id, instance_id, client_id)

    resultat = tenter_generation_avec_boucle()
    reponse = _construire_reponse(resultat, registre, client_id, structure, signature_obj)

    _persister_tentatives(etat, job_id, resultat.boucle_reparation)
    etat.terminer_job_generation(
        job_id,
        reussi=reponse["reussi"],
        id_solveur=reponse["id_solveur"],
        specification=resultat.specification,
        plan_technique=resultat.plan_technique,
        code_genere=resultat.code_genere,
        tests_generes=resultat.tests_generes,
        code_final=resultat.code_final,
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
    client_id, structure, signature_obj = _instance_et_cle(instance_id, etat, utilisateur)

    job_id = str(uuid.uuid4())
    job = _JobGeneration(id=job_id, instance_id=instance_id, client_id=client_id)
    _JOBS[job_id] = job
    etat.enregistrer_job_generation(job_id, instance_id, client_id)

    fil = threading.Thread(
        target=_executer_job,
        args=(job, registre, etat, client_id, structure, signature_obj),
        daemon=True,
    )
    fil.start()

    return {"job_id": job_id}


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
        "code_genere": job.code_genere,
        "tests_generes": job.tests_generes,
        "code_final": job.code_final,
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
