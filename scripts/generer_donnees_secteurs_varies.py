#!/usr/bin/env python
"""Génère des données ERP pour des secteurs d'activité variés.

Crée des petits fichiers (10-20 opérations) pour enrichir le répertoire
data/donnees_brutes/json_erp avec de nouveaux cas d'usage.

Usage:
    uv run python -m scripts.generer_donnees_secteurs_varies
"""

from __future__ import annotations

import json
from pathlib import Path


def generer_hopital_bloc_operatoire() -> dict:
    """Hôpital - Bloc opératoire."""
    operations = [
        {
            "code_operation": "PATIENT_001_ADMISSION",
            "duree_jours": 1,
            "poste_id": "SALLE_ADMISSION",
            "operation_precedente": None,
        },
        {
            "code_operation": "PATIENT_001_EXAMENS_PREOP",
            "duree_jours": 1,
            "poste_id": "LABORATOIRE_ANALYSES",
            "operation_precedente": "PATIENT_001_ADMISSION",
        },
        {
            "code_operation": "PATIENT_001_PREPARATION",
            "duree_jours": 1,
            "poste_id": "SALLE_PREPARATION",
            "operation_precedente": "PATIENT_001_EXAMENS_PREOP",
        },
        {
            "code_operation": "PATIENT_001_ANESTHESIE",
            "duree_jours": 1,
            "poste_id": "BLOC_ANESTHESIE",
            "operation_precedente": "PATIENT_001_PREPARATION",
        },
        {
            "code_operation": "PATIENT_001_INTERVENTION",
            "duree_jours": 3,
            "poste_id": "BLOC_CHIRURGIE_GENERALE",
            "operation_precedente": "PATIENT_001_ANESTHESIE",
        },
        {
            "code_operation": "PATIENT_001_REVEIL",
            "duree_jours": 1,
            "poste_id": "SALLE_REVEIL",
            "operation_precedente": "PATIENT_001_INTERVENTION",
        },
        {
            "code_operation": "PATIENT_001_SOINS_POSTOP",
            "duree_jours": 2,
            "poste_id": "UNITE_SOINS_INTENSIFS",
            "operation_precedente": "PATIENT_001_REVEIL",
        },
        {
            "code_operation": "PATIENT_001_SURVEILLANCE",
            "duree_jours": 3,
            "poste_id": "CHAMBRE_HOPITAL",
            "operation_precedente": "PATIENT_001_SOINS_POSTOP",
        },
    ]

    postes = [
        {"code_poste": "SALLE_ADMISSION"},
        {"code_poste": "LABORATOIRE_ANALYSES"},
        {"code_poste": "SALLE_PREPARATION"},
        {"code_poste": "BLOC_ANESTHESIE"},
        {"code_poste": "BLOC_CHIRURGIE_GENERALE"},
        {"code_poste": "SALLE_REVEIL"},
        {"code_poste": "UNITE_SOINS_INTENSIFS"},
        {"code_poste": "CHAMBRE_HOPITAL"},
    ]

    return {"operations": operations, "postes": postes}


