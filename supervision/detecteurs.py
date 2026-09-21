"""Détection de signaux (§2, MT7) — **atelier par atelier** : chaque instance (atelier) est
analysée séparément, avec un appel LLM qui ne voit que ses propres données (l'instance, ses
propres solveurs, ses propres exécutions — `detecter_signaux_instance`). Jamais tous les ateliers
d'un client mélangés dans un même prompt : un atelier ne peut pas « contaminer » le jugement porté
sur un autre, et un atelier chargé ne noie pas les autres dans un prompt géant.
`detecter_signaux` (niveau client) n'est plus qu'une boucle sur ses ateliers.

La décision (quel signal s'applique) est déléguée au LLM (`supervision.agent.detecter_signaux_llm`)
plutôt qu'à des comparaisons Python : c'est le LLM qui compare les `instance_id`, les dates de
modification/exécution et l'historique d'échecs, à partir des faits bruts assemblés ici. Ce
module se limite à rassembler ces faits et à valider ce que le LLM en tire avant de le convertir
en signaux typés — jamais recalculé ni redécidé ici, mais jamais non plus accepté aveuglément :
un `instance_id`, `id_solveur_disponible` ou `execution_id` qui ne correspond à aucune donnée
réellement fournie est silencieusement écarté plutôt que propagé (le LLM peut se tromper ou
halluciner, voir `supervision.agent.SignalBrutLLM`) — y compris un `id_solveur_disponible` réel
mais appartenant à une **autre** instance : un solveur ne sert jamais que l'instance qui l'a fait
générer (`solver_store/registry.py`), jamais une autre même de structure/objectifs identiques.

Trois signaux détectés par le LLM :

1. **Signature orpheline** — aucun solveur actif enregistré pour ce client n'a d'`instance_id`
   égal à celui de cette instance.
2. **Instance à replanifier** — un solveur actif a bien un `instance_id` égal à celui de cette
   instance (le sien), mais soit l'instance n'a jamais été exécutée, soit elle l'a été puis a été
   modifiée depuis (`modifier_instance`/`modifier_objectifs`, `api/etat.py`) sans être
   ré-exécutée.
3. **Échecs répétés** — les 3 dernières exécutions d'une même instance sont toutes en échec.

Un quatrième signal, **commande en retard** (`detecter_commandes_en_retard` ci-dessous), est
volontairement détecté **sans appel LLM** : contrairement aux trois précédents, la comparaison
nécessaire (date de fin prévue vs date limite d'une commande) est déjà calculée de façon exacte
par `api.comparaison_scenarios.calculer_statut_commande`, utilisée telle quelle ailleurs dans
l'app (page Commandes) — redemander cette comparaison à un LLM n'apporterait rien, seulement un
risque d'erreur sur une simple comparaison d'entiers déjà fiable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from api.comparaison_scenarios import calculer_statut_commande
from api.etat import CommandeEnregistree, EtatAPI, instance_a_la_date, signature_objectifs, structure_contraintes
from solver_store.registry import Registre
from supervision.adequation import EvaluationSolveur, SolveurHorsAtelier
from supervision.agent import (
    ExecutionSupervision,
    InstanceSupervision,
    RaisonReplanification,
    SolveurSupervision,
    detecter_signaux_llm,
)

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel


@dataclass(frozen=True)
class SignalSignatureOrpheline:
    instance_id: str
    client_id: str
    structure_contraintes: str
    signature_objectifs: str


@dataclass(frozen=True)
class SignalInstanceAReplanifier:
    instance_id: str
    client_id: str
    structure_contraintes: str
    signature_objectifs: str
    id_solveur_disponible: str
    raison: RaisonReplanification


@dataclass(frozen=True)
class SignalEchecsRepetes:
    instance_id: str
    client_id: str
    id_solveur: str
    execution_ids: tuple[str, ...]
    structure_contraintes: str
    signature_objectifs: str


@dataclass(frozen=True)
class SignalCommandeEnRetard:
    commande_id: str
    instance_id: str
    client_id: str
    date_fin_prevue: int
    date_limite: int


@dataclass(frozen=True)
class SignalSolveurARegenerer:
    """Le solveur de l'atelier ne répond plus à l'instance actuelle : contraintes ou objectifs non
    pris en charge, ou algorithme qui n'est plus celui recommandé — voir `supervision/adequation.py`."""

    instance_id: str
    client_id: str
    evaluation: EvaluationSolveur
    structure_contraintes: str
    signature_objectifs: str


