"""Déclenche le pipeline de génération de solveur multi-agents avec boucle
de réparation bornée (`generation.pipeline_avec_boucle`, Étape 6 — déjà
construite : orchestrateur → analyste → architecte → développeur → testeur
→ [Reviewer/Debugger, jusqu'à 3 tentatives] → optimiseur → documentation)
depuis une instance déjà ingérée. La boucle reste bornée : après épuisement
des tentatives, l'échec est renvoyé tel quel à l'humain, jamais masqué par
un acharnement automatique (§6.5).

Distinct de l'agent de compréhension (`adapters/agent_comprehension/`) : ici
on génère du **code** de solveur, générique à l'ensemble du DSL — l'instance
ne sert qu'à retrouver le `client_id` et la clé de matching
(`structure_contraintes` + `signature_objectifs`) sous laquelle enregistrer
le résultat, jamais comme donnée injectée dans le prompt (le code produit
n'est pas spécifique à cette instance, §5.2 "generate once, re-execute
many")."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.autorisation import verifier_acces_client
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat
from api.etat import signature_objectifs as calculer_signature_objectifs
from api.etat import structure_contraintes
from api.routes.auth import obtenir_utilisateur_courant
from generation.pipeline_avec_boucle import tenter_generation_avec_boucle
from solver_store.registry import Registre

router = APIRouter(prefix="/generation", tags=["generation"])


@router.post("/{instance_id}")
def generer_solveur(
    instance_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    registre: Registre = Depends(obtenir_registre),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Synchrone et bloquant (plusieurs appels LLM — 8 agents, jusqu'à 3
    tentatives de réparation — plus exécution sandboxée et cascade complète
    à chaque tentative : potentiellement plusieurs minutes). Même convention
    que `/projets/{id}/generer-instance` (§5.4 bis) : pas de file d'attente/
    job séparé pour l'instant, le client attend la réponse aussi longtemps
    qu'il le faut (timeout désactivé côté frontend)."""
    try:
        client_id, instance = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)

    structure = structure_contraintes(instance)
    signature_obj = calculer_signature_objectifs(instance)

    resultat = tenter_generation_avec_boucle()
    nombre_tentatives = resultat.boucle_reparation.nombre_tentatives

    if not resultat.reussi:
        erreur: str | None = None
        if resultat.validation_statique is not None and not resultat.validation_statique.valide:
            erreur = "code rejeté par la validation statique : " + "; ".join(
                resultat.validation_statique.violations
            )
        elif resultat.erreur_execution is not None:
            erreur = f"erreur à l'exécution du code : {resultat.erreur_execution}"

        echecs_cascade = list(resultat.verdict_cascade.echecs) if resultat.verdict_cascade else []
        return {
            "reussi": False,
            "id_solveur": None,
            "structure_contraintes": structure,
            "signature_objectifs": signature_obj,
            "nombre_tentatives": nombre_tentatives,
            "erreur": erreur,
            "echecs_cascade": [
                {"nom": d.nom, "brique_en_echec": d.brique_en_echec, "details": list(d.details)}
                for d in echecs_cascade
            ],
        }

    assert resultat.verdict_cascade is not None  # garanti par ResultatPipelineAvecBoucle.reussi
    id_solveur = registre.enregistrer_solveur(
        resultat.code_final, structure, resultat.verdict_cascade, client_id, signature_obj
    )
    return {
        "reussi": True,
        "id_solveur": id_solveur,
        "structure_contraintes": structure,
        "signature_objectifs": signature_obj,
        "nombre_tentatives": nombre_tentatives,
        "erreur": None,
        "echecs_cascade": [],
    }
