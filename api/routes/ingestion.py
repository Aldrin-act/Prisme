"""Réception du payload T-R-C-O canonique venant d'un adaptateur ERP (§5.1, §5.5)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError

from adapters.commande_derivation import Commande, deriver_echeances_par_commande
from adapters.competence_derivation import CompetenceSansDureeEstimee
from adapters.gamme_derivation import ErreurExplosionGamme, GammeAvecQuantite, traiter_nouvelle_commande
from api.autorisation import client_id_pour_filtre, verifier_acces_client
from api.comparaison_scenarios import calculer_metriques, calculer_statut_commande
from api.dependencies import obtenir_registre
from api.etat import CommandeEnregistree, EtatAPI, GammeCommandeEnregistree, obtenir_etat, structure_contraintes
from api.input_validation import erreurs_serialisables, valider_payload_trco
from api.routes.auth import obtenir_utilisateur_courant
from api.routes.execution import executer_pour_instance
from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, Objectif

if TYPE_CHECKING:
    from estimation import EstimateurDuree

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


class RequeteModificationObjectifs(BaseModel):
    objectifs: list[Objectif] = Field(min_length=1)


class RequeteGammeCommande(BaseModel):
    """Une entrée de `RequeteNouvelleCommande.gammes` — une commande peut référencer plusieurs
    gammes (plusieurs produits), chacune avec sa propre quantité."""

    gamme_id: str
    quantite: int | None = Field(default=None, ge=1)


class RequeteNouvelleCommande(BaseModel):
    # Tâches déjà existantes, choisies directement — optionnel dès lors qu'au moins une gamme est
    # fournie (validé plus bas, voir `_valider_taches_ou_gammes`). Les deux mécanismes coexistent :
    # une commande peut mélanger tâches choisies à la main et gammes explosées.
    taches: list[str] = Field(default_factory=list)
    # Durée propre à chaque tâche choisie directement, dans l'unité de l'instance
    # (`InstanceTRCO.unite_temps`) — ex. {"T1": 25, "T2": 12}. Contrairement à `duree_heures`
    # ci-dessous, ce n'est pas de la traçabilité : la valeur remplace la durée de la tâche sur
    # toutes ses ressources compatibles (voir `_appliquer_durees_taches`), donc le planning en
    # tient compte. Une tâche absente du dict garde ses durées actuelles.
    durees_taches: dict[str, int] = Field(default_factory=dict)
    gammes: list[RequeteGammeCommande] = Field(default_factory=list)
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


def _estimateur_duree_optionnel() -> EstimateurDuree | None:
    """`estimation` (scikit-learn) est un extra optionnel (`uv sync --extra estimation`) — import
    paresseux, même motif que dans `api/routes/adapters.py`/`sources.py`. Absent, une durée
    d'étape de gamme manquante reste une erreur explicite (`CompetenceSansDureeEstimee`), jamais
    devinée silencieusement."""
    try:
        from estimation import estimateur_par_defaut
    except ImportError:
        return None
    return estimateur_par_defaut()


def _gammes_commande_en_dicts(gammes: tuple[GammeCommandeEnregistree, ...]) -> list[dict[str, object]]:
    """Sérialisation de `CommandeEnregistree.gammes` pour les réponses JSON ci-dessous — même
    forme que `RequeteGammeCommande` côté écriture, plus `produit`/`nom` (copie figée à la
    création, voir docstring de `GammeCommandeEnregistree`)."""
    return [{"gamme_id": g.gamme_id, "produit": g.produit, "nom": g.nom, "quantite": g.quantite} for g in gammes]


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
                    "duree_heures": commande.duree_heures,
                    "numero": commande.numero,
                    "date_debut_au_plus_tot": commande.date_debut_au_plus_tot,
                    "est_prospect": commande.est_prospect,
                    "description": commande.description,
                    "nom_client": commande.nom_client,
                    "gammes": _gammes_commande_en_dicts(commande.gammes),
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


@router.post("/{instance_id}/commandes")
def ajouter_commande(
    instance_id: str,
    requete: RequeteNouvelleCommande,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Associe des tâches à une commande et en dérive une `Echeance`
    (`adapters/commande_derivation.py`, même mécanisme que `csv_import`/`json_import`) — deux
    sources de tâches, combinables librement : `requete.taches` (déjà présentes dans l'instance,
    ne crée jamais de tâche) et `requete.gammes` (une ou plusieurs gammes réutilisables, chacune
    explosée en tâches fraîches — `adapters/gamme_derivation.py`, une commande pouvant référencer
    plusieurs produits). `commande_id` généré ici, jamais fourni par l'appelant : aucun risque de
    collision. Repasse par `EtatAPI.modifier_instance` (remplacement complet, historique
    d'exécution intact).

    Déclenche ensuite une exécution automatique (best-effort, même composition que
    `POST /planifier/...` via `executer_pour_instance`) plutôt que d'attendre qu'une analyse de
    supervision le propose : la commande vient de modifier l'instance (nouvelle `Echeance`), le
    planning affiché doit refléter ça sans étape supplémentaire. Ne génère jamais de solveur à la
    volée (principe fondateur "generate once") : si aucun solveur validé n'existe pour la
    structure de contraintes résultante (ex. première commande à échéance de cette instance —
    change `structure_contraintes`, un solveur déjà enregistré ne correspond plus tant qu'il
    n'est pas régénéré), le 409 levé par `executer_pour_instance` est attrapé ici et renvoyé comme
    statut informatif (`erreur_execution`) — jamais comme un échec de l'ajout de commande
    lui-même, qui a déjà réussi à ce stade.

    `Registre` volontairement obtenu à la main (`obtenir_registre()`), jamais via `Depends` —
    sinon FastAPI résoudrait la dépendance (connexion Postgres) *avant* d'entrer dans cette
    fonction, hors de portée du `try`/`except` ci-dessous : Postgres injoignable ferait alors
    échouer tout l'ajout de commande, pas seulement l'exécution automatique best-effort. Même
    raison, aucun fixture `registre_test` requis dans les tests de ce endpoint (§ tests unitaires
    `EtatAPI` sans service externe, voir `test_api_commandes.py`)."""
    try:
        client_id, instance = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)

    if not requete.taches and not requete.gammes:
        raise HTTPException(status_code=422, detail="une commande doit référencer au moins une tâche ou une gamme")

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

    commande_id = f"cmd-{uuid.uuid4().hex[:8]}"

    # Résout chaque gamme référencée avant toute explosion — 404/400 explicites plutôt que de
    # fusionner partiellement une instance si une seule des gammes de la liste est invalide.
    gammes_resolues: list[GammeAvecQuantite] = []
    for entree in requete.gammes:
        try:
            gamme = etat.recuperer_gamme(entree.gamme_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"gamme inconnue : {entree.gamme_id!r}") from None
        if gamme.client_id != client_id:
            raise HTTPException(
                status_code=400, detail=f"la gamme {entree.gamme_id!r} n'appartient pas au client de l'instance"
            )
        gammes_resolues.append(GammeAvecQuantite(gamme=gamme, quantite=entree.quantite))

    instance_avec_gammes = instance
    taches_explodees: tuple[str, ...] = ()
    avertissements: tuple[str, ...] = ()
    if gammes_resolues:
        try:
            resultat_gammes = traiter_nouvelle_commande(
                instance, gammes_resolues, commande_id, estimateur_duree=_estimateur_duree_optionnel()
            )
        except (ErreurExplosionGamme, CompetenceSansDureeEstimee) as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from erreur
        except ValidationError as erreur:
            raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur
        instance_avec_gammes = resultat_gammes.instance
        taches_explodees = resultat_gammes.taches_explodees
        avertissements = resultat_gammes.avertissements

    # Échéance dérivée une seule fois, sur l'ensemble complet des tâches de la commande — choisies
    # directement et/ou explosées depuis une gamme, sans distinction à ce stade.
    toutes_taches_commande = (*requete.taches, *taches_explodees)
    try:
        nouvelles_echeances = deriver_echeances_par_commande(
            [Commande(id=commande_id, taches=toutes_taches_commande, date_limite=requete.date_limite)],
            instance_avec_gammes.contraintes,
        )
        instance_fusionnee_dsl = instance_avec_gammes.model_copy(
            update={"contraintes": [*instance_avec_gammes.contraintes, *nouvelles_echeances]}
        )
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur

    instance_fusionnee = etat.modifier_instance(instance_id, instance_fusionnee_dsl)

    etat.enregistrer_commande(
        commande_id,
        instance_id,
        client_id,
        requete.date_limite,
        toutes_taches_commande,
        duree_heures=requete.duree_heures,
        numero=requete.numero,
        date_debut_au_plus_tot=requete.date_debut_au_plus_tot,
        est_prospect=requete.est_prospect,
        description=requete.description,
        nom_client=requete.nom_client,
        gammes=tuple(
            GammeCommandeEnregistree(
                gamme_id=g.gamme.id, produit=g.gamme.produit, nom=g.gamme.nom, quantite=g.quantite
            )
            for g in gammes_resolues
        ),
    )

    execution_id: str | None = None
    execution_reussie: bool | None = None
    erreur_execution: str | None = None
    try:
        registre = obtenir_registre()
        execution_id, resultat_execution, _ = executer_pour_instance(etat, registre, instance_id, utilisateur)
        execution_reussie = resultat_execution.reussi
        erreur_execution = resultat_execution.erreur
    except HTTPException as erreur:
        erreur_execution = str(erreur.detail)
    except psycopg.OperationalError as erreur:
        erreur_execution = f"exécution automatique indisponible (Postgres injoignable) : {erreur}"

    return {
        "instance_id": instance_id,
        "commande_id": commande_id,
        "structure_contraintes": structure_contraintes(instance_fusionnee),
        "avertissements": list(avertissements),
        "execution_id": execution_id,
        "execution_reussie": execution_reussie,
        "erreur_execution": erreur_execution,
    }


