"""Canal opérationnel (§5.1, §5.5) : retourne le planning en JSON, à chaque itération.

Gantt interactif (Phase 3, `POST /{execution_id}/ajuster` + `GET /{execution_id}/ajuste`) :
un planning ajusté à la main sur le Gantt reste **une proposition**, jamais appliqué
silencieusement — revalidé par le même `verifier_faisabilite` déterministe que tout le reste du
système avant toute persistance, et persisté à part de l'original figé par le solveur (jamais une
modification en place), qui reste accessible sans changement via `GET /{execution_id}`."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.autorisation import verifier_acces_client
from api.etat import EtatAPI, durees_par_contrainte, obtenir_etat
from api.routes.auth import obtenir_utilisateur_courant
from dsl.schema import Planning
from validation_engine.feasibility_checker import verifier_faisabilite
from validation_engine.makespan import calculer_makespan

router = APIRouter(prefix="/planning", tags=["planning"])


@router.get("/{execution_id}")
def obtenir_planning(
    execution_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, Any]:
    try:
        _, instance_id, resultat = etat.recuperer_execution(execution_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="exécution inconnue") from None

    # instance_id est garanti exister : supprimer_instance cascade-supprime
    # ses propres exécutions plutôt que de les orpheliner.
    client_id, instance = etat.recuperer_instance(instance_id)
    verifier_acces_client(utilisateur, client_id)

    if resultat.planning is None:
        raise HTTPException(status_code=422, detail=resultat.erreur or "aucun planning disponible")

    # Durées ajoutées pour le Gantt du dashboard : `Planning` n'a délibérément
    # pas de champ durée (§ dsl/schema/planning.py) — elle vit sur
    # `CompatibiliteRessourceTache`, propre au couple (tâche, ressource).
    return {**resultat.planning.model_dump(mode="json"), "durees": durees_par_contrainte(instance)}


@router.post("/{execution_id}/ajuster")
def ajuster_planning(
    execution_id: str,
    planning: Planning,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, Any]:
    """Revalide `planning` (proposé à la main sur le Gantt) avec le même vérificateur
    déterministe que tout le reste du système, puis persiste comme révision ajustée distincte de
    l'original — jamais en place. Toujours 200, légal ou non : un refus métier n'est pas une
    erreur système (même convention que `ResultatExecution`/`POST /execution`) ; rien n'est
    persisté si `legal` est faux."""
    try:
        _, instance_id, _ = etat.recuperer_execution(execution_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="exécution inconnue") from None

    client_id, instance = etat.recuperer_instance(instance_id)
    verifier_acces_client(utilisateur, client_id)

    verdict = verifier_faisabilite(instance, planning)
    if not verdict.legal:
        return {"legal": False, "violations": [asdict(v) for v in verdict.violations], "planning": None}

    etat.enregistrer_planning_ajuste(execution_id, planning, calculer_makespan(instance, planning))
    return {
        "legal": True,
        "violations": [],
        "planning": {**planning.model_dump(mode="json"), "durees": durees_par_contrainte(instance)},
    }


@router.get("/{execution_id}/ajuste")
def obtenir_planning_ajuste(
    execution_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, Any] | None:
    """`None` (jamais un 404) si cette exécution n'a encore aucune révision ajustée — reste une
    simple lecture côté frontend, sans logique spéciale de gestion d'erreur pour le cas courant
    "rien n'a encore été ajusté"."""
    try:
        _, instance_id, _ = etat.recuperer_execution(execution_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="exécution inconnue") from None

    client_id, instance = etat.recuperer_instance(instance_id)
    verifier_acces_client(utilisateur, client_id)

    planning_ajuste = etat.recuperer_planning_ajuste(execution_id)
    if planning_ajuste is None:
        return None

    return {**planning_ajuste.model_dump(mode="json"), "durees": durees_par_contrainte(instance)}
