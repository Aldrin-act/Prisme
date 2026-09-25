"""Déclenchement d'une exécution : bac à sable + code figé du store (§5.1, §5.5, §7)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from api.autorisation import verifier_acces_client
from api.dependencies import obtenir_registre
from api.etat import (
    EtatAPI,
    obtenir_etat,
    signature_objectifs,
    solveurs_pour_instance_ou_scenario_de_base,
    structure_contraintes,
)
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
    (transparence : distingue "rien à figer" d'un vrai gel appliqué).

    Un scénario (`POST .../scenarios`) sans solveur enregistré à son propre `instance_id` réutilise
    celui de l'instance de base dont il varie (voir `solveurs_pour_instance_ou_scenario_de_base`) —
    son historique d'exécution/planning reste, lui, entièrement le sien."""
    try:
        client_id, instance = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)

    structure = structure_contraintes(instance)
    objectifs = signature_objectifs(instance)
    # instance_id en plus de structure/objectifs : un solveur ne sert que l'instance qui l'a
    # fait générer (plus de partage par signature entre instances d'un même client) — le filtre
    # structure/objectifs reste en plus, pour détecter le cas où l'instance a été modifiée
    # depuis la génération de son propre solveur (devenu incompatible sans être régénéré). Une
    # exception : un scénario (`POST .../scenarios`) sans solveur propre retombe sur celui de
    # l'instance de base dont il varie (voir `solveurs_pour_instance_ou_scenario_de_base`).
    solveurs = solveurs_pour_instance_ou_scenario_de_base(
        etat,
        registre,
        client_id,
        instance_id,
        structure_contraintes=structure,
        signature_objectifs=objectifs,
    )
    if not solveurs:
        raise HTTPException(
            status_code=409,
            detail=(
                f"aucun solveur validé pour instance={instance_id!r} "
                f"(client={client_id!r}, structure={structure!r}, objectifs={objectifs!r})"
            ),
        )
    artefact = solveurs[0]

    planning_precedent = etat.dernier_planning_pour_instance(instance_id) if horizon_gele_jours > 0 else None

    # Un seul instant pour l'exécution ET pour la date enregistrée : il ancre le calendrier ouvré
    # (heures ouvrées, week-end) du solveur, et doit se relire à l'identique à l'affichage.
    date_execution = datetime.now(UTC)
    resultat = executer_solveur_valide(
        registre,
        artefact.id,
        instance,
        planning_precedent=planning_precedent,
        horizon_gele_jours=horizon_gele_jours,
        reference=date_execution,
    )
    execution_id = etat.enregistrer_execution(artefact.id, instance_id, resultat, date_execution=date_execution)
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
