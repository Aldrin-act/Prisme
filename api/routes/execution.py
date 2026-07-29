"""Déclenchement d'une exécution : bac à sable + code figé du store (§5.1, §5.5, §7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.autorisation import verifier_acces_client
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat, signature_objectifs, structure_contraintes
from api.routes.auth import obtenir_utilisateur_courant
from sandbox.runner import ResultatExecution, executer_solveur_valide
from solver_store.registry import Registre

router = APIRouter(prefix="/execution", tags=["execution"])


def executer_pour_projet(
    etat: EtatAPI, registre: Registre, projet_id: str, client_id: str, utilisateur: dict
) -> tuple[str, ResultatExecution]:
    """Chaîne lookup projet → instance courante → recherche solveur validé →
    sandbox → enregistrement (§annexe modèle Instance/Projet : chaque projet
    a son planning attitré, indépendant des autres projets réutilisant la
    même instance). Un aléa (panne, retard...) se traite en réingérant une
    instance avec ses contraintes mises à jour puis en la ré-associant à ce
    projet (`associer_instance_projet`), avant de rappeler cette même
    fonction — aucun mécanisme d'alerte dédié dans le noyau."""
    try:
        projet = etat.recuperer_projet(projet_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="projet inconnu") from None

    verifier_acces_client(utilisateur, projet.client_id)

    if projet.instance_id is None:
        raise HTTPException(status_code=409, detail="ce projet n'a pas encore d'instance T-R-C-O associée")
    _, instance = etat.recuperer_instance(projet.instance_id)

    structure = structure_contraintes(instance)
    objectifs = signature_objectifs(instance)
    solveurs = registre.rechercher_solveurs(
        client_id=client_id, structure_contraintes=structure, signature_objectifs=objectifs
    )
    if not solveurs:
        raise HTTPException(
            status_code=409,
            detail=(
                f"aucun solveur validé pour client={client_id!r}, "
                f"structure={structure!r}, objectifs={objectifs!r}"
            ),
        )
    artefact = solveurs[0]

    resultat = executer_solveur_valide(registre, artefact.id, instance)
    execution_id = etat.enregistrer_execution(artefact.id, projet_id, projet.instance_id, resultat)
    return execution_id, resultat


@router.post("/{projet_id}")
def declencher_execution(
    projet_id: str,
    client_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    registre: Registre = Depends(obtenir_registre),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, str | bool | None]:
    execution_id, resultat = executer_pour_projet(etat, registre, projet_id, client_id, utilisateur)
    return {"execution_id": execution_id, "reussi": resultat.reussi, "erreur": resultat.erreur}
