"""Génération de jeux de données brutes à grande échelle (100+ opérations).

Crée des instances réalistes simulant de vrais ateliers de production avec
environ 100 opérations par fichier, permettant de tester la scalabilité
de la pipeline PRISME.

Usage:
    python -m scripts.generer_donnees_brutes_grande_echelle
    python -m scripts.generer_donnees_brutes_grande_echelle --taille 150
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from scripts.generer_donnees_depuis_config import sauvegarder_csv

# Chaque poste est généré comme `f"{type_poste}_{i}"` (instance numérotée d'un type — voir
# les 9 générateurs ci-dessous, tous antérieurs à l'enrichissement compétences de §5.4) :
# retirer ce suffixe numérique donne une compétence stable par type, partagée par toutes ses
# instances.
_SUFFIXE_INSTANCE = re.compile(r"_\d+$")


def _competence_depuis_code_poste(code_poste: str) -> str:
    return _SUFFIXE_INSTANCE.sub("", code_poste).lower()


def enrichir_avec_competences(data: dict) -> dict:
    """Ajoute `competences`/`competence_requise`, absents des générateurs ci-dessus — une
    compétence par type de poste, dérivée du code (`_competence_depuis_code_poste`), donc déjà
    cohérente entre `postes` et `operations` par construction (même fonction appliquée aux deux
    côtés, jamais de dérive possible entre les deux). Permet de réutiliser tel quel
    `sauvegarder_csv` (`scripts/generer_donnees_depuis_config.py`), qui suppose ces deux champs
    présents."""
    for poste in data["postes"]:
        poste["competences"] = [_competence_depuis_code_poste(poste["code_poste"])]
    for operation in data["operations"]:
        operation["competence_requise"] = _competence_depuis_code_poste(operation["poste_id"])
    return data


def generer_atelier_mecanique_large(n_operations: int = 100) -> dict:
    """Atelier de fabrication mécanique - grande échelle."""
    # Noms de pièces réalistes
    noms_pieces = [
        "CARTER",
        "ARBRE",
        "VILEBREQUIN",
        "PISTON",
        "VANNE",
        "FLASQUE",
        "BOITIER",
        "CHASSIS",
        "BRIDE",
        "AXE",
        "PALIER",
        "ENGRENAGE",
        "POULIE",
        "ROTOR",
        "STATOR",
        "BIELLE",
        "PLAQUE",
        "SUPPORT",
        "EQUERRE",
        "MANIVELLE",
        "COUVERCLE",
        "SOCLE",
        "CORPS_VALVE",
        "ARBRE_TRANSMISSION",
        "MOYEU",
    ]

    # Définir les types de postes et leurs caractéristiques (durées en jours)
    types_postes = {
        "DECOUPEUSE_LASER": {"duree_min": 1, "duree_max": 2, "capacite": 5},
        "DECOUPEUSE_PLASMA": {"duree_min": 1, "duree_max": 2, "capacite": 3},
        "PERCEUSE_CNC": {"duree_min": 1, "duree_max": 1, "capacite": 8},
        "FRAISEUSE_CNC": {"duree_min": 1, "duree_max": 3, "capacite": 6},
        "PRESSE_PLIAGE": {"duree_min": 1, "duree_max": 2, "capacite": 4},
        "PRESSE_EMBOUTISSAGE": {"duree_min": 1, "duree_max": 2, "capacite": 3},
        "POSTE_SOUDURE": {"duree_min": 1, "duree_max": 4, "capacite": 10},
        "ROBOT_SOUDURE": {"duree_min": 1, "duree_max": 3, "capacite": 4},
        "CABINE_PEINTURE": {"duree_min": 1, "duree_max": 3, "capacite": 6},
        "TUNNEL_PEINTURE": {"duree_min": 1, "duree_max": 2, "capacite": 3},
        "POSTE_ASSEMBLAGE": {"duree_min": 1, "duree_max": 2, "capacite": 12},
        "STATION_CONTROLE": {"duree_min": 1, "duree_max": 1, "capacite": 8},
        "POSTE_EBAVURAGE": {"duree_min": 1, "duree_max": 1, "capacite": 6},
        "CENTRE_USINAGE": {"duree_min": 1, "duree_max": 4, "capacite": 5},
        "POSTE_POLISSAGE": {"duree_min": 1, "duree_max": 2, "capacite": 4},
    }

    # Créer les postes (instances multiples de chaque type)
    postes = []
    for type_poste, specs in types_postes.items():
        for i in range(1, specs["capacite"] + 1):
            postes.append({"code_poste": f"{type_poste}_{i}"})

    # Générer les opérations organisées en lots de production
    operations = []
    n_lots = n_operations // 10  # Environ 10 opérations par lot

    phases = [
        ("PREPARATION", ["DECOUPEUSE_LASER", "DECOUPEUSE_PLASMA", "PERCEUSE_CNC"]),
        ("USINAGE", ["FRAISEUSE_CNC", "CENTRE_USINAGE", "POSTE_EBAVURAGE"]),
        ("FORMAGE", ["PRESSE_PLIAGE", "PRESSE_EMBOUTISSAGE"]),
        ("SOUDURE", ["POSTE_SOUDURE", "ROBOT_SOUDURE"]),
        ("FINITION", ["POSTE_POLISSAGE", "POSTE_EBAVURAGE"]),
        ("PEINTURE", ["CABINE_PEINTURE", "TUNNEL_PEINTURE"]),
        ("ASSEMBLAGE", ["POSTE_ASSEMBLAGE"]),
        ("CONTROLE", ["STATION_CONTROLE"]),
    ]

    op_id = 1
    for lot in range(1, n_lots + 1):
        precedente = None
        # Choisir un nom de pièce pour ce lot
        nom_piece = random.choice(noms_pieces)

        # Chaque lot passe par 8-12 phases aléatoires
        n_phases_lot = random.randint(8, 12)
        phases_lot = random.sample(phases, min(n_phases_lot, len(phases)))

        for phase_nom, types_poste_phase in phases_lot:
            # Choisir un type de poste aléatoire pour cette phase
            type_poste = random.choice(types_poste_phase)

            # Choisir une instance de ce type de poste
            instances_disponibles = [p["code_poste"] for p in postes if p["code_poste"].startswith(type_poste)]
            poste_choisi = random.choice(instances_disponibles)

            # Générer une durée aléatoire
            specs = types_postes[type_poste]
            duree = random.randint(specs["duree_min"], specs["duree_max"])

            # Créer l'opération avec nom réaliste
            code_op = f"{nom_piece}_{phase_nom}_{op_id:04d}"
            operations.append(
                {
                    "code_operation": code_op,
                    "duree_jours": duree,
                    "poste_id": poste_choisi,
                    "operation_precedente": precedente,
                }
            )

            precedente = code_op
            op_id += 1

            if op_id > n_operations:
                break

        if op_id > n_operations:
            break

    # Compléter si nécessaire
    while len(operations) < n_operations:
        nom_piece = random.choice(noms_pieces)
        type_poste = random.choice(list(types_postes.keys()))
        instances_disponibles = [p["code_poste"] for p in postes if p["code_poste"].startswith(type_poste)]
        poste_choisi = random.choice(instances_disponibles)
        specs = types_postes[type_poste]
        duree = random.randint(specs["duree_min"], specs["duree_max"])

        code_op = f"{nom_piece}_COMP_{op_id:04d}"
        operations.append(
            {
                "code_operation": code_op,
                "duree_jours": duree,
                "poste_id": poste_choisi,
                "operation_precedente": None,
            }
        )
        op_id += 1

    return {"operations": operations[:n_operations], "postes": postes}


def generer_assemblage_electronique_large(n_operations: int = 100) -> dict:
    """Assemblage électronique - grande échelle."""
    # Noms de produits/cartes réalistes
    noms_produits = [
        "PLATINE_SMARTPHONE",
        "CARTE_ROUTEUR",
        "PCB_LED",
        "CONTROLEUR_MOTEUR",
        "MODULE_WIFI",
        "CARTE_ALIMENTATION",
        "PCB_CAPTEUR",
        "INTERFACE_USB",
        "CARTE_AUDIO",
        "MODULE_BLUETOOTH",
        "REGULATEUR_TENSION",
        "CARTE_MERE",
        "MODULE_GPS",
        "CONVERTISSEUR_DC",
        "CARTE_AFFICHAGE",
        "PCB_TEMPERATURE",
        "CONTROLEUR_RGB",
        "MODULE_ZIGBEE",
        "CARTE_ETHERNET",
        "DRIVER_LED",
        "CARTE_MEMOIRE",
        "INTERFACE_CAN",
        "MODULE_LORA",
        "PCB_PUISSANCE",
    ]

    types_postes = {
        "PICK_PLACE": {"duree_min": 1, "duree_max": 3, "capacite": 6},
        "FOUR_REFUSION": {"duree_min": 1, "duree_max": 1, "capacite": 4},
        "AOI": {"duree_min": 1, "duree_max": 1, "capacite": 5},
        "POSTE_SOUDURE_MANUEL": {"duree_min": 1, "duree_max": 2, "capacite": 15},
        "BANC_TEST_ICT": {"duree_min": 1, "duree_max": 2, "capacite": 8},
        "BANC_TEST_FONCTIONNEL": {"duree_min": 1, "duree_max": 2, "capacite": 6},
        "ROBOT_COATING": {"duree_min": 1, "duree_max": 1, "capacite": 3},
        "STATION_ASSEMBLAGE": {"duree_min": 1, "duree_max": 2, "capacite": 10},
        "POSTE_DEPANNELISATION": {"duree_min": 1, "duree_max": 1, "capacite": 4},
        "STATION_PACKAGING": {"duree_min": 1, "duree_max": 1, "capacite": 8},
    }

    postes = []
    for type_poste, specs in types_postes.items():
        for i in range(1, specs["capacite"] + 1):
            postes.append({"code_poste": f"{type_poste}_{i}"})

    operations = []
    n_cartes = n_operations // 8  # Environ 8 opérations par carte

    phases_pcb = [
        ("PREP", ["STATION_ASSEMBLAGE"]),
        ("POSE_CMS_A", ["PICK_PLACE"]),
        ("REFUSION_A", ["FOUR_REFUSION"]),
        ("AOI_A", ["AOI"]),
        ("POSE_CMS_B", ["PICK_PLACE"]),
        ("REFUSION_B", ["FOUR_REFUSION"]),
        ("SOUDURE_THT", ["POSTE_SOUDURE_MANUEL"]),
        ("TEST_ICT", ["BANC_TEST_ICT"]),
        ("TEST_FONC", ["BANC_TEST_FONCTIONNEL"]),
        ("COATING", ["ROBOT_COATING"]),
        ("DEPANEL", ["POSTE_DEPANNELISATION"]),
        ("PACKAGE", ["STATION_PACKAGING"]),
    ]

    op_id = 1
    for carte in range(1, n_cartes + 1):
        precedente = None
        # Choisir un nom de produit pour cette carte
        nom_produit = random.choice(noms_produits)

        # Chaque carte suit un processus standard
        n_phases = random.randint(8, len(phases_pcb))
        phases_carte = random.sample(phases_pcb, n_phases)

        for phase_nom, types_poste_phase in phases_carte:
            type_poste = random.choice(types_poste_phase)
            instances_disponibles = [p["code_poste"] for p in postes if p["code_poste"].startswith(type_poste)]
            poste_choisi = random.choice(instances_disponibles)
            specs = types_postes[type_poste]
            duree = random.randint(specs["duree_min"], specs["duree_max"])

            code_op = f"{nom_produit}_{phase_nom}_{op_id:04d}"
            operations.append(
                {
                    "code_operation": code_op,
                    "duree_jours": duree,
                    "poste_id": poste_choisi,
                    "operation_precedente": precedente,
                }
            )

            precedente = code_op
            op_id += 1

            if op_id > n_operations:
                break

        if op_id > n_operations:
            break

    while len(operations) < n_operations:
        nom_produit = random.choice(noms_produits)
        type_poste = random.choice(list(types_postes.keys()))
        instances_disponibles = [p["code_poste"] for p in postes if p["code_poste"].startswith(type_poste)]
        poste_choisi = random.choice(instances_disponibles)
        specs = types_postes[type_poste]
        duree = random.randint(specs["duree_min"], specs["duree_max"])

        code_op = f"{nom_produit}_EXTRA_{op_id:04d}"
        operations.append(
            {
                "code_operation": code_op,
                "duree_jours": duree,
                "poste_id": poste_choisi,
                "operation_precedente": None,
            }
        )
        op_id += 1

    return {"operations": operations[:n_operations], "postes": postes}


def generer_agroalimentaire_large(n_operations: int = 100) -> dict:
    """Production agro-alimentaire - grande échelle."""
    # Noms de produits alimentaires réalistes
    noms_produits = [
        "CONSERVE_TOMATES",
        "LOT_CAROTTES",
        "BATCH_HARICOTS",
        "PUREE_POMMES",
        "COMPOTE_FRUITS",
        "SOUPE_LEGUMES",
        "SAUCE_TOMATE",
        "CONFITURE_FRAISES",
        "JUS_ORANGE",
        "PLAT_PREPARE",
        "SALADE_MACEDOINE",
        "RATATOUILLE",
        "PATE_TOMATE",
        "COULIS_FRUITS",
        "SIROP_AGAVE",
        "VELOUTE_POTIRON",
        "MACEDOINE_LEGUMES",
        "CHAMPIGNONS_BOCAL",
        "CORNICHONS",
        "KETCHUP",
        "MAYONNAISE",
        "MOUTARDE",
        "VINAIGRETTE",
        "PESTO",
    ]

    types_postes = {
        "QUAI_RECEPTION": {"duree_min": 1, "duree_max": 1, "capacite": 4},
        "TUNNEL_LAVAGE": {"duree_min": 1, "duree_max": 1, "capacite": 3},
        "LIGNE_EPLUCHAGE": {"duree_min": 1, "duree_max": 2, "capacite": 5},
        "ROBOT_DECOUPE": {"duree_min": 1, "duree_max": 1, "capacite": 6},
        "AUTOCLAVE": {"duree_min": 2, "duree_max": 5, "capacite": 8},
        "TUNNEL_REFROIDISSEMENT": {"duree_min": 1, "duree_max": 3, "capacite": 4},
        "LIGNE_CONDITIONNEMENT": {"duree_min": 1, "duree_max": 2, "capacite": 10},
        "ETIQUETEUSE": {"duree_min": 1, "duree_max": 1, "capacite": 6},
        "ROBOT_PALETTISEUR": {"duree_min": 1, "duree_max": 1, "capacite": 5},
        "POSTE_CONTROLE_QUALITE": {"duree_min": 1, "duree_max": 1, "capacite": 8},
    }

    postes = []
    for type_poste, specs in types_postes.items():
        for i in range(1, specs["capacite"] + 1):
            postes.append({"code_poste": f"{type_poste}_{i}"})

    operations = []
    n_lots = n_operations // 9

    phases_production = [
        ("RECEPTION", ["QUAI_RECEPTION"]),
        ("LAVAGE", ["TUNNEL_LAVAGE"]),
        ("EPLUCHAGE", ["LIGNE_EPLUCHAGE"]),
        ("DECOUPE", ["ROBOT_DECOUPE"]),
        ("CUISSON", ["AUTOCLAVE"]),
        ("REFROIDISSEMENT", ["TUNNEL_REFROIDISSEMENT"]),
        ("CONDITIONNEMENT", ["LIGNE_CONDITIONNEMENT"]),
        ("ETIQUETAGE", ["ETIQUETEUSE"]),
        ("CONTROLE", ["POSTE_CONTROLE_QUALITE"]),
        ("PALETTISATION", ["ROBOT_PALETTISEUR"]),
    ]

    op_id = 1
    for lot in range(1, n_lots + 1):
        precedente = None
        # Choisir un produit pour ce lot
        nom_produit = random.choice(noms_produits)

        n_phases = random.randint(7, len(phases_production))
        phases_lot = random.sample(phases_production, n_phases)

        for phase_nom, types_poste_phase in phases_lot:
            type_poste = random.choice(types_poste_phase)
            instances_disponibles = [p["code_poste"] for p in postes if p["code_poste"].startswith(type_poste)]
            poste_choisi = random.choice(instances_disponibles)
            specs = types_postes[type_poste]
            duree = random.randint(specs["duree_min"], specs["duree_max"])

            code_op = f"{nom_produit}_{phase_nom}_{op_id:04d}"
            operations.append(
                {
                    "code_operation": code_op,
                    "duree_jours": duree,
                    "poste_id": poste_choisi,
                    "operation_precedente": precedente,
                }
            )

            precedente = code_op
            op_id += 1

            if op_id > n_operations:
                break

        if op_id > n_operations:
            break

    while len(operations) < n_operations:
        nom_produit = random.choice(noms_produits)
        type_poste = random.choice(list(types_postes.keys()))
        instances_disponibles = [p["code_poste"] for p in postes if p["code_poste"].startswith(type_poste)]
        poste_choisi = random.choice(instances_disponibles)
        specs = types_postes[type_poste]
        duree = random.randint(specs["duree_min"], specs["duree_max"])

        code_op = f"{nom_produit}_SUPP_{op_id:04d}"
        operations.append(
            {
                "code_operation": code_op,
                "duree_jours": duree,
                "poste_id": poste_choisi,
                "operation_precedente": None,
            }
        )
        op_id += 1

    return {"operations": operations[:n_operations], "postes": postes}


def generer_hopital_bloc_operatoire_large(n_operations: int = 100) -> dict:
    """Hôpital - Bloc opératoire - grande échelle."""
    # Noms de patients réalistes
    noms_patients = [
        "PATIENT_DUPONT",
        "PATIENT_MARTIN",
        "PATIENT_BERNARD",
        "PATIENT_THOMAS",
        "PATIENT_ROBERT",
        "PATIENT_PETIT",
        "PATIENT_DUBOIS",
        "PATIENT_RICHARD",
        "PATIENT_MOREAU",
        "PATIENT_SIMON",
        "PATIENT_LAURENT",
        "PATIENT_LEFEBVRE",
        "PATIENT_MICHEL",
        "PATIENT_GARCIA",
        "PATIENT_DAVID",
        "PATIENT_BERTRAND",
        "PATIENT_ROUX",
        "PATIENT_VINCENT",
        "PATIENT_FOURNIER",
        "PATIENT_MOREL",
        "PATIENT_GIRARD",
        "PATIENT_ANDRE",
        "PATIENT_LEFEVRE",
        "PATIENT_MERCIER",
    ]

    types_postes = {
        "BLOC_CHIRURGIE_GENERALE": {"duree_min": 1, "duree_max": 4, "capacite": 8},
        "BLOC_CHIRURGIE_ORTHOPEDIQUE": {"duree_min": 2, "duree_max": 6, "capacite": 6},
        "BLOC_CHIRURGIE_CARDIAQUE": {"duree_min": 3, "duree_max": 8, "capacite": 4},
        "SALLE_REVEIL": {"duree_min": 1, "duree_max": 2, "capacite": 12},
        "SALLE_PREPARATION": {"duree_min": 1, "duree_max": 1, "capacite": 10},
        "UNITE_SOINS_INTENSIFS": {"duree_min": 1, "duree_max": 24, "capacite": 8},
        "SALLE_RADIOLOGIE": {"duree_min": 1, "duree_max": 1, "capacite": 6},
        "LABORATOIRE_ANALYSES": {"duree_min": 1, "duree_max": 2, "capacite": 5},
        "BLOC_URGENCES": {"duree_min": 1, "duree_max": 3, "capacite": 10},
    }

    postes = []
    for type_poste, specs in types_postes.items():
        for i in range(1, specs["capacite"] + 1):
            postes.append({"code_poste": f"{type_poste}_{i}"})

    operations = []
    n_patients = n_operations // 6

    phases = [
        ("ADMISSION", ["SALLE_PREPARATION"]),
        ("EXAMENS_PREOP", ["SALLE_RADIOLOGIE", "LABORATOIRE_ANALYSES"]),
        ("PREPARATION_PATIENT", ["SALLE_PREPARATION"]),
        ("INTERVENTION", ["BLOC_CHIRURGIE_GENERALE", "BLOC_CHIRURGIE_ORTHOPEDIQUE", "BLOC_CHIRURGIE_CARDIAQUE"]),
        ("REVEIL", ["SALLE_REVEIL"]),
        ("SOINS_POSTOP", ["UNITE_SOINS_INTENSIFS"]),
        ("CONTROLE_POSTOP", ["SALLE_RADIOLOGIE"]),
    ]

    op_id = 1
    for patient in range(1, n_patients + 1):
        precedente = None
        # Choisir un nom de patient
        nom_patient = random.choice(noms_patients)

        n_phases = random.randint(4, 7)
        phases_patient = random.sample(phases, n_phases)

        for phase_nom, types_poste_phase in phases_patient:
            type_poste = random.choice(types_poste_phase)
            instances_disponibles = [p["code_poste"] for p in postes if p["code_poste"].startswith(type_poste)]
            poste_choisi = random.choice(instances_disponibles)
            specs = types_postes[type_poste]
            duree = random.randint(specs["duree_min"], specs["duree_max"])

            code_op = f"{nom_patient}_{phase_nom}_{op_id:04d}"
            operations.append(
                {
                    "code_operation": code_op,
                    "duree_jours": duree,
                    "poste_id": poste_choisi,
                    "operation_precedente": precedente,
                }
            )

            precedente = code_op
            op_id += 1

            if op_id > n_operations:
                break

        if op_id > n_operations:
            break

    return {"operations": operations[:n_operations], "postes": postes}


def generer_logistique_transport_large(n_operations: int = 100) -> dict:
    """Logistique et transport - grande échelle."""
    # Noms de villes/destinations réalistes
    noms_destinations = [
        "CMD_PARIS",
        "CMD_LYON",
        "CMD_MARSEILLE",
        "CMD_TOULOUSE",
        "CMD_BORDEAUX",
        "CMD_LILLE",
        "CMD_NANTES",
        "CMD_STRASBOURG",
        "CMD_RENNES",
        "CMD_NICE",
        "LIV_GRENOBLE",
        "LIV_DIJON",
        "LIV_ANGERS",
        "LIV_TOURS",
        "LIV_REIMS",
        "COLIS_CAEN",
        "COLIS_NANCY",
        "COLIS_ROUEN",
        "ENVOI_CLERMONT",
        "ENVOI_ORLEANS",
        "PALETTE_LIMOGES",
        "PALETTE_TROYES",
        "FRET_VALENCE",
    ]

    types_postes = {
        "CAMION_20T": {"duree_min": 1, "duree_max": 8, "capacite": 15},
        "CAMION_10T": {"duree_min": 1, "duree_max": 5, "capacite": 20},
        "CAMIONNETTE": {"duree_min": 1, "duree_max": 3, "capacite": 25},
        "CHARIOT_ELEVATEUR": {"duree_min": 1, "duree_max": 1, "capacite": 12},
        "QUAI_CHARGEMENT": {"duree_min": 1, "duree_max": 2, "capacite": 8},
        "QUAI_DECHARGEMENT": {"duree_min": 1, "duree_max": 2, "capacite": 8},
        "ZONE_PREPARATION": {"duree_min": 1, "duree_max": 2, "capacite": 10},
        "POSTE_CONTROLE": {"duree_min": 1, "duree_max": 1, "capacite": 6},
        "ZONE_STOCKAGE": {"duree_min": 1, "duree_max": 1, "capacite": 20},
    }

    postes = []
    for type_poste, specs in types_postes.items():
        for i in range(1, specs["capacite"] + 1):
            postes.append({"code_poste": f"{type_poste}_{i}"})

    operations = []
    n_commandes = n_operations // 7

    phases = [
        ("RECEPTION", ["QUAI_DECHARGEMENT"]),
        ("CONTROLE_ENTREE", ["POSTE_CONTROLE"]),
        ("STOCKAGE", ["CHARIOT_ELEVATEUR", "ZONE_STOCKAGE"]),
        ("PREPARATION_COMMANDE", ["ZONE_PREPARATION"]),
        ("EMBALLAGE", ["ZONE_PREPARATION"]),
        ("CHARGEMENT", ["QUAI_CHARGEMENT", "CHARIOT_ELEVATEUR"]),
        ("TRANSPORT", ["CAMION_20T", "CAMION_10T", "CAMIONNETTE"]),
        ("LIVRAISON", ["CAMION_20T", "CAMION_10T", "CAMIONNETTE"]),
    ]

    op_id = 1
    for commande in range(1, n_commandes + 1):
        precedente = None
        # Choisir une destination
        nom_destination = random.choice(noms_destinations)

        n_phases = random.randint(6, 8)
        phases_commande = random.sample(phases, n_phases)

        for phase_nom, types_poste_phase in phases_commande:
            type_poste = random.choice(types_poste_phase)
            instances_disponibles = [p["code_poste"] for p in postes if p["code_poste"].startswith(type_poste)]
            poste_choisi = random.choice(instances_disponibles)
            specs = types_postes[type_poste]
            duree = random.randint(specs["duree_min"], specs["duree_max"])

            code_op = f"{nom_destination}_{phase_nom}_{op_id:04d}"
            operations.append(
                {
                    "code_operation": code_op,
                    "duree_jours": duree,
                    "poste_id": poste_choisi,
                    "operation_precedente": precedente,
                }
            )

            precedente = code_op
            op_id += 1

            if op_id > n_operations:
                break

        if op_id > n_operations:
            break

    return {"operations": operations[:n_operations], "postes": postes}


def generer_restauration_collective_large(n_operations: int = 100) -> dict:
    """Restauration collective - grande échelle."""
    # Noms de plats/menus réalistes
    noms_menus = [
        "MENU_VEGETARIEN",
        "PLAT_POULET_ROTI",
        "ENTREE_SALADE",
        "DESSERT_TARTE",
        "MENU_POISSON",
        "PLAT_BOEUF_BOURGUIGNON",
        "SOUPE_JOUR",
        "GRATIN_DAUPHINOIS",
        "SALADE_CESAR",
        "QUICHE_LORRAINE",
        "LASAGNES_MAISON",
        "COUSCOUS",
        "PAELLA",
        "BLANQUETTE_VEAU",
        "CHILI_CON_CARNE",
        "CURRY_LEGUMES",
        "PIZZA_MARGHERITA",
        "HAMBURGER_MAISON",
        "TAJINE_POULET",
        "RISOTTO",
        "PATES_BOLOGNAISE",
        "HACHIS_PARMENTIER",
        "CASSOULET",
        "POT_AU_FEU",
    ]

    types_postes = {
        "ZONE_RECEPTION": {"duree_min": 1, "duree_max": 1, "capacite": 5},
        "CHAMBRE_FROIDE": {"duree_min": 1, "duree_max": 3, "capacite": 8},
        "ZONE_PREPARATION_LEGUMES": {"duree_min": 1, "duree_max": 2, "capacite": 10},
        "ZONE_PREPARATION_VIANDES": {"duree_min": 1, "duree_max": 2, "capacite": 8},
        "FOUR_CUISINE": {"duree_min": 1, "duree_max": 4, "capacite": 12},
        "ZONE_CUISSON": {"duree_min": 1, "duree_max": 3, "capacite": 15},
        "ZONE_ASSEMBLAGE_PLATS": {"duree_min": 1, "duree_max": 1, "capacite": 12},
        "ZONE_CONDITIONNEMENT": {"duree_min": 1, "duree_max": 1, "capacite": 10},
        "ZONE_DISTRIBUTION": {"duree_min": 1, "duree_max": 2, "capacite": 8},
    }

    postes = []
    for type_poste, specs in types_postes.items():
        for i in range(1, specs["capacite"] + 1):
            postes.append({"code_poste": f"{type_poste}_{i}"})

    operations = []
    n_repas = n_operations // 7

    phases = [
        ("RECEPTION", ["ZONE_RECEPTION"]),
        ("STOCKAGE", ["CHAMBRE_FROIDE"]),
        ("PREP_LEGUMES", ["ZONE_PREPARATION_LEGUMES"]),
        ("PREP_VIANDES", ["ZONE_PREPARATION_VIANDES"]),
        ("CUISSON", ["FOUR_CUISINE", "ZONE_CUISSON"]),
        ("ASSEMBLAGE", ["ZONE_ASSEMBLAGE_PLATS"]),
        ("CONDITIONNEMENT", ["ZONE_CONDITIONNEMENT"]),
        ("DISTRIBUTION", ["ZONE_DISTRIBUTION"]),
    ]

    op_id = 1
    for repas in range(1, n_repas + 1):
        precedente = None
        # Choisir un menu
        nom_menu = random.choice(noms_menus)

        n_phases = random.randint(6, 8)
        phases_repas = random.sample(phases, n_phases)

        for phase_nom, types_poste_phase in phases_repas:
            type_poste = random.choice(types_poste_phase)
            instances_disponibles = [p["code_poste"] for p in postes if p["code_poste"].startswith(type_poste)]
            poste_choisi = random.choice(instances_disponibles)
            specs = types_postes[type_poste]
            duree = random.randint(specs["duree_min"], specs["duree_max"])

            code_op = f"{nom_menu}_{phase_nom}_{op_id:04d}"
            operations.append(
                {
                    "code_operation": code_op,
                    "duree_jours": duree,
                    "poste_id": poste_choisi,
                    "operation_precedente": precedente,
                }
            )

            precedente = code_op
            op_id += 1

            if op_id > n_operations:
                break

        if op_id > n_operations:
            break

    return {"operations": operations[:n_operations], "postes": postes}


def generer_services_nettoyage_large(n_operations: int = 100) -> dict:
    """Services de nettoyage - grande échelle."""
    # Noms de bâtiments/sites réalistes
    noms_sites = [
        "IMMEUBLE_HAUSMANN",
        "BUREAUX_LAFAYETTE",
        "TOUR_MONTPARNASSE",
        "CENTRE_COMMERCIAL_VELIZY",
        "HOPITAL_POMPIDOU",
        "ECOLE_PASTEUR",
        "RESIDENCE_BELLE_VUE",
        "USINE_RENAULT",
        "ENTREPOT_LOGISTICS",
        "HOTEL_MERIDIEN",
        "AEROPORT_ORLY",
        "GARE_LYON",
        "STADE_FRANCE",
        "MUSEE_LOUVRE",
        "THEATRE_CHATELET",
        "PISCINE_MUNICIPALE",
        "MAIRIE_15EME",
        "CASERNE_POMPIERS",
        "COMMISSARIAT_CENTRAL",
        "TRIBUNAL_GRANDE_INSTANCE",
        "CENTRE_LOISIRS",
        "MEDIATHEQUE",
    ]

    types_postes = {
        "EQUIPE_BUREAUX": {"duree_min": 1, "duree_max": 2, "capacite": 15},
        "EQUIPE_ESPACES_COMMUNS": {"duree_min": 1, "duree_max": 3, "capacite": 12},
        "EQUIPE_SANITAIRES": {"duree_min": 1, "duree_max": 2, "capacite": 10},
        "EQUIPE_VITRES": {"duree_min": 1, "duree_max": 4, "capacite": 8},
        "EQUIPE_SOLS": {"duree_min": 1, "duree_max": 3, "capacite": 12},
        "MACHINE_AUTOLAVEUSE": {"duree_min": 1, "duree_max": 2, "capacite": 6},
        "POSTE_CONTROLE_QUALITE": {"duree_min": 1, "duree_max": 1, "capacite": 5},
    }

    postes = []
    for type_poste, specs in types_postes.items():
        for i in range(1, specs["capacite"] + 1):
            postes.append({"code_poste": f"{type_poste}_{i}"})

    operations = []
    n_sites = n_operations // 6

    phases = [
        ("NETTOYAGE_BUREAUX", ["EQUIPE_BUREAUX"]),
        ("NETTOYAGE_COMMUNS", ["EQUIPE_ESPACES_COMMUNS"]),
        ("NETTOYAGE_SANITAIRES", ["EQUIPE_SANITAIRES"]),
        ("NETTOYAGE_VITRES", ["EQUIPE_VITRES"]),
        ("NETTOYAGE_SOLS", ["EQUIPE_SOLS", "MACHINE_AUTOLAVEUSE"]),
        ("CONTROLE_QUALITE", ["POSTE_CONTROLE_QUALITE"]),
    ]

    op_id = 1
    for site in range(1, n_sites + 1):
        precedente = None
        # Choisir un nom de site
        nom_site = random.choice(noms_sites)

        n_phases = random.randint(4, 6)
        phases_site = random.sample(phases, n_phases)

        for phase_nom, types_poste_phase in phases_site:
            type_poste = random.choice(types_poste_phase)
            instances_disponibles = [p["code_poste"] for p in postes if p["code_poste"].startswith(type_poste)]
            poste_choisi = random.choice(instances_disponibles)
            specs = types_postes[type_poste]
            duree = random.randint(specs["duree_min"], specs["duree_max"])

            code_op = f"{nom_site}_{phase_nom}_{op_id:04d}"
            operations.append(
                {
                    "code_operation": code_op,
                    "duree_jours": duree,
                    "poste_id": poste_choisi,
                    "operation_precedente": precedente,
                }
            )

            precedente = code_op
            op_id += 1

            if op_id > n_operations:
                break

        if op_id > n_operations:
            break

    return {"operations": operations[:n_operations], "postes": postes}


def generer_gestion_espaces_verts_large(n_operations: int = 100) -> dict:
    """Gestion d'espaces verts - grande échelle."""
    # Noms de parcs/zones réalistes
    noms_zones = [
        "PARC_MONCEAU",
        "JARDIN_LUXEMBOURG",
        "ZONE_TUILERIES",
        "BOIS_VINCENNES",
        "PARC_BUTTES_CHAUMONT",
        "JARDIN_PLANTES",
        "PARC_MONTSOURIS",
        "SQUARE_TEMPLE",
        "JARDIN_PALAIS_ROYAL",
        "ESPLANADE_INVALIDES",
        "PARC_ANDRE_CITROEN",
        "JARDIN_ACCLIMATATION",
        "PARC_BERCY",
        "SQUARE_BATIGNOLLES",
        "JARDIN_ATLANTIQUE",
        "PROMENADE_PLANTEE",
        "PARC_BELLEVILLE",
        "SQUARE_TROUSSEAU",
        "JARDIN_CATHERINE_LABOURE",
        "PARC_SAINTE_PERINE",
        "SQUARE_RECAMIER",
        "JARDIN_SERRES_AUTEUIL",
    ]

    types_postes = {
        "EQUIPE_TONTE": {"duree_min": 1, "duree_max": 3, "capacite": 12},
        "EQUIPE_TAILLE": {"duree_min": 1, "duree_max": 4, "capacite": 10},
        "EQUIPE_DESHERBAGE": {"duree_min": 1, "duree_max": 2, "capacite": 15},
        "EQUIPE_ARROSAGE": {"duree_min": 1, "duree_max": 2, "capacite": 8},
        "EQUIPE_PLANTATION": {"duree_min": 1, "duree_max": 5, "capacite": 10},
        "EQUIPE_TRAITEMENT": {"duree_min": 1, "duree_max": 2, "capacite": 6},
        "TONDEUSE_TRACTEE": {"duree_min": 1, "duree_max": 3, "capacite": 8},
        "CAMION_BENNE": {"duree_min": 1, "duree_max": 2, "capacite": 5},
    }

    postes = []
    for type_poste, specs in types_postes.items():
        for i in range(1, specs["capacite"] + 1):
            postes.append({"code_poste": f"{type_poste}_{i}"})

    operations = []
    n_zones = n_operations // 6

    phases = [
        ("TONTE", ["EQUIPE_TONTE", "TONDEUSE_TRACTEE"]),
        ("TAILLE_HAIES", ["EQUIPE_TAILLE"]),
        ("DESHERBAGE", ["EQUIPE_DESHERBAGE"]),
        ("ARROSAGE", ["EQUIPE_ARROSAGE"]),
        ("PLANTATION", ["EQUIPE_PLANTATION"]),
        ("TRAITEMENT", ["EQUIPE_TRAITEMENT"]),
        ("EVACUATION_DECHETS", ["CAMION_BENNE"]),
    ]

    op_id = 1
    for zone in range(1, n_zones + 1):
        precedente = None
        # Choisir un nom de zone
        nom_zone = random.choice(noms_zones)

        n_phases = random.randint(5, 7)
        phases_zone = random.sample(phases, n_phases)

        for phase_nom, types_poste_phase in phases_zone:
            type_poste = random.choice(types_poste_phase)
            instances_disponibles = [p["code_poste"] for p in postes if p["code_poste"].startswith(type_poste)]
            poste_choisi = random.choice(instances_disponibles)
            specs = types_postes[type_poste]
            duree = random.randint(specs["duree_min"], specs["duree_max"])

            code_op = f"{nom_zone}_{phase_nom}_{op_id:04d}"
            operations.append(
                {
                    "code_operation": code_op,
                    "duree_jours": duree,
                    "poste_id": poste_choisi,
                    "operation_precedente": precedente,
                }
            )

            precedente = code_op
            op_id += 1

            if op_id > n_operations:
                break

        if op_id > n_operations:
            break

    return {"operations": operations[:n_operations], "postes": postes}


