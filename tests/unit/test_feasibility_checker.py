"""Couche 1 (§6.1) : le vérificateur de faisabilité est du code écrit à la
main, déterministe. Batterie exhaustive (§6.2 brique 1) — chaque type de
violation qu'il sait diagnostiquer est couvert par au moins un cas légal
voisin et un cas illégal qui le déclenche, en isolation des autres.
"""

from __future__ import annotations

from dsl.schema import (
    CompatibiliteRessourceTache,
    ContrainteCapacite,
    ContrainteChangementSerie,
    ContrainteDisponibiliteRessource,
    ContrainteIncompatibilite,
    ContrainteTailleLot,
    Echeance,
    InstanceTRCO,
    MinimiserMakespan,
    OperationPlanifiee,
    Planning,
    Precedence,
    Ressource,
    Tache,
)
from validation_engine.feasibility_checker import verifier_faisabilite


def _instance(taches, ressources, contraintes=(), unite_temps="jours") -> InstanceTRCO:
    return InstanceTRCO(
        taches=taches,
        ressources=ressources,
        contraintes=list(contraintes),
        objectifs=[MinimiserMakespan()],
        unite_temps=unite_temps,
    )


def _planning(*operations: OperationPlanifiee) -> Planning:
    return Planning(operations=list(operations))


def _op(tache: str, ressource: str, debut: int) -> OperationPlanifiee:
    return OperationPlanifiee(tache=tache, ressource=ressource, debut=debut)


def test_planning_legal_est_accepte() -> None:
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2"), Tache(id="T3")],
        ressources=[Ressource(id="R1"), Ressource(id="R2")],
        contraintes=[
            Precedence(avant="T1", apres="T2"),
            Precedence(avant="T2", apres="T3"),
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=30),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=45),
            CompatibiliteRessourceTache(tache="T2", ressource="R2", duree=45),
            CompatibiliteRessourceTache(tache="T3", ressource="R2", duree=15),
        ],
    )
    planning = _planning(
        _op("T1", "R1", 0),
        _op("T2", "R2", 30),
        _op("T3", "R2", 75),
    )

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal
    assert resultat.violations == ()


def test_operations_bout_a_bout_sur_la_meme_ressource_sont_legales() -> None:
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=10),
        ],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R1", 10))

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_precedence_violee_est_detectee() -> None:
    # Deux ressources distinctes pour isoler la violation de précédence de
    # toute violation de chevauchement (même ressource + mêmes instants
    # déclencherait aussi un chevauchement_ressource).
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1"), Ressource(id="R2")],
        contraintes=[
            Precedence(avant="T1", apres="T2"),
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=30),
            CompatibiliteRessourceTache(tache="T2", ressource="R2", duree=10),
        ],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R2", 20))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["precedence_violee"]
    assert resultat.violations[0].tache == "T1"
    assert resultat.violations[0].tache_secondaire == "T2"


def test_chevauchement_ressource_est_detecte() -> None:
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=10),
        ],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R1", 5))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["chevauchement_ressource"]
    violation = resultat.violations[0]
    assert violation.ressource == "R1"
    assert {violation.tache, violation.tache_secondaire} == {"T1", "T2"}


def test_incompatibilite_ressource_tache_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1"), Ressource(id="R2")],
        contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
    )
    planning = _planning(_op("T1", "R2", 0))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["incompatibilite_ressource_tache"]
    assert resultat.violations[0].tache == "T1"
    assert resultat.violations[0].ressource == "R2"


def test_tache_non_planifiee_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=10),
        ],
    )
    planning = _planning(_op("T1", "R1", 0))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["tache_non_planifiee"]
    assert resultat.violations[0].tache == "T2"


def test_tache_planifiee_plusieurs_fois_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1"), Ressource(id="R2")],
        contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T1", "R2", 0))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["tache_planifiee_plusieurs_fois"]
    assert resultat.violations[0].tache == "T1"


