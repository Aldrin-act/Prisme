"""Store de code persistant (§5.2, §7) : indexation et récupération des
solveurs validés, par client / structure de contraintes.

Backend SQLite (stdlib, zéro configuration) plutôt que PostgreSQL pour ce
stade de PoC — même interface (`Registre`), migrable plus tard vers
PostgreSQL sans redesign du reste du système, ce module étant le seul point
de contact.

Le code source n'est jamais dupliqué en base : seul son chemin sur disque
(`artifacts/<id>/solveur.py`) et son empreinte SHA-256 le sont, pour détecter
toute altération du fichier « figé » après coup — le principe fondateur
veut que le code persiste tel quel, jamais réécrit une fois validé.
"""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from validation_engine.cascade import VerdictCascade

DOSSIER_STORE = Path(__file__).resolve().parent
DOSSIER_ARTEFACTS = DOSSIER_STORE / "artifacts"
CHEMIN_BASE_PAR_DEFAUT = DOSSIER_STORE / "registre.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS solveurs (
    id TEXT PRIMARY KEY,
    client_id TEXT,
    structure_contraintes TEXT NOT NULL,
    chemin_code TEXT NOT NULL,
    empreinte_sha256 TEXT NOT NULL,
    date_validation TEXT NOT NULL
);
"""


class ErreurIntegriteSolveur(Exception):
    """Le code sur disque ne correspond plus à l'empreinte enregistrée —
    le principe « code figé » est possiblement violé."""


@dataclass(frozen=True)
class ArtefactSolveur:
    id: str
    client_id: str | None
    structure_contraintes: str
    chemin_code: Path
    empreinte_sha256: str
    date_validation: str
    code_source: str


def _empreinte(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


class Registre:
    """Un registre SQLite de solveurs validés.

    Chaque instance pointe vers un fichier `.sqlite3` (`chemin_base`) et un
    dossier d'artefacts (`dossier_artefacts`) ; les deux valent par défaut
    ceux de `solver_store/`, mais des chemins dédiés (ex. `tmp_path` en
    test) évitent de polluer le store réel.
    """

    def __init__(
        self,
        chemin_base: Path = CHEMIN_BASE_PAR_DEFAUT,
        dossier_artefacts: Path = DOSSIER_ARTEFACTS,
    ) -> None:
        self._chemin_base = chemin_base
        self._dossier_artefacts = dossier_artefacts
        self._dossier_artefacts.mkdir(parents=True, exist_ok=True)
        with closing(self._connexion()) as connexion:
            connexion.execute(_SCHEMA)
            connexion.commit()

    def _connexion(self) -> sqlite3.Connection:
        return sqlite3.connect(self._chemin_base)

    def enregistrer_solveur(
        self,
        code_source: str,
        structure_contraintes: str,
        verdict_cascade: VerdictCascade,
        client_id: str | None = None,
    ) -> str:
        """N'enregistre que du code déjà passé au vert par la cascade
        (Étape 5) — le store ne persiste jamais un solveur non validé
        (principe fondateur, §5.2)."""
        if not verdict_cascade.reussi:
            raise ValueError(
                "refus d'enregistrer un solveur dont la cascade de validation n'est pas au vert"
            )

        id_solveur = str(uuid.uuid4())
        dossier = self._dossier_artefacts / id_solveur
        dossier.mkdir(parents=True, exist_ok=False)
        chemin_code = dossier / "solveur.py"
        chemin_code.write_text(code_source, encoding="utf-8")

        with closing(self._connexion()) as connexion:
            connexion.execute(
                "INSERT INTO solveurs "
                "(id, client_id, structure_contraintes, chemin_code, empreinte_sha256, date_validation) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    id_solveur,
                    client_id,
                    structure_contraintes,
                    str(chemin_code),
                    _empreinte(code_source),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            connexion.commit()

        return id_solveur

    def recuperer_solveur(self, id_solveur: str) -> ArtefactSolveur:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                "SELECT id, client_id, structure_contraintes, chemin_code, empreinte_sha256, "
                "date_validation FROM solveurs WHERE id = ?",
                (id_solveur,),
            ).fetchone()

        if ligne is None:
            raise KeyError(f"aucun solveur enregistré avec l'id {id_solveur!r}")

        id_, client_id, structure, chemin_code, empreinte, date_validation = ligne
        code_source = Path(chemin_code).read_text(encoding="utf-8")
        if _empreinte(code_source) != empreinte:
            raise ErreurIntegriteSolveur(
                f"le code de {id_solveur!r} sur disque ne correspond plus à l'empreinte enregistrée"
            )

        return ArtefactSolveur(
            id=id_,
            client_id=client_id,
            structure_contraintes=structure,
            chemin_code=Path(chemin_code),
            empreinte_sha256=empreinte,
            date_validation=date_validation,
            code_source=code_source,
        )

    def rechercher_solveurs(
        self, client_id: str | None = None, structure_contraintes: str | None = None
    ) -> list[ArtefactSolveur]:
        requete = "SELECT id FROM solveurs WHERE 1 = 1"
        parametres: list[str] = []
        if client_id is not None:
            requete += " AND client_id = ?"
            parametres.append(client_id)
        if structure_contraintes is not None:
            requete += " AND structure_contraintes = ?"
            parametres.append(structure_contraintes)

        with closing(self._connexion()) as connexion:
            ids = [ligne[0] for ligne in connexion.execute(requete, parametres).fetchall()]

        return [self.recuperer_solveur(id_solveur) for id_solveur in ids]