def generer_construction_batiment() -> dict:
    """Construction d'un bâtiment."""
    operations = [
        {
            "code_operation": "TERRASSEMENT",
            "duree_jours": 5,
            "poste_id": "PELLETEUSE",
            "operation_precedente": None,
        },
        {
            "code_operation": "FONDATIONS",
            "duree_jours": 7,
            "poste_id": "EQUIPE_GROS_OEUVRE",
            "operation_precedente": "TERRASSEMENT",
        },
        {
            "code_operation": "DALLE_BETON",
            "duree_jours": 3,
            "poste_id": "EQUIPE_GROS_OEUVRE",
            "operation_precedente": "FONDATIONS",
        },
        {
            "code_operation": "ELEVATION_MURS",
            "duree_jours": 10,
            "poste_id": "EQUIPE_MACONNERIE",
            "operation_precedente": "DALLE_BETON",
        },
        {
            "code_operation": "CHARPENTE",
            "duree_jours": 5,
            "poste_id": "EQUIPE_CHARPENTE",
            "operation_precedente": "ELEVATION_MURS",
        },
        {
            "code_operation": "COUVERTURE",
            "duree_jours": 4,
            "poste_id": "EQUIPE_COUVREURS",
            "operation_precedente": "CHARPENTE",
        },
        {
            "code_operation": "ISOLATION",
            "duree_jours": 6,
            "poste_id": "EQUIPE_ISOLATION",
            "operation_precedente": "COUVERTURE",
        },
        {
            "code_operation": "PLOMBERIE",
            "duree_jours": 5,
            "poste_id": "EQUIPE_PLOMBIERS",
            "operation_precedente": "ISOLATION",
        },
        {
            "code_operation": "ELECTRICITE",
            "duree_jours": 5,
            "poste_id": "EQUIPE_ELECTRICIENS",
            "operation_precedente": "ISOLATION",
        },
        {
            "code_operation": "PLATRERIE",
            "duree_jours": 7,
            "poste_id": "EQUIPE_PLATRIERS",
            "operation_precedente": "PLOMBERIE",
        },
        {
            "code_operation": "PEINTURE",
            "duree_jours": 5,
            "poste_id": "EQUIPE_PEINTRES",
            "operation_precedente": "PLATRERIE",
        },
        {
            "code_operation": "MENUISERIE",
            "duree_jours": 4,
            "poste_id": "EQUIPE_MENUISIERS",
            "operation_precedente": "PEINTURE",
        },
    ]

    postes = [
        {"code_poste": "PELLETEUSE"},
        {"code_poste": "EQUIPE_GROS_OEUVRE"},
        {"code_poste": "EQUIPE_MACONNERIE"},
        {"code_poste": "EQUIPE_CHARPENTE"},
        {"code_poste": "EQUIPE_COUVREURS"},
        {"code_poste": "EQUIPE_ISOLATION"},
        {"code_poste": "EQUIPE_PLOMBIERS"},
        {"code_poste": "EQUIPE_ELECTRICIENS"},
        {"code_poste": "EQUIPE_PLATRIERS"},
        {"code_poste": "EQUIPE_PEINTRES"},
        {"code_poste": "EQUIPE_MENUISIERS"},
    ]

    return {"operations": operations, "postes": postes}


def generer_hotel_gestion() -> dict:
    """Gestion d'un hôtel - préparation d'une chambre."""
    operations = [
        {
            "code_operation": "DEPART_CLIENT",
            "duree_jours": 1,
            "poste_id": "RECEPTION",
            "operation_precedente": None,
        },
        {
            "code_operation": "INSPECTION_CHAMBRE",
            "duree_jours": 1,
            "poste_id": "GOUVERNANTE",
            "operation_precedente": "DEPART_CLIENT",
        },
        {
            "code_operation": "NETTOYAGE_SALLE_BAIN",
            "duree_jours": 1,
            "poste_id": "FEMME_CHAMBRE",
            "operation_precedente": "INSPECTION_CHAMBRE",
        },
        {
            "code_operation": "NETTOYAGE_CHAMBRE",
            "duree_jours": 1,
            "poste_id": "FEMME_CHAMBRE",
            "operation_precedente": "NETTOYAGE_SALLE_BAIN",
        },
        {
            "code_operation": "CHANGEMENT_LINGE",
            "duree_jours": 1,
            "poste_id": "LINGERIE",
            "operation_precedente": "NETTOYAGE_CHAMBRE",
        },
        {
            "code_operation": "REAPPROVISIONNEMENT",
            "duree_jours": 1,
            "poste_id": "FEMME_CHAMBRE",
            "operation_precedente": "CHANGEMENT_LINGE",
        },
        {
            "code_operation": "CONTROLE_QUALITE",
            "duree_jours": 1,
            "poste_id": "GOUVERNANTE",
            "operation_precedente": "REAPPROVISIONNEMENT",
        },
        {
            "code_operation": "VALIDATION_CHAMBRE",
            "duree_jours": 1,
            "poste_id": "RECEPTION",
            "operation_precedente": "CONTROLE_QUALITE",
        },
    ]

    postes = [
        {"code_poste": "RECEPTION"},
        {"code_poste": "GOUVERNANTE"},
        {"code_poste": "FEMME_CHAMBRE"},
        {"code_poste": "LINGERIE"},
    ]

    return {"operations": operations, "postes": postes}


