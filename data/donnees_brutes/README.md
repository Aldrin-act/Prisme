# Données Brutes - Sources ERP Simulées

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
│   └── imprimerie.json
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
