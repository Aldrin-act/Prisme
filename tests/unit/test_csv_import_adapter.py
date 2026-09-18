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
    taches_csv = b"id,nom\nT1,Decoupe\n"
    ressources_csv = b"id,nom,competences\nR1,Decoupeuse,decoupe;affutage\nR2,Assembleuse,assemblage\n"
    contraintes_csv = b"type,tache,competence\ncompetence_requise,T1,decoupe\n"

    resultat = _traduire_resultat(
        taches_csv, ressources_csv, contraintes_csv, estimateur_duree=_EstimateurFaux(25)
    )
    instance = resultat.instance

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
    taches_csv = b"id\nT1\n"
    ressources_csv = b"id,competences\nR1,decoupe\nR2,decoupe;affutage\n"
    contraintes_csv = b"type,tache,competence\ncompetence_requise,T1,decoupe\ncompetence_requise,T1,affutage\n"

    resultat = _traduire_resultat(
        taches_csv, ressources_csv, contraintes_csv, estimateur_duree=_EstimateurFaux(25)
    )
    instance = resultat.instance

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
    La durée déclarée pour la tâche (40 sur R2) sert aussi à la compatibilité dérivée (R1) :
    une durée réelle l'emporte toujours sur une estimation, qui ne comble que les tâches sans
    aucune durée connue (`durees_declarees_par_tache`, `completer_durees_par_estimation`)."""
    taches_csv = b"id\nT1\n"
    ressources_csv = b"id,competences\nR1,decoupe\nR2,decoupe\n"
    contraintes_csv = (
        b"type,tache,ressource,duree_jours,competence\n"
        b"compatibilite_ressource_tache,T1,R2,40,\n"
        b"competence_requise,T1,,,decoupe\n"
    )

    resultat = _traduire_resultat(
        taches_csv, ressources_csv, contraintes_csv, estimateur_duree=_EstimateurFaux(25)
    )
    instance = resultat.instance

    compatibilites = {
        (c.tache, c.ressource, c.duree) for c in instance.contraintes if c.type == "compatibilite_ressource_tache"
    }
    assert compatibilites == {("T1", "R2", 40), ("T1", "R1", 40)}


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


# --- Matières (declaration_materiau/consommation_matiere, deux types de contraintes.csv de plus) ---


def test_sans_declaration_materiau_ne_produit_aucune_contrainte_matiere() -> None:
    instance = traduire(TACHES_CSV, RESSOURCES_CSV, CONTRAINTES_CSV)
    assert not [c for c in instance.contraintes if c.type in ("declaration_materiau", "consommation_matiere")]


def test_declaration_materiau_et_consommation_matiere_sont_lues() -> None:
    contraintes_csv = (
        b"type,tache_avant,tache_apres,tache,ressource,duree_jours,materiau,quantite,stock_initial,unite\n"
        b"precedence,T1,T2,,,,,,,\n"
        b"compatibilite_ressource_tache,,,T1,R1,10,,,,\n"
        b"compatibilite_ressource_tache,,,T2,R1,15,,,,\n"
        b"declaration_materiau,,,,,,M1,,100,kg\n"
        b"consommation_matiere,,,T1,,,M1,5,,\n"
    )

    instance = traduire(TACHES_CSV, RESSOURCES_CSV, contraintes_csv)

    declarations = [c for c in instance.contraintes if c.type == "declaration_materiau"]
    assert len(declarations) == 1
    assert declarations[0].stock_initial == 100
    assert declarations[0].unite == "kg"
    consommations = [c for c in instance.contraintes if c.type == "consommation_matiere"]
    assert len(consommations) == 1
    assert consommations[0].tache == "T1"
    assert consommations[0].materiau == "M1"
    assert consommations[0].quantite == 5


def test_declaration_materiau_stock_non_numerique_leve_erreur_fichier_invalide() -> None:
    contraintes_csv = b"type,materiau,stock_initial\ndeclaration_materiau,M1,pas-un-nombre\n"

    with pytest.raises(ErreurFichierInvalide, match="stock initial invalide"):
        traduire(TACHES_CSV, RESSOURCES_CSV, contraintes_csv)


def test_consommation_matiere_quantite_non_numerique_leve_erreur_fichier_invalide() -> None:
    contraintes_csv = b"type,tache,materiau,quantite\nconsommation_matiere,T1,M1,pas-un-nombre\n"

    with pytest.raises(ErreurFichierInvalide, match="quantité invalide"):
        traduire(TACHES_CSV, RESSOURCES_CSV, contraintes_csv)


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
    taches_csv = b"id;nom\nT1;Decoupe\n"
    ressources_csv = b"id;competences\nR1;decoupe\n"
    contraintes_csv = b"type;tache;competence\ncompetence_requise;T1;decoupe\n"
    commandes_csv = b"id;taches;client;date_limite\nCMD1;T1;Client A;20\n"

    resultat = _traduire_resultat(
        taches_csv,
        ressources_csv,
        contraintes_csv,
        commandes_csv,
        estimateur_duree=_EstimateurFaux(25),
        delimiteur=";",
    )

    assert [t.id for t in resultat.instance.taches] == ["T1"]
    compatibilites = [c for c in resultat.instance.contraintes if c.type == "compatibilite_ressource_tache"]
    assert [(c.tache, c.ressource, c.duree) for c in compatibilites] == [("T1", "R1", 25)]
    echeances = {c.tache: c.echeance for c in resultat.instance.contraintes if c.type == "echeance"}
    assert echeances == {"T1": 20}


def test_delimiteur_par_defaut_reste_la_virgule() -> None:
    """Comportement inchangé pour tout appelant existant qui ne déclare rien."""
    instance = traduire(TACHES_CSV, RESSOURCES_CSV, CONTRAINTES_CSV)
    assert [t.id for t in instance.taches] == ["T1", "T2"]


# --- Colonne de durée selon l'unité de temps (duree_jours / duree_heures / duree) ---

_TACHES_UNE = b"id\nT1\n"
_RESSOURCES_UNE = b"id\nR1\n"


def _contraintes_avec_colonne(colonne: str, valeur: str = "6") -> bytes:
    return f"type,tache,ressource,{colonne}\ncompatibilite_ressource_tache,T1,R1,{valeur}\n".encode()


def test_colonne_duree_heures_lue_telle_quelle_en_mode_heures() -> None:
    resultat = _traduire_resultat(
        _TACHES_UNE, _RESSOURCES_UNE, _contraintes_avec_colonne("duree_heures"), unite_temps="heures"
    )

    assert resultat.instance.unite_temps == "heures"
    assert [c.duree for c in resultat.instance.contraintes] == [6]
    assert resultat.avertissements == ()


def test_colonne_duree_neutre_acceptee_dans_les_deux_unites() -> None:
    for unite in ("jours", "heures"):
        resultat = _traduire_resultat(
            _TACHES_UNE, _RESSOURCES_UNE, _contraintes_avec_colonne("duree"), unite_temps=unite
        )
        assert [c.duree for c in resultat.instance.contraintes] == [6]
        assert resultat.avertissements == ()


def test_colonne_duree_d_une_autre_unite_avertit_sans_convertir() -> None:
    """Un nom de colonne n'est qu'une étiquette : jamais de conversion silencieuse, mais
    l'incohérence probable (mauvaise unité choisie à l'import) est signalée à l'humain."""
    resultat = _traduire_resultat(
        _TACHES_UNE, _RESSOURCES_UNE, _contraintes_avec_colonne("duree_heures"), unite_temps="jours"
    )

    assert [c.duree for c in resultat.instance.contraintes] == [6]
    assert len(resultat.avertissements) == 1
    assert "duree_heures" in resultat.avertissements[0]
    assert "duree_jours" in resultat.avertissements[0]


