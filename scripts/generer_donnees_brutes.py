"""Génération de jeux de données brutes simulant des sources ERP réelles.

Ces données sont au format "brut" tel qu'elles sortiraient d'un système ERP
ou d'une saisie manuelle, AVANT leur transformation en instances TRCO.

Formats générés:
- JSON (format ERP de référence)
- CSV (import simple)
- Excel (gabarit structuré)

Usage:
    python -m scripts.generer_donnees_brutes
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


def creer_donnees_atelier_mecanique_json() -> dict:
    """Atelier de fabrication mécanique - format ERP JSON."""
    return {
        "operations": [
            {
                "code_operation": "DECOUP_001",
                "duree_jours": 1,
                "poste_id": "DECOUPEUSE_LASER",
                "operation_precedente": None,
            },
            {
                "code_operation": "PERCAGE_001",
                "duree_jours": 1,
                "poste_id": "PERCEUSE_CNC",
                "operation_precedente": "DECOUP_001",
            },
            {
                "code_operation": "PLIAGE_001",
                "duree_jours": 1,
                "poste_id": "PRESSE_PLIAGE",
                "operation_precedente": "PERCAGE_001",
            },
            {
                "code_operation": "SOUDURE_001",
                "duree_jours": 2,
                "poste_id": "POSTE_SOUDURE_1",
                "operation_precedente": "PLIAGE_001",
            },
            {
                "code_operation": "SOUDURE_002",
                "duree_jours": 2,
                "poste_id": "POSTE_SOUDURE_2",
                "operation_precedente": "PLIAGE_001",
            },
            {
                "code_operation": "PEINTURE_001",
                "duree_jours": 1,
                "poste_id": "CABINE_PEINTURE",
                "operation_precedente": "SOUDURE_001",
            },
            {
                "code_operation": "ASSEMBLAGE_FINAL",
                "duree_jours": 2,
                "poste_id": "POSTE_ASSEMBLAGE",
                "operation_precedente": "PEINTURE_001",
            },
            {
                "code_operation": "CONTROLE_QUALITE",
                "duree_jours": 1,
                "poste_id": "POSTE_CONTROLE",
                "operation_precedente": "ASSEMBLAGE_FINAL",
            },
        ],
        "postes": [
            {"code_poste": "DECOUPEUSE_LASER"},
            {"code_poste": "PERCEUSE_CNC"},
            {"code_poste": "PRESSE_PLIAGE"},
            {"code_poste": "POSTE_SOUDURE_1"},
            {"code_poste": "POSTE_SOUDURE_2"},
            {"code_poste": "CABINE_PEINTURE"},
            {"code_poste": "POSTE_ASSEMBLAGE"},
            {"code_poste": "POSTE_CONTROLE"},
        ],
    }


def creer_donnees_electronique_json() -> dict:
    """Atelier d'assemblage électronique - format ERP JSON."""
    return {
        "operations": [
            {
                "code_operation": "PREP_PCB",
                "duree_jours": 1,
                "poste_id": "STATION_PREP",
                "operation_precedente": None,
            },
            {
                "code_operation": "POSE_CMS_FACE_A",
                "duree_jours": 2,
                "poste_id": "MACHINE_PICK_PLACE_1",
                "operation_precedente": "PREP_PCB",
            },
            {
                "code_operation": "SOUDURE_REFUSION_A",
                "duree_jours": 1,
                "poste_id": "FOUR_REFUSION",
                "operation_precedente": "POSE_CMS_FACE_A",
            },
            {
                "code_operation": "INSPECTION_AOI_A",
                "duree_jours": 1,
                "poste_id": "AOI_AUTOMATIQUE",
                "operation_precedente": "SOUDURE_REFUSION_A",
            },
            {
                "code_operation": "POSE_CMS_FACE_B",
                "duree_jours": 2,
                "poste_id": "MACHINE_PICK_PLACE_2",
                "operation_precedente": "INSPECTION_AOI_A",
            },
            {
                "code_operation": "SOUDURE_REFUSION_B",
                "duree_jours": 1,
                "poste_id": "FOUR_REFUSION",
                "operation_precedente": "POSE_CMS_FACE_B",
            },
            {
                "code_operation": "SOUDURE_MANUELLE",
                "duree_jours": 2,
                "poste_id": "POSTE_SOUDURE_MANUEL",
                "operation_precedente": "SOUDURE_REFUSION_B",
            },
            {
                "code_operation": "TEST_FONCTIONNEL",
                "duree_jours": 1,
                "poste_id": "BANC_TEST",
                "operation_precedente": "SOUDURE_MANUELLE",
            },
            {
                "code_operation": "CONFORMAL_COATING",
                "duree_jours": 1,
                "poste_id": "ROBOT_COATING",
                "operation_precedente": "TEST_FONCTIONNEL",
            },
            {
                "code_operation": "CONTROLE_FINAL",
                "duree_jours": 1,
                "poste_id": "POSTE_CONTROLE_VISUEL",
                "operation_precedente": "CONFORMAL_COATING",
            },
        ],
        "postes": [
            {"code_poste": "STATION_PREP"},
            {"code_poste": "MACHINE_PICK_PLACE_1"},
            {"code_poste": "MACHINE_PICK_PLACE_2"},
            {"code_poste": "FOUR_REFUSION"},
            {"code_poste": "AOI_AUTOMATIQUE"},
            {"code_poste": "POSTE_SOUDURE_MANUEL"},
            {"code_poste": "BANC_TEST"},
            {"code_poste": "ROBOT_COATING"},
            {"code_poste": "POSTE_CONTROLE_VISUEL"},
        ],
    }


