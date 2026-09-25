"""Canal de supervision : la vue lecture seule d'origine (instances en
attente, historique des exécutions, solveurs enregistrés, santé API/sandbox)
plus l'agent de supervision (§2, MT7) — détecte des signaux (signature
orpheline, échecs répétés, instance en attente de replanification) sur
l'historique d'un client, atelier par atelier, et **propose** une action, jamais ne l'applique
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
from api.etat import Decision, EtatAPI, PropositionSupervision, obtenir_etat
from api.routes.auth import obtenir_utilisateur_courant
from api.routes.execution import executer_pour_instance
from api.routes.generation import demarrer_generation_solveur
from diagnostics import construire_solveur_sandbox, diagnostiquer
from generation.agents.client_llm import construire_modele_supervision
from sandbox.runner import sandbox_disponible
from solver_store.registry import Registre
from supervision import (
    SolveurHorsAtelier,
    analyser_et_proposer,
    analyser_instance,
    evaluer_solveur,
    solveur_a_evaluer,
)

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

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
            "instance_id": artefact.instance_id,
            "structure_contraintes": artefact.structure_contraintes,
            "signature_objectifs": artefact.signature_objectifs,
            "date_validation": artefact.date_validation,
            "empreinte_sha256": artefact.empreinte_sha256,
            "algorithme": artefact.algorithme,
            "algorithme_raison": artefact.algorithme_raison,
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
        "commande_id": p.commande_id,
    }


class RequeteAnalyseSupervision(BaseModel):
    client_id: str | None = None
    # Entrée de l'analyse d'un atelier : `instance_id` + `id_solveur` (le solveur de cet atelier
    # dont on veut superviser les exécutions). `id_solveur` peut rester vide pour un atelier qui
    # n'a encore aucun solveur — c'est justement ce que l'analyse doit signaler. Sans
    # `instance_id`, tous les ateliers du ou des clients visés sont analysés un par un.
    instance_id: str | None = None
    id_solveur: str | None = None


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
    """Analyse atelier par atelier. `instance_id` fourni : ce seul atelier (accès vérifié sur le
    client propriétaire de l'instance). Sinon, chaque atelier du ou des clients visés, l'un après
    l'autre — chacun avec sa propre détection et sa propre rédaction LLM."""
    if requete.id_solveur is not None and requete.instance_id is None:
        raise HTTPException(status_code=422, detail="id_solveur exige instance_id (l'atelier de ce solveur)")

    if requete.instance_id is not None:
        try:
            client_id, _ = etat.recuperer_instance(requete.instance_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="instance inconnue") from None
        verifier_acces_client(utilisateur, client_id)
        try:
            propositions = analyser_instance(etat, registre, modele, requete.instance_id, requete.id_solveur)
        except SolveurHorsAtelier as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from erreur
        return [_proposition_en_dict(p) for p in propositions]

    clients = _clients_a_analyser(requete.client_id, utilisateur, etat)
    propositions: list[PropositionSupervision] = []
    for client_id in clients:
        propositions.extend(analyser_et_proposer(etat, registre, modele, client_id))
    return [_proposition_en_dict(p) for p in propositions]


class RequeteEvaluationSolveur(BaseModel):
    instance_id: str
    # Absent : le solveur actif le plus récent de l'atelier.
    id_solveur: str | None = None


@router.post("/evaluer-solveur")
def evaluer_solveur_atelier(
    requete: RequeteEvaluationSolveur,
    etat: EtatAPI = Depends(obtenir_etat),
    registre: Registre = Depends(obtenir_registre),
    modele: BaseChatModel = Depends(construire_modele_supervision),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, Any]:
    """Faut-il régénérer le solveur de cet atelier ? Renvoie un constat argumenté par changement
    (contrainte ou objectif ajouté/retiré, algorithme) — preuves à l'appui : essai réel en bac à
    sable, lecture du code, Benchmarker (voir `supervision/adequation.py`). Seul un constat
    « bloquant » recommande de régénérer. Rien n'est enregistré ni déclenché : c'est une
    indication pour un humain. `POST /analyser` fait la même vérification et en tire une
    proposition « solveur à régénérer » quand il le faut."""
    try:
        client_id, _ = etat.recuperer_instance(requete.instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None
    verifier_acces_client(utilisateur, client_id)
    try:
        solveur = solveur_a_evaluer(etat, registre, client_id, requete.instance_id, requete.id_solveur)
    except SolveurHorsAtelier as erreur:
        raise HTTPException(status_code=422, detail=str(erreur)) from erreur
    if solveur is None:
        raise HTTPException(
            status_code=404, detail="aucun solveur actif pour cet atelier — un solveur doit d'abord être généré"
        )
    return evaluer_solveur(etat, registre, modele, requete.instance_id, solveur).en_dict()


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
    if proposition.action_suggeree == "aucune":
        # commande_en_retard — purement informatif, aucun retard déjà constaté par le planning
        # actuel ne peut être rattrapé par une action système. Accepter sert seulement à faire
        # remonter l'alerte pour une action humaine hors système.
        return {"action": "aucune"}

    if proposition.action_suggeree in ("regenerer_solveur", "executer") and proposition.instance_id is None:
        raise HTTPException(
            status_code=422, detail="l'instance associée à cette proposition a depuis été supprimée"
        )

    if proposition.action_suggeree == "regenerer_solveur":
        resultat = demarrer_generation_solveur(proposition.instance_id, etat, registre, utilisateur)
        return {"action": "regenerer_solveur", "job_id": resultat["job_id"]}

    if proposition.action_suggeree == "executer":
        execution_id, resultat_execution, _ = executer_pour_instance(
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
