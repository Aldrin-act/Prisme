"""Déclenche le pipeline de génération de solveur multi-agents avec boucle
de réparation bornée (`generation.pipeline_avec_boucle`, Étape 6 — déjà
construite : orchestrateur → analyste → architecte → développeur → testeur
→ [Reviewer/Debugger, jusqu'à 10 tentatives] → optimiseur → documentation)
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

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.autorisation import client_id_pour_filtre, verifier_acces_client
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat, structure_contraintes
from api.etat import signature_objectifs as calculer_signature_objectifs
from api.routes.auth import obtenir_utilisateur_courant
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


def _executer_job(
    job: _JobGeneration, registre: Registre, client_id: str, structure: str, signature_obj: str
) -> None:
    """Corps du fil d'exécution — jamais laissé mourir en silence (§6.6 : le
    pipeline peut échouer, la mesure/le suivi doit survivre)."""
    try:
        for item in tenter_generation_avec_boucle_stream():
            if isinstance(item, ResultatPipelineAvecBoucle):
                job.resultat = _construire_reponse(item, registre, client_id, structure, signature_obj)
            else:
                job.evenements.append(item)
    except Exception as erreur:  # noqa: BLE001 — le pipeline peut lever n'importe quoi (appel LLM, réseau...)
        job.erreur = str(erreur)
    finally:
        job.termine = True


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
    resultat = tenter_generation_avec_boucle()
    return _construire_reponse(resultat, registre, client_id, structure, signature_obj)


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

    fil = threading.Thread(
        target=_executer_job,
        args=(job, registre, client_id, structure, signature_obj),
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
    non-admin ne voit que les jobs de son propre client."""
    filtre_client = client_id_pour_filtre(utilisateur)
    return [
        {
            "job_id": job.id,
            "instance_id": job.instance_id,
            "termine": job.termine,
            "reussi": job.resultat.get("reussi") if job.resultat else None,
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