def test_tache_inconnue_dans_planning_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T99", "R1", 10))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["tache_inconnue_dans_planning"]
    assert resultat.violations[0].tache == "T99"


def test_ressource_inconnue_dans_planning_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
    )
    planning = _planning(_op("T1", "R99", 0))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["ressource_inconnue_dans_planning"]
    assert resultat.violations[0].ressource == "R99"


def test_echeance_respectee_est_legale() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            Echeance(tache="T1", echeance=10),
        ],
    )
    planning = _planning(_op("T1", "R1", 0))  # finit à 10 : échéance respectée pile

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_echeance_depassee_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            Echeance(tache="T1", echeance=5),
        ],
    )
    planning = _planning(_op("T1", "R1", 0))  # finit à 10, échéance à 5

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["echeance_depassee"]
    assert resultat.violations[0].tache == "T1"


def test_capacite_respectee_est_legale() -> None:
    """Deux tâches simultanées sur une ressource de capacité 2 : légal — le
    chevauchement seul (`chevauchement_ressource`, capacité implicite de 1)
    ne s'applique plus dès qu'une `ContrainteCapacite` couvre la ressource."""
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=10),
            ContrainteCapacite(ressource="R1", capacite=2),
        ],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R1", 5))

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_capacite_depassee_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2"), Tache(id="T3")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T3", ressource="R1", duree=10),
            ContrainteCapacite(ressource="R1", capacite=2),
        ],
    )
    # T1 [0,10), T2 [0,10), T3 [5,15) : 3 tâches actives à l'instant 5 > capacité 2.
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R1", 0), _op("T3", "R1", 5))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["capacite_depassee"]
    assert resultat.violations[0].ressource == "R1"


def test_capacite_bout_a_bout_reste_legale() -> None:
    """Une ressource de capacité 2 qui ne voit jamais plus de 2 tâches
    simultanées reste légale même avec plusieurs tâches au total."""
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2"), Tache(id="T3")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T3", ressource="R1", duree=10),
            ContrainteCapacite(ressource="R1", capacite=2),
        ],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R1", 0), _op("T3", "R1", 10))

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_incompatibilite_taches_respectee_est_legale() -> None:
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1"), Ressource(id="R2")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T2", ressource="R2", duree=10),
            ContrainteIncompatibilite(tache="T1", tache_incompatible="T2"),
        ],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R2", 0))

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_incompatibilite_taches_violee_est_detectee() -> None:
    """Même sans chevauchement temporel : deux tâches incompatibles sur la
    même ressource sont illégales quelle que soit l'heure."""
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=10),
            ContrainteIncompatibilite(tache="T1", tache_incompatible="T2"),
        ],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R1", 10))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert "incompatibilite_taches_violee" in [v.type for v in resultat.violations]
    violation = next(v for v in resultat.violations if v.type == "incompatibilite_taches_violee")
    assert {violation.tache, violation.tache_secondaire} == {"T1", "T2"}
    assert violation.ressource == "R1"


def test_disponibilite_ressource_respectee_est_legale() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=2),
            ContrainteDisponibiliteRessource(ressource="R1", jours_indisponibles=[5, 6]),
        ],
    )
    planning = _planning(_op("T1", "R1", 0))  # [0, 2) : ne touche pas [5, 6]

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_disponibilite_ressource_violee_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=2),
            ContrainteDisponibiliteRessource(ressource="R1", jours_indisponibles=[5, 6]),
        ],
    )
    planning = _planning(_op("T1", "R1", 5))  # [5, 7) : chevauche le jour indisponible 5 et 6

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["ressource_indisponible"]
    assert resultat.violations[0].tache == "T1"
    assert resultat.violations[0].ressource == "R1"


