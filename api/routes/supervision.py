"""Canal de supervision : la vue lecture seule d'origine (instances en
attente, historique des exécutions, solveurs enregistrés, santé API/sandbox)
plus l'agent de supervision (§2, MT7) — détecte des signaux (signature
orpheline, échecs répétés, instance en attente de replanification) sur
l'historique d'un client et **propose** une action, jamais ne l'applique
elle-même : `POST /analyser` déclenche une passe (aussi joignable en
périodique, voir `supervision/planificateur.py`), `GET /propositions` liste
ce qui attend une décision, `POST /propositions/{id}/decision` enregistre
cette décision et, si acceptée, déclenche l'action correspondante en
réutilisant telle quelle la route existante (génération, exécution ou
diagnostic) — jamais une réimplémentation. Jamais de code source ici :
`code_source` ne sort que par `/audit/{execution_id}` sur demande
explicite (§5.1, §5.5). Chaque vue est filtrée par le `client_id` du
compte authentifié (§ `api/autorisation.py`) — sauf l'admin, qui voit tout."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.autorisation import client_id_pour_filtre, verifier_acces_client
from api.dependencies import obtenir_registre
from api.etat import Decision, EtatAPI, PropositionSupervision, SecteurActivite, obtenir_etat
from api.routes.auth import obtenir_utilisateur_courant
from api.routes.execution import executer_pour_instance
from api.routes.generation import demarrer_generation_solveur
from diagnostics import construire_solveur_sandbox, diagnostiquer
from generation.agents.client_llm import construire_modele_supervision
from sandbox.runner import sandbox_disponible
from solver_store.registry import Registre
from supervision import analyser_et_proposer

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

router = APIRouter(prefix="/supervision", tags=["supervision"])


@router.get("/instances")
def lister_instances(
    nom_projet: str | None = None,
    secteur_activite: SecteurActivite | None = None,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> list[dict[str, Any]]:
    return etat.lister_instances(
        client_id=client_id_pour_filtre(utilisateur), nom_projet=nom_projet, secteur_activite=secteur_activite
    )


@router.get("/noms-projet")
def lister_noms_projet(
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> list[dict[str, Any]]:
    """Noms de projet distincts déjà utilisés par ce client (avec leur
    nombre d'instances) — alimente l'auto-complétion du champ `nom_projet` à
    l'ingestion, pour éviter qu'une faute de frappe fragmente silencieusement
    un regroupement."""
    return etat.lister_noms_projet(client_id=client_id_pour_filtre(utilisateur))


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


# --- Agent de supervision (MT7) --------------------------------------------


def _proposition_en_dict(p: PropositionSupervision) -> dict[str, Any]:
    return {
        "proposition_id": p.id,
        "client_id": p.client_id,
        "type_signal": p.type_signal,
        "action_suggeree": p.action_suggeree,
        "resume": p.resume,
        "priorite": p.priorite,
        "details": list(p.details),
        "date_creation": p.date_creation,
        "instance_id": p.instance_id,
        "execution_ids": list(p.execution_ids),
        "structure_contraintes": p.structure_contraintes,
        "signature_objectifs": p.signature_objectifs,
        "decision": p.decision,
        "horodatage_decision": p.horodatage_decision,
        "commentaire": p.commentaire,
    }


class RequeteAnalyseSupervision(BaseModel):
    client_id: str | None = None


class RequeteDecisionProposition(BaseModel):
    decision: Decision
    commentaire: str | None = None


def _clients_a_analyser(requete_client_id: str | None, utilisateur: dict, etat: EtatAPI) -> list[str]:
    """Contrat différent de `sources.py::_client_id_effectif` : ici `None`
    pour un admin signifie « tous les clients connus », jamais une erreur —
    la boucle périodique (`supervision/planificateur.py`) appelle
    `analyser_et_proposer` directement par client, cette fonction ne sert
    qu'au déclenchement manuel."""
    if utilisateur.get("role") == "admin":
        if requete_client_id:
            return [requete_client_id]
        return [c["client_id"] for c in etat.lister_clients()]
    if requete_client_id:
        verifier_acces_client(utilisateur, requete_client_id)
    client_id = utilisateur.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="compte sans client_id associé")
    return [client_id]