def creer_donnees_agroalimentaire_json() -> dict:
    """Production agro-alimentaire - format ERP JSON."""
    return {
        "operations": [
            {
                "code_operation": "RECEPTION_MP",
                "duree_jours": 1,
                "poste_id": "QUAI_RECEPTION",
                "operation_precedente": None,
            },
            {
                "code_operation": "LAVAGE_LEGUMES",
                "duree_jours": 1,
                "poste_id": "TUNNEL_LAVAGE",
                "operation_precedente": "RECEPTION_MP",
            },
            {
                "code_operation": "EPLUCHAGE",
                "duree_jours": 1,
                "poste_id": "LIGNE_EPLUCHAGE",
                "operation_precedente": "LAVAGE_LEGUMES",
            },
            {
                "code_operation": "DECOUPE",
                "duree_jours": 1,
                "poste_id": "ROBOT_DECOUPE",
                "operation_precedente": "EPLUCHAGE",
            },
            {
                "code_operation": "CUISSON",
                "duree_jours": 3,
                "poste_id": "AUTOCLAVE_1",
                "operation_precedente": "DECOUPE",
            },
            {
                "code_operation": "REFROIDISSEMENT",
                "duree_jours": 2,
                "poste_id": "TUNNEL_REFROIDISSEMENT",
                "operation_precedente": "CUISSON",
            },
            {
                "code_operation": "CONDITIONNEMENT",
                "duree_jours": 1,
                "poste_id": "LIGNE_CONDITIONNEMENT",
                "operation_precedente": "REFROIDISSEMENT",
            },
            {
                "code_operation": "ETIQUETAGE",
                "duree_jours": 1,
                "poste_id": "ETIQUETEUSE_AUTO",
                "operation_precedente": "CONDITIONNEMENT",
            },
            {
                "code_operation": "PALETTISATION",
                "duree_jours": 1,
                "poste_id": "ROBOT_PALETTISEUR",
                "operation_precedente": "ETIQUETAGE",
            },
        ],
        "postes": [
            {"code_poste": "QUAI_RECEPTION"},
            {"code_poste": "TUNNEL_LAVAGE"},
            {"code_poste": "LIGNE_EPLUCHAGE"},
            {"code_poste": "ROBOT_DECOUPE"},
            {"code_poste": "AUTOCLAVE_1"},
            {"code_poste": "TUNNEL_REFROIDISSEMENT"},
            {"code_poste": "LIGNE_CONDITIONNEMENT"},
            {"code_poste": "ETIQUETEUSE_AUTO"},
            {"code_poste": "ROBOT_PALETTISEUR"},
        ],
    }