def test_disponibilite_ressource_motif_hebdomadaire_respecte_est_legal() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=2),
            # Positions 5 et 6 du cycle de 7 jours indisponibles (repos hebdomadaire).
            ContrainteDisponibiliteRessource(ressource="R1", jours_semaine_indisponibles=[5, 6]),
        ],
    )
    planning = _planning(_op("T1", "R1", 0))  # [0, 2) : positions 0-1 du cycle, jamais 5/6

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_disponibilite_ressource_motif_hebdomadaire_viole_est_detecte() -> None:
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=1),
            ContrainteDisponibiliteRessource(ressource="R1", jours_semaine_indisponibles=[5, 6]),
        ],
    )
    planning = _planning(_op("T1", "R1", 12))  # jour 12 % 7 == 5 : indisponible

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["ressource_indisponible"]


def test_disponibilite_ressource_motif_hebdomadaire_se_repete_sur_tout_l_horizon() -> None:
    """Le motif n'est pas juste appliqué à la première semaine — chaque
    occurrence future du cycle de 7 jours est bloquée, sans borne d'horizon."""
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=1),
            ContrainteDisponibiliteRessource(ressource="R1", jours_semaine_indisponibles=[5]),
        ],
    )
    planning = _planning(_op("T1", "R1", 5 + 7 * 6))  # 6 semaines plus tard, même position de cycle

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal


def test_disponibilite_ressource_motif_hebdomadaire_mode_heures_utilise_un_cycle_de_168() -> None:
    """L'instant 100 est à la position 100 d'un cycle de 168 (mode heures) — un motif qui bloque
    la position 100 doit donc détecter une violation à cet instant précis."""
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=1),
            ContrainteDisponibiliteRessource(ressource="R1", jours_semaine_indisponibles=[100]),
        ],
        unite_temps="heures",
    )
    # instant 100 : position 100 dans le cycle de 168 (100 % 168 == 100) -> indisponible.
    planning = _planning(_op("T1", "R1", 100))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["ressource_indisponible"]


def test_disponibilite_ressource_motif_hebdomadaire_mode_heures_hors_motif_est_legal() -> None:
    """Le même instant (100) serait bloqué avec un cycle de 7 (100 % 7 == 2) si le motif
    contenait 2 — ici le motif ([2]) bloque bien la position 2 du cycle de 168 (l'instant 2, pas
    100), preuve que le bon cycle (168, pas 7) est réellement utilisé en mode heures."""
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=1),
            ContrainteDisponibiliteRessource(ressource="R1", jours_semaine_indisponibles=[2]),
        ],
        unite_temps="heures",
    )
    # instant 100 : position 100 dans le cycle de 168 (100 % 168 == 100, pas dans [2]) -> légal.
    # Avec un cycle de 7 (bug), 100 % 7 == 2, qui EST dans le motif -> détecterait à tort une violation.
    planning = _planning(_op("T1", "R1", 100))

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_disponibilite_ressource_jours_explicites_et_motif_hebdomadaire_se_combinent() -> None:
    """Deux contraintes distinctes pour la même ressource (jours explicites +
    motif récurrent) s'additionnent — aucune n'écrase l'autre (§4.2, même
    principe que plusieurs CompatibiliteRessourceTache pour une même tâche)."""
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=1),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=1),
            ContrainteDisponibiliteRessource(ressource="R1", jours_indisponibles=[10]),
            ContrainteDisponibiliteRessource(ressource="R1", jours_semaine_indisponibles=[5]),
        ],
    )
    # T1 tombe sur le jour explicite (10), T2 sur une occurrence du motif (12 % 7 == 5).
    planning = _planning(_op("T1", "R1", 10), _op("T2", "R1", 12))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert len(resultat.violations) == 2
    assert {v.tache for v in resultat.violations} == {"T1", "T2"}


def test_disponibilite_ressource_avec_capacite_superieure_a_un_reste_bloquee() -> None:
    """Une ressource de capacité 2 reste bloquée un jour indisponible même
    sans dépasser sa capacité — l'indisponibilité est une interdiction
    totale ce jour-là, pas seulement une réduction de capacité."""
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=2),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=2),
            ContrainteCapacite(ressource="R1", capacite=2),
            ContrainteDisponibiliteRessource(ressource="R1", jours_indisponibles=[5]),
        ],
    )
    # T1 [0,2) ne touche pas le jour 5 ; T2 [5,7) le touche — aucun
    # chevauchement temporel entre T1 et T2, donc la capacité (2) n'est
    # jamais en cause : seule l'indisponibilité doit être détectée.
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R1", 5))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["ressource_indisponible"]
    assert resultat.violations[0].tache == "T2"


