"""Canal de supervision (lecture seule) : donne au dashboard une vue globale
de l'état du système — instances en attente, historique des exécutions,
solveurs enregistrés, santé API/sandbox — sans passer par le fil
alerte -> déclenchement. Jamais de code source ici : `code_source` ne sort
que par `/audit/{execution_id}` sur demande explicite (§5.1, §5.5)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat
from sandbox.runner import sandbox_disponible
from solver_store.registry import Registre

router = APIRouter(prefix="/supervision", tags=["supervision"])


@router.get("/instances")
def lister_instances(etat: EtatAPI = Depends(obtenir_etat)) -> list[dict[str, Any]]:
    return etat.lister_instances()


@router.get("/executions")
def lister_executions(etat: EtatAPI = Depends(obtenir_etat)) -> list[dict[str, Any]]:
    return etat.lister_executions()


@router.get("/solveurs")
def lister_solveurs(registre: Registre = Depends(obtenir_registre)) -> list[dict[str, Any]]:
    return [
        {
            "id": artefact.id,
            "client_id": artefact.client_id,
            "structure_contraintes": artefact.structure_contraintes,
            "date_validation": artefact.date_validation,
            "empreinte_sha256": artefact.empreinte_sha256,
        }
        for artefact in registre.rechercher_solveurs()
    ]


@router.get("/sante")
def sante() -> dict[str, bool]:
    return {"api": True, "sandbox_docker": sandbox_disponible()}