@router.post("/analyser")
def analyser(
    requete: RequeteAnalyseSupervision = RequeteAnalyseSupervision(),
    etat: EtatAPI = Depends(obtenir_etat),
    registre: Registre = Depends(obtenir_registre),
    modele: BaseChatModel = Depends(construire_modele_supervision),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> list[dict[str, Any]]:
    clients = _clients_a_analyser(requete.client_id, utilisateur, etat)
    propositions: list[PropositionSupervision] = []
    for client_id in clients:
        propositions.extend(analyser_et_proposer(etat, registre, modele, client_id))
    return [_proposition_en_dict(p) for p in propositions]


@router.get("/propositions")
def lister_propositions(
    en_attente: bool = False,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> list[dict[str, Any]]:
    return etat.lister_propositions(client_id=client_id_pour_filtre(utilisateur), en_attente_seulement=en_attente)


def _dispatcher_action(
    proposition: PropositionSupervision, etat: EtatAPI, registre: Registre, utilisateur: dict
) -> dict[str, Any]:
    """Sur acceptation, déclenche l'action correspondante en réutilisant la
    route existante — jamais une réimplémentation. Le clic « Accepter » EST
    la décision humaine explicite qui autorise cette action (§ principe
    fondateur, humain-dans-la-boucle)."""
    if proposition.action_suggeree in ("regenerer_solveur", "executer") and proposition.instance_id is None:
        raise HTTPException(
            status_code=422, detail="l'instance associée à cette proposition a depuis été supprimée"
        )

    if proposition.action_suggeree == "regenerer_solveur":
        resultat = demarrer_generation_solveur(proposition.instance_id, etat, registre, utilisateur)
        return {"action": "regenerer_solveur", "job_id": resultat["job_id"]}

    if proposition.action_suggeree == "executer":
        execution_id, resultat_execution = executer_pour_instance(
            etat, registre, proposition.instance_id, utilisateur
        )
        return {"action": "executer", "execution_id": execution_id, "reussi": resultat_execution.reussi}

    # "diagnostiquer" — `diagnostiquer()` exige un planning non nul
    # (`diagnostics/attribution.py`) ; un échec peut avoir `planning=None`
    # (solveur introuvable, crash/timeout sandbox) donc pas forcément
    # diagnosable. Essaie du plus récent au plus ancien, s'arrête au premier
    # exploitable plutôt que de planter sur le premier échec venu.
    for execution_id in proposition.execution_ids:
        try:
            id_solveur, instance_id, resultat_execution = etat.recuperer_execution(execution_id)
        except KeyError:
            continue
        if resultat_execution.planning is None:
            continue
        _, instance = etat.recuperer_instance(instance_id)
        solveur = construire_solveur_sandbox(registre, id_solveur)
        diagnostic = diagnostiquer(
            solveur,
            instance,
            resultat_execution.planning,
            motif_declenchement=f"proposition de supervision {proposition.id} acceptée",
        )
        return {
            "action": "diagnostiquer",
            "execution_id": execution_id,
            "cause": diagnostic.cause,
            "proposition": diagnostic.proposition,
        }
    raise HTTPException(
        status_code=422, detail="aucune exécution diagnosable parmi les échecs récents (aucun planning produit)"
    )


@router.post("/propositions/{proposition_id}/decision")
def decider(
    proposition_id: str,
    requete: RequeteDecisionProposition,
    etat: EtatAPI = Depends(obtenir_etat),
    registre: Registre = Depends(obtenir_registre),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, Any]:
    try:
        proposition = etat.recuperer_proposition(proposition_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="proposition inconnue") from None

    verifier_acces_client(utilisateur, proposition.client_id)
    etat.decider_proposition(proposition_id, requete.decision, commentaire=requete.commentaire)

    reponse: dict[str, Any] = {"proposition_id": proposition_id, "decision": requete.decision}
    if requete.decision == "acceptee":
        reponse["resultat"] = _dispatcher_action(proposition, etat, registre, utilisateur)
    return reponse