def generer_education_planification_cours_large(n_operations: int = 100) -> dict:
    """Éducation - Planification de cours - grande échelle."""
    # Noms de cours/matières réalistes
    noms_cours = [
        "COURS_MATHS",
        "ALGO_AVANCE",
        "CHIMIE_ORGANIQUE",
        "PHYSIQUE_QUANTIQUE",
        "PROG_PYTHON",
        "BASE_DONNEES",
        "RESEAUX_TELECOM",
        "GENIE_LOGICIEL",
        "THERMODYNAMIQUE",
        "MECANIQUE_FLUIDES",
        "ELECTRONIQUE_ANALOGIQUE",
        "ANALYSE_NUMERIQUE",
        "INTELLIGENCE_ARTIFICIELLE",
        "SYSTEMES_EMBARQUES",
        "TRAITEMENT_SIGNAL",
        "AUTOMATIQUE",
        "RESISTANCE_MATERIAUX",
        "ELECTROMAGNETISME",
        "OPTIQUE_PHOTONIQUE",
        "CRYPTO_SECURITE",
        "COMPILATEURS",
        "SYSTEMES_EXPLOITATION",
        "CLOUD_COMPUTING",
        "DEVOPS",
    ]

    types_postes = {
        "SALLE_COURS_STANDARD": {"duree_min": 1, "duree_max": 2, "capacite": 25},
        "SALLE_TP_INFORMATIQUE": {"duree_min": 1, "duree_max": 3, "capacite": 10},
        "LABORATOIRE_CHIMIE": {"duree_min": 1, "duree_max": 4, "capacite": 6},
        "LABORATOIRE_PHYSIQUE": {"duree_min": 1, "duree_max": 4, "capacite": 6},
        "SALLE_CONFERENCE": {"duree_min": 1, "duree_max": 3, "capacite": 5},
        "ATELIER_PRATIQUE": {"duree_min": 1, "duree_max": 5, "capacite": 8},
        "BIBLIOTHEQUE": {"duree_min": 1, "duree_max": 2, "capacite": 12},
    }

    postes = []
    for type_poste, specs in types_postes.items():
        for i in range(1, specs["capacite"] + 1):
            postes.append({"code_poste": f"{type_poste}_{i}"})

    operations = []
    n_cours = n_operations // 5

    phases = [
        ("COURS_MAGISTRAL", ["SALLE_COURS_STANDARD", "SALLE_CONFERENCE"]),
        ("TP_INFORMATIQUE", ["SALLE_TP_INFORMATIQUE"]),
        ("TP_CHIMIE", ["LABORATOIRE_CHIMIE"]),
        ("TP_PHYSIQUE", ["LABORATOIRE_PHYSIQUE"]),
        ("ATELIER", ["ATELIER_PRATIQUE"]),
        ("RECHERCHE", ["BIBLIOTHEQUE"]),
    ]

    op_id = 1
    for cours in range(1, n_cours + 1):
        precedente = None
        # Choisir un nom de cours
        nom_cours = random.choice(noms_cours)

        n_phases = random.randint(3, 6)
        phases_cours = random.sample(phases, n_phases)

        for phase_nom, types_poste_phase in phases_cours:
            type_poste = random.choice(types_poste_phase)
            instances_disponibles = [p["code_poste"] for p in postes if p["code_poste"].startswith(type_poste)]
            poste_choisi = random.choice(instances_disponibles)
            specs = types_postes[type_poste]
            duree = random.randint(specs["duree_min"], specs["duree_max"])

            code_op = f"{nom_cours}_{phase_nom}_{op_id:04d}"
            operations.append(
                {
                    "code_operation": code_op,
                    "duree_jours": duree,
                    "poste_id": poste_choisi,
                    "operation_precedente": precedente,
                }
            )

            precedente = code_op
            op_id += 1

            if op_id > n_operations:
                break

        if op_id > n_operations:
            break

    return {"operations": operations[:n_operations], "postes": postes}