def creer_donnees_maintenance_json() -> dict:
    """Planning de maintenance industrielle - format ERP JSON."""
    return {
        "operations": [
            {
                "code_operation": "DIAG_PANNE_001",
                "duree_jours": 1,
                "poste_id": "EQUIPE_DIAG",
                "operation_precedente": None,
            },
            {
                "code_operation": "CMD_PIECES_001",
                "duree_jours": 3,
                "poste_id": "SERVICE_ACHATS",
                "operation_precedente": "DIAG_PANNE_001",
            },
            {
                "code_operation": "DEMONTAGE_001",
                "duree_jours": 1,
                "poste_id": "EQUIPE_MECA",
                "operation_precedente": "CMD_PIECES_001",
            },
            {
                "code_operation": "REPARATION_001",
                "duree_jours": 2,
                "poste_id": "ATELIER_REPARATION",
                "operation_precedente": "DEMONTAGE_001",
            },
            {
                "code_operation": "REMONTAGE_001",
                "duree_jours": 1,
                "poste_id": "EQUIPE_MECA",
                "operation_precedente": "REPARATION_001",
            },
            {
                "code_operation": "TEST_MARCHE_001",
                "duree_jours": 1,
                "poste_id": "EQUIPE_TEST",
                "operation_precedente": "REMONTAGE_001",
            },
            {
                "code_operation": "NETTOYAGE_FINAL",
                "duree_jours": 1,
                "poste_id": "EQUIPE_MECA",
                "operation_precedente": "TEST_MARCHE_001",
            },
        ],
        "postes": [
            {"code_poste": "EQUIPE_DIAG"},
            {"code_poste": "SERVICE_ACHATS"},
            {"code_poste": "EQUIPE_MECA"},
            {"code_poste": "ATELIER_REPARATION"},
            {"code_poste": "EQUIPE_TEST"},
        ],
    }


def creer_donnees_imprimerie_json() -> dict:
    """Atelier d'imprimerie - format ERP JSON."""
    return {
        "operations": [
            {
                "code_operation": "PRE_PRESSE",
                "duree_jours": 1,
                "poste_id": "STATION_PAO",
                "operation_precedente": None,
            },
            {
                "code_operation": "CALAGE_PRESSE",
                "duree_jours": 1,
                "poste_id": "PRESSE_OFFSET_1",
                "operation_precedente": "PRE_PRESSE",
            },
            {
                "code_operation": "IMPRESSION_RECTO",
                "duree_jours": 2,
                "poste_id": "PRESSE_OFFSET_1",
                "operation_precedente": "CALAGE_PRESSE",
            },
            {
                "code_operation": "SECHAGE_RECTO",
                "duree_jours": 1,
                "poste_id": "TUNNEL_SECHAGE",
                "operation_precedente": "IMPRESSION_RECTO",
            },
            {
                "code_operation": "IMPRESSION_VERSO",
                "duree_jours": 2,
                "poste_id": "PRESSE_OFFSET_2",
                "operation_precedente": "SECHAGE_RECTO",
            },
            {
                "code_operation": "SECHAGE_VERSO",
                "duree_jours": 1,
                "poste_id": "TUNNEL_SECHAGE",
                "operation_precedente": "IMPRESSION_VERSO",
            },
            {
                "code_operation": "VERNIS_SELECTIF",
                "duree_jours": 1,
                "poste_id": "MACHINE_VERNIS",
                "operation_precedente": "SECHAGE_VERSO",
            },
            {
                "code_operation": "DECOUPE_PLIAGE",
                "duree_jours": 1,
                "poste_id": "PLIEUSE_COLLEUSE",
                "operation_precedente": "VERNIS_SELECTIF",
            },
            {
                "code_operation": "FINITION",
                "duree_jours": 1,
                "poste_id": "POSTE_FINITION",
                "operation_precedente": "DECOUPE_PLIAGE",
            },
        ],
        "postes": [
            {"code_poste": "STATION_PAO"},
            {"code_poste": "PRESSE_OFFSET_1"},
            {"code_poste": "PRESSE_OFFSET_2"},
            {"code_poste": "TUNNEL_SECHAGE"},
            {"code_poste": "MACHINE_VERNIS"},
            {"code_poste": "PLIEUSE_COLLEUSE"},
            {"code_poste": "POSTE_FINITION"},
        ],
    }


