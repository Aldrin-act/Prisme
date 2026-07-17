"""Traduction ERP → T-R-C-O (§5.4) : la couche anti-corruption. PRISME ne se
connecte jamais directement aux bases de production des clients — chaque
ERP a son adaptateur, qui traduit son format propriétaire vers le canonique.

Voir `mapping/regles.md` pour la table de correspondance champ par champ.
"""

from __future__ import annotations

from dsl.schema import (
    CompatibiliteRessourceTache,
    Contrainte,
    InstanceTRCO,
    MinimiserMakespan,
    Precedence,
    Ressource,
    Tache,
)

from .schema_erp import PayloadERP


def traduire(payload: PayloadERP) -> InstanceTRCO:
    """Traduit un payload de l'ERP de référence en instance T-R-C-O canonique."""
    taches = [Tache(id=operation.code_operation) for operation in payload.operations]
    ressources = [Ressource(id=poste.code_poste) for poste in payload.postes]

    contraintes: list[Contrainte] = []
    for operation in payload.operations:
        contraintes.append(
            CompatibiliteRessourceTache(
                tache=operation.code_operation, ressource=operation.poste_id, duree=operation.duree_minutes
            )
        )
        if operation.operation_precedente is not None:
            contraintes.append(Precedence(avant=operation.operation_precedente, apres=operation.code_operation))

    return InstanceTRCO(
        taches=taches,
        ressources=ressources,
        contraintes=contraintes,
        objectifs=[MinimiserMakespan()],
    )