@router.post("/commandes/{commande_id}/produits")
def ajouter_produit_a_commande(
    commande_id: str,
    requete: RequeteGammeCommande,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Ajoute un produit (gamme) supplémentaire à une commande déjà créée — complète
    `POST /{instance_id}/commandes`, qui ne permet de référencer des gammes qu'à la création.
    Explose la gamme en tâches fraîches (`adapters/gamme_derivation.py`, même mécanisme), fusionne
    dans l'instance de la commande, et étend `CommandeEnregistree.taches`/`.gammes` en place —
    `commande_id`/`date_creation`/`date_limite` inchangés. `index_depart=len(commande.gammes)`
    (voir `traiter_nouvelle_commande`) évite toute collision de préfixe de tâche avec les produits
    déjà explosés pour cette même commande.

    Échéance dérivée uniquement pour les tâches fraîchement explosées : les tâches déjà présentes
    dans la commande ont déjà la leur (ou aucune), `deriver_echeances_par_commande` ne touche
    jamais une tâche à échéance explicite (voir sa docstring) — pas de re-dérivation sur l'existant.

    Même best-effort d'exécution automatique post-fusion que `ajouter_commande` ci-dessus, pour
    les mêmes raisons (409 si aucun solveur ne correspond encore à la structure de contraintes
    résultante — jamais une génération à la volée)."""
    try:
        commande = etat.recuperer_commande(commande_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="commande inconnue") from None

    verifier_acces_client(utilisateur, commande.client_id)

    try:
        client_id, instance = etat.recuperer_instance(commande.instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    try:
        gamme = etat.recuperer_gamme(requete.gamme_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"gamme inconnue : {requete.gamme_id!r}") from None
    if gamme.client_id != client_id:
        raise HTTPException(
            status_code=400, detail=f"la gamme {requete.gamme_id!r} n'appartient pas au client de l'instance"
        )

    try:
        resultat_gamme = traiter_nouvelle_commande(
            instance,
            [GammeAvecQuantite(gamme=gamme, quantite=requete.quantite)],
            commande_id,
            estimateur_duree=_estimateur_duree_optionnel(),
            index_depart=len(commande.gammes),
        )
    except (ErreurExplosionGamme, CompetenceSansDureeEstimee) as erreur:
        raise HTTPException(status_code=422, detail=str(erreur)) from erreur
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur

    try:
        nouvelles_echeances = deriver_echeances_par_commande(
            [Commande(id=commande_id, taches=resultat_gamme.taches_explodees, date_limite=commande.date_limite)],
            resultat_gamme.instance.contraintes,
        )
        instance_fusionnee_dsl = resultat_gamme.instance.model_copy(
            update={"contraintes": [*resultat_gamme.instance.contraintes, *nouvelles_echeances]}
        )
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur

    instance_fusionnee = etat.modifier_instance(commande.instance_id, instance_fusionnee_dsl)

    commande_mise_a_jour = etat.ajouter_gamme_a_commande(
        commande_id,
        resultat_gamme.taches_explodees,
        GammeCommandeEnregistree(
            gamme_id=gamme.id, produit=gamme.produit, nom=gamme.nom, quantite=requete.quantite
        ),
    )

    execution_id: str | None = None
    execution_reussie: bool | None = None
    erreur_execution: str | None = None
    try:
        registre = obtenir_registre()
        execution_id, resultat_execution, _ = executer_pour_instance(
            etat, registre, commande.instance_id, utilisateur
        )
        execution_reussie = resultat_execution.reussi
        erreur_execution = resultat_execution.erreur
    except HTTPException as erreur:
        erreur_execution = str(erreur.detail)
    except psycopg.OperationalError as erreur:
        erreur_execution = f"exécution automatique indisponible (Postgres injoignable) : {erreur}"

    return {
        "instance_id": commande.instance_id,
        "commande_id": commande_id,
        "taches": list(commande_mise_a_jour.taches),
        "gammes": _gammes_commande_en_dicts(commande_mise_a_jour.gammes),
        "structure_contraintes": structure_contraintes(instance_fusionnee),
        "avertissements": list(resultat_gamme.avertissements),
        "execution_id": execution_id,
        "execution_reussie": execution_reussie,
        "erreur_execution": erreur_execution,
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
            "duree_heures": commande.duree_heures,
            "numero": commande.numero,
            "date_debut_au_plus_tot": commande.date_debut_au_plus_tot,
            "est_prospect": commande.est_prospect,
            "description": commande.description,
            "nom_client": commande.nom_client,
            "gammes": _gammes_commande_en_dicts(commande.gammes),
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
        "duree_heures": commande.duree_heures,
        "numero": commande.numero,
        "date_debut_au_plus_tot": commande.date_debut_au_plus_tot,
        "est_prospect": commande.est_prospect,
        "description": commande.description,
        "nom_client": commande.nom_client,
        "gammes": _gammes_commande_en_dicts(commande.gammes),
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
