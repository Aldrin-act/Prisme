"""Couche 1 (§6.1) : `adapters/csv_import/traducteur.py` — la version CSV
(trois fichiers séparés) du gabarit d'ingestion T-R-C-O, miroir de
`adapters/tableur/` (xlsx, une seule pièce jointe à onglets).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from adapters.csv_import import ErreurFichierInvalide
from adapters.csv_import import traduire as _traduire_resultat
from dsl.schema import InstanceTRCO


def traduire(*args: object, **kwargs: object) -> InstanceTRCO:
    """`traduire()` renvoie désormais un `ResultatTraduction` (instance +
    avertissements, §FC4) — les tests ci-dessous ne portent que sur
    l'instance produite ; le comportement des avertissements/de
    `estimateur_duree` est couvert séparément plus bas."""
    return _traduire_resultat(*args, **kwargs).instance  # type: ignore[arg-type]


TACHES_CSV = b"id,nom\nT1,Decoupe\nT2,Assemblage\n"
RESSOURCES_CSV = b"id,nom\nR1,Decoupeuse\n"
CONTRAINTES_CSV = (
    b"type,tache_avant,tache_apres,tache,ressource,duree_jours\n"
    b"precedence,T1,T2,,,\n"
    b"compatibilite_ressource_tache,,,T1,R1,10\n"
    b"compatibilite_ressource_tache,,,T2,R1,15\n"
)


def test_traduire_lit_les_trois_fichiers() -> None:
    instance = traduire(TACHES_CSV, RESSOURCES_CSV, CONTRAINTES_CSV)

    assert [t.id for t in instance.taches] == ["T1", "T2"]
    assert instance.taches[0].nom == "Decoupe"
    assert [r.id for r in instance.ressources] == ["R1"]
    assert len(instance.contraintes) == 3
    assert instance.objectifs[0].type == "minimiser_makespan"


def test_traduire_tolere_bom_utf8() -> None:
    """Excel ajoute un BOM UTF-8 en tête de fichier à l'export CSV."""
    taches_avec_bom = b"\xef\xbb\xbf" + TACHES_CSV
    instance = traduire(taches_avec_bom, RESSOURCES_CSV, CONTRAINTES_CSV)
    assert instance.taches[0].id == "T1"


def test_traduire_ignore_les_lignes_vides() -> None:
    taches_avec_ligne_vide = b"id,nom\nT1,Decoupe\n\nT2,Assemblage\n"
    instance = traduire(taches_avec_ligne_vide, RESSOURCES_CSV, CONTRAINTES_CSV)
    assert [t.id for t in instance.taches] == ["T1", "T2"]


def test_colonne_manquante_leve_erreur_fichier_invalide() -> None:
    taches_sans_id = b"identifiant,nom\nT1,Decoupe\n"
    with pytest.raises(ErreurFichierInvalide, match="colonne"):
        traduire(taches_sans_id, RESSOURCES_CSV, CONTRAINTES_CSV)


def test_fichier_vide_leve_erreur_fichier_invalide() -> None:
    with pytest.raises(ErreurFichierInvalide, match="vide"):
        traduire(b"", RESSOURCES_CSV, CONTRAINTES_CSV)


def test_type_contrainte_inconnu_leve_erreur_fichier_invalide() -> None:
    contraintes_type_invalide = b"type,tache_avant,tache_apres,tache,ressource,duree_jours\nechance,T1,T2,,,\n"
    with pytest.raises(ErreurFichierInvalide, match="type de contrainte inconnu"):
        traduire(TACHES_CSV, RESSOURCES_CSV, contraintes_type_invalide)


def test_duree_non_numerique_leve_erreur_fichier_invalide() -> None:
    contraintes_duree_invalide = (
        b"type,tache_avant,tache_apres,tache,ressource,duree_jours\n"
        b"compatibilite_ressource_tache,,,T1,R1,pas-un-nombre\n"
    )
    with pytest.raises(ErreurFichierInvalide, match="durée invalide"):
        traduire(TACHES_CSV, RESSOURCES_CSV, contraintes_duree_invalide)


def test_tache_sans_compatibilite_rejetee_par_le_garde_fou_dsl() -> None:
    """Le garde-fou (§6.7) tranche pareil, quel que soit le canal d'ingestion :
    T2 n'a aucune compatibilité ressource-tâche ici."""
    contraintes_incompletes = (
        b"type,tache_avant,tache_apres,tache,ressource,duree_jours\ncompatibilite_ressource_tache,,,T1,R1,10\n"
    )
    with pytest.raises(ValidationError):
        traduire(TACHES_CSV, RESSOURCES_CSV, contraintes_incompletes)


# --- Compatibilité dérivée par compétence (plutôt que saisie à la main) ---


