"""Réception du payload T-R-C-O canonique venant d'un adaptateur ERP (§5.1, §5.5)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError

from adapters.commande_derivation import Commande, deriver_echeances_par_commande
from adapters.processus_derivation import ErreurProcessus, eclater_processus, valider_processus
from api.autorisation import client_id_pour_filtre, verifier_acces_client
from api.comparaison_scenarios import calculer_metriques, calculer_statut_commande
from api.dependencies import obtenir_registre
from api.etat import (
    CommandeEnregistree,
    EtapeProcessus,
    EtatAPI,
    StatutRealisationCommande,
    instance_a_la_date,
    obtenir_etat,
    signature_objectifs,
    solveurs_pour_instance_ou_scenario_de_base,
    structure_contraintes,
)
from api.input_validation import erreurs_serialisables, valider_payload_trco
from api.routes.auth import obtenir_utilisateur_courant
from api.routes.execution import executer_pour_instance
from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, Objectif, Planning
from sandbox.runner import solveur_supporte_horizon_gele

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


class RequeteModificationObjectifs(BaseModel):
    objectifs: list[Objectif] = Field(min_length=1)


class RequeteEtapeProcessus(BaseModel):
    id: str
    nom: str | None = None
    competences: list[str] = Field(min_length=1)
    predecesseurs: list[str] = Field(default_factory=list)
    duree_par_piece: int = Field(ge=1)


class RequeteProcessus(BaseModel):
    etapes: list[RequeteEtapeProcessus] = Field(min_length=1)


class RequeteNouvelleCommande(BaseModel):
    # Tâches déjà présentes dans l'atelier, choisies directement. Vide (cas normal depuis le
    # formulaire) : la commande éclate le processus de l'atelier, `quantite` pièces — voir
    # `ajouter_commande`. Les deux chemins ne se combinent jamais dans une même commande.
    taches: list[str] = Field(default_factory=list)
    # Durée propre à chaque tâche choisie directement, dans l'unité de l'instance
    # (`InstanceTRCO.unite_temps`) — ex. {"T1": 25, "T2": 12}. Contrairement à `duree_heures`
    # ci-dessous, ce n'est pas de la traçabilité : la valeur remplace la durée de la tâche sur
    # toutes ses ressources compatibles (voir `_appliquer_durees_taches`), donc le planning en
    # tient compte. Une tâche absente du dict garde ses durées actuelles.
    durees_taches: dict[str, int] = Field(default_factory=dict)
    # Nombre de pièces, pour une commande qui éclate le processus de l'atelier : chaque étape
    # dure `duree_par_piece × quantite`. Ignorée pour une commande sur tâches existantes.
    quantite: int = Field(default=1, ge=1)
    date_limite: int | None = Field(default=None, ge=0)
    # Durée globale prévue, saisie librement par l'utilisateur (heures) — pure métadonnée de
    # traçabilité (voir `CommandeEnregistree.duree_heures`), jamais dérivée en Echeance.
    duree_heures: int | None = Field(default=None, ge=0)
    # Métadonnées de traçabilité supplémentaires (même principe que duree_heures ci-dessus — voir
    # `CommandeEnregistree` dans `api/etat.py` pour le détail de chaque champ).
    numero: str | None = None
    date_debut_au_plus_tot: int | None = Field(default=None, ge=0)
    est_prospect: bool = False
    description: str | None = None
    nom_client: str | None = None


def _horizon_gele_jusqu_a_maintenant(unite_temps: str, date_execution_precedente: str) -> int:
    """Convertit « maintenant » en instant relatif de l'instance, dans le même référentiel que
    `OperationPlanifiee.debut` — pour figer (`horizon_gele_jours`) tout ce que le dernier planning
    plaçait avant cet instant : ces opérations sont déjà censées avoir démarré, dans la vraie vie,
    au moment où une nouvelle commande arrive. Jamais négatif (une horloge en clientèle légèrement
    en avance sur le serveur ne doit pas produire un horizon négatif)."""
    ancrage = datetime.fromisoformat(date_execution_precedente)
    ecoule = datetime.now(UTC) - ancrage.astimezone(UTC)
    heures_ecoulees = ecoule.total_seconds() / 3600
    pas_heures = 1 if unite_temps == "heures" else 24
    return max(0, int(heures_ecoulees // pas_heures))


def _appliquer_durees_taches(instance: InstanceTRCO, durees: dict[str, int]) -> InstanceTRCO:
    """Remplace la durée de chaque tâche de `durees` sur **toutes** ses compatibilités
    ressource-tâche : une commande dit combien dure la tâche, pas combien elle dure sur telle
    ressource. Une durée différente par ressource (FJSP flexible) redevient donc uniforme pour ces
    tâches-là — choix assumé, c'est ce que la saisie d'une durée unique par tâche exprime.
    Revalide l'instance complète (garde-fou §6.7) plutôt qu'un `model_copy` qui ne valide rien."""
    if not durees:
        return instance
    contraintes = [
        {**c.model_dump(), "duree": durees[c.tache]}
        if isinstance(c, CompatibiliteRessourceTache) and c.tache in durees
        else c.model_dump()
        for c in instance.contraintes
    ]
    return InstanceTRCO.model_validate({**instance.model_dump(), "contraintes": contraintes})


def _commande_en_dict(
    commande: CommandeEnregistree,
    instance: InstanceTRCO,
    planning: Planning | None,
    date_execution: str | None,
) -> dict[str, object]:
    """Représentation JSON d'une commande, partagée par les trois routes qui en renvoient une —
    elle croise deux statuts qui ne disent pas la même chose et ne doivent jamais être confondus :
    `statut_realisation`/`date_realisation`, **déclarés par un humain** (l'atelier a-t-il fait le
    travail ?), et le reste (`planifiee`/`date_fin_prevue`/`en_retard`), **recalculé à la volée**
    contre le dernier planning réussi (que prévoit l'ordonnancement ?). Une commande dont la fin
    prévue est dépassée reste `non_debutee` tant que personne ne l'a confirmée : le système ne
    déduit jamais une réalisation de l'écoulement du temps."""
    return {
        "commande_id": commande.id,
        "instance_id": commande.instance_id,
        "client_id": commande.client_id,
        "date_limite": commande.date_limite,
        "taches": list(commande.taches),
        "date_creation": commande.date_creation,
        "duree_heures": commande.duree_heures,
        "numero": commande.numero,
        "date_debut_au_plus_tot": commande.date_debut_au_plus_tot,
        "est_prospect": commande.est_prospect,
        "description": commande.description,
        "nom_client": commande.nom_client,
        "quantite": commande.quantite,
        "statut_realisation": commande.statut_realisation,
        "date_realisation": commande.date_realisation,
        "date_execution": date_execution,
        **calculer_statut_commande(
            instance_a_la_date(instance, date_execution), planning, commande.taches, commande.date_limite
        ).en_dict(),
    }


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
            resultats.append(_commande_en_dict(commande, instance, planning, date_execution))
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
    d'utilisation par ressource, commandes en retard
    (`api/comparaison_scenarios.py`). Ne déclenche jamais d'exécution : une
    instance du groupe pas encore exécutée apparaît avec `metriques: null`,
    à exécuter explicitement via `POST /execution/{instance_id}` (§2.3,
    l'exécution reste toujours une décision humaine explicite, jamais un
    effet de bord d'une lecture).

    `commandes_en_retard` (compte, pas une liste de tâches) : par commande de ce membre
    (`etat.lister_commandes`), même calcul que `calculer_statut_commande` (déjà utilisé par
    `GET .../commandes` et le détecteur de supervision `commande_en_retard`) — `None` tant
    qu'aucune exécution réussie n'existe pour ce membre, même garde que `metriques`.

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
        commandes_en_retard = None
        if derniere is not None:
            _, _, resultat = etat.recuperer_execution(derniere["execution_id"])
            if resultat.reussi and resultat.planning is not None:
                instance_membre = instance_a_la_date(instance_membre, derniere["date_execution"])
                metriques = calculer_metriques(instance_membre, resultat.planning).en_dict()
                commandes_en_retard = sum(
                    1
                    for commande in etat.lister_commandes(instance_id=membre_id)
                    if calculer_statut_commande(
                        instance_membre, resultat.planning, commande.taches, commande.date_limite
                    ).en_retard
                )
        scenarios.append(
            {
                "instance_id": membre_id,
                "est_instance_de_base": membre_id == racine_id,
                "execution_id": derniere["execution_id"] if derniere else None,
                "date_execution": derniere["date_execution"] if derniere else None,
                "metriques": metriques,
                "commandes_en_retard": commandes_en_retard,
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


def _etapes_domaine(requete: RequeteProcessus) -> tuple[EtapeProcessus, ...]:
    return tuple(
        EtapeProcessus(
            id=e.id,
            nom=e.nom,
            competences=tuple(e.competences),
            predecesseurs=tuple(e.predecesseurs),
            duree_par_piece=e.duree_par_piece,
        )
        for e in requete.etapes
    )


def _processus_en_dict(etapes: tuple[EtapeProcessus, ...]) -> dict[str, object]:
    return {
        "etapes": [
            {
                "id": e.id,
                "nom": e.nom,
                "competences": list(e.competences),
                "predecesseurs": list(e.predecesseurs),
                "duree_par_piece": e.duree_par_piece,
            }
            for e in etapes
        ]
    }


@router.get("/{instance_id}/processus")
def obtenir_processus(
    instance_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Le processus unique de l'atelier — `etapes` vide tant qu'il n'a jamais été défini."""
    try:
        client_id, _ = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None
    verifier_acces_client(utilisateur, client_id)
    return _processus_en_dict(etat.recuperer_processus(instance_id))


@router.put("/{instance_id}/processus")
def definir_processus(
    instance_id: str,
    requete: RequeteProcessus,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Définit (ou remplace) le processus de l'atelier. Validé entièrement ici (étapes en double,
    prédécesseur inconnu, cycle...) plutôt qu'à la première commande, des jours plus tard. Les
    commandes déjà passées ne sont jamais réécrites : seules les suivantes suivent le nouveau
    processus."""
    try:
        client_id, _ = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None
    verifier_acces_client(utilisateur, client_id)

    etapes = _etapes_domaine(requete)
    try:
        valider_processus(etapes)
    except ErreurProcessus as erreur:
        raise HTTPException(status_code=422, detail=str(erreur)) from erreur
    return _processus_en_dict(etat.definir_processus(instance_id, etapes))


@router.post("/{instance_id}/commandes")
def ajouter_commande(
    instance_id: str,
    requete: RequeteNouvelleCommande,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Crée une commande et en dérive une `Echeance` commune à toutes ses tâches
    (`adapters/commande_derivation.py`, même mécanisme que `csv_import`/`json_import`). Deux
    chemins, jamais combinés dans une même commande :

    - **cas normal** (`requete.taches` vide) : le processus de l'atelier est éclaté en tâches
      fraîches propres à cette commande, chaque étape durant `duree_par_piece × quantite`
      (`adapters/processus_derivation.py`). 422 si l'atelier n'a pas encore de processus ;
    - `requete.taches` fourni : la commande référence des tâches déjà présentes dans l'atelier,
      sans en créer (import de données existantes, API).

    `commande_id` généré ici, jamais fourni par l'appelant : aucun risque de collision. Repasse
    par `EtatAPI.modifier_instance` (remplacement complet, historique d'exécution intact).

    Déclenche ensuite une exécution automatique (best-effort, même composition que
    `POST /planifier/...` via `executer_pour_instance`) : la commande vient de modifier
    l'instance, le planning affiché doit en tenir compte sans étape supplémentaire. Cette
    réexécution fige automatiquement (`horizon_gele_jours` calculé jusqu'à l'instant présent, voir
    `_horizon_gele_jusqu_a_maintenant`) toute opération du planning précédent censée avoir déjà
    démarré — pour ne jamais redéplacer, à l'ajout d'une commande, ce qui est déjà réellement en
    cours dans l'atelier — sauf pour la toute première exécution (rien à figer) ou si le solveur
    actif ne supporte pas ce paramètre (`avertissements` le signale alors, le replan reste complet
    comme avant l'ajout de cette protection). Ne génère
    jamais de solveur à la volée (principe fondateur "generate once") : si aucun solveur validé
    ne correspond à la structure de contraintes résultante, le 409 levé par
    `executer_pour_instance` est renvoyé comme statut informatif (`erreur_execution`), jamais
    comme un échec de l'ajout de commande lui-même, qui a déjà réussi à ce stade.

    `Registre` obtenu à la main (`obtenir_registre()`), jamais via `Depends` — sinon FastAPI
    résoudrait la dépendance (connexion Postgres) *avant* d'entrer ici, hors de portée du
    `try`/`except` : Postgres injoignable ferait échouer tout l'ajout de commande."""
    try:
        client_id, instance = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)

    commande_id = f"cmd-{uuid.uuid4().hex[:8]}"
    avertissements: tuple[str, ...] = ()
    quantite: int | None = None

    if requete.taches:
        ids_connus = {t.id for t in instance.taches}
        inconnues = [t for t in requete.taches if t not in ids_connus]
        if inconnues:
            raise HTTPException(status_code=422, detail=f"tâche(s) inconnue(s) de cette instance : {inconnues}")
        hors_commande = sorted(set(requete.durees_taches) - set(requete.taches))
        if hors_commande:
            raise HTTPException(
                status_code=422,
                detail=f"durée fournie pour des tâches absentes de la commande : {hors_commande}",
            )
        durees_invalides = sorted(t for t, d in requete.durees_taches.items() if d < 1)
        if durees_invalides:
            raise HTTPException(
                status_code=422, detail=f"durée invalide (entier ≥ 1 attendu) pour : {durees_invalides}"
            )
        try:
            instance = _appliquer_durees_taches(instance, requete.durees_taches)
        except ValidationError as erreur:
            raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur
        taches_commande = tuple(requete.taches)
    else:
        processus = etat.recuperer_processus(instance_id)
        if not processus:
            raise HTTPException(
                status_code=422,
                detail="cet atelier n'a pas encore de processus : définissez-le avant de créer une commande",
            )
        try:
            resultat = eclater_processus(instance, processus, commande_id, requete.quantite)
        except ErreurProcessus as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from erreur
        except ValidationError as erreur:
            raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur
        instance = resultat.instance
        taches_commande = resultat.taches_creees
        avertissements = resultat.avertissements
        quantite = requete.quantite

    try:
        nouvelles_echeances = deriver_echeances_par_commande(
            [Commande(id=commande_id, taches=taches_commande, date_limite=requete.date_limite)],
            instance.contraintes,
        )
        instance_fusionnee_dsl = InstanceTRCO(
            **{**dict(instance), "contraintes": [*instance.contraintes, *nouvelles_echeances]}
        )
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur

    instance_fusionnee = etat.modifier_instance(instance_id, instance_fusionnee_dsl)

    etat.enregistrer_commande(
        commande_id,
        instance_id,
        client_id,
        requete.date_limite,
        taches_commande,
        duree_heures=requete.duree_heures,
        numero=requete.numero,
        date_debut_au_plus_tot=requete.date_debut_au_plus_tot,
        est_prospect=requete.est_prospect,
        description=requete.description,
        nom_client=requete.nom_client,
        quantite=quantite,
    )

    avertissements_liste = list(avertissements)
    execution_id: str | None = None
    execution_reussie: bool | None = None
    erreur_execution: str | None = None
    gel_applique = False
    try:
        registre = obtenir_registre()

        # Protège ce qui tourne déjà réellement dans l'atelier : sans ça, cette réexécution
        # automatique (comme toute réexécution normale, `horizon_gele_jours=0` par défaut) peut
        # redéplacer une opération déjà en cours au moment même où la commande est ajoutée — le
        # planning ne le sait jamais tout seul (§ human-in-the-loop, voir `declarer_retard_tache`
        # ci-dessus pour le même principe côté durée). Jamais pour la toute première exécution
        # (rien n'a encore pu commencer) ; jamais non plus si le solveur actif ne sait pas honorer
        # ce paramètre — dans ce cas, on retombe sur le replan complet d'avant plutôt que de faire
        # échouer l'ajout d'une commande pour une protection que ce solveur ne peut pas offrir,
        # mais l'utilisateur en est informé (contrairement à `POST /execution` qui, lui, échoue
        # explicitement — ici, rien n'a été demandé explicitement pour cette exécution précise).
        horizon_gele_jours = 0
        date_precedente = etat.date_derniere_execution_reussie(instance_id)
        if date_precedente is not None:
            solveurs_actifs = solveurs_pour_instance_ou_scenario_de_base(
                etat,
                registre,
                client_id,
                instance_id,
                structure_contraintes=structure_contraintes(instance_fusionnee),
                signature_objectifs=signature_objectifs(instance_fusionnee),
            )
            if solveurs_actifs and solveur_supporte_horizon_gele(solveurs_actifs[0].code_source):
                horizon_gele_jours = _horizon_gele_jusqu_a_maintenant(
                    instance_fusionnee.unite_temps, date_precedente
                )
            elif solveurs_actifs:
                avertissements_liste.append(
                    "ce solveur ne protège pas les tâches déjà en cours (généré avant l'ajout de "
                    "l'horizon gelé) — le planning précédent a été entièrement recalculé ; "
                    "régénérez le solveur pour que les prochaines commandes ne déplacent plus ce "
                    "qui est déjà engagé"
                )

        execution_id, resultat_execution, gel_applique = executer_pour_instance(
            etat, registre, instance_id, utilisateur, horizon_gele_jours=horizon_gele_jours
        )
        execution_reussie = resultat_execution.reussi
        erreur_execution = resultat_execution.erreur
    except HTTPException as erreur:
        erreur_execution = str(erreur.detail)
    except psycopg.OperationalError as erreur:
        erreur_execution = f"exécution automatique indisponible (Postgres injoignable) : {erreur}"

    return {
        "instance_id": instance_id,
        "commande_id": commande_id,
        "taches": list(taches_commande),
        "structure_contraintes": structure_contraintes(instance_fusionnee),
        "avertissements": avertissements_liste,
        "execution_id": execution_id,
        "execution_reussie": execution_reussie,
        "erreur_execution": erreur_execution,
        # Transparence sur la protection appliquée à cette réexécution automatique (voir
        # `executer_pour_instance` : distingue "rien à figer" — première exécution, ou solveur qui
        # ne supporte pas ce paramètre, `avertissements` le dit alors — d'un vrai gel appliqué).
        "gel_applique": gel_applique,
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
        _commande_en_dict(commande, instance, planning, date_execution)
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
    date_execution = etat.date_derniere_execution_reussie(commande.instance_id)

    return _commande_en_dict(commande, instance, planning, date_execution)


class RequeteStatutCommande(BaseModel):
    """`date_realisation` n'est lue que pour `statut="realisee"` (déclaration rétroactive :
    « finie mardi dernier ») — ignorée sinon, jamais une date de réalisation sur une commande
    qu'on vient de remettre en cours."""

    statut: StatutRealisationCommande
    date_realisation: str | None = None


@router.patch("/commandes/{commande_id}/statut")
def changer_statut_commande(
    commande_id: str,
    requete: RequeteStatutCommande,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Avancement réel de la commande dans l'atelier, **déclaré par un humain** : non débutée,
    en cours, ou réalisée (§ human-in-the-loop). C'est la seule façon pour PRISME de savoir
    qu'un travail a été fait — le planning ne dit que ce qui *devrait* arriver, et une date de
    fin prévue dépassée ne prouve rien (panne, absence, matière manquante...).

    `PATCH` et non `POST` : on modifie un champ d'une commande existante, jamais on n'en crée
    une. Deux segments après le préfixe `/ingestion` comme `GET /commandes/{commande_id}` :
    aucune collision avec `GET /{instance_id}`."""
    try:
        commande = etat.recuperer_commande(commande_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="commande inconnue") from None

    verifier_acces_client(utilisateur, commande.client_id)

    commande = etat.mettre_a_jour_statut_commande(commande_id, requete.statut, requete.date_realisation)
    _, instance = etat.recuperer_instance(commande.instance_id)
    planning = etat.dernier_planning_pour_instance(commande.instance_id)
    date_execution = etat.date_derniere_execution_reussie(commande.instance_id)

    return _commande_en_dict(commande, instance, planning, date_execution)


class RequeteRetardTache(BaseModel):
    # La ressource sur laquelle la tâche tourne réellement (celle du dernier planning) — jamais
    # toutes ses ressources compatibles comme `_appliquer_durees_taches` : ce n'est pas la tâche
    # en général qui est corrigée, seulement ce qui est réellement observé sur cette ressource-là ;
    # une durée hypothétique jamais essayée sur une autre ressource ne doit pas changer.
    ressource: str
    nouvelle_duree: int = Field(ge=1)


@router.patch("/{instance_id}/taches/{tache_id}/retard")
def declarer_retard_tache(
    instance_id: str,
    tache_id: str,
    requete: RequeteRetardTache,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """PRISME ne sait jamais qu'une tâche tourne en retard par elle-même — aucun capteur ne
    remonte l'atelier en direct, seul un humain qui l'observe peut le dire (§ human-in-the-loop,
    même principe que `changer_statut_commande` ci-dessus, mais au grain de la tâche plutôt que de
    la commande entière). Cette route ne fait que corriger la durée réelle constatée sur
    `(tache_id, requete.ressource)` — jamais un mécanisme d'alerte automatique, jamais une
    exécution déclenchée ici : l'appelant relance `POST /execution/{instance_id}` ensuite pour
    obtenir un planning qui en tient compte (voir `executer_pour_instance`, même geste qu'un aléa
    quelconque : réingérer une donnée corrigée puis réexécuter)."""
    try:
        client_id, instance = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)

    couple_connu = any(
        isinstance(c, CompatibiliteRessourceTache) and c.tache == tache_id and c.ressource == requete.ressource
        for c in instance.contraintes
    )
    if not couple_connu:
        raise HTTPException(
            status_code=404,
            detail=f"aucune compatibilité ressource-tâche {tache_id!r}/{requete.ressource!r} sur cette instance",
        )

    contraintes = [
        {**c.model_dump(), "duree": requete.nouvelle_duree}
        if isinstance(c, CompatibiliteRessourceTache) and c.tache == tache_id and c.ressource == requete.ressource
        else c.model_dump()
        for c in instance.contraintes
    ]
    instance_corrigee = InstanceTRCO.model_validate({**instance.model_dump(), "contraintes": contraintes})
    instance_corrigee = etat.modifier_instance(instance_id, instance_corrigee)

    return {
        "instance_id": instance_id,
        "client_id": client_id,
        "structure_contraintes": structure_contraintes(instance_corrigee),
        **instance_corrigee.model_dump(mode="json"),
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