@dataclass(frozen=True)
class SignalInstanceJugeeInfaisable:
    """Essai réel du solveur sur l'instance actuelle : « aucune solution ». Peut venir des données
    (échéances impossibles, stock insuffisant...) autant que du solveur — jamais une raison de le
    régénérer à elle seule ; un humain vérifie d'abord les données (voir supervision/adequation.py)."""

    instance_id: str
    client_id: str
    id_solveur: str
    structure_contraintes: str
    signature_objectifs: str


SignalDetecte = (
    SignalSignatureOrpheline
    | SignalInstanceAReplanifier
    | SignalEchecsRepetes
    | SignalCommandeEnRetard
    | SignalSolveurARegenerer
    | SignalInstanceJugeeInfaisable
)


def detecter_signaux_instance(
    etat: EtatAPI,
    registre: Registre,
    modele: BaseChatModel,
    instance_id: str,
    id_solveur: str | None = None,
) -> tuple[SignalDetecte, ...]:
    """Détection pour **un seul atelier** : rassemble uniquement l'instance `instance_id`, ses
    propres solveurs actifs (`Registre.rechercher_solveurs(instance_id=...)` — un solveur ne sert
    que l'instance qui l'a fait générer) et ses propres exécutions, délègue à
    `supervision.agent.detecter_signaux_llm`, puis valide et convertit sa réponse. Tout signal
    renvoyé pour un autre `instance_id` que celui analysé est écarté (hallucination, ou recopie
    d'un identifiant vu ailleurs). Lève `KeyError` si l'instance n'existe pas.

    `id_solveur` (entrée explicite de l'analyse, avec `instance_id`) : l'analyse porte alors sur
    le couple (atelier, solveur) — seul ce solveur est montré au LLM, seules ses exécutions sont
    prises en compte, et `signature_orpheline` est écarté (l'atelier a justement ce solveur).
    Lève `SolveurHorsAtelier` s'il n'est pas un solveur actif de cet atelier. `None` : tous les
    solveurs actifs de l'atelier (cas d'un atelier sans solveur, ou boucle périodique)."""
    client_id, instance_dsl = etat.recuperer_instance(instance_id)
    info = next(
        (i for i in etat.lister_instances(client_id=client_id) if i["instance_id"] == instance_id),
        {},
    )
    instance = InstanceSupervision(
        instance_id=instance_id,
        structure_contraintes=structure_contraintes(instance_dsl),
        signature_objectifs=signature_objectifs(instance_dsl),
        date_modification=info.get("date_modification"),
    )

    solveurs = {
        s.id: SolveurSupervision(
            id=s.id,
            instance_id=s.instance_id,
            structure_contraintes=s.structure_contraintes,
            signature_objectifs=s.signature_objectifs,
        )
        for s in registre.rechercher_solveurs(client_id=client_id, instance_id=instance_id)
    }
    if id_solveur is not None:
        if id_solveur not in solveurs:
            raise SolveurHorsAtelier(
                f"le solveur {id_solveur!r} n'est pas un solveur actif de l'atelier {instance_id!r}"
            )
        solveurs = {id_solveur: solveurs[id_solveur]}

    executions = {
        e["execution_id"]: ExecutionSupervision(
            execution_id=e["execution_id"],
            instance_id=e["instance_id"],
            id_solveur=e["id_solveur"],
            date_execution=e["date_execution"],
            reussi=e["reussi"],
        )
        for e in etat.lister_executions(client_id=client_id)
        if e["instance_id"] == instance_id and (id_solveur is None or e["id_solveur"] == id_solveur)
    }

    bruts = detecter_signaux_llm(modele, (instance,), tuple(solveurs.values()), tuple(executions.values()))

    signaux: list[SignalDetecte] = []
    for brut in bruts:
        if brut.instance_id != instance_id:
            continue  # autre atelier ou instance_id halluciné — jamais propagé

        if brut.type_signal == "signature_orpheline":
            if solveurs:
                continue  # l'atelier a un solveur actif (celui analysé au moins) — signal impossible
            signaux.append(
                SignalSignatureOrpheline(
                    instance_id=instance_id,
                    client_id=client_id,
                    structure_contraintes=instance.structure_contraintes,
                    signature_objectifs=instance.signature_objectifs,
                )
            )
        elif brut.type_signal == "instance_a_replanifier":
            # Un solveur ne sert que l'instance qui l'a fait générer — `solveurs` ne contient déjà
            # que ceux de cet atelier, revérifié quand même : le LLM peut se tromper ou halluciner.
            if (
                brut.raison is None
                or brut.id_solveur_disponible not in solveurs
                or solveurs[brut.id_solveur_disponible].instance_id != instance_id
            ):
                continue
            signaux.append(
                SignalInstanceAReplanifier(
                    instance_id=instance_id,
                    client_id=client_id,
                    structure_contraintes=instance.structure_contraintes,
                    signature_objectifs=instance.signature_objectifs,
                    id_solveur_disponible=brut.id_solveur_disponible,
                    raison=brut.raison,
                )
            )
        else:  # echecs_repetes
            ids_valides = tuple(e for e in brut.execution_ids if e in executions)
            if brut.id_solveur is None or not ids_valides:
                continue
            signaux.append(
                SignalEchecsRepetes(
                    instance_id=instance_id,
                    client_id=client_id,
                    id_solveur=brut.id_solveur,
                    execution_ids=ids_valides,
                    structure_contraintes=instance.structure_contraintes,
                    signature_objectifs=instance.signature_objectifs,
                )
            )
    return tuple(signaux)