def test_compatibilite_derivee_pour_chaque_ressource_competente() -> None:
    taches_csv = b"id,nom,duree_estimee_jours\nT1,Decoupe,25\n"
    ressources_csv = b"id,nom,competences\nR1,Decoupeuse,decoupe;affutage\nR2,Assembleuse,assemblage\n"
    contraintes_csv = b"type,tache,competence\ncompetence_requise,T1,decoupe\n"

    instance = traduire(taches_csv, ressources_csv, contraintes_csv)

    compatibilites = [c for c in instance.contraintes if c.type == "compatibilite_ressource_tache"]
    assert len(compatibilites) == 1
    assert compatibilites[0].tache == "T1"
    assert compatibilites[0].ressource == "R1"
    assert compatibilites[0].duree == 25
    # R2 n'a pas la compétence requise — jamais rendue compatible.
    assert not any(c.ressource == "R2" for c in compatibilites)
    # La compétence requise elle-même reste dans l'instance (garde-fou DSL, §6.7).
    assert any(c.type == "competence_requise" and c.tache == "T1" for c in instance.contraintes)


def test_compatibilite_derivee_exige_toutes_les_competences_requises() -> None:
    """Une tâche à plusieurs compétences requises n'est compatible qu'avec une
    ressource qui les couvre TOUTES — même exigence que le garde-fou DSL
    (`InstanceTRCO._competences_requises_respectees`), pas une simple
    intersection non vide."""
    taches_csv = b"id,duree_estimee_jours\nT1,25\n"
    ressources_csv = b"id,competences\nR1,decoupe\nR2,decoupe;affutage\n"
    contraintes_csv = b"type,tache,competence\ncompetence_requise,T1,decoupe\ncompetence_requise,T1,affutage\n"

    instance = traduire(taches_csv, ressources_csv, contraintes_csv)

    compatibilites = [c for c in instance.contraintes if c.type == "compatibilite_ressource_tache"]
    assert [c.ressource for c in compatibilites] == ["R2"]


def test_compatibilite_derivee_sans_duree_estimee_leve_erreur_fichier_invalide() -> None:
    taches_csv = b"id\nT1\n"
    ressources_csv = b"id,competences\nR1,decoupe\n"
    contraintes_csv = b"type,tache,competence\ncompetence_requise,T1,decoupe\n"

    with pytest.raises(ErreurFichierInvalide, match="durée estimée manquante"):
        traduire(taches_csv, ressources_csv, contraintes_csv)


def test_compatibilite_explicite_et_derivee_par_competence_coexistent() -> None:
    """Une même tâche peut combiner compatibilité déclarée à la main et
    compatibilité dérivée par compétence — les deux mécanismes s'additionnent.
    R2 possède aussi la compétence requise (le garde-fou DSL l'exige pour
    toute compatibilité, explicite ou dérivée, dès qu'une compétence est
    requise) mais avec une durée déclarée à la main, différente de celle,
    dérivée, appliquée à R1."""
    taches_csv = b"id,duree_estimee_jours\nT1,25\n"
    ressources_csv = b"id,competences\nR1,decoupe\nR2,decoupe\n"
    contraintes_csv = (
        b"type,tache,ressource,duree_jours,competence\n"
        b"compatibilite_ressource_tache,T1,R2,40,\n"
        b"competence_requise,T1,,,decoupe\n"
    )

    instance = traduire(taches_csv, ressources_csv, contraintes_csv)

    compatibilites = {
        (c.tache, c.ressource, c.duree) for c in instance.contraintes if c.type == "compatibilite_ressource_tache"
    }
    assert compatibilites == {("T1", "R2", 40), ("T1", "R1", 25)}


# --- Commandes (quatrième fichier optionnel, dérive des échéances) ---


def test_commandes_absentes_ne_derivent_aucune_echeance() -> None:
    instance = traduire(TACHES_CSV, RESSOURCES_CSV, CONTRAINTES_CSV)
    assert not [c for c in instance.contraintes if c.type == "echeance"]


def test_commande_avec_date_limite_derive_une_echeance_par_tache_liee() -> None:
    commandes_csv = b"id,taches,client,date_limite\nCMD1,T1;T2,Client A,20\n"

    instance = traduire(TACHES_CSV, RESSOURCES_CSV, CONTRAINTES_CSV, commandes_csv)

    echeances = {c.tache: c.echeance for c in instance.contraintes if c.type == "echeance"}
    assert echeances == {"T1": 20, "T2": 20}


def test_commande_sans_date_limite_ne_derive_rien() -> None:
    commandes_csv = b"id,taches,client\nCMD1,T1;T2,Client A\n"

    instance = traduire(TACHES_CSV, RESSOURCES_CSV, CONTRAINTES_CSV, commandes_csv)

    assert not [c for c in instance.contraintes if c.type == "echeance"]


def test_commande_sans_tache_liee_leve_erreur_fichier_invalide() -> None:
    commandes_csv = b"id,taches,date_limite\nCMD1,,20\n"

    with pytest.raises(ErreurFichierInvalide, match="sans aucune t.che li.e"):
        traduire(TACHES_CSV, RESSOURCES_CSV, CONTRAINTES_CSV, commandes_csv)


def test_commande_date_limite_non_numerique_leve_erreur_fichier_invalide() -> None:
    commandes_csv = b"id,taches,date_limite\nCMD1,T1,pas-un-nombre\n"

    with pytest.raises(ErreurFichierInvalide, match="date limite invalide"):
        traduire(TACHES_CSV, RESSOURCES_CSV, CONTRAINTES_CSV, commandes_csv)


