"""Point d'entrée unique pour une intégration ERP externe (§5.1, §5.4, §5.5) :
un seul appel qui ingère un payload, exécute le solveur déjà validé pour ce
client/cette structure de contraintes/ces objectifs, et renvoie directement
le planning — sans que l'appelant ait à enchaîner lui-même les appels
séparés que ça recouvre normalement (`POST /ingestion/{client_id}` ou
`POST /adapters/.../ingerer`, puis `POST /execution/{instance_id}`, puis
`GET /planning/{execution_id}`, voir ces modules).

Ne génère jamais de solveur à la volée (principe fondateur "generate once,
re-execute many", voir CLAUDE.md) : si aucun solveur validé n'existe pour
cette structure de contraintes et ces objectifs, l'appel échoue avec un 409
explicite (propagé depuis `executer_pour_instance`) — la génération reste un
geste humain, hors ligne, déclenché depuis le Générateur de solveurs, jamais
un effet de bord d'un appel ERP.

Trois entrées, une par forme de donnée reçue :
- `POST /greensig` — lit GreenSIG via `adapters.greensig.extraire_et_traduire`
  (base Postgres directe ou API HTTP publique selon `GREENSIG_MODE`, voir
  `adapters/greensig/service.py`) ; pas de `{client_id}` dans le chemin, le
  client GreenSIG est fixe (`CLIENT_ID_GREENSIG`). Déclarée avant `/{client_id}`
  ci-dessous : un chemin littéral doit toujours être enregistré avant un
  chemin paramétré qui matcherait la même forme (Starlette résout dans
  l'ordre de déclaration), sinon `/greensig` ne serait jamais atteinte.
- `POST /{client_id}` — payload T-R-C-O déjà canonique.
- `POST /{client_id}/comprehension` — texte brut dans un format propriétaire
  quelconque, traduit par l'agent de compréhension (`adapters/agent_comprehension/`),
  pour un ERP sans adaptateur dédié écrit à la main.

Chacune ne fait que composer des briques déjà existantes ailleurs (les mêmes
fonctions de traduction que `api/routes/adapters.py`, la même
`executer_pour_instance` que `POST /execution/{instance_id}`) — jamais une
réimplémentation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError

from adapters.agent_comprehension import comprendre_donnees_erp
from adapters.greensig import extraire_et_traduire
from api.autorisation import verifier_acces_client
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, SecteurActivite, durees_par_contrainte, obtenir_etat, structure_contraintes
from api.input_validation import erreurs_serialisables, valider_payload_trco
from api.routes.adapters import CLIENT_ID_GREENSIG
from api.routes.auth import obtenir_utilisateur_courant
from api.routes.execution import executer_pour_instance
from dsl.schema import InstanceTRCO
from generation.agents.base import ErreurReponseAgentInvalide
from generation.agents.client_llm import construire_modele_comprehension
from sandbox.runner import ResultatExecution
from solver_store.registry import Registre

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

router = APIRouter(prefix="/planifier", tags=["planifier"])


def _reponse_planning(
    instance_id: str, execution_id: str, instance: InstanceTRCO, resultat: ResultatExecution
) -> dict[str, object]:
    """Forme de réponse commune aux trois routes ci-dessous — construite une
    seule fois plutôt que trois fois, voir docstring du module."""
    planning = None
    if resultat.planning is not None:
        planning = {**resultat.planning.model_dump(mode="json"), "durees": durees_par_contrainte(instance)}
    return {
        "instance_id": instance_id,
        "execution_id": execution_id,
        "structure_contraintes": structure_contraintes(instance),
        "reussi": resultat.reussi,
        "erreur": resultat.erreur,
        "planning": planning,
    }


@router.post("/greensig")
def planifier_depuis_greensig(
    nom_projet: str | None = None,
    secteur_activite: SecteurActivite | None = None,
    etat: EtatAPI = Depends(obtenir_etat),
    registre: Registre = Depends(obtenir_registre),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Lit GreenSIG (base directe ou API HTTP publique selon `GREENSIG_MODE`,
    voir `adapters/greensig/service.py`), puis compose exactement comme
    `planifier()` — même garde-fou, même composition ingestion+exécution en
    un seul appel. Pas de `{client_id}` dans le chemin : le client GreenSIG
    est fixe."""
    try:
        instance = extraire_et_traduire()
    except (psycopg.OperationalError, httpx.HTTPError) as erreur:
        raise HTTPException(status_code=503, detail="service GreenSIG injoignable") from erreur
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur

    instance_id = etat.enregistrer_instance(
        CLIENT_ID_GREENSIG, instance, nom_projet=nom_projet, secteur_activite=secteur_activite
    )

    execution_id, resultat = executer_pour_instance(etat, registre, instance_id, utilisateur)

    return _reponse_planning(instance_id, execution_id, instance, resultat)


@router.post("/{client_id}")
def planifier(
    client_id: str,
    payload: dict[str, Any],
    nom_projet: str | None = None,
    secteur_activite: SecteurActivite | None = None,
    etat: EtatAPI = Depends(obtenir_etat),
    registre: Registre = Depends(obtenir_registre),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Ingère `payload` (T-R-C-O canonique) pour `client_id`, exécute le
    solveur correspondant, renvoie le planning en un seul aller-retour."""
    verifier_acces_client(utilisateur, client_id)
    instance = valider_payload_trco(payload)
    instance_id = etat.enregistrer_instance(
        client_id, instance, nom_projet=nom_projet, secteur_activite=secteur_activite
    )

    execution_id, resultat = executer_pour_instance(etat, registre, instance_id, utilisateur)

    return _reponse_planning(instance_id, execution_id, instance, resultat)


class RequeteComprehension(BaseModel):
    donnees_brutes: str
    nom_projet: str | None = None
    secteur_activite: SecteurActivite | None = None


@router.post("/{client_id}/comprehension")
def planifier_via_comprehension(
    client_id: str,
    requete: RequeteComprehension,
    etat: EtatAPI = Depends(obtenir_etat),
    registre: Registre = Depends(obtenir_registre),
    modele: BaseChatModel = Depends(construire_modele_comprehension),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Pour un ERP sans adaptateur dédié : traduit `donnees_brutes` (texte
    libre, n'importe quel format) via l'agent de compréhension, puis compose
    exactement comme `planifier()` ci-dessus. Le même garde-fou déterministe
    (§6.7) tranche la traduction proposée par l'agent, comme pour tout autre
    payload — un rejet reste un 422 explicite, jamais masqué."""
    verifier_acces_client(utilisateur, client_id)
    try:
        resultat_comprehension = comprendre_donnees_erp(
            modele, requete.donnees_brutes, secteur_activite=requete.secteur_activite
        )
    except ErreurReponseAgentInvalide as erreur:
        raise HTTPException(status_code=502, detail=f"agent de compréhension : {erreur}") from erreur

    instance = valider_payload_trco(resultat_comprehension.instance_brute)  # lève déjà un 422 si invalide

    instance_id = etat.enregistrer_instance(
        client_id,
        instance,
        description_metier=resultat_comprehension.description_metier,
        nom_projet=requete.nom_projet,
        secteur_activite=requete.secteur_activite,
    )

    execution_id, resultat = executer_pour_instance(etat, registre, instance_id, utilisateur)

    reponse = _reponse_planning(instance_id, execution_id, instance, resultat)
    reponse["description_metier"] = resultat_comprehension.description_metier
    reponse["avertissements"] = list(resultat_comprehension.avertissements)
    return reponse