def detecter_signaux(
    etat: EtatAPI, registre: Registre, modele: BaseChatModel, client_id: str
) -> tuple[SignalDetecte, ...]:
    """Tous les ateliers d'un client, **un par un** (`detecter_signaux_instance`) — un appel LLM
    par atelier, jamais un seul pour tous. N'appelle jamais le LLM si le client n'a aucune
    instance — rien à détecter."""
    signaux: list[SignalDetecte] = []
    for info in etat.lister_instances(client_id=client_id):
        signaux.extend(detecter_signaux_instance(etat, registre, modele, info["instance_id"]))
    return tuple(signaux)


def detecter_commandes_en_retard(
    etat: EtatAPI, client_id: str, instance_id: str | None = None
) -> tuple[SignalCommandeEnRetard, ...]:
    """Aucun appel LLM (voir docstring de module) — réutilise directement
    `calculer_statut_commande`, déjà utilisée telle quelle par la page Commandes
    (`api/routes/ingestion.py::lister_toutes_commandes`, même patron de groupement par instance
    repris ici : un seul appel à `recuperer_instance`/`dernier_planning_pour_instance` par
    instance distincte, puis un appel à `calculer_statut_commande` par commande du groupe).

    `instance_id` restreint la détection aux commandes de cet atelier (analyse atelier par
    atelier, voir `supervision/orchestrateur.py::analyser_instance`) ; `None` = tous les ateliers
    du client.

    Ne retient que `statut.en_retard is True` explicitement — jamais `None`, qui signifie
    "aucun jugement possible" (commande jamais planifiée ou tâches encore manquantes du
    planning), pas "en retard"."""
    commandes = [c for c in etat.lister_commandes(instance_id=instance_id) if c.client_id == client_id]
    if not commandes:
        return ()

    par_instance: dict[str, list[CommandeEnregistree]] = {}
    for commande in commandes:
        par_instance.setdefault(commande.instance_id, []).append(commande)

    signaux: list[SignalCommandeEnRetard] = []
    for instance_id, commandes_instance in par_instance.items():
        _, instance = etat.recuperer_instance(instance_id)
        planning = etat.dernier_planning_pour_instance(instance_id)
        instance = instance_a_la_date(instance, etat.date_derniere_execution_reussie(instance_id))
        for commande in commandes_instance:
            statut = calculer_statut_commande(instance, planning, commande.taches, commande.date_limite)
            if statut.en_retard is True:
                signaux.append(
                    SignalCommandeEnRetard(
                        commande_id=commande.id,
                        instance_id=instance_id,
                        client_id=client_id,
                        date_fin_prevue=statut.date_fin_prevue,
                        date_limite=commande.date_limite,
                    )
                )
    return tuple(signaux)
