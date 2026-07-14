"""Instance T-R-C-O complète : le payload canonique échangé avec les ERP (§4, §5.4).

Agrège les quatre axes et applique le garde-fou amont (§6.7) : identifiants
uniques par axe, toute contrainte ne référence que des tâches ou ressources
réellement déclarées dans l'instance, et toute tâche est couverte par au
moins une contrainte `CompatibiliteMachineTache` (la durée, désormais propre
à chaque couple tâche-ressource, n'existe que là — une tâche sans aucune
compatibilité déclarée n'aurait donc aucune durée connue). Un payload qui
échoue cette validation est rejeté avant d'atteindre le solveur.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contraintes import CompatibiliteMachineTache, Contrainte, Precedence
from .objectifs import MinimiserMakespan
from .ressources import Ressource
from .taches import Tache


class InstanceTRCO(BaseModel):
    """Un payload T-R-C-O : une instance complète à planifier."""

    model_config = ConfigDict(extra="forbid")

    taches: list[Tache] = Field(min_length=1)
    ressources: list[Ressource] = Field(min_length=1)
    contraintes: list[Contrainte] = Field(default_factory=list)
    objectifs: list[MinimiserMakespan] = Field(min_length=1)

    @model_validator(mode="after")
    def _identifiants_uniques_par_axe(self) -> InstanceTRCO:
        ids_taches = [t.id for t in self.taches]
        if len(ids_taches) != len(set(ids_taches)):
            raise ValueError("identifiants de tâches dupliqués")

        ids_ressources = [r.id for r in self.ressources]
        if len(ids_ressources) != len(set(ids_ressources)):
            raise ValueError("identifiants de ressources dupliqués")

        return self

    @model_validator(mode="after")
    def _contraintes_referencent_des_entites_declarees(self) -> InstanceTRCO:
        ids_taches = {t.id for t in self.taches}
        ids_ressources = {r.id for r in self.ressources}

        for contrainte in self.contraintes:
            if isinstance(contrainte, Precedence):
                for id_tache in (contrainte.avant, contrainte.apres):
                    if id_tache not in ids_taches:
                        raise ValueError(f"précédence référence une tâche inconnue : {id_tache!r}")
            elif isinstance(contrainte, CompatibiliteMachineTache):
                if contrainte.tache not in ids_taches:
                    raise ValueError(f"compatibilité référence une tâche inconnue : {contrainte.tache!r}")
                if contrainte.ressource not in ids_ressources:
                    raise ValueError(f"compatibilité référence une ressource inconnue : {contrainte.ressource!r}")

        return self

    @model_validator(mode="after")
    def _chaque_tache_a_au_moins_une_ressource_compatible(self) -> InstanceTRCO:
        ids_avec_compatibilite = {c.tache for c in self.contraintes if isinstance(c, CompatibiliteMachineTache)}
        ids_sans_compatibilite = sorted(t.id for t in self.taches if t.id not in ids_avec_compatibilite)
        if ids_sans_compatibilite:
            raise ValueError(
                f"tâche(s) sans aucune contrainte de compatibilité machine-tâche déclarée : "
                f"{ids_sans_compatibilite!r}"
            )
        return self
