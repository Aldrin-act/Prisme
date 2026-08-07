"""Détection de signaux (§2, MT7) : purs, déterministes, sans appel LLM — le
LLM (`supervision/agent.py`) n'intervient qu'après, pour habiller ces faits
d'une proposition priorisée en langage naturel. Trois signaux, tous dérivés
de données déjà présentes dans `api/etat.py`/`solver_store/registry.py`, jamais
recalculés ailleurs :

1. **Signature orpheline** — la signature courante (`structure_contraintes`/
   `signature_objectifs`, `api/etat.py:33-47`) d'une instance ne correspond à
   aucun solveur actif enregistré pour son client. C'est exactement le cas
   qui échoue aujourd'hui en synchrone avec un `HTTPException(409, ...)`
   (`api/routes/execution.py`), sans jamais être tracé nulle part.
2. **Instance à replanifier** — signature qui correspond bien à un solveur
   actif, mais soit l'instance n'a jamais été exécutée, soit elle l'a été
   puis a été modifiée depuis (`modifier_instance`/`modifier_objectifs`,
   `api/etat.py`) sans être ré-exécutée : le planning existant ne
   correspond plus à son contenu actuel, alors que le solveur enregistré
   reste valide, juste besoin d'une exécution. Distingue les deux cas via
   `SignalInstanceAReplanifier.raison`, en comparant la dernière
   modification de l'instance (`info["date_modification"]`) à sa dernière
   exécution (`lister_executions`) — jamais via le seul booléen `executee`,
   qui reste vrai indéfiniment une fois l'instance exécutée au moins une
   fois, y compris après une modification en place ultérieure.
3. **Échecs répétés** — les `seuil` dernières exécutions d'une même instance
   sont toutes en échec.

Les signaux 1 et 2 se combinent naturellement sans logique dédiée : une
instance dont la modification a aussi changé le *type* d'une contrainte ou
d'un objectif tombe dans le signal 1 (régénération, `structure_contraintes`/
`signature_objectifs` recalculées à chaque appel) ; une modification qui ne
touche que des valeurs (durées, poids, `methode`...) tombe dans le signal 2
(ré-exécution) — le même passage sur `lister_instances` répond aux deux à la
fois.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from api.etat import EtatAPI, signature_objectifs, structure_contraintes
from solver_store.registry import Registre

SEUIL_ECHECS_CONSECUTIFS = 3

RaisonReplanification = Literal["jamais_executee", "modifiee_apres_derniere_execution"]


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
    execution_ids: tuple[str, ...]  # la plus récente en premier
    structure_contraintes: str
    signature_objectifs: str


def _derniere_execution_par_instance(etat: EtatAPI, client_id: str) -> dict[str, str]:
    """Date de la plus récente exécution de chaque instance — même motif de
    regroupement que `detecter_echecs_repetes`, sans dépendre de l'ordre déjà
    trié ou non de `lister_executions` (in-memory vs Postgres)."""
    dernieres: dict[str, str] = {}
    for execution in etat.lister_executions(client_id=client_id):
        instance_id = execution["instance_id"]
        date_execution = execution["date_execution"]
        if date_execution is not None and (
            instance_id not in dernieres or date_execution > dernieres[instance_id]
        ):
            dernieres[instance_id] = date_execution
    return dernieres


def detecter_signature_et_replanification(
    etat: EtatAPI, registre: Registre, client_id: str
) -> tuple[tuple[SignalSignatureOrpheline, ...], tuple[SignalInstanceAReplanifier, ...]]:
    """Un seul passage sur `lister_instances` répond aux deux signaux à la
    fois (voir docstring du module)."""
    orphelines: list[SignalSignatureOrpheline] = []
    a_replanifier: list[SignalInstanceAReplanifier] = []
    dernieres_executions = _derniere_execution_par_instance(etat, client_id)
    for info in etat.lister_instances(client_id=client_id):
        instance_id = info["instance_id"]
        _, instance = etat.recuperer_instance(instance_id)
        structure = structure_contraintes(instance)
        objectifs = signature_objectifs(instance)
        solveurs = registre.rechercher_solveurs(
            client_id=client_id, structure_contraintes=structure, signature_objectifs=objectifs
        )
        if not solveurs:
            orphelines.append(
                SignalSignatureOrpheline(
                    instance_id=instance_id,
                    client_id=client_id,
                    structure_contraintes=structure,
                    signature_objectifs=objectifs,
                )
            )
            continue

        derniere_execution = dernieres_executions.get(instance_id)
        raison: RaisonReplanification | None = None
        if derniere_execution is None:
            raison = "jamais_executee"
        elif info["date_modification"] is not None and info["date_modification"] > derniere_execution:
            raison = "modifiee_apres_derniere_execution"

        if raison is not None:
            a_replanifier.append(
                SignalInstanceAReplanifier(
                    instance_id=instance_id,
                    client_id=client_id,
                    structure_contraintes=structure,
                    signature_objectifs=objectifs,
                    id_solveur_disponible=solveurs[0].id,
                    raison=raison,
                )
            )
    return tuple(orphelines), tuple(a_replanifier)


def detecter_echecs_repetes(
    etat: EtatAPI, client_id: str, seuil: int = SEUIL_ECHECS_CONSECUTIFS
) -> tuple[SignalEchecsRepetes, ...]:
    """Groupe par instance, trie explicitement par `date_execution` — les
    implémentations in-memory et Postgres de `lister_executions` n'ordonnent
    pas pareil (insertion vs `ORDER BY date_execution DESC`), cette fonction
    ne doit dépendre d'aucune des deux."""
    par_instance: dict[str, list[dict]] = {}
    for execution in etat.lister_executions(client_id=client_id):
        par_instance.setdefault(execution["instance_id"], []).append(execution)

    signaux: list[SignalEchecsRepetes] = []
    for instance_id, executions in par_instance.items():
        executions_triees = sorted(executions, key=lambda e: e["date_execution"], reverse=True)
        dernieres = executions_triees[:seuil]
        if len(dernieres) < seuil or any(e["reussi"] for e in dernieres):
            continue
        _, instance = etat.recuperer_instance(instance_id)
        signaux.append(
            SignalEchecsRepetes(
                instance_id=instance_id,
                client_id=client_id,
                id_solveur=dernieres[0]["id_solveur"],
                execution_ids=tuple(e["execution_id"] for e in dernieres),
                structure_contraintes=structure_contraintes(instance),
                signature_objectifs=signature_objectifs(instance),
            )
        )
    return tuple(signaux)
