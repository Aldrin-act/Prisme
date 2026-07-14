"""Démo bout en bout de l'Étape 8 (§8) : un format propriétaire ERP simulé
entre par l'adaptateur, ressort en planning JSON via l'API, et le code du
solveur est exportable via le canal d'audit.

Nécessite Docker (le sandbox exécute réellement le solveur figé, §7) et
suppose l'image construite : voir `sandbox/README.md`.

Usage, depuis la racine du dépôt : python -m scripts.demo_bout_en_bout
(`python scripts/demo_bout_en_bout.py` échouerait : ce module importe
`scripts.enregistrer_solveur_reference`, qui n'est résoluble que si la
racine du dépôt est sur `sys.path` — ce que `-m` garantit, pas l'exécution
directe d'un fichier.)
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from adapters.erp_reference import OperationERP, PayloadERP, PosteERP, traduire
from api.app import app
from api.dependencies import obtenir_registre
from scripts.enregistrer_solveur_reference import enregistrer

CLIENT_ID = "demo"


def _payload_erp_simule() -> PayloadERP:
    """Un atelier à deux postes, deux opérations liées — le format brut tel
    qu'un ERP legacy le fournirait (voir `adapters/erp_reference/mapping/regles.md`)."""
    return PayloadERP(
        operations=[
            OperationERP(code_operation="OP10", duree_minutes=30, poste_id="POSTE_A"),
            OperationERP(
                code_operation="OP20",
                duree_minutes=45,
                poste_id="POSTE_B",
                operation_precedente="OP10",
            ),
        ],
        postes=[PosteERP(code_poste="POSTE_A"), PosteERP(code_poste="POSTE_B")],
    )


def main() -> None:
    registre = obtenir_registre()
    print("1. Enregistrement du solveur de référence dans le store (§7)...")
    id_solveur = enregistrer(registre, client_id=CLIENT_ID)
    print(f"   -> id_solveur = {id_solveur}")

    print("\n2. Traduction ERP -> T-R-C-O (adaptateur, §5.4)...")
    payload_erp = _payload_erp_simule()
    instance = traduire(payload_erp)
    print(f"   -> {len(instance.taches)} tâches, {len(instance.ressources)} ressources")

    client = TestClient(app)

    print("\n3. POST /ingestion (garde-fou amont, §6.7)...")
    reponse = client.post(f"/ingestion/{CLIENT_ID}", json=instance.model_dump(mode="json"))
    reponse.raise_for_status()
    instance_id = reponse.json()["instance_id"]
    print(f"   -> instance_id = {instance_id}")

    print("\n4. POST /execution (bac à sable + store, §7)...")
    reponse = client.post(f"/execution/{instance_id}", params={"client_id": CLIENT_ID})
    reponse.raise_for_status()
    corps_execution = reponse.json()
    execution_id = corps_execution["execution_id"]
    print(f"   -> execution_id = {execution_id}, reussi = {corps_execution['reussi']}")

    print("\n5. GET /planning (canal opérationnel)...")
    reponse = client.get(f"/planning/{execution_id}")
    reponse.raise_for_status()
    print(json.dumps(reponse.json(), indent=2, ensure_ascii=False))

    print("\n6. GET /audit (canal d'audit, transparence)...")
    reponse = client.get(f"/audit/{execution_id}")
    reponse.raise_for_status()
    print(f"   -> {len(reponse.json()['code_source'])} caractères de code source disponibles")


if __name__ == "__main__":
    main()
