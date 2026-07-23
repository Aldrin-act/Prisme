"""Canal de supervision (lecture seule) : donne au dashboard une vue globale
de l'état du système — instances en attente, historique des exécutions,
solveurs enregistrés, santé API/sandbox. Jamais de code source ici :
`code_source` ne sort que par `/audit/{execution_id}` sur demande
explicite (§5.1, §5.5). Chaque vue est filtrée par le `client_id` du
compte authentifié (§ `api/autorisation.py`) — sauf l'admin, qui voit tout."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from api.autorisation import client_id_pour_filtre
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat
from api.routes.auth import obtenir_utilisateur_courant
from sandbox.runner import sandbox_disponible
from solver_store.registry import Registre

router = APIRouter(prefix="/supervision", tags=["supervision"])


@router.get("/instances")
def lister_instances(
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> list[dict[str, Any]]:
    return etat.lister_instances(client_id=client_id_pour_filtre(utilisateur))


@router.get("/executions")
def lister_executions(
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> list[dict[str, Any]]:
    return etat.lister_executions(client_id=client_id_pour_filtre(utilisateur))


@router.get("/solveurs")
def lister_solveurs(
    registre: Registre = Depends(obtenir_registre),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> list[dict[str, Any]]:
    return [
        {
            "id": artefact.id,
            "client_id": artefact.client_id,
            "structure_contraintes": artefact.structure_contraintes,
            "signature_objectifs": artefact.signature_objectifs,
            "date_validation": artefact.date_validation,
            "empreinte_sha256": artefact.empreinte_sha256,
        }
        for artefact in registre.rechercher_solveurs(client_id=client_id_pour_filtre(utilisateur))
    ]


@router.get("/sante")
def sante() -> dict[str, bool]:
    return {"api": True, "sandbox_docker": sandbox_disponible()}