def sauvegarder_donnees(nom: str, data: dict, output_dir: Path) -> tuple[Path, Path, Path, Path]:
    """Sauvegarde les données en JSON (vocabulaire ERP, `adapters.erp_reference.translator`)
    et en CSV à 3 fichiers (`sauvegarder_csv`, `scripts/generer_donnees_depuis_config.py` —
    compatible `adapters.csv_import.traducteur.traduire`). `data` doit déjà être passé par
    `enrichir_avec_competences` (le CSV en a besoin, voir sa docstring)."""
    json_dir = output_dir / "json_erp"
    json_dir.mkdir(parents=True, exist_ok=True)
    json_path = json_dir / f"{nom}.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    chemin_taches, chemin_ressources, chemin_contraintes = sauvegarder_csv(
        data, nom, repertoire=output_dir / "csv"
    )

    return json_path, chemin_taches, chemin_ressources, chemin_contraintes


def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Genere des jeux de donnees brutes a grande echelle (100+ operations)"
    )
    parser.add_argument(
        "--taille",
        type=int,
        default=100,
        help="Nombre d'operations par jeu de donnees (defaut: 100)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Repertoire de sortie (defaut: data/donnees_brutes_large)",
    )

    args = parser.parse_args()

    # Déterminer le répertoire de sortie
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = Path(__file__).parent.parent / "data" / "donnees_brutes_large"

    output_dir.mkdir(parents=True, exist_ok=True)

    print("Generation de jeux de donnees a grande echelle")
    print(f"Taille cible: {args.taille} operations par fichier")
    print(f"Repertoire de sortie: {output_dir}")
    print()

    # Générer les jeux de données
    datasets = [
        ("atelier_mecanique_large", generer_atelier_mecanique_large),
        ("assemblage_electronique_large", generer_assemblage_electronique_large),
        ("production_agroalimentaire_large", generer_agroalimentaire_large),
        ("hopital_bloc_operatoire_large", generer_hopital_bloc_operatoire_large),
        ("logistique_transport_large", generer_logistique_transport_large),
        ("restauration_collective_large", generer_restauration_collective_large),
        ("services_nettoyage_large", generer_services_nettoyage_large),
        ("gestion_espaces_verts_large", generer_gestion_espaces_verts_large),
        ("education_planification_cours_large", generer_education_planification_cours_large),
    ]

    for nom, generateur in datasets:
        print(f"[GENERATION] {nom}...")
        data = enrichir_avec_competences(generateur(args.taille))

        json_path, chemin_taches, chemin_ressources, chemin_contraintes = sauvegarder_donnees(
            nom, data, output_dir
        )

        print(f"  Operations: {len(data['operations'])}")
        print(f"  Postes: {len(data['postes'])}")
        print(f"  JSON: {json_path.relative_to(output_dir.parent)}")
        print(f"  CSV: {chemin_taches.relative_to(output_dir.parent)}")
        print(f"       {chemin_ressources.relative_to(output_dir.parent)}")
        print(f"       {chemin_contraintes.relative_to(output_dir.parent)}")
        print()

    # Créer un README
    readme_path = output_dir / "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(f"""# Données Brutes à Grande Échelle

