"""Point d'entrée unique pour valider un payload T-R-C-O brut (§6.7).

Le schéma (`dsl/schema/`) porte déjà toutes les règles — types, contraintes de
champs, cohérence inter-axes. Ce module ne fait qu'exposer le point d'entrée
que l'API (`api/input_validation/`) et les adaptateurs ERP appelleront : un
payload reçu (JSON brut ou dict déjà désérialisé) entre, une `InstanceTRCO`
valide sort, ou une `pydantic.ValidationError` diagnostique est levée.
"""

from __future__ import annotations

from typing import Any

from dsl.schema import InstanceTRCO


def charger_instance(payload: str | bytes | dict[str, Any]) -> InstanceTRCO:
    """Valide `payload` et construit l'instance T-R-C-O correspondante."""
    if isinstance(payload, (str, bytes)):
        return InstanceTRCO.model_validate_json(payload)
    return InstanceTRCO.model_validate(payload)