def test_colonne_duree_jours_historique_inchangee_en_mode_jours() -> None:
    resultat = _traduire_resultat(_TACHES_UNE, _RESSOURCES_UNE, _contraintes_avec_colonne("duree_jours"))
    assert [c.duree for c in resultat.instance.contraintes] == [6]
    assert resultat.avertissements == ()


def test_plusieurs_colonnes_de_duree_levent_erreur_fichier_invalide() -> None:
    contraintes = b"type,tache,ressource,duree_jours,duree_heures\ncompatibilite_ressource_tache,T1,R1,1,24\n"
    with pytest.raises(ErreurFichierInvalide, match="colonnes de durée multiples"):
        traduire(_TACHES_UNE, _RESSOURCES_UNE, contraintes)


def test_duree_invalide_en_mode_heures_nomme_l_unite_et_la_colonne() -> None:
    with pytest.raises(ErreurFichierInvalide, match="nombre entier de heures, colonne « duree_heures »"):
        traduire(
            _TACHES_UNE,
            _RESSOURCES_UNE,
            _contraintes_avec_colonne("duree_heures", "abc"),
            unite_temps="heures",
        )


@pytest.mark.parametrize(
    ("dossier", "unite", "suffixe"),
    [
        ("docs/dsl/gabarit_csv", "jours", ""),
        ("docs/dsl/gabarit_csv", "heures", "_heures"),
        ("Front/prismatron-solver-forge/public/gabarits", "jours", ""),
        ("Front/prismatron-solver-forge/public/gabarits", "heures", "_heures"),
    ],
)
def test_gabarits_csv_de_chaque_unite_s_ingerent_sans_avertissement(
    dossier: str, unite: str, suffixe: str
) -> None:
    """Les gabarits téléchargeables (générés par `scripts/generer_gabarit_csv.py`, recopiés côté
    frontend) doivent rester lisibles par l'adaptateur dans l'unité qu'ils annoncent."""
    from pathlib import Path

    racine = Path(__file__).resolve().parents[2] / dossier
    resultat = _traduire_resultat(
        (racine / "taches.csv").read_bytes(),
        (racine / "ressources.csv").read_bytes(),
        (racine / f"contraintes{suffixe}.csv").read_bytes(),
        (racine / f"commandes{suffixe}.csv").read_bytes(),
        unite_temps=unite,  # type: ignore[arg-type]
    )

    assert resultat.instance.unite_temps == unite
    # Aucun gabarit ne porte de durée (elle se fixe à la commande) : le seul avertissement attendu
    # est celui qui annonce la durée d'attente, jamais un autre.
    assert all(a.startswith("aucune durée déclarée") for a in resultat.avertissements)


