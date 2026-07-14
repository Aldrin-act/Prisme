"""Déclenchement d'une exécution : bac à sable + code figé du store (§5.1, §5.5, §7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat, structure_contraintes
from sandbox.runner import executer_solveur_valide
from solver_store.registry import Registre

router = APIRouter(prefix="/execution", tags=["execution"])


@router.post("/{instance_id}")
def declencher_execution(
    instance_id: str,
    client_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    registre: Registre = Depends(obtenir_registre),
) -> dict[str, str | bool | None]:
    try:
        _, instance = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    structure = structure_contraintes(instance)
    solveurs = registre.rechercher_solveurs(client_id=client_id, structure_contraintes=structure)
    if not solveurs:
        raise HTTPException(
            status_code=409,
            detail=f"aucun solveur validé pour client={client_id!r}, structure={structure!r}",
        )
    artefact = solveurs[0]

    resultat = executer_solveur_valide(registre, artefact.id, instance)
    execution_id = etat.enregistrer_execution(artefact.id, resultat)

    return {"execution_id": execution_id, "reussi": resultat.reussi, "erreur": resultat.erreur}