def generer_laboratoire_recherche() -> dict:
    """Laboratoire de recherche - protocole expérimental."""
    operations = [
        {
            "code_operation": "PREPARATION_ECHANTILLONS",
            "duree_jours": 2,
            "poste_id": "POSTE_PREPARATION",
            "operation_precedente": None,
        },
        {
            "code_operation": "STERILISATION",
            "duree_jours": 1,
            "poste_id": "AUTOCLAVE",
            "operation_precedente": "PREPARATION_ECHANTILLONS",
        },
        {
            "code_operation": "CULTURE_CELLULAIRE",
            "duree_jours": 5,
            "poste_id": "INCUBATEUR",
            "operation_precedente": "STERILISATION",
        },
        {
            "code_operation": "EXTRACTION_ADN",
            "duree_jours": 2,
            "poste_id": "POSTE_BIOLOGIE_MOLECULAIRE",
            "operation_precedente": "CULTURE_CELLULAIRE",
        },
        {
            "code_operation": "AMPLIFICATION_PCR",
            "duree_jours": 1,
            "poste_id": "THERMOCYCLEUR",
            "operation_precedente": "EXTRACTION_ADN",
        },
        {
            "code_operation": "ELECTROPHORESE",
            "duree_jours": 1,
            "poste_id": "BANC_ELECTROPHORESE",
            "operation_precedente": "AMPLIFICATION_PCR",
        },
        {
            "code_operation": "SEQUENCAGE",
            "duree_jours": 3,
            "poste_id": "SEQUENCEUR",
            "operation_precedente": "ELECTROPHORESE",
        },
        {
            "code_operation": "ANALYSE_BIOINFORMATIQUE",
            "duree_jours": 2,
            "poste_id": "STATION_INFORMATIQUE",
            "operation_precedente": "SEQUENCAGE",
        },
        {
            "code_operation": "REDACTION_RAPPORT",
            "duree_jours": 2,
            "poste_id": "BUREAU_CHERCHEUR",
            "operation_precedente": "ANALYSE_BIOINFORMATIQUE",
        },
    ]

    postes = [
        {"code_poste": "POSTE_PREPARATION"},
        {"code_poste": "AUTOCLAVE"},
        {"code_poste": "INCUBATEUR"},
        {"code_poste": "POSTE_BIOLOGIE_MOLECULAIRE"},
        {"code_poste": "THERMOCYCLEUR"},
        {"code_poste": "BANC_ELECTROPHORESE"},
        {"code_poste": "SEQUENCEUR"},
        {"code_poste": "STATION_INFORMATIQUE"},
        {"code_poste": "BUREAU_CHERCHEUR"},
    ]

    return {"operations": operations, "postes": postes}


