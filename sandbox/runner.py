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

import ast
import json
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dsl.schema import InstanceTRCO, Planning
from solver_store.registry import ErreurIntegriteSolveur, Registre
from validation_engine.feasibility_checker import ResultatFaisabilite, verifier_faisabilite
from validation_engine.jours_non_ouvres import repousser_hors_jours_non_ouvres

IMAGE_SANDBOX = "prisme-sandbox:latest"
_CHEMIN_CODE_CONTENEUR = "/mnt/solveur.py"
_CHEMIN_INSTANCE_CONTENEUR = "/mnt/instance.json"
_CHEMIN_PLANNING_PRECEDENT_CONTENEUR = "/mnt/planning_precedent.json"
_PARAMETRES_HORIZON_GELE = {"planning_precedent", "horizon_gele_jours"}


def _solveur_supporte_horizon_gele(code_source: str) -> bool:
    """`ast.parse` uniquement (§5.3 : jamais d'exécution de code non fiable hors sandbox) —
    vrai si la fonction top-level `resoudre` déclare `planning_precedent`/`horizon_gele_jours`
    parmi ses paramètres (replanification à horizon glissant, Phase 2). Les solveurs enregistrés
    avant l'ajout de cette fonctionnalité (signature à un seul paramètre) renvoient `False`."""
    try:
        arbre = ast.parse(code_source)
    except SyntaxError:
        return False
    for noeud in arbre.body:
        if isinstance(noeud, ast.FunctionDef) and noeud.name == "resoudre":
            noms_parametres = {a.arg for a in (*noeud.args.args, *noeud.args.kwonlyargs)}
            return _PARAMETRES_HORIZON_GELE.issubset(noms_parametres)
    return False


# Mode audit des tests générés (canal d'audit, voir generation/agents/testeur.py) — même
# image que le mode solveur ci-dessus, sélectionné par un `entrypoint=` docker-py explicite
# (voir `_executer_et_recuperer_logs`/`executer_tests_dans_sandbox`) plutôt qu'un second
# Dockerfile/image à maintenir. Le solveur DOIT être monté sous ce nom de fichier exact —
# c'est le contrat d'import des tests générés (`from solveur_candidat import resoudre`,
# voir `generation/prompts/testeur.md`).
_CHEMIN_SOLVEUR_TESTS_CONTENEUR = "/mnt/solveur_candidat.py"
_CHEMIN_TESTS_CONTENEUR = "/mnt/test_solveur_candidat.py"
_ENTRYPOINT_TESTS = ["python", "/app/executer_tests_dans_conteneur.py"]


class ErreurExecutionSandbox(Exception):
    """Le conteneur n'a pas pu s'exécuter proprement (image absente, délai
    dépassé, sortie non nulle, isolation ayant bloqué une tentative...)."""


def sandbox_disponible() -> bool:
    """Le démon Docker est-il joignable ? Même logique que `_docker_disponible`
    de `tests/integration/conftest.py`, exposée ici pour la route de santé de
    l'API (`/supervision/sante`) — import paresseux : `docker` est un extra
    optionnel (`.[sandbox]`)."""
    try:
        import docker

        docker.from_env().ping()
        return True
    except Exception:
        return False


@dataclass(frozen=True)
class LimitesSandbox:
    limite_temps_s: float = 30.0
    limite_memoire: str = "512m"
    limite_cpu_nano: int = 1_000_000_000  # 1 vCPU
    limite_pids: int = 64