Ce répertoire contient des jeux de données volumineux (~{args.taille} opérations par fichier)
pour tester la scalabilité de la pipeline PRISME.

## Jeux de Données

- **atelier_mecanique_large** : {args.taille}+ opérations, fabrication métallique
- **assemblage_electronique_large** : {args.taille}+ opérations, assemblage PCB
- **production_agroalimentaire_large** : {args.taille}+ opérations, transformation alimentaire
- **hopital_bloc_operatoire_large** : {args.taille}+ opérations, planification hospitalière
- **logistique_transport_large** : {args.taille}+ opérations, logistique et transport
- **restauration_collective_large** : {args.taille}+ opérations, restauration collective
- **services_nettoyage_large** : {args.taille}+ opérations, services de nettoyage
- **gestion_espaces_verts_large** : {args.taille}+ opérations, gestion d'espaces verts
- **education_planification_cours_large** : {args.taille}+ opérations, planification de cours

## Utilisation

### Transformation en instances TRCO

```bash
python -m scripts.transformer_donnees_brutes --input-dir data/donnees_brutes_large/json_erp
```

### Régénération

```bash
# Taille par défaut (100 opérations)
python -m scripts.generer_donnees_brutes_grande_echelle

# Taille personnalisée
python -m scripts.generer_donnees_brutes_grande_echelle --taille 150
python -m scripts.generer_donnees_brutes_grande_echelle --taille 200
```

## Caractéristiques

- Opérations organisées en lots de production réalistes
- Précédences entre opérations d'un même lot
- Multiples instances de chaque type de poste (haute capacité)
- Durées variables selon le type de poste
- Format compatible avec l'adaptateur ERP de référence

## Note

Ces instances volumineuses permettent de :
- Tester les performances du générateur LLM sur de grandes instances
- Valider la scalabilité du solveur
- Évaluer les temps d'exécution dans le sandbox
- Benchmarker la cascade de validation

Génération : {args.taille} opérations/fichier
Date : 2026-07-23
""")

    print(f"[OK] README cree: {readme_path}")
    print()
    print(f"Generation terminee ! {len(datasets)} jeux de donnees crees")
    print(f"Repertoire: {output_dir}")


if __name__ == "__main__":
    main()