# --- ResultatTraduction / estimateur_duree (§FC4, décision humaine préservée) ---
#
# Un faux estimateur duck-typé (pas `estimation.EstimateurDuree`) : ces tests
# vérifient le branchement dans l'adaptateur, pas le modèle de régression
# lui-même (couvert par `tests/unit/test_estimation.py`, qui a besoin de
# l'extra optionnel `estimation` — cette suite `tests/unit` n'en a pas besoin).


class _EstimationFausse:
    def __init__(self, duree_estimee_jours: int, confiance: float) -> None:
        self.duree_estimee_jours = duree_estimee_jours
        self.confiance = confiance


class _EstimateurFaux:
    def __init__(self, duree: int, confiance: float = 0.9) -> None:
        self._duree = duree
        self._confiance = confiance

    def estimer(self, tache: object, ressource: object) -> _EstimationFausse:
        return _EstimationFausse(self._duree, self._confiance)


def test_traduire_par_defaut_renvoie_un_resultat_sans_avertissement() -> None:
    resultat = _traduire_resultat(TACHES_CSV, RESSOURCES_CSV, CONTRAINTES_CSV)
    assert resultat.avertissements == ()


def test_estimateur_duree_comble_une_duree_manquante_et_previent() -> None:
    taches_csv = b"id\nT1\n"
    ressources_csv = b"id,competences\nR1,decoupe\n"
    contraintes_csv = b"type,tache,competence\ncompetence_requise,T1,decoupe\n"

    resultat = _traduire_resultat(
        taches_csv, ressources_csv, contraintes_csv, estimateur_duree=_EstimateurFaux(17)
    )

    compatibilites = [c for c in resultat.instance.contraintes if c.type == "compatibilite_ressource_tache"]
    assert [(c.tache, c.ressource, c.duree) for c in compatibilites] == [("T1", "R1", 17)]
    assert len(resultat.avertissements) == 1
    assert "T1" in resultat.avertissements[0]


def test_duree_declaree_l_emporte_toujours_sur_l_estimateur() -> None:
    taches_csv = b"id,duree_estimee_jours\nT1,25\n"
    ressources_csv = b"id,competences\nR1,decoupe\n"
    contraintes_csv = b"type,tache,competence\ncompetence_requise,T1,decoupe\n"

    resultat = _traduire_resultat(
        taches_csv, ressources_csv, contraintes_csv, estimateur_duree=_EstimateurFaux(99)
    )

    compatibilites = [c for c in resultat.instance.contraintes if c.type == "compatibilite_ressource_tache"]
    assert [(c.tache, c.ressource, c.duree) for c in compatibilites] == [("T1", "R1", 25)]
    assert resultat.avertissements == ()


def test_sans_estimateur_duree_manquante_leve_toujours_erreur() -> None:
    """`estimateur_duree` est strictement optionnel — comportement par défaut
    inchangé quand il est absent, même pour une tâche qu'un estimateur
    aurait pu combler."""
    taches_csv = b"id\nT1\n"
    ressources_csv = b"id,competences\nR1,decoupe\n"
    contraintes_csv = b"type,tache,competence\ncompetence_requise,T1,decoupe\n"

    with pytest.raises(ErreurFichierInvalide, match="durée estimée manquante"):
        _traduire_resultat(taches_csv, ressources_csv, contraintes_csv)


# --- Délimiteur (page Données, import CSV direct) ---


def test_delimiteur_point_virgule_lit_les_quatre_fichiers() -> None:
    """Export Excel FR typique : `;` partout, la virgule étant déjà le
    séparateur décimal — jamais deviné, toujours déclaré explicitement."""
    taches_csv = b"id;nom;duree_estimee_jours\nT1;Decoupe;25\n"
    ressources_csv = b"id;competences\nR1;decoupe\n"
    contraintes_csv = b"type;tache;competence\ncompetence_requise;T1;decoupe\n"
    commandes_csv = b"id;taches;client;date_limite\nCMD1;T1;Client A;20\n"

    resultat = _traduire_resultat(taches_csv, ressources_csv, contraintes_csv, commandes_csv, delimiteur=";")

    assert [t.id for t in resultat.instance.taches] == ["T1"]
    compatibilites = [c for c in resultat.instance.contraintes if c.type == "compatibilite_ressource_tache"]
    assert [(c.tache, c.ressource, c.duree) for c in compatibilites] == [("T1", "R1", 25)]
    echeances = {c.tache: c.echeance for c in resultat.instance.contraintes if c.type == "echeance"}
    assert echeances == {"T1": 20}


def test_delimiteur_par_defaut_reste_la_virgule() -> None:
    """Comportement inchangé pour tout appelant existant qui ne déclare rien."""
    instance = traduire(TACHES_CSV, RESSOURCES_CSV, CONTRAINTES_CSV)
    assert [t.id for t in instance.taches] == ["T1", "T2"]