def generer_centre_appels() -> dict:
    """Centre d'appels - traitement d'une réclamation."""
    operations = [
        {
            "code_operation": "RECEPTION_APPEL",
            "duree_jours": 1,
            "poste_id": "POSTE_TELEPHONIQUE_N1",
            "operation_precedente": None,
        },
        {
            "code_operation": "QUALIFICATION_DEMANDE",
            "duree_jours": 1,
            "poste_id": "POSTE_TELEPHONIQUE_N1",
            "operation_precedente": "RECEPTION_APPEL",
        },
        {
            "code_operation": "CREATION_TICKET",
            "duree_jours": 1,
            "poste_id": "SYSTEME_CRM",
            "operation_precedente": "QUALIFICATION_DEMANDE",
        },
        {
            "code_operation": "ESCALADE_N2",
            "duree_jours": 1,
            "poste_id": "POSTE_TELEPHONIQUE_N2",
            "operation_precedente": "CREATION_TICKET",
        },
        {
            "code_operation": "INVESTIGATION_TECHNIQUE",
            "duree_jours": 2,
            "poste_id": "POSTE_SUPPORT_TECHNIQUE",
            "operation_precedente": "ESCALADE_N2",
        },
        {
            "code_operation": "RESOLUTION",
            "duree_jours": 1,
            "poste_id": "POSTE_SUPPORT_TECHNIQUE",
            "operation_precedente": "INVESTIGATION_TECHNIQUE",
        },
        {
            "code_operation": "RAPPEL_CLIENT",
            "duree_jours": 1,
            "poste_id": "POSTE_TELEPHONIQUE_N2",
            "operation_precedente": "RESOLUTION",
        },
        {
            "code_operation": "CLOTURE_TICKET",
            "duree_jours": 1,
            "poste_id": "SYSTEME_CRM",
            "operation_precedente": "RAPPEL_CLIENT",
        },
    ]

    postes = [
        {"code_poste": "POSTE_TELEPHONIQUE_N1"},
        {"code_poste": "POSTE_TELEPHONIQUE_N2"},
        {"code_poste": "SYSTEME_CRM"},
        {"code_poste": "POSTE_SUPPORT_TECHNIQUE"},
    ]

    return {"operations": operations, "postes": postes}


def generer_salon_coiffure() -> dict:
    """Salon de coiffure - prestation complète."""
    operations = [
        {
            "code_operation": "ACCUEIL_CLIENT",
            "duree_jours": 1,
            "poste_id": "RECEPTION_SALON",
            "operation_precedente": None,
        },
        {
            "code_operation": "SHAMPOOING",
            "duree_jours": 1,
            "poste_id": "BAC_LAVAGE",
            "operation_precedente": "ACCUEIL_CLIENT",
        },
        {
            "code_operation": "COUPE",
            "duree_jours": 1,
            "poste_id": "FAUTEUIL_COIFFURE_1",
            "operation_precedente": "SHAMPOOING",
        },
        {
            "code_operation": "COLORATION",
            "duree_jours": 1,
            "poste_id": "ZONE_COLORATION",
            "operation_precedente": "COUPE",
        },
        {
            "code_operation": "SECHAGE",
            "duree_jours": 1,
            "poste_id": "FAUTEUIL_COIFFURE_1",
            "operation_precedente": "COLORATION",
        },
        {
            "code_operation": "COIFFAGE",
            "duree_jours": 1,
            "poste_id": "FAUTEUIL_COIFFURE_1",
            "operation_precedente": "SECHAGE",
        },
        {
            "code_operation": "FINITION",
            "duree_jours": 1,
            "poste_id": "FAUTEUIL_COIFFURE_1",
            "operation_precedente": "COIFFAGE",
        },
        {
            "code_operation": "ENCAISSEMENT",
            "duree_jours": 1,
            "poste_id": "CAISSE",
            "operation_precedente": "FINITION",
        },
    ]

    postes = [
        {"code_poste": "RECEPTION_SALON"},
        {"code_poste": "BAC_LAVAGE"},
        {"code_poste": "FAUTEUIL_COIFFURE_1"},
        {"code_poste": "ZONE_COLORATION"},
        {"code_poste": "CAISSE"},
    ]

    return {"operations": operations, "postes": postes}


