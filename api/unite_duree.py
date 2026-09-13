"""Détection automatique de l'unité d'affichage (`unite_duree`) d'une instance à partir de ses
propres contraintes — remplace la saisie manuelle historique (l'unité était autrefois choisie à
la création d'une `SourceDonnees` et recopiée telle quelle sur chaque instance générée ; ce champ
a été retiré). Purement cosmétique, comme l'unité qu'elle produit : `dsl`/le solveur généré/le
vérificateur de faisabilité continuent de raisonner en jours entiers, inchangés — seule la
présentation (voir `Front/.../lib/unite-duree.ts`) convertit selon la valeur retournée ici."""

from __future__ import annotations

from dsl.schema import CompatibiliteRessourceTache, Echeance, InstanceTRCO

# En-dessous de ce seuil (en jours), afficher en jours entiers reste lisible tel quel.
_SEUIL_SEMAINES_JOURS = 14
# Au-delà, l'affichage en semaines devient lui-même peu lisible (des dizaines de semaines) —
# basculer en mois.
_SEUIL_MOIS_JOURS = 60


def detecter_unite_duree(instance: InstanceTRCO) -> str:
    """ "heures"/"jours"/"semaines"/"mois" — "heures" directement si `instance.unite_temps ==
    "heures"` (pas de sur-échelle, non demandé), sinon choisie à partir de la plus grande durée
    réellement présente dans les contraintes de l'instance — échéances (`Echeance.echeance`) et
    durées tâche-ressource (`CompatibiliteRessourceTache.duree`), les deux seules valeurs que le
    frontend convertit via `formatDuree`/`formatDureeCourte`. Une instance en mode jours sans
    aucune de ces deux contraintes retombe sur "jours" (comportement par défaut historique,
    inchangé)."""
    if instance.unite_temps == "heures":
        return "heures"
    valeurs = [
        c.duree if isinstance(c, CompatibiliteRessourceTache) else c.echeance
        for c in instance.contraintes
        if isinstance(c, (CompatibiliteRessourceTache, Echeance))
    ]
    if not valeurs:
        return "jours"
    plus_grande = max(valeurs)
    if plus_grande < _SEUIL_SEMAINES_JOURS:
        return "jours"
    if plus_grande < _SEUIL_MOIS_JOURS:
        return "semaines"
    return "mois"
