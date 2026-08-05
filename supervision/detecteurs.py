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
   actif, mais instance jamais exécutée (`executee=False`,
   `EtatAPI.lister_instances`) : couvre le cas d'une instance réingérée après
   un aléa (ressource indisponible, tâche modifiée — mécanisme documenté en
   `api/etat.py:9-14`) pour laquelle le solveur existant reste valide, juste
   besoin d'une exécution.
3. **Échecs répétés** — les `seuil` dernières exécutions d'une même instance
   sont toutes en échec.

Les signaux 1 et 2 se combinent naturellement sans logique dédiée : une
instance dont la modification a aussi changé le *type* d'une contrainte
tombe dans le signal 1 (régénération), une modification qui ne touche que
des valeurs tombe dans le signal 2 (ré-exécution) — le même passage sur
`lister_instances` répond aux deux à la fois.
"""

from __future__ import annotations

from dataclasses import dataclass

from api.etat import EtatAPI, signature_objectifs, structure_contraintes
from solver_store.registry import Registre

SEUIL_ECHECS_CONSECUTIFS = 3


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


@dataclass(frozen=True)
class SignalEchecsRepetes:
    instance_id: str
    client_id: str
    id_solveur: str
    execution_ids: tuple[str, ...]  # la plus récente en premier
    structure_contraintes: str
    signature_objectifs: str


def detecter_signature_et_replanification(
    etat: EtatAPI, registre: Registre, client_id: str
) -> tuple[tuple[SignalSignatureOrpheline, ...], tuple[SignalInstanceAReplanifier, ...]]:
    """Un seul passage sur `lister_instances` répond aux deux signaux à la
    fois (voir docstring du module)."""
    orphelines: list[SignalSignatureOrpheline] = []
    a_replanifier: list[SignalInstanceAReplanifier] = []
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
        elif not info["executee"]:
            a_replanifier.append(
                SignalInstanceAReplanifier(
                    instance_id=instance_id,
                    client_id=client_id,
                    structure_contraintes=structure,
                    signature_objectifs=objectifs,
                    id_solveur_disponible=solveurs[0].id,
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
