"""Réception du payload T-R-C-O canonique venant d'un adaptateur ERP (§5.1, §5.5)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError

from adapters.commande_derivation import Commande, deriver_echeances_par_commande
from api.autorisation import client_id_pour_filtre, verifier_acces_client
from api.comparaison_scenarios import calculer_metriques, calculer_statut_commande
from api.etat import CommandeEnregistree, EtatAPI, obtenir_etat, structure_contraintes
from api.input_validation import erreurs_serialisables, valider_payload_trco
from api.routes.auth import obtenir_utilisateur_courant
from dsl.schema import InstanceTRCO, Objectif

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


class RequeteModificationObjectifs(BaseModel):
    objectifs: list[Objectif] = Field(min_length=1)


class RequeteNouvelleCommande(BaseModel):
    taches: list[str] = Field(min_length=1)
    date_limite: int | None = Field(default=None, ge=0)


def _ressources_manquantes_par_rapport_a_la_base(base: InstanceTRCO, scenario: InstanceTRCO) -> set[str]:
    """Un scénario compare des façons différentes de faire tourner le MÊME atelier — jamais deux
    ateliers différents (une instance représente un atelier, voir CLAUDE.md). Le scénario peut
    ajouter des ressources (ex. « et si on achetait une nouvelle machine ? ») mais ne peut pas en
    retirer une déjà présente sur l'instance de base : un ensemble de ressources disjoint
    signalerait un atelier différent, pas une variante du même."""
    return {r.id for r in base.ressources} - {r.id for r in scenario.ressources}


@router.post("/{client_id}")
def ingerer_instance(
    client_id: str,
    payload: dict[str, Any],
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, str]:
    """Valide le payload (garde-fou amont, §6.7) et le met en attente
    d'exécution. Pour modifier une instance déjà ingérée, voir
    `PUT /{instance_id}` ci-dessous — modification en place, jamais une
    nouvelle instance."""
    verifier_acces_client(utilisateur, client_id)
    instance = valider_payload_trco(payload)
    instance_id = etat.enregistrer_instance(client_id, instance, canal_ingestion="manuel")
    return {"instance_id": instance_id, "structure_contraintes": structure_contraintes(instance)}


@router.get("/commandes")
def lister_toutes_commandes(
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> list[dict[str, object]]:
    """Toutes les commandes de tous les ateliers (instances) du client authentifié — sans filtre
    pour un admin, voir `client_id_pour_filtre` (même patron que `supervision.py::lister_instances`).
    Même calcul de statut, à la volée, que `lister_commandes_instance` plus bas, mais un seul
    appel à `dernier_planning_pour_instance`/`date_derniere_execution_reussie` par instance
    *distincte* plutôt que par instance à chaque requête — une commande ne référence jamais une
    instance inconnue (`enregistrer_commande` n'est jamais appelé sans instance déjà existante) ni
    supprimée (`supprimer_instance` cascade-supprime ses commandes, voir `api/etat.py`).

    Déclarée ici, avant `GET /{instance_id}` ci-dessous plutôt qu'à côté des autres routes
    `/commandes*` (§ordre de correspondance FastAPI/Starlette) : un chemin à un seul segment
    (`/commandes`) serait sinon capturé par `GET /{instance_id}` (instance_id="commandes"),
    déclarée avant elle dans le fichier — l'ordre d'enregistrement des routes prime sur leur
    position dans le code source, jamais l'inverse."""
    filtre_client = client_id_pour_filtre(utilisateur)
    commandes = [
        c for c in etat.lister_commandes(instance_id=None) if filtre_client is None or c.client_id == filtre_client
    ]

    par_instance: dict[str, list[CommandeEnregistree]] = {}
    for commande in commandes:
        par_instance.setdefault(commande.instance_id, []).append(commande)

    resultats: list[dict[str, object]] = []
    for instance_id, commandes_instance in par_instance.items():
        _, instance = etat.recuperer_instance(instance_id)
        planning = etat.dernier_planning_pour_instance(instance_id)
        date_execution = etat.date_derniere_execution_reussie(instance_id)
        for commande in commandes_instance:
            resultats.append(
                {
                    "commande_id": commande.id,
                    "instance_id": commande.instance_id,
                    "client_id": commande.client_id,
                    "date_limite": commande.date_limite,
                    "taches": list(commande.taches),
                    "date_creation": commande.date_creation,
                    "date_execution": date_execution,
                    **calculer_statut_commande(
                        instance, planning, commande.taches, commande.date_limite
                    ).en_dict(),
                }
            )
    return resultats


@router.get("/{instance_id}")
def obtenir_instance(
    instance_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Contenu T-R-C-O complet d'une instance déjà ingérée — pour l'afficher
    (dashboard), jamais pour la re-générer (le solveur, une fois validé,
    reste figé quelle que soit la relecture qu'on en fait, §7)."""
    try:
        client_id, instance = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)

    return {
        "instance_id": instance_id,
        "client_id": client_id,
        "structure_contraintes": structure_contraintes(instance),
        "description_metier": etat.recuperer_description_metier(instance_id),
        "unite_duree": etat.recuperer_unite_duree(instance_id),
        "canal_ingestion": etat.recuperer_canal_ingestion(instance_id),
        **instance.model_dump(mode="json"),
    }


@router.post("/{instance_id}/scenarios")
def creer_scenario(
    instance_id: str,
    payload: dict[str, Any],
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, str]:
    """Crée une instance variante d'`instance_id` (payload T-R-C-O complet,
    même garde-fou §6.7 qu'une ingestion normale) et la rattache au même
    groupe de scénarios comparatifs — voir
    `GET /{instance_id}/scenarios/comparaison`. Une nouvelle instance à part
    entière (son propre historique d'exécution), jamais une modification de
    l'originale : `instance_id` reste intact et exécutable indépendamment.
    Doit conserver toutes les ressources de l'instance de base (`_ressources_
    manquantes_par_rapport_a_la_base`) — un scénario compare des variantes
    du même atelier, jamais deux ateliers différents."""
    try:
        client_id, instance_base = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)
    instance = valider_payload_trco(payload)

    manquantes = _ressources_manquantes_par_rapport_a_la_base(instance_base, instance)
    if manquantes:
        raise HTTPException(
            status_code=422,
            detail=(
                "un scénario doit conserver toutes les ressources de l'instance de base "
                f"(même atelier) — ressource(s) manquante(s) : {sorted(manquantes)}. Pour un "
                "atelier différent, ingérez une nouvelle instance indépendante via "
                "POST /ingestion/{client_id}."
            ),
        )

    scenario_id = etat.enregistrer_instance(
        client_id, instance, groupe_scenario_id=instance_id, canal_ingestion="scenario"
    )
    return {"instance_id": scenario_id, "structure_contraintes": structure_contraintes(instance)}


@router.get("/{instance_id}/scenarios/comparaison")
def comparer_scenarios(
    instance_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Compare toutes les instances du groupe de scénarios d'`instance_id`
    (elle comprise) sur leur dernière exécution connue — makespan, taux
    d'utilisation par ressource, tâches en retard
    (`api/comparaison_scenarios.py`). Ne déclenche jamais d'exécution : une
    instance du groupe pas encore exécutée apparaît avec `metriques: null`,
    à exécuter explicitement via `POST /execution/{instance_id}` (§2.3,
    l'exécution reste toujours une décision humaine explicite, jamais un
    effet de bord d'une lecture).

    `est_instance_de_base` est calculé contre `racine_groupe_scenario(instance_id)`,
    jamais contre `instance_id` lui-même : appeler cette route depuis une variante
    (`instance_id` = un scénario, pas l'instance d'origine) doit quand même désigner
    la vraie racine du groupe comme base, jamais la variante consultée."""
    try:
        client_id, _ = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)
    membres = etat.lister_instances_du_groupe_scenario(instance_id)
    racine_id = etat.racine_groupe_scenario(instance_id)

    dernieres_executions: dict[str, dict[str, object]] = {}
    for execution in etat.lister_executions(client_id=client_id):
        iid = execution["instance_id"]
        if iid not in membres:
            continue
        existante = dernieres_executions.get(iid)
        if existante is None or (execution["date_execution"] or "") > (existante["date_execution"] or ""):
            dernieres_executions[iid] = execution

    scenarios: list[dict[str, object]] = []
    for membre_id in membres:
        _, instance_membre = etat.recuperer_instance(membre_id)
        derniere = dernieres_executions.get(membre_id)
        metriques = None
        if derniere is not None:
            _, _, resultat = etat.recuperer_execution(derniere["execution_id"])
            if resultat.reussi and resultat.planning is not None:
                metriques = calculer_metriques(instance_membre, resultat.planning).en_dict()
        scenarios.append(
            {
                "instance_id": membre_id,
                "est_instance_de_base": membre_id == racine_id,
                "execution_id": derniere["execution_id"] if derniere else None,
                "date_execution": derniere["date_execution"] if derniere else None,
                "metriques": metriques,
            }
        )

    return {"instance_id": instance_id, "scenarios": scenarios}


@router.patch("/{instance_id}/objectifs")
def modifier_objectifs_instance(
    instance_id: str,
    requete: RequeteModificationObjectifs,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Change l'objectif d'optimisation d'une instance déjà ingérée sans
    devoir tout réingérer — seul champ pour lequel une modification en place
    a du sens (taches/ressources/contraintes définissent le problème,
    l'objectif ne fait qu'orienter le solveur dessus)."""
    try:
        client_id, _ = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)

    try:
        instance = etat.modifier_objectifs(instance_id, requete.objectifs)
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur

    return {
        "instance_id": instance_id,
        "client_id": client_id,
        "structure_contraintes": structure_contraintes(instance),
        **instance.model_dump(mode="json"),
    }


@router.put("/{instance_id}")
def modifier_instance(
    instance_id: str,
    payload: dict[str, Any],
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Remplace en place le contenu T-R-C-O complet (tâches/ressources/
    contraintes/objectifs) d'une instance déjà ingérée — même instance_id,
    historique d'exécution intact (rien n'est dupliqué). Repasse par le même
    garde-fou amont (§6.7, `valider_payload_trco`) que la création."""
    try:
        client_id, _ = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)
    instance = valider_payload_trco(payload)
    instance = etat.modifier_instance(instance_id, instance)

    return {
        "instance_id": instance_id,
        "client_id": client_id,
        "structure_contraintes": structure_contraintes(instance),
        **instance.model_dump(mode="json"),
    }


@router.post("/{instance_id}/commandes")
def ajouter_commande(
    instance_id: str,
    requete: RequeteNouvelleCommande,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Associe des tâches déjà présentes dans l'instance à une commande et en dérive une
    `Echeance` (`adapters/commande_derivation.py`, même mécanisme que `csv_import`/`json_import`)
    — ne crée jamais de tâche, contrairement à l'ancienne explosion de gamme (fonctionnalité
    retirée). `commande_id` généré ici, jamais fourni par l'appelant : aucun risque de collision.
    Repasse par `EtatAPI.modifier_instance` (remplacement complet, historique d'exécution intact)."""
    try:
        client_id, instance = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)

    ids_connus = {t.id for t in instance.taches}
    inconnues = [t for t in requete.taches if t not in ids_connus]
    if inconnues:
        raise HTTPException(status_code=422, detail=f"tâche(s) inconnue(s) de cette instance : {inconnues}")

    commande_id = f"cmd-{uuid.uuid4().hex[:8]}"
    try:
        nouvelles_echeances = deriver_echeances_par_commande(
            [Commande(id=commande_id, taches=tuple(requete.taches), date_limite=requete.date_limite)],
            instance.contraintes,
        )
        instance_fusionnee_dsl = instance.model_copy(
            update={"contraintes": [*instance.contraintes, *nouvelles_echeances]}
        )
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur

    instance_fusionnee = etat.modifier_instance(instance_id, instance_fusionnee_dsl)

    etat.enregistrer_commande(commande_id, instance_id, client_id, requete.date_limite, tuple(requete.taches))

    return {
        "instance_id": instance_id,
        "commande_id": commande_id,
        "structure_contraintes": structure_contraintes(instance_fusionnee),
    }


@router.get("/{instance_id}/commandes")
def lister_commandes_instance(
    instance_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> list[dict[str, object]]:
    """Toutes les commandes de cet atelier (créées via `POST /{instance_id}/commandes`),
    chacune avec son statut recalculé à la volée contre le dernier planning *réussi* de
    l'instance — même calcul, jamais mis en cache, que `GET /commandes/{commande_id}` ci-dessous
    (voir sa docstring). Un seul appel à `dernier_planning_pour_instance` pour toutes les
    commandes de l'instance, plutôt qu'un par commande."""
    try:
        client_id, instance = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)

    planning = etat.dernier_planning_pour_instance(instance_id)
    date_execution = etat.date_derniere_execution_reussie(instance_id)
    return [
        {
            "commande_id": commande.id,
            "instance_id": commande.instance_id,
            "client_id": commande.client_id,
            "date_limite": commande.date_limite,
            "taches": list(commande.taches),
            "date_creation": commande.date_creation,
            "date_execution": date_execution,
            **calculer_statut_commande(instance, planning, commande.taches, commande.date_limite).en_dict(),
        }
        for commande in etat.lister_commandes(instance_id=instance_id)
    ]


@router.get("/commandes/{commande_id}")
def obtenir_commande(
    commande_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Statut d'une commande traitée via `POST /{instance_id}/commandes` — recalculé à la volée
    contre le dernier planning *réussi* de son instance (jamais mis en cache : reflète toujours
    l'état courant, y compris après une réexécution suite à un aléa, voir `api/etat.py` en-tête).
    Deux segments après le préfixe `/ingestion` : aucune collision avec `GET /{instance_id}`."""
    try:
        commande = etat.recuperer_commande(commande_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="commande inconnue") from None

    verifier_acces_client(utilisateur, commande.client_id)

    _, instance = etat.recuperer_instance(commande.instance_id)
    planning = etat.dernier_planning_pour_instance(commande.instance_id)
    statut = calculer_statut_commande(instance, planning, commande.taches, commande.date_limite)

    return {
        "commande_id": commande.id,
        "instance_id": commande.instance_id,
        "client_id": commande.client_id,
        "date_limite": commande.date_limite,
        "taches": list(commande.taches),
        "date_creation": commande.date_creation,
        "date_execution": etat.date_derniere_execution_reussie(commande.instance_id),
        **statut.en_dict(),
    }


@router.delete("/{instance_id}", status_code=204)
def supprimer_instance(
    instance_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> None:
    """Supprime une instance et son historique d'exécution — n'affecte jamais
    les solveurs enregistrés (indépendants, §7)."""
    try:
        client_id, _ = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)
    etat.supprimer_instance(instance_id)