def creer_donnees_centre_appels_json() -> dict:
    """Centre d'appels / support client - format ERP JSON.

    Seul secteur à exercer `competence_requise`/`competences` (OperationERP/
    PosteERP) — les 5 autres n'en ont pas besoin pour rester représentatifs
    d'un ERP legacy pauvre (§5.4). Un poste par compétence ici (pas plusieurs
    opérateurs par poste) : suffisant pour que la traduction produise une
    `CompetenceRequise` par opération qualifiée, sans complexifier le reste.
    """
    return {
        "operations": [
            {
                "code_operation": "RECEPTION_APPEL",
                "duree_jours": 1,
                "poste_id": "POSTE_TELEPHONIQUE_N1",
                "operation_precedente": None,
                "competence_requise": "telephonique_n1",
            },
            {
                "code_operation": "QUALIFICATION_DEMANDE",
                "duree_jours": 1,
                "poste_id": "POSTE_TELEPHONIQUE_N1",
                "operation_precedente": "RECEPTION_APPEL",
                "competence_requise": "telephonique_n1",
            },
            {
                "code_operation": "CREATION_TICKET",
                "duree_jours": 1,
                "poste_id": "SYSTEME_CRM",
                "operation_precedente": "QUALIFICATION_DEMANDE",
                "competence_requise": "systeme_crm",
            },
            {
                "code_operation": "ESCALADE_N2",
                "duree_jours": 1,
                "poste_id": "POSTE_TELEPHONIQUE_N2",
                "operation_precedente": "CREATION_TICKET",
                "competence_requise": "telephonique_n2",
            },
            {
                "code_operation": "INVESTIGATION_TECHNIQUE",
                "duree_jours": 2,
                "poste_id": "POSTE_SUPPORT_TECHNIQUE",
                "operation_precedente": "ESCALADE_N2",
                "competence_requise": "support_technique",
            },
            {
                "code_operation": "RESOLUTION",
                "duree_jours": 1,
                "poste_id": "POSTE_SUPPORT_TECHNIQUE",
                "operation_precedente": "INVESTIGATION_TECHNIQUE",
                "competence_requise": "support_technique",
            },
            {
                "code_operation": "RAPPEL_CLIENT",
                "duree_jours": 1,
                "poste_id": "POSTE_TELEPHONIQUE_N2",
                "operation_precedente": "RESOLUTION",
                "competence_requise": "telephonique_n2",
            },
            {
                "code_operation": "CLOTURE_TICKET",
                "duree_jours": 1,
                "poste_id": "SYSTEME_CRM",
                "operation_precedente": "RAPPEL_CLIENT",
                "competence_requise": "systeme_crm",
            },
        ],
        "postes": [
            {"code_poste": "POSTE_TELEPHONIQUE_N1", "competences": ["telephonique_n1"]},
            {"code_poste": "POSTE_TELEPHONIQUE_N2", "competences": ["telephonique_n2"]},
            {"code_poste": "SYSTEME_CRM", "competences": ["systeme_crm"]},
            {"code_poste": "POSTE_SUPPORT_TECHNIQUE", "competences": ["support_technique"]},
        ],
    }


