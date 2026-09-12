"""Déclenchement d'une exécution : bac à sable + code figé du store (§5.1, §5.5, §7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.autorisation import verifier_acces_client
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat, signature_objectifs, structure_contraintes
from api.routes.auth import obtenir_utilisateur_courant
from sandbox.runner import ResultatExecution, executer_solveur_valide
from solver_store.registry import Registre

router = APIRouter(prefix="/execution", tags=["execution"])


def executer_pour_instance(
    etat: EtatAPI, registre: Registre, instance_id: str, utilisateur: dict, horizon_gele_jours: int = 0
) -> tuple[str, ResultatExecution, bool]:
    """Chaîne lookup instance → recherche solveur validé → sandbox →
    enregistrement, directement par `instance_id` — aucun intermédiaire.
    `client_id` est résolu depuis l'instance elle-même, jamais fourni par
    l'appelant (élimine tout écart possible entre le client vérifié par le
    contrôle d'accès et celui utilisé pour la recherche de solveur). Un aléa
    (panne, retard...) se traite en réingérant une instance avec ses
    contraintes mises à jour puis en rappelant cette même fonction sur son
    nouvel `instance_id` — aucun mécanisme d'alerte dédié dans le noyau.

    `horizon_gele_jours` (Phase 2, replanification à horizon glissant) : si > 0, va chercher le
    dernier planning *réussi* de cette même instance (`etat.dernier_planning_pour_instance`) et
    le transmet comme `planning_precedent` — un solveur qui ne supporte pas ce paramètre échoue
    explicitement dans `executer_solveur_valide`, jamais une dégradation silencieuse vers un
    solve normal. Le booléen renvoyé indique si un planning précédent a réellement été trouvé
    (transparence : distingue "rien à figer" d'un vrai gel appliqué)."""
    try:
        client_id, instance = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)

    structure = structure_contraintes(instance)
    objectifs = signature_objectifs(instance)
    solveurs = registre.rechercher_solveurs(
        client_id=client_id, structure_contraintes=structure, signature_objectifs=objectifs
    )
    if not solveurs:
        raise HTTPException(
            status_code=409,
            detail=(
                f"aucun solveur validé pour client={client_id!r}, structure={structure!r}, objectifs={objectifs!r}"
            ),
        )
    artefact = solveurs[0]

    planning_precedent = etat.dernier_planning_pour_instance(instance_id) if horizon_gele_jours > 0 else None

    resultat = executer_solveur_valide(
        registre,
        artefact.id,
        instance,
        planning_precedent=planning_precedent,
        horizon_gele_jours=horizon_gele_jours,
    )
    execution_id = etat.enregistrer_execution(artefact.id, instance_id, resultat)
    return execution_id, resultat, planning_precedent is not None


@router.post("/{instance_id}")
def declencher_execution(
    instance_id: str,
    horizon_gele_jours: int = Query(default=0, ge=0),
    etat: EtatAPI = Depends(obtenir_etat),
    registre: Registre = Depends(obtenir_registre),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, str | bool | int | None]:
    execution_id, resultat, planning_precedent_utilise = executer_pour_instance(
        etat, registre, instance_id, utilisateur, horizon_gele_jours=horizon_gele_jours
    )
    return {
        "execution_id": execution_id,
        "reussi": resultat.reussi,
        "erreur": resultat.erreur,
        "horizon_gele_jours": horizon_gele_jours,
        "planning_precedent_utilise": planning_precedent_utilise,
        # Ancrage calendaire stable du Gantt (voir EtatAPI.recuperer_date_execution) — évite un
        # aller-retour supplémentaire pour le connaître juste après avoir déclenché l'exécution.
        "date_execution": etat.recuperer_date_execution(execution_id),
    }