def generer_garage_automobile() -> dict:
    """Garage automobile - réparation véhicule."""
    operations = [
        {
            "code_operation": "RECEPTION_VEHICULE",
            "duree_jours": 1,
            "poste_id": "ACCUEIL_GARAGE",
            "operation_precedente": None,
        },
        {
            "code_operation": "DIAGNOSTIC_PANNE",
            "duree_jours": 1,
            "poste_id": "PONT_ELEVATEUR_1",
            "operation_precedente": "RECEPTION_VEHICULE",
        },
        {
            "code_operation": "DEVIS",
            "duree_jours": 1,
            "poste_id": "BUREAU_MECANICIEN",
            "operation_precedente": "DIAGNOSTIC_PANNE",
        },
        {
            "code_operation": "COMMANDE_PIECES",
            "duree_jours": 2,
            "poste_id": "BUREAU_PIECES",
            "operation_precedente": "DEVIS",
        },
        {
            "code_operation": "DEMONTAGE",
            "duree_jours": 1,
            "poste_id": "PONT_ELEVATEUR_1",
            "operation_precedente": "COMMANDE_PIECES",
        },
        {
            "code_operation": "REPARATION",
            "duree_jours": 2,
            "poste_id": "POSTE_MECANIQUE",
            "operation_precedente": "DEMONTAGE",
        },
        {
            "code_operation": "REMONTAGE",
            "duree_jours": 1,
            "poste_id": "PONT_ELEVATEUR_1",
            "operation_precedente": "REPARATION",
        },
        {
            "code_operation": "TEST_ROUTE",
            "duree_jours": 1,
            "poste_id": "AIRE_ESSAI",
            "operation_precedente": "REMONTAGE",
        },
        {
            "code_operation": "NETTOYAGE_VEHICULE",
            "duree_jours": 1,
            "poste_id": "STATION_LAVAGE",
            "operation_precedente": "TEST_ROUTE",
        },
        {
            "code_operation": "RESTITUTION",
            "duree_jours": 1,
            "poste_id": "ACCUEIL_GARAGE",
            "operation_precedente": "NETTOYAGE_VEHICULE",
        },
    ]

    postes = [
        {"code_poste": "ACCUEIL_GARAGE"},
        {"code_poste": "PONT_ELEVATEUR_1"},
        {"code_poste": "BUREAU_MECANICIEN"},
        {"code_poste": "BUREAU_PIECES"},
        {"code_poste": "POSTE_MECANIQUE"},
        {"code_poste": "AIRE_ESSAI"},
        {"code_poste": "STATION_LAVAGE"},
    ]

    return {"operations": operations, "postes": postes}


def generer_pressing() -> dict:
    """Pressing - nettoyage de vêtements."""
    operations = [
        {
            "code_operation": "RECEPTION_LINGE",
            "duree_jours": 1,
            "poste_id": "COMPTOIR_ACCUEIL",
            "operation_precedente": None,
        },
        {
            "code_operation": "TRIAGE",
            "duree_jours": 1,
            "poste_id": "ZONE_TRI",
            "operation_precedente": "RECEPTION_LINGE",
        },
        {
            "code_operation": "DETACHAGE",
            "duree_jours": 1,
            "poste_id": "POSTE_DETACHAGE",
            "operation_precedente": "TRIAGE",
        },
        {
            "code_operation": "NETTOYAGE_SEC",
            "duree_jours": 1,
            "poste_id": "MACHINE_NETTOYAGE_SEC",
            "operation_precedente": "DETACHAGE",
        },
        {
            "code_operation": "SECHAGE",
            "duree_jours": 1,
            "poste_id": "SECHOIR_INDUSTRIEL",
            "operation_precedente": "NETTOYAGE_SEC",
        },
        {
            "code_operation": "REPASSAGE",
            "duree_jours": 1,
            "poste_id": "TABLE_REPASSAGE",
            "operation_precedente": "SECHAGE",
        },
        {
            "code_operation": "CONDITIONNEMENT",
            "duree_jours": 1,
            "poste_id": "ZONE_EMBALLAGE",
            "operation_precedente": "REPASSAGE",
        },
        {
            "code_operation": "MISE_DISPOSITION",
            "duree_jours": 1,
            "poste_id": "RAYON_RETRAIT",
            "operation_precedente": "CONDITIONNEMENT",
        },
    ]

    postes = [
        {"code_poste": "COMPTOIR_ACCUEIL"},
        {"code_poste": "ZONE_TRI"},
        {"code_poste": "POSTE_DETACHAGE"},
        {"code_poste": "MACHINE_NETTOYAGE_SEC"},
        {"code_poste": "SECHOIR_INDUSTRIEL"},
        {"code_poste": "TABLE_REPASSAGE"},
        {"code_poste": "ZONE_EMBALLAGE"},
        {"code_poste": "RAYON_RETRAIT"},
    ]

    return {"operations": operations, "postes": postes}