def test_taille_lot_respectee_est_legale() -> None:
    instance = _instance(
        taches=[Tache(id="T1", quantite=500)],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=2),
            ContrainteTailleLot(tache="T1", lot_min=50, lot_max=1000),
        ],
    )
    planning = _planning(_op("T1", "R1", 0))

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_taille_lot_violee_est_detectee() -> None:
    instance = _instance(
        taches=[Tache(id="T1", quantite=5)],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=2),
            ContrainteTailleLot(tache="T1", lot_min=50, lot_max=1000),
        ],
    )
    planning = _planning(_op("T1", "R1", 0))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["taille_lot_hors_bornes"]
    assert resultat.violations[0].tache == "T1"


def test_taille_lot_sans_quantite_est_ignoree() -> None:
    """`Tache.quantite` non renseignée : rien à vérifier, aucune anomalie —
    même logique que `Echeance` quand la durée du couple est inconnue."""
    instance = _instance(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=2),
            ContrainteTailleLot(tache="T1", lot_min=50, lot_max=1000),
        ],
    )
    planning = _planning(_op("T1", "R1", 0))

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_changement_serie_respecte_est_legal() -> None:
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=2),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=2),
            ContrainteChangementSerie(ressource="R1", tache_avant="T1", tache_apres="T2", duree_setup=3),
        ],
    )
    # T1 finit à 2, T2 démarre à 5 : écart de 3, exactement le setup requis.
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R1", 5))

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_changement_serie_insuffisant_est_detecte() -> None:
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=2),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=2),
            ContrainteChangementSerie(ressource="R1", tache_avant="T1", tache_apres="T2", duree_setup=3),
        ],
    )
    # T1 finit à 2, T2 démarre à 3 : écart de 1 seulement, 3 requis.
    planning = _planning(_op("T1", "R1", 0), _op("T2", "R1", 3))

    resultat = verifier_faisabilite(instance, planning)

    assert not resultat.legal
    assert [v.type for v in resultat.violations] == ["changement_serie_insuffisant"]
    assert resultat.violations[0].tache == "T1"
    assert resultat.violations[0].tache_secondaire == "T2"
    assert resultat.violations[0].ressource == "R1"


def test_changement_serie_sans_effet_si_taches_non_consecutives() -> None:
    """T3 s'intercale entre T1 et T2 sur la même ressource — la paire
    déclarée n'est plus directement consécutive, aucune violation."""
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2"), Tache(id="T3")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=2),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=2),
            CompatibiliteRessourceTache(tache="T3", ressource="R1", duree=2),
            ContrainteChangementSerie(ressource="R1", tache_avant="T1", tache_apres="T2", duree_setup=3),
        ],
    )
    planning = _planning(_op("T1", "R1", 0), _op("T3", "R1", 2), _op("T2", "R1", 4))

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal


def test_changement_serie_ne_s_applique_pas_dans_l_ordre_inverse() -> None:
    """Contrainte dirigée : T1 → T2 déclarée, mais le planning enchaîne T2
    puis T1 — cette paire précise (T2, T1) n'est jamais couverte."""
    instance = _instance(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=2),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=2),
            ContrainteChangementSerie(ressource="R1", tache_avant="T1", tache_apres="T2", duree_setup=3),
        ],
    )
    # T2 d'abord (finit à 2), puis T1 juste après (démarre à 2) — pas la paire déclarée.
    planning = _planning(_op("T2", "R1", 0), _op("T1", "R1", 2))

    resultat = verifier_faisabilite(instance, planning)

    assert resultat.legal