# --- Durée de travail quotidienne d'une ressource (heures_par_jour) ---


def test_heures_par_jour_derive_une_indisponibilite_en_mode_heures() -> None:
    """8 h travaillées par jour = indisponible les 16 autres heures de chaque journée du cycle
    (7 × 24). Dérivé à l'ingestion en `ContrainteDisponibiliteRessource` — le DSL et le solveur
    n'ont rien de nouveau à connaître."""
    ressources = b"id,nom,competences,heures_par_jour\nR1,Scie,,8\n"
    contraintes = b"type,tache,ressource,duree_heures\ncompatibilite_ressource_tache,T1,R1,6\n"

    resultat = _traduire_resultat(_TACHES_UNE, ressources, contraintes, unite_temps="heures")

    assert resultat.instance.ressources[0].heures_par_jour == 8
    disponibilites = [c for c in resultat.instance.contraintes if c.type == "disponibilite_ressource"]
    assert len(disponibilites) == 1
    positions = disponibilites[0].jours_semaine_indisponibles
    assert len(positions) == 7 * 16
    assert positions[:3] == [8, 9, 10]  # la journée commence à la position 0 de chaque journée
    assert all(p % 24 >= 8 for p in positions)
    assert any("journée de travail de 8 h" in a for a in resultat.avertissements)


def test_heures_par_jour_en_mode_jours_reste_informatif_et_previent() -> None:
    ressources = b"id,nom,competences,heures_par_jour\nR1,Scie,,8\n"
    contraintes = b"type,tache,ressource,duree_jours\ncompatibilite_ressource_tache,T1,R1,3\n"

    resultat = _traduire_resultat(_TACHES_UNE, ressources, contraintes)

    assert resultat.instance.ressources[0].heures_par_jour == 8
    assert not [c for c in resultat.instance.contraintes if c.type == "disponibilite_ressource"]
    assert any("n'est pas appliqué" in a for a in resultat.avertissements)


def test_heures_par_jour_absent_ne_derive_rien() -> None:
    contraintes = b"type,tache,ressource,duree_heures\ncompatibilite_ressource_tache,T1,R1,6\n"

    resultat = _traduire_resultat(_TACHES_UNE, _RESSOURCES_UNE, contraintes, unite_temps="heures")

    assert resultat.instance.ressources[0].heures_par_jour is None
    assert not [c for c in resultat.instance.contraintes if c.type == "disponibilite_ressource"]
    assert resultat.avertissements == ()


def test_heures_par_jour_non_numerique_leve_erreur_fichier_invalide() -> None:
    ressources = b"id,nom,competences,heures_par_jour\nR1,Scie,,huit\n"
    contraintes = b"type,tache,ressource,duree_heures\ncompatibilite_ressource_tache,T1,R1,6\n"

    with pytest.raises(ErreurFichierInvalide, match="durée de travail quotidienne invalide"):
        traduire(_TACHES_UNE, ressources, contraintes, unite_temps="heures")


def test_heures_par_jour_hors_bornes_rejete_par_le_dsl() -> None:
    ressources = b"id,nom,competences,heures_par_jour\nR1,Scie,,30\n"
    contraintes = b"type,tache,ressource,duree_heures\ncompatibilite_ressource_tache,T1,R1,6\n"

    with pytest.raises(ValidationError):
        traduire(_TACHES_UNE, ressources, contraintes, unite_temps="heures")


# --- Durée déclarée sur la tâche (taches.csv), plus sur la compatibilité ---

