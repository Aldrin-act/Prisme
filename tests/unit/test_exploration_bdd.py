"""Couche 1 (§6.1) : le filtre SQL statique est du code écrit à la main,
déterministe et pur (aucune base) — testé en isolation. C'est un premier
filtre faible (voir `exploration_bdd.py`, docstring du module) ; la vraie
frontière (rôle Postgres lecture seule) n'est testable qu'avec une vraie
base, voir `tests/integration/test_exploration_bdd_greensig.py`.
"""

from __future__ import annotations

import pytest

from adapters.agent_comprehension.exploration_bdd import (
    ErreurRequeteNonAutorisee,
    _valider_requete_lecture_seule,
    dsn_lecture_seule_pour_client,
)


def test_select_simple_accepte() -> None:
    requete = "SELECT id, nom FROM taches"
    assert _valider_requete_lecture_seule(requete) == requete


def test_select_avec_point_virgule_final_accepte() -> None:
    requete = "SELECT id FROM taches;"
    assert _valider_requete_lecture_seule(requete) == requete


def test_with_cte_accepte() -> None:
    requete = "WITH actives AS (SELECT id FROM taches WHERE statut = 'PLANIFIEE') SELECT * FROM actives"
    assert _valider_requete_lecture_seule(requete) == requete


def test_select_insensible_a_la_casse_accepte() -> None:
    assert _valider_requete_lecture_seule("select id from taches") == "select id from taches"


@pytest.mark.parametrize(
    "requete",
    [
        "INSERT INTO taches (id) VALUES (1)",
        "UPDATE taches SET statut = 'DONE'",
        "DELETE FROM taches",
        "DROP TABLE taches",
        "ALTER TABLE taches ADD COLUMN x int",
        "GRANT SELECT ON taches TO public",
        "CREATE TABLE x (id int)",
        "TRUNCATE taches",
        "CALL une_procedure()",
    ],
)
def test_instruction_non_select_rejetee(requete: str) -> None:
    with pytest.raises(ErreurRequeteNonAutorisee):
        _valider_requete_lecture_seule(requete)


def test_plusieurs_instructions_rejetees() -> None:
    with pytest.raises(ErreurRequeteNonAutorisee, match="plusieurs instructions"):
        _valider_requete_lecture_seule("SELECT id FROM taches; DELETE FROM taches")


def test_mot_interdit_dans_un_select_par_ailleurs_valide_rejete() -> None:
    with pytest.raises(ErreurRequeteNonAutorisee, match="mot-clé non autorisé"):
        _valider_requete_lecture_seule("SELECT pg_terminate_backend(pid) FROM pg_stat_activity")


def test_mot_interdit_mentionne_dans_un_commentaire_nest_pas_execute_mais_reste_inoffensif() -> None:
    """Un commentaire est inerte pour Postgres (jamais exécuté) — le filtre
    retire les commentaires avant de chercher un point-virgule ou un mot
    interdit, donc un commentaire mentionnant un mot interdit ou contenant
    un `;` ne doit pas faire rejeter à tort une requête par ailleurs sûre."""
    requete = "SELECT id FROM taches -- ne pas faire DROP TABLE ici ; jamais\n"
    assert _valider_requete_lecture_seule(requete) == requete


def test_requete_vide_rejetee() -> None:
    with pytest.raises(ErreurRequeteNonAutorisee, match="vide"):
        _valider_requete_lecture_seule("   ")


def test_dsn_lecture_seule_pour_client_greensig_delegue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GREENSIG_LECTURE_SEULE_DATABASE_URL", "postgresql://sentinel")
    assert dsn_lecture_seule_pour_client("greensig") == "postgresql://sentinel"


def test_dsn_lecture_seule_pour_client_non_configure_renvoie_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRISME_DSN_LECTURE_SEULE_ACME", raising=False)
    assert dsn_lecture_seule_pour_client("acme") is None


def test_dsn_lecture_seule_pour_client_lit_la_variable_dediee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISME_DSN_LECTURE_SEULE_ACME", "postgresql://acme")
    assert dsn_lecture_seule_pour_client("acme") == "postgresql://acme"


def test_dsn_lecture_seule_pour_client_normalise_les_caracteres_non_alphanumeriques(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRISME_DSN_LECTURE_SEULE_ACME_CORP_FR", "postgresql://acme-corp")
    assert dsn_lecture_seule_pour_client("acme-corp.fr") == "postgresql://acme-corp"


def test_dsn_lecture_seule_pour_client_variable_vide_traitee_comme_absente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRISME_DSN_LECTURE_SEULE_ACME", "")
    assert dsn_lecture_seule_pour_client("acme") is None