def generer_librairie_edition() -> dict:
    """Maison d'édition - publication d'un livre."""
    operations = [
        {
            "code_operation": "RECEPTION_MANUSCRIT",
            "duree_jours": 1,
            "poste_id": "BUREAU_EDITEUR",
            "operation_precedente": None,
        },
        {
            "code_operation": "LECTURE_COMITE",
            "duree_jours": 10,
            "poste_id": "SALLE_REUNION",
            "operation_precedente": "RECEPTION_MANUSCRIT",
        },
        {
            "code_operation": "CORRECTION_EDITORIALE",
            "duree_jours": 15,
            "poste_id": "BUREAU_CORRECTEUR",
            "operation_precedente": "LECTURE_COMITE",
        },
        {
            "code_operation": "MISE_EN_PAGE",
            "duree_jours": 5,
            "poste_id": "POSTE_PAO",
            "operation_precedente": "CORRECTION_EDITORIALE",
        },
        {
            "code_operation": "CREATION_COUVERTURE",
            "duree_jours": 3,
            "poste_id": "STUDIO_GRAPHISME",
            "operation_precedente": "MISE_EN_PAGE",
        },
        {
            "code_operation": "VALIDATION_AUTEUR",
            "duree_jours": 5,
            "poste_id": "BUREAU_EDITEUR",
            "operation_precedente": "CREATION_COUVERTURE",
        },
        {
            "code_operation": "IMPRESSION",
            "duree_jours": 7,
            "poste_id": "IMPRIMERIE",
            "operation_precedente": "VALIDATION_AUTEUR",
        },
        {
            "code_operation": "RELIURE",
            "duree_jours": 3,
            "poste_id": "ATELIER_RELIURE",
            "operation_precedente": "IMPRESSION",
        },
        {
            "code_operation": "DISTRIBUTION",
            "duree_jours": 2,
            "poste_id": "ENTREPOT_LOGISTIQUE",
            "operation_precedente": "RELIURE",
        },
    ]

    postes = [
        {"code_poste": "BUREAU_EDITEUR"},
        {"code_poste": "SALLE_REUNION"},
        {"code_poste": "BUREAU_CORRECTEUR"},
        {"code_poste": "POSTE_PAO"},
        {"code_poste": "STUDIO_GRAPHISME"},
        {"code_poste": "IMPRIMERIE"},
        {"code_poste": "ATELIER_RELIURE"},
        {"code_poste": "ENTREPOT_LOGISTIQUE"},
    ]

    return {"operations": operations, "postes": postes}


def sauvegarder_fichier(nom: str, data: dict, output_dir: Path) -> None:
    """Sauvegarde un fichier JSON."""
    fichier_path = output_dir / f"{nom}.json"
    with open(fichier_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  [CREE] {fichier_path.name}")
    print(f"    - {len(data['operations'])} operations")
    print(f"    - {len(data['postes'])} postes")


def main():
    """Génère les nouveaux fichiers de secteurs variés."""
    output_dir = Path("data/donnees_brutes/json_erp")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Generation de donnees ERP - Secteurs varies")
    print("=" * 60)
    print()

    secteurs = [
        ("hopital_bloc_operatoire", generer_hopital_bloc_operatoire),
        ("construction_batiment", generer_construction_batiment),
        ("hotel_gestion", generer_hotel_gestion),
        ("laboratoire_recherche", generer_laboratoire_recherche),
        ("centre_appels", generer_centre_appels),
        ("salon_coiffure", generer_salon_coiffure),
        ("garage_automobile", generer_garage_automobile),
        ("pressing", generer_pressing),
        ("librairie_edition", generer_librairie_edition),
    ]

    for nom, generateur in secteurs:
        print(f"[GENERATION] {nom}...")
        data = generateur()
        sauvegarder_fichier(nom, data, output_dir)
        print()

    print("=" * 60)
    print(f"[OK] {len(secteurs)} fichiers generes avec succes")
    print("=" * 60)
    print()
    print("Prochaine etape : enrichir avec les competences")
    print("  uv run python -m scripts.enrichir_competences_erp")


if __name__ == "__main__":
    main()
