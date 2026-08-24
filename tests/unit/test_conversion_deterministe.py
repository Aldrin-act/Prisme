"""Couche 1 (§6.1) : la reconstitution de blocs CSV/JSON à partir du texte brut
d'une source (`api/routes/sources.py`, alternative sans agent LLM à
`generer_instance`) est une fonction pure, sans dépendance externe — testée
ici indépendamment de toute route FastAPI (voir `tests/integration/test_api_sources.py`
pour le comportement bout en bout via `POST /sources/{id}/generer-instance-deterministe`).
"""

from __future__ import annotations

import pytest

from api.routes.sources import (
    ErreurStructureNonReconnue,
    _decouper_blocs_csv,
    _reconstruire_fichiers_csv,
    _traduire_deterministe,
    _type_par_entete,
    _type_par_nom_fichier,
)


def test_decouper_blocs_csv_sans_marqueur_renvoie_un_bloc_anonyme() -> None:
    assert _decouper_blocs_csv("id,nom\nT1,Decoupe") == [("", "id,nom\nT1,Decoupe")]


def test_decouper_blocs_csv_avec_marqueurs() -> None:
    texte = "--- taches.csv ---\nid,nom\nT1,Decoupe\n\n--- ressources.csv ---\nid,nom\nR1,Decoupeuse"

    blocs = _decouper_blocs_csv(texte)

    assert blocs == [
        ("taches.csv", "id,nom\nT1,Decoupe"),
        ("ressources.csv", "id,nom\nR1,Decoupeuse"),
    ]


@pytest.mark.parametrize(
    ("nom", "attendu"),
    [
        ("taches.csv", "taches"),
        ("mes_taches_export.csv", "taches"),
        ("ressources.csv", "ressources"),
        ("contraintes.csv", "contraintes"),
        ("export1.csv", None),
        ("", None),
    ],
)
def test_type_par_nom_fichier(nom: str, attendu: str | None) -> None:
    assert _type_par_nom_fichier(nom) == attendu


@pytest.mark.parametrize(
    ("entete", "attendu"),
    [
        ("type,tache_avant,tache_apres,tache,ressource,duree_jours", "contraintes"),
        ("id,nom,competences", "ressources"),
        ("id,nom,duree_estimee_jours", "taches"),
        ("id,nom", None),
        ("", None),
    ],
)
def test_type_par_entete(entete: str, attendu: str | None) -> None:
    assert _type_par_entete(entete) == attendu


def test_reconstruire_fichiers_csv_par_nom_de_fichier() -> None:
    texte = (
        "--- taches.csv ---\nid\nT1\n\n"
        "--- ressources.csv ---\nid\nR1\n\n"
        "--- contraintes.csv ---\ntype,tache,ressource,duree_jours\n"
        "compatibilite_ressource_tache,T1,R1,10"
    )

    taches, ressources, contraintes = _reconstruire_fichiers_csv(texte)

    assert taches == b"id\nT1"
    assert ressources == b"id\nR1"
    assert b"compatibilite_ressource_tache" in contraintes


def test_reconstruire_fichiers_csv_par_entete_sans_nom_parlant() -> None:
    texte = (
        "--- export1.csv ---\nid,duree_estimee_jours\nT1,5\n\n"
        "--- export2.csv ---\nid,competences\nR1,decoupe\n\n"
        "--- export3.csv ---\ntype,tache,competence\ncompetence_requise,T1,decoupe"
    )

    taches, ressources, contraintes = _reconstruire_fichiers_csv(texte)

    assert b"duree_estimee_jours" in taches
    assert b"competences" in ressources
    assert b"competence_requise" in contraintes


def test_reconstruire_fichiers_csv_leve_une_erreur_si_un_fichier_manque() -> None:
    texte = "--- taches.csv ---\nid\nT1\n\n--- ressources.csv ---\nid\nR1"

    with pytest.raises(ErreurStructureNonReconnue, match="contraintes"):
        _reconstruire_fichiers_csv(texte)


def test_traduire_deterministe_reconnait_un_json_canonique() -> None:
    payload = (
        '{"taches": [{"id": "T1"}], "ressources": [{"id": "R1"}], '
        '"contraintes": [{"type": "compatibilite_ressource_tache", "tache": "T1", '
        '"ressource": "R1", "duree": 10}]}'
    )

    resultat = _traduire_deterministe(payload)

    assert [t.id for t in resultat.instance.taches] == ["T1"]


def test_traduire_deterministe_reconnait_un_csv_multi_blocs() -> None:
    texte = (
        "--- taches.csv ---\nid\nT1\n\n"
        "--- ressources.csv ---\nid\nR1\n\n"
        "--- contraintes.csv ---\ntype,tache,ressource,duree_jours\n"
        "compatibilite_ressource_tache,T1,R1,10"
    )

    resultat = _traduire_deterministe(texte)

    assert [t.id for t in resultat.instance.taches] == ["T1"]


def test_traduire_deterministe_leve_une_erreur_sur_texte_libre_non_structure() -> None:
    with pytest.raises(ErreurStructureNonReconnue):
        _traduire_deterministe("precedence,CALAGE_PRESSE,IMPRESSION_RECTO,,,\n")
