"""Exécution en conteneur jetable (§5.2, §5.3, §7) : conteneur neuf → code
figé + données injectés → calcul → destruction.

Restrictions appliquées à chaque exécution : réseau coupé (`network_mode=
"none"`), système de fichiers racine en lecture seule, utilisateur non-root
(défini dans l'image), limites CPU/mémoire/PID, délai d'exécution, `--rm`.

Ce module suppose l'image `IMAGE_SANDBOX` déjà construite
(`docker build -t prisme-sandbox:latest -f sandbox/container/Dockerfile .`) —
il ne la reconstruit jamais lui-même : construire une image est une
opération d'environnement, pas une exécution de solveur.

`executer_solveur_valide` chaîne les trois pièces du critère de validation
de l'Étape 7 : récupération dans le store (`solver_store/registry.py`),
exécution sandboxée, puis garde-fou de faisabilité en aval (§6.7). La
validation d'entrée (garde-fou amont) est supposée déjà faite par l'appelant
(`dsl.validation.charger_instance`) avant d'arriver ici.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from dsl.schema import InstanceTRCO, Planning
from solver_store.registry import ErreurIntegriteSolveur, Registre
from validation_engine.feasibility_checker import ResultatFaisabilite, verifier_faisabilite

IMAGE_SANDBOX = "prisme-sandbox:latest"
_CHEMIN_CODE_CONTENEUR = "/mnt/solveur.py"
_CHEMIN_INSTANCE_CONTENEUR = "/mnt/instance.json"


class ErreurExecutionSandbox(Exception):
    """Le conteneur n'a pas pu s'exécuter proprement (image absente, délai
    dépassé, sortie non nulle, isolation ayant bloqué une tentative...)."""


@dataclass(frozen=True)
class LimitesSandbox:
    limite_temps_s: float = 30.0
    limite_memoire: str = "512m"
    limite_cpu_nano: int = 1_000_000_000  # 1 vCPU
    limite_pids: int = 64


def executer_dans_sandbox(
    chemin_code: Path, instance: InstanceTRCO, limites: LimitesSandbox = LimitesSandbox()
) -> Planning | None:
    """Exécute le code figé à `chemin_code` sur `instance`, dans un
    conteneur jetable et isolé. Lève `ErreurExecutionSandbox` si le
    conteneur échoue, dépasse son délai, ou si l'isolation a empêché
    l'exécution (image absente en premier lieu)."""
    import docker
    from docker.errors import DockerException, ImageNotFound

    try:
        client = docker.from_env()
    except DockerException as erreur:
        raise ErreurExecutionSandbox(f"impossible de joindre le démon Docker : {erreur}") from erreur

    with tempfile.TemporaryDirectory() as dossier_temp:
        chemin_instance_hote = Path(dossier_temp) / "instance.json"
        chemin_instance_hote.write_text(instance.model_dump_json(), encoding="utf-8")

        conteneur = None
        try:
            conteneur = client.containers.run(
                IMAGE_SANDBOX,
                command=[_CHEMIN_CODE_CONTENEUR, _CHEMIN_INSTANCE_CONTENEUR],
                volumes={
                    str(Path(chemin_code).resolve()): {"bind": _CHEMIN_CODE_CONTENEUR, "mode": "ro"},
                    str(chemin_instance_hote.resolve()): {
                        "bind": _CHEMIN_INSTANCE_CONTENEUR,
                        "mode": "ro",
                    },
                },
                network_mode="none",
                read_only=True,
                tmpfs={"/tmp": "size=64m"},
                mem_limit=limites.limite_memoire,
                nano_cpus=limites.limite_cpu_nano,
                pids_limit=limites.limite_pids,
                security_opt=["no-new-privileges"],
                user="10001:10001",
                detach=True,
                auto_remove=False,
            )
            resultat_attente = conteneur.wait(timeout=limites.limite_temps_s)
            code_sortie = resultat_attente.get("StatusCode", 1)
            sortie_brute = conteneur.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
        except ImageNotFound as erreur:
            raise ErreurExecutionSandbox(
                f"image {IMAGE_SANDBOX!r} introuvable — construire avec "
                "`docker build -t prisme-sandbox:latest -f sandbox/container/Dockerfile .`"
            ) from erreur
        except Exception as erreur:  # délai dépassé, erreur du démon, etc.
            if conteneur is not None:
                try:
                    conteneur.kill()
                except Exception:
                    pass
            raise ErreurExecutionSandbox(f"échec d'exécution dans le sandbox : {erreur}") from erreur
        finally:
            if conteneur is not None:
                try:
                    conteneur.remove(force=True)
                except Exception:
                    pass

    if code_sortie != 0:
        raise ErreurExecutionSandbox(f"le conteneur a quitté avec le code {code_sortie} : {sortie_brute.strip()}")

    sortie = sortie_brute.strip()
    if sortie == "null":
        return None
    return Planning.model_validate_json(sortie)


@dataclass(frozen=True)
class ResultatExecution:
    """Le résultat de la chaîne complète store → sandbox → garde-fou aval."""

    planning: Planning | None
    verdict_faisabilite: ResultatFaisabilite | None
    erreur: str | None

    @property
    def reussi(self) -> bool:
        return (
            self.erreur is None
            and self.planning is not None
            and self.verdict_faisabilite is not None
            and self.verdict_faisabilite.legal
        )


def executer_solveur_valide(
    registre: Registre,
    id_solveur: str,
    instance: InstanceTRCO,
    limites: LimitesSandbox = LimitesSandbox(),
) -> ResultatExecution:
    """Récupère `id_solveur` dans le store, l'exécute en sandbox sur
    `instance`, puis applique le garde-fou de faisabilité en aval (§6.7).

    `instance` est supposée déjà validée en amont
    (`dsl.validation.charger_instance`) — ce n'est pas refait ici.
    """
    try:
        artefact = registre.recuperer_solveur(id_solveur)
    except (KeyError, ErreurIntegriteSolveur) as erreur:
        return ResultatExecution(None, None, f"solveur introuvable ou corrompu : {erreur}")

    try:
        planning = executer_dans_sandbox(artefact.chemin_code, instance, limites)
    except ErreurExecutionSandbox as erreur:
        return ResultatExecution(None, None, str(erreur))

    if planning is None:
        return ResultatExecution(None, None, "le solveur a jugé l'instance infaisable")

    verdict = verifier_faisabilite(instance, planning)
    return ResultatExecution(planning, verdict, None)
