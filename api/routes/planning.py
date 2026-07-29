"""Canal opérationnel (§5.1, §5.5) : retourne le planning en JSON, à chaque itération."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.autorisation import verifier_acces_client
from api.etat import EtatAPI, durees_par_contrainte, obtenir_etat
from api.routes.auth import obtenir_utilisateur_courant

router = APIRouter(prefix="/planning", tags=["planning"])


@router.get("/{execution_id}")
def obtenir_planning(
    execution_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, Any]:
    try:
        _, projet_id, instance_id, resultat = etat.recuperer_execution(execution_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="exécution inconnue") from None

    # Accès vérifié via le projet (source de vérité pour le cloisonnement,
    # §7) — jamais via l'instance, qui peut avoir été supprimée depuis
    # (`instance_id` nullable, voir `EtatAPI.supprimer_instance`).
    projet = etat.recuperer_projet(projet_id)
    verifier_acces_client(utilisateur, projet.client_id)

    if resultat.planning is None:
        raise HTTPException(status_code=422, detail=resultat.erreur or "aucun planning disponible")

    # Durées ajoutées pour le Gantt du dashboard : `Planning` n'a délibérément
    # pas de champ durée (§ dsl/schema/planning.py) — elle vit sur
    # `CompatibiliteRessourceTache`, propre au couple (tâche, ressource).
    # Dégradé en {} si l'instance sous-jacente a été supprimée depuis
    # l'exécution : le planning reste consultable, juste sans les durées.
    durees: dict[str, int] = {}
    if instance_id is not None:
        try:
            _, instance = etat.recuperer_instance(instance_id)
        except KeyError:
            pass
        else:
            durees = durees_par_contrainte(instance)

    return {**resultat.planning.model_dump(mode="json"), "durees": durees}