def _executer_et_recuperer_logs(
    client: Any,
    *,
    entrypoint: list[str] | None,
    command: list[str],
    volumes: dict[str, dict[str, str]],
    limites: LimitesSandbox,
) -> tuple[int, str]:
    """Lance un conteneur jetable avec les restrictions d'isolation standard
    (§5.2/§7 : réseau coupé, racine en lecture seule, non-root, limites
    CPU/mémoire/PID, `--rm`), attend sa fin, récupère ses logs, le
    force-supprime — commun aux deux modes du sandbox (solveur et audit des
    tests générés, qui ne diffèrent que par `entrypoint`/`command`/
    `volumes`). Lève `ErreurExecutionSandbox` pour tout échec Docker (image
    absente, délai dépassé, erreur du démon) ; ne juge jamais du contenu de
    la sortie — ça reste au appelant (code de sortie non nul, parsing...)."""
    from docker.errors import ImageNotFound

    conteneur = None
    try:
        conteneur = client.containers.run(
            IMAGE_SANDBOX,
            entrypoint=entrypoint,
            command=command,
            volumes=volumes,
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

    return code_sortie, sortie_brute


def executer_dans_sandbox(
    chemin_code: Path,
    instance: InstanceTRCO,
    limites: LimitesSandbox = LimitesSandbox(),
    planning_precedent: Planning | None = None,
    horizon_gele_jours: int = 0,
) -> Planning | None:
    """Exécute le code figé à `chemin_code` sur `instance`, dans un
    conteneur jetable et isolé. Lève `ErreurExecutionSandbox` si le
    conteneur échoue, dépasse son délai, ou si l'isolation a empêché
    l'exécution (image absente en premier lieu).

    `planning_precedent`/`horizon_gele_jours` (Phase 2, replanification à horizon glissant) ne
    changent rien à la commande/aux volumes envoyés au conteneur quand `horizon_gele_jours == 0`
    (le défaut) — comportement strictement identique à avant l'ajout de cette fonctionnalité.
    L'appelant (`executer_solveur_valide`) est responsable de vérifier au préalable que le
    solveur ciblé supporte ces paramètres (`_solveur_supporte_horizon_gele`) — ce module ne le
    refait pas ici."""
    import docker
    from docker.errors import DockerException

    try:
        client = docker.from_env()
    except DockerException as erreur:
        raise ErreurExecutionSandbox(f"impossible de joindre le démon Docker : {erreur}") from erreur

    with tempfile.TemporaryDirectory() as dossier_temp:
        chemin_instance_hote = Path(dossier_temp) / "instance.json"
        chemin_instance_hote.write_text(instance.model_dump_json(), encoding="utf-8")

        command = [_CHEMIN_CODE_CONTENEUR, _CHEMIN_INSTANCE_CONTENEUR]
        volumes = {
            str(Path(chemin_code).resolve()): {"bind": _CHEMIN_CODE_CONTENEUR, "mode": "ro"},
            str(chemin_instance_hote.resolve()): {
                "bind": _CHEMIN_INSTANCE_CONTENEUR,
                "mode": "ro",
            },
        }
        if horizon_gele_jours > 0:
            chemin_planning_conteneur = "-"
            if planning_precedent is not None:
                chemin_planning_precedent_hote = Path(dossier_temp) / "planning_precedent.json"
                chemin_planning_precedent_hote.write_text(planning_precedent.model_dump_json(), encoding="utf-8")
                volumes[str(chemin_planning_precedent_hote.resolve())] = {
                    "bind": _CHEMIN_PLANNING_PRECEDENT_CONTENEUR,
                    "mode": "ro",
                }
                chemin_planning_conteneur = _CHEMIN_PLANNING_PRECEDENT_CONTENEUR
            command += [chemin_planning_conteneur, str(horizon_gele_jours)]

        code_sortie, sortie_brute = _executer_et_recuperer_logs(
            client,
            entrypoint=None,
            command=command,
            volumes=volumes,
            limites=limites,
        )

    if code_sortie != 0:
        raise ErreurExecutionSandbox(f"le conteneur a quitté avec le code {code_sortie} : {sortie_brute.strip()}")

    sortie = sortie_brute.strip()
    if sortie == "null":
        return None
    return Planning.model_validate_json(sortie)


@dataclass(frozen=True)
class ResultatTestUnitaire:
    nom: str
    reussi: bool
    message: str | None


@dataclass(frozen=True)
class RapportTestsSandbox:
    """Résultat de l'exécution des tests générés par l'agent Testeur dans le
    bac à sable — canal d'audit pur (voir `generation/agents/testeur.py`),
    jamais un critère d'acceptation."""

    tests: tuple[ResultatTestUnitaire, ...]
    erreur: str | None

    @property
    def reussi(self) -> bool:
        """Aucune erreur de collecte ET tous les tests générés passent.
        `tests == ()` avec `erreur is None` compte comme réussi (Testeur peu
        prolixe, pas un échec du sandbox) — de toute façon jamais un gate."""
        return self.erreur is None and all(t.reussi for t in self.tests)

    def en_dict(self) -> dict:
        """Forme sérialisable pour la persistance (`api/etat.py`/
        `api/etat_postgres.py`, colonne JSONB) — écrit à la main plutôt que
        `dataclasses.asdict` (convention `.en_texte()`/`.en_dict()` du reste
        du code, jamais de sérialisation par réflexion générique)."""
        return {
            "tests": [{"nom": t.nom, "reussi": t.reussi, "message": t.message} for t in self.tests],
            "erreur": self.erreur,
            "reussi": self.reussi,
        }


def executer_tests_dans_sandbox(
    code_source: str, code_tests: str, limites: LimitesSandbox = LimitesSandbox()
) -> RapportTestsSandbox:
    """Écrit `code_source`/`code_tests` sur disque (contrairement à
    `executer_dans_sandbox`, rien n'existe encore sur le disque hôte à ce
    stade — voir `generation/graph.py::_noeud_test_sandbox`), monte les deux
    en lecture seule dans le même conteneur jetable que le mode solveur
    (`entrypoint=` explicite pour sélectionner le mode, voir
    `sandbox/container/executer_tests_dans_conteneur.py`), et parse le JSON
    produit. Canal d'audit : lève `ErreurExecutionSandbox` uniquement pour un
    échec Docker (démon injoignable, image absente, délai dépassé, sortie non
    nulle) — jamais parce que des tests générés ont échoué, ce que
    `RapportTestsSandbox.reussi` porte déjà."""
    import docker
    from docker.errors import DockerException

    try:
        client = docker.from_env()
    except DockerException as erreur:
        raise ErreurExecutionSandbox(f"impossible de joindre le démon Docker : {erreur}") from erreur

    with tempfile.TemporaryDirectory() as dossier_temp:
        chemin_solveur_hote = Path(dossier_temp) / "solveur_candidat.py"
        chemin_tests_hote = Path(dossier_temp) / "test_solveur_candidat.py"
        chemin_solveur_hote.write_text(code_source, encoding="utf-8")
        chemin_tests_hote.write_text(code_tests, encoding="utf-8")

        code_sortie, sortie_brute = _executer_et_recuperer_logs(
            client,
            entrypoint=_ENTRYPOINT_TESTS,
            command=[_CHEMIN_SOLVEUR_TESTS_CONTENEUR, _CHEMIN_TESTS_CONTENEUR],
            volumes={
                str(chemin_solveur_hote.resolve()): {"bind": _CHEMIN_SOLVEUR_TESTS_CONTENEUR, "mode": "ro"},
                str(chemin_tests_hote.resolve()): {"bind": _CHEMIN_TESTS_CONTENEUR, "mode": "ro"},
            },
            limites=limites,
        )

    if code_sortie != 0:
        raise ErreurExecutionSandbox(f"le conteneur a quitté avec le code {code_sortie} : {sortie_brute.strip()}")

    # pytest imprime lui-même son propre rapport (points de progression, erreurs de
    # collecte...) sur stdout AVANT le JSON du harnais — jamais après (`print(json.dumps(...))`
    # est toujours le tout dernier appel de `main()`, une fois `pytest.main()` déjà retourné) —
    # donc seule la dernière ligne non vide est le contrat à parser, jamais la sortie entière.
    lignes = [ligne for ligne in sortie_brute.splitlines() if ligne.strip()]
    if not lignes:
        raise ErreurExecutionSandbox("le conteneur n'a produit aucune sortie exploitable")
    donnees = json.loads(lignes[-1])
    return RapportTestsSandbox(
        tests=tuple(
            ResultatTestUnitaire(nom=t["nom"], reussi=t["reussi"], message=t.get("message"))
            for t in donnees["tests"]
        ),
        erreur=donnees.get("erreur"),
    )


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
    planning_precedent: Planning | None = None,
    horizon_gele_jours: int = 0,
) -> ResultatExecution:
    """Récupère `id_solveur` dans le store, l'exécute en sandbox sur
    `instance`, puis applique le garde-fou de faisabilité en aval (§6.7).

    `instance` est supposée déjà validée en amont
    (`dsl.validation.charger_instance`) — ce n'est pas refait ici.

    Si `horizon_gele_jours > 0` et que le solveur enregistré ne supporte pas ce paramètre
    (généré avant l'ajout de la replanification à horizon glissant, Phase 2), l'exécution échoue
    explicitement ici — jamais une dégradation silencieuse vers un solve normal, jamais un
    conteneur lancé pour rien (décision confirmée : les solveurs déjà enregistrés continuent de
    fonctionner normalement pour toute exécution *sans* horizon gelé, mais n'apprennent jamais à
    en gérer un sans être régénérés)."""
    try:
        artefact = registre.recuperer_solveur(id_solveur)
    except (KeyError, ErreurIntegriteSolveur) as erreur:
        return ResultatExecution(None, None, f"solveur introuvable ou corrompu : {erreur}")

    if horizon_gele_jours > 0 and not _solveur_supporte_horizon_gele(artefact.code_source):
        return ResultatExecution(
            None,
            None,
            "ce solveur (généré avant l'ajout de l'horizon gelé) ne supporte pas "
            "horizon_gele_jours — régénérez-le pour activer cette fonctionnalité",
        )

    try:
        planning = executer_dans_sandbox(
            artefact.chemin_code,
            instance,
            limites,
            planning_precedent=planning_precedent,
            horizon_gele_jours=horizon_gele_jours,
        )
    except ErreurExecutionSandbox as erreur:
        return ResultatExecution(None, None, str(erreur))

    if planning is None:
        return ResultatExecution(None, None, "le solveur a jugé l'instance infaisable")

    # Jours non ouvrés par défaut (samedi/dimanche) : correction après coup, jamais appris au
    # solveur généré — voir validation_engine/jours_non_ouvres.py. Les opérations déjà gelées par
    # horizon_gele_jours ne sont jamais décalées, quel que soit le jour où elles tombent.
    operations_gelees = frozenset(
        (op.tache, op.ressource)
        for op in (planning_precedent.operations if planning_precedent else [])
        if op.debut < horizon_gele_jours
    )
    # Heure locale du serveur (et non UTC) : les heures ouvrées se lisent sur l'horloge de l'atelier,
    # la même que celle du navigateur qui affiche le planning (l'ancrage du jour 0).
    planning = repousser_hors_jours_non_ouvres(
        instance, planning, datetime.now(UTC).astimezone(), operations_gelees
    )

    verdict = verifier_faisabilite(instance, planning)
    return ResultatExecution(planning, verdict, None)
