"""Traduction ERP → T-R-C-O (§5.4) : la couche anti-corruption. PRISME ne se
connecte jamais directement aux bases de production des clients — chaque
ERP a son adaptateur, qui traduit son format propriétaire vers le canonique.

Voir `mapping/regles.md` pour la table de correspondance champ par champ.
"""

from __future__ import annotations

from dsl.schema import (
    CompatibiliteRessourceTache,
    CompetenceRequise,
    Contrainte,
    InstanceTRCO,
    MinimiserMakespan,
    Precedence,
    Ressource,
    Tache,
)

from .schema_erp import OperationERP, PayloadERP

_DUREE_MINIMALE_JOURS = 1  # CompatibiliteRessourceTache.duree exige > 0 ; jamais 0 si les dates coïncident


def duree_jours_pour(operation: OperationERP) -> int:
    """Résout la durée d'une opération vers le référentiel jours relatifs du DSL — directement si
    `duree_jours` est déclaré, sinon par différence calendaire `date_fin - date_debut` (les deux
    modes sont mutuellement exclusifs, déjà vérifié par `OperationERP`, §5.4). Même motif que
    `adapters/greensig/translator.py::duree_jours_pour` : la conversion reste dans l'adaptateur,
    jamais une notion que le DSL connaît."""
    if operation.duree_jours is not None:
        return operation.duree_jours
    assert operation.date_debut is not None and operation.date_fin is not None
    return max((operation.date_fin - operation.date_debut).days, _DUREE_MINIMALE_JOURS)


def traduire(payload: PayloadERP) -> InstanceTRCO:
    """Traduit un payload de l'ERP de référence en instance T-R-C-O canonique."""
    taches = [Tache(id=operation.code_operation) for operation in payload.operations]
    ressources = [Ressource(id=poste.code_poste, competences=poste.competences) for poste in payload.postes]

    contraintes: list[Contrainte] = []
    for operation in payload.operations:
        contraintes.append(
            CompatibiliteRessourceTache(
                tache=operation.code_operation, ressource=operation.poste_id, duree=duree_jours_pour(operation)
            )
        )
        if operation.operation_precedente is not None:
            contraintes.append(Precedence(avant=operation.operation_precedente, apres=operation.code_operation))
        if operation.competence_requise is not None:
            contraintes.append(
                CompetenceRequise(tache=operation.code_operation, competence=operation.competence_requise)
            )

    return InstanceTRCO(
        taches=taches,
        ressources=ressources,
        contraintes=contraintes,
        objectifs=[MinimiserMakespan()],
    )
