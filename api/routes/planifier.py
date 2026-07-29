"""Point d'entrée unique pour une intégration ERP externe (§5.1, §5.4, §5.5) :
un seul appel qui ingère un payload T-R-C-O, exécute le solveur déjà validé
pour ce client/cette structure de contraintes/ces objectifs, et renvoie
directement le planning — sans que l'appelant ait à enchaîner lui-même les
appels séparés que ça recouvre normalement (`POST /ingestion/{client_id}`,
un projet wrapper implicite, puis `POST /execution/{projet_id}` puis
`GET /planning/{execution_id}`, voir ces modules).

Un projet sans nom ni données brutes (`donnees_brutes=""`, ce payload est déjà
T-R-C-O canonique, pas de l'ERP brut à convertir) est créé à la volée pour
porter l'instance ingérée — l'exécution reste toujours déclenchée par projet
(§annexe modèle Instance/Projet), même pour ce chemin one-shot qui n'a pas de
notion de projet dans son contrat d'origine.

Ne génère jamais de solveur à la volée (principe fondateur "generate once,
re-execute many", voir CLAUDE.md) : si aucun solveur validé n'existe pour
cette structure de contraintes et ces objectifs, l'appel échoue avec un 409
explicite (propagé depuis `executer_pour_projet`) — la génération reste un
geste humain, hors ligne, déclenché depuis le Générateur de solveurs, jamais
un effet de bord d'un appel ERP.

Un ERP qui ne parle pas encore T-R-C-O passe par un adaptateur
(`adapters.py` : GreenSIG, tableur, agent de compréhension...) pour obtenir
d'abord ce payload — ce module ne remplace pas cette étape, il compose ce
qui vient après elle."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from api.autorisation import verifier_acces_client
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, durees_par_contrainte, obtenir_etat, structure_contraintes
from api.input_validation import valider_payload_trco
from api.routes.auth import obtenir_utilisateur_courant
from api.routes.execution import executer_pour_projet
from solver_store.registry import Registre

router = APIRouter(prefix="/planifier", tags=["planifier"])


@router.post("/{client_id}")
def planifier(
    client_id: str,
    payload: dict[str, Any],
    etat: EtatAPI = Depends(obtenir_etat),
    registre: Registre = Depends(obtenir_registre),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Ingère `payload` (T-R-C-O canonique) pour `client_id`, exécute le
    solveur correspondant, renvoie le planning en un seul aller-retour."""
    verifier_acces_client(utilisateur, client_id)
    instance = valider_payload_trco(payload)
    instance_id = etat.enregistrer_instance(client_id, instance)
    projet_id = etat.enregistrer_projet(client_id, donnees_brutes="")
    etat.associer_instance_projet(projet_id, instance_id)

    execution_id, resultat = executer_pour_projet(etat, registre, projet_id, client_id, utilisateur)

    planning = None
    if resultat.planning is not None:
        planning = {**resultat.planning.model_dump(mode="json"), "durees": durees_par_contrainte(instance)}

    return {
        "instance_id": instance_id,
        "projet_id": projet_id,
        "execution_id": execution_id,
        "structure_contraintes": structure_contraintes(instance),
        "reussi": resultat.reussi,
        "erreur": resultat.erreur,
        "planning": planning,
    }