def creer_donnees_csv_simple(nom_fichier: str, operations: list[dict], postes: list[dict]) -> None:
    """Crée des fichiers CSV simples pour operations et postes.

    `extrasaction="ignore"` : `competence_requise`/`competences` (secteur
    centre_appels) n'ont pas de colonne CSV dédiée — cette voie d'export
    reste volontairement au format historique à 4/1 colonnes, le JSON ERP
    est le format de référence pour ce secteur (voir `mapping/regles.md`).
    """
    output_dir = Path(__file__).parent.parent / "data" / "donnees_brutes" / "csv"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Fichier opérations
    operations_path = output_dir / f"{nom_fichier}_operations.csv"
    with open(operations_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["code_operation", "duree_jours", "poste_id", "operation_precedente"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(operations)

    # Fichier postes
    postes_path = output_dir / f"{nom_fichier}_postes.csv"
    with open(postes_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["code_poste"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(postes)

    return operations_path, postes_path


def generer_toutes_les_donnees() -> None:
    """Génère tous les jeux de données brutes."""
    output_dir = Path(__file__).parent.parent / "data" / "donnees_brutes"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Créer sous-répertoires
    json_dir = output_dir / "json_erp"
    csv_dir = output_dir / "csv"
    json_dir.mkdir(exist_ok=True)
    csv_dir.mkdir(exist_ok=True)

    # Jeux de données
    datasets = {
        "atelier_mecanique": creer_donnees_atelier_mecanique_json(),
        "assemblage_electronique": creer_donnees_electronique_json(),
        "production_agroalimentaire": creer_donnees_agroalimentaire_json(),
        "maintenance_industrielle": creer_donnees_maintenance_json(),
        "imprimerie": creer_donnees_imprimerie_json(),
        "centre_appels": creer_donnees_centre_appels_json(),
    }

    print(f"Generation de {len(datasets)} jeux de donnees brutes...\n")

    for nom, data in datasets.items():
        # Format JSON (ERP)
        json_path = json_dir / f"{nom}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"[OK] {nom}")
        print(f"  - JSON ERP: {json_path.relative_to(output_dir.parent)}")
        print(f"  - Operations: {len(data['operations'])}")
        print(f"  - Postes: {len(data['postes'])}")

        # Format CSV
        ops_path, postes_path = creer_donnees_csv_simple(nom, data["operations"], data["postes"])
        print(f"  - CSV Operations: {ops_path.relative_to(output_dir.parent)}")
        print(f"  - CSV Postes: {postes_path.relative_to(output_dir.parent)}")
        print()

    # Créer un README
    readme_path = output_dir / "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(
            """# Données Brutes - Sources ERP Simulées

Ce répertoire contient des jeux de données brutes simulant des exports de différents ERP,
AVANT leur transformation en instances TRCO.

## Structure

```
donnees_brutes/
├── json_erp/          # Format JSON ERP de référence
│   ├── atelier_mecanique.json
│   ├── assemblage_electronique.json
│   ├── production_agroalimentaire.json
│   ├── maintenance_industrielle.json
│   ├── imprimerie.json
│   └── centre_appels.json
├── csv/               # Format CSV simple
│   ├── atelier_mecanique_operations.csv
│   ├── atelier_mecanique_postes.csv
│   └── ... (paires pour chaque jeu de données)
└── README.md
```

## Jeux de Données Disponibles

### 1. Atelier Mécanique
- **Secteur**: Fabrication métallique
- **Operations**: 8 (découpe, perçage, pliage, soudure, peinture...)
- **Postes**: 8 (découpeuse laser, CNC, presse, cabine peinture...)
- **Particularité**: Chaîne de production linéaire avec alternatives de soudure

### 2. Assemblage Électronique
- **Secteur**: Fabrication de cartes électroniques (PCB)
- **Opérations**: 10 (pose CMS, soudure refusion, AOI, tests...)
- **Postes**: 9 (pick&place, four, AOI, banc test...)
- **Particularité**: Double face PCB, inspection automatique

### 3. Production Agro-alimentaire
- **Secteur**: Transformation alimentaire
- **Opérations**: 9 (réception, lavage, cuisson, conditionnement...)
- **Postes**: 9 (tunnel lavage, autoclave, étiqueteuse...)
- **Particularité**: Longues durées (cuisson 3 jours), séquence stricte

### 4. Maintenance Industrielle
- **Secteur**: Gestion de pannes/réparations
- **Opérations**: 7 (diagnostic, commande pièces, réparation...)
- **Postes**: 5 (équipes diagnostique, mécanique, tests...)
- **Particularité**: Dépendances avec service achats

### 5. Imprimerie
- **Secteur**: Impression offset
- **Opérations**: 9 (pré-presse, impression, vernissage...)
- **Postes**: 7 (presses offset, tunnel séchage, plieuse...)
- **Particularité**: Impression recto/verso, ressource partagée (tunnel séchage)

### 6. Centre d'Appels
- **Secteur**: Support client / helpdesk
- **Opérations**: 8 (réception d'appel, qualification, escalade N2, résolution...)
- **Postes**: 4 (téléphonique N1/N2, système CRM, support technique)
- **Particularité**: Seul secteur avec `competence_requise`/`competences` — chaque
  opération exige une compétence précise, un seul poste par compétence

## Formats

### Format JSON (ERP de référence)

```json
{
  "operations": [
    {
      "code_operation": "OP_001",
      "duree_jours": 2,
      "poste_id": "POSTE_A",
      "operation_precedente": null  // ou "OP_000"
    }
  ],
  "postes": [
    {"code_poste": "POSTE_A"}
  ]
}
```

### Format CSV

**Fichier `*_operations.csv`**:
```csv
code_operation,duree_jours,poste_id,operation_precedente
OP_001,2,POSTE_A,
OP_002,1,POSTE_B,OP_001
```

**Fichier `*_postes.csv`**:
```csv
code_poste
POSTE_A
POSTE_B
```

## Transformation en Instances TRCO

Pour transformer ces données brutes en instances TRCO :

```python
# Format JSON ERP
from adapters.erp_reference.schema_erp import PayloadERP
from adapters.erp_reference.translator import traduire
import json

with open("donnees_brutes/json_erp/atelier_mecanique.json") as f:
    payload_erp = PayloadERP(**json.load(f))

instance_trco = traduire(payload_erp)
```

```bash
# Utiliser le script de transformation
python -m scripts.transformer_donnees_brutes --input data/donnees_brutes/json_erp/atelier_mecanique.json
```

## Régénération

Pour régénérer tous les jeux de données :

```bash
python -m scripts.generer_donnees_brutes
```

## Utilisation dans la Pipeline

Ces données brutes sont le point de départ du workflow PRISME :

1. **Données brutes** (ce répertoire) ← Source ERP
2. **Adaptateur** (transformation) ← `adapters/erp_reference/translator.py`
3. **Instance TRCO** (format canonique) ← Validation DSL
4. **Génération solveur** ← LLM
5. **Exécution** ← Sandbox

## Notes

- Ces données simulent des exports ERP réels mais restent simplifiées
- Le format "ERP de référence" est volontairement basique (1 poste par opération)
- Pour des cas plus complexes (FJSP avec choix de ressources), utiliser directement
  le format TRCO ou le gabarit Excel
"""
        )

    print(f"[OK] {readme_path.name}")
    print(f"\nGeneration terminee ! {len(datasets)} jeux de donnees crees")
    print(f"Repertoire: {output_dir}")


if __name__ == "__main__":
    generer_toutes_les_donnees()