_TACHES_AVEC_DUREE = b"id,nom,duree_heures\nT1,Decoupe,6\nT2,Assemblage,4\n"
_RESSOURCES_DEUX = b"id,nom\nR1,Scie\nR2,Fraise\n"
_COMPATIBILITES_SANS_DUREE = (
    b"type,tache,ressource\n"
    b"compatibilite_ressource_tache,T1,R1\n"
    b"compatibilite_ressource_tache,T1,R2\n"
    b"compatibilite_ressource_tache,T2,R1\n"
)


def test_duree_de_la_tache_s_applique_a_chacune_de_ses_ressources() -> None:
    resultat = _traduire_resultat(
        _TACHES_AVEC_DUREE, _RESSOURCES_DEUX, _COMPATIBILITES_SANS_DUREE, unite_temps="heures"
    )

    durees = {
        (c.tache, c.ressource): c.duree
        for c in resultat.instance.contraintes
        if c.type == "compatibilite_ressource_tache"
    }
    assert durees == {("T1", "R1"): 6, ("T1", "R2"): 6, ("T2", "R1"): 4}
    assert resultat.avertissements == ()


def test_duree_absente_partout_prend_la_duree_d_attente_et_previent() -> None:
    """Le cas normal désormais : aucun fichier ne déclare de durée, elle se fixe à la commande.
    L'instance existe quand même (le DSL exige une durée) avec la plus petite valeur valide,
    annoncée — jamais une estimation déguisée."""
    taches_sans_duree = b"id,nom\nT1,Decoupe\n"
    contraintes = b"type,tache,ressource\ncompatibilite_ressource_tache,T1,R1\n"

    resultat = _traduire_resultat(taches_sans_duree, _RESSOURCES_DEUX, contraintes, unite_temps="heures")

    assert [c.duree for c in resultat.instance.contraintes if c.type == "compatibilite_ressource_tache"] == [1]
    assert any("aucune durée déclarée pour T1" in a for a in resultat.avertissements)
    assert any("commande" in a for a in resultat.avertissements)


def test_duree_encore_sur_la_compatibilite_reste_acceptee() -> None:
    """Fichiers écrits dans l'ancien format (durée sur la ligne de compatibilité) : toujours lus,
    sans rien exiger de neuf."""
    taches = b"id\nT1\n"
    contraintes = b"type,tache,ressource,duree_jours\ncompatibilite_ressource_tache,T1,R1,3\n"

    resultat = _traduire_resultat(taches, _RESSOURCES_DEUX, contraintes)

    assert [c.duree for c in resultat.instance.contraintes if c.type == "compatibilite_ressource_tache"] == [3]
    assert resultat.avertissements == ()


def test_duree_sur_la_compatibilite_lemporte_sur_celle_de_la_tache_et_previent() -> None:
    contraintes = (
        b"type,tache,ressource,duree_heures\n"
        b"compatibilite_ressource_tache,T1,R1,9\n"
        b"compatibilite_ressource_tache,T1,R2\n"
    )

    taches = b"id,duree_heures\nT1,6\n"

    resultat = _traduire_resultat(taches, _RESSOURCES_DEUX, contraintes, unite_temps="heures")

    durees = {
        c.ressource: c.duree for c in resultat.instance.contraintes if c.type == "compatibilite_ressource_tache"
    }
    assert durees == {"R1": 9, "R2": 6}  # R1 garde sa durée propre, R2 reprend celle de la tâche
    assert any("elle l'emporte sur la durée 6" in a for a in resultat.avertissements)


def test_duree_de_tache_non_numerique_leve_erreur_fichier_invalide() -> None:
    taches = b"id,duree_heures\nT1,six\n"
    contraintes = b"type,tache,ressource\ncompatibilite_ressource_tache,T1,R1\n"

    with pytest.raises(ErreurFichierInvalide, match="taches.csv : durée invalide"):
        traduire(taches, _RESSOURCES_DEUX, contraintes, unite_temps="heures")


def test_duree_de_tache_alimente_la_derivation_par_competence() -> None:
    """Déclarer la durée une fois sur la tâche suffit à dériver ses compatibilités par compétence,
    sans estimation automatique."""
    taches = b"id,duree_heures\nT1,6\n"
    ressources = b"id,competences\nR1,decoupe\nR2,decoupe\n"
    contraintes = b"type,tache,competence\ncompetence_requise,T1,decoupe\n"

    resultat = _traduire_resultat(taches, ressources, contraintes, unite_temps="heures")

    compatibilites = {
        (c.ressource, c.duree) for c in resultat.instance.contraintes if c.type == "compatibilite_ressource_tache"
    }
    assert compatibilites == {("R1", 6), ("R2", 6)}
