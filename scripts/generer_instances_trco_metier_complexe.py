"""Générateur d'instances TRCO à *complexité métier* accrue, à partir des mêmes
configurations YAML de secteur que `scripts/generer_donnees_depuis_config.py`
(`data/configurations_secteurs/`) — mais en ciblant directement le DSL T-R-C-O
(`dsl.schema.InstanceTRCO`) plutôt que le format ERP intermédiaire
(`adapters.erp_reference`), pour exercer les extensions du DSL que la chaîne
ERP → `translator.py` ne produit jamais aujourd'hui :

- **Vraie flexibilité FJSP** : chaque tâche est compatible avec plusieurs
  instances physiques d'un type de poste (`types_postes.<type>.capacite`,
  jusqu'ici lu comme un simple commentaire, jamais utilisé pour créer
  plusieurs ressources), avec une durée qui varie légèrement d'une ressource
  compatible à l'autre — pas juste une compatibilité unique par tâche.
- **Échéances** sur la dernière tâche de chaque lot (delivery deadline).
- **Capacité** sur une partie des ressources (équipement/équipe pouvant
  traiter plusieurs opérations en parallèle).
- **Indisponibilité récurrente** sur une partie des ressources (jour de
  maintenance hebdomadaire).
- **Changement de série** entre deux tâches de lots différents partageant un
  même type de poste propice au retoolage (peinture, presses...).
- **Incompatibilité** entre quelques tâches de lots différents (traçabilité :
  ne jamais partager une ressource, indépendamment du planning).
- **Priorité** et **taille de lot** (`Tache.priorite`/`quantite` +
  `ContrainteTailleLot`) sur une partie des tâches.

Ces instances ne visent pas la preuve d'optimum du banc synthétique
(`validation_engine/synthetic_bench/`, §Étape 3 du CLAUDE.md) — elles servent
à exercer la richesse du DSL et la chaîne de génération sur des données
métier plausibles, pas à fournir un optimum connu par construction.

Deux sorties par secteur, dérivées l'une de l'autre (même contenu, deux
formes) :
- `data/instances_trco_metier_complexe/<secteur>_<taille>.json` — l'instance
  T-R-C-O canonique (`InstanceTRCO`), prête pour le pipeline PRISME.
- `data/donnees_brutes_metier_complexe/<secteur>_<taille>.json` — la même
  donnée sous forme « brute » (vocabulaire ERP à plat, voir
  `vers_donnees_brutes`) — un format dédié à ce générateur, non ré-ingérable
  par `adapters.csv_import`/`adapters.erp_reference` (trop minimaux pour ces
  extensions), à but de lecture/démonstration seulement.

Usage :
    uv run python -m scripts.generer_instances_trco_metier_complexe --secteur atelier_mecanique --taille 60
    uv run python -m scripts.generer_instances_trco_metier_complexe --tous --taille 60
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from dsl.schema import (
    CompatibiliteRessourceTache,
    CompetenceRequise,
    Contrainte,
    ContrainteCapacite,
    ContrainteChangementSerie,
    ContrainteDisponibiliteRessource,
    ContrainteIncompatibilite,
    ContrainteTailleLot,
    Echeance,
    EquilibrerCharge,
    InstanceTRCO,
    MinimiserMakespan,
    MinimiserRetards,
    Objectif,
    Precedence,
    Ressource,
    Tache,
)
from scripts.generer_donnees_depuis_config import (
    MINUTES_PAR_JOUR_OUVRE,
    charger_configuration,
    lister_configurations_disponibles,
)

# Types de postes propices à un changement de série coûteux (retoolage,
# changement de couleur/outillage) — reconnus par mot-clé dans le nom du
# type, faute d'un champ dédié dans la configuration YAML (§ pas d'ajout de
# nouveau champ pour rester compatible avec les 9 configs existantes).
_MOTS_CLES_CHANGEMENT_SERIE = ("PRESSE", "PEINTURE", "FOUR", "MARMITE", "MOULE")

MAX_RESSOURCES_PAR_TYPE = 4


def _duree_jours(duree_min_minutes: int, duree_max_minutes: int) -> int:
    duree_minutes = random.randint(duree_min_minutes, duree_max_minutes)
    return max(1, round(duree_minutes / MINUTES_PAR_JOUR_OUVRE))


def _ressources_pour_type(type_poste_nom: str, type_poste_config: dict[str, Any]) -> list[Ressource]:
    """Une ressource physique par unité déclarée (`capacite`, plafonnée à
    `MAX_RESSOURCES_PAR_TYPE`) — c'est ce qui donne la vraie flexibilité FJSP
    (plusieurs ressources compatibles par tâche), jamais exploité par
    `generer_donnees_depuis_config.py` qui n'en crée qu'une seule."""
    n = max(1, min(int(type_poste_config.get("capacite", 1)), MAX_RESSOURCES_PAR_TYPE))
    competence = type_poste_nom.lower()
    if n == 1:
        return [Ressource(id=type_poste_nom, competences=[competence])]
    return [Ressource(id=f"{type_poste_nom}_{i}", competences=[competence]) for i in range(1, n + 1)]


def generer_instance_metier_complexe(
    config: dict[str, Any], n_operations: int, *, graine: int | None = None
) -> InstanceTRCO:
    if graine is not None:
        random.seed(graine)

    types_postes: dict[str, dict[str, Any]] = config["types_postes"]
    phases: list[dict[str, Any]] = config["phases_production"]
    generation = config.get("generation", {})
    ops_par_lot_min = generation.get("operations_par_lot_min", 4)
    ops_par_lot_max = generation.get("operations_par_lot_max", 8)
    ops_par_lot_moyen = (ops_par_lot_min + ops_par_lot_max) / 2
    n_lots = max(1, int(n_operations / ops_par_lot_moyen))

    # Une ressource physique par (type de poste), tous les types confondus.
    ressources: dict[str, Ressource] = {}
    ressources_par_type: dict[str, list[str]] = {}
    for type_poste_nom, type_poste_config in types_postes.items():
        instances = _ressources_pour_type(type_poste_nom, type_poste_config)
        ressources_par_type[type_poste_nom] = [r.id for r in instances]
        for r in instances:
            ressources[r.id] = r

    taches: list[Tache] = []
    contraintes: list[Contrainte] = []
    op_id = 1
    # Rassemble, par type de poste propice, les tâches qui l'utilisent — pour
    # ensuite tirer des paires de tâches de lots différents (changement de
    # série / incompatibilité), sans dépendre de l'ordre de résolution.
    taches_par_type_changement_serie: dict[str, list[tuple[str, str]]] = {}  # type -> [(tache_id, ressource_id)]

    for _i_lot in range(n_lots):
        n_ops_lot = random.randint(ops_par_lot_min, ops_par_lot_max)
        phases_lot = random.sample(phases, min(len(phases), n_ops_lot))
        taches_du_lot: list[str] = []
        precedent_id: str | None = None

        for phase in phases_lot:
            type_poste_nom = random.choice(phase["types_poste"])
            type_poste_config = types_postes[type_poste_nom]
            competence = type_poste_nom.lower()

            tache_id = f"{phase['nom']}_{op_id:03d}"
            op_id += 1

            priorite = random.randint(1, 5) if random.random() < 0.6 else None
            quantite = random.randint(5, 200) if random.random() < 0.3 else None

            taches.append(Tache(id=tache_id, priorite=priorite, quantite=quantite))
            contraintes.append(CompetenceRequise(tache=tache_id, competence=competence))
            if quantite is not None:
                marge = max(1, quantite // 5)
                contraintes.append(
                    ContrainteTailleLot(
                        tache=tache_id,
                        lot_min=max(1, quantite - marge),
                        lot_max=quantite + marge,
                    )
                )

            # Vraie flexibilité : compatible avec CHAQUE instance physique de
            # ce type de poste, durée qui varie de +/-15% d'une ressource à
            # l'autre (deux machines identiques ne tournent jamais exactement
            # à la même cadence).
            duree_base = _duree_jours(type_poste_config["duree_min"], type_poste_config["duree_max"])
            for ressource_id in ressources_par_type[type_poste_nom]:
                jitter = random.uniform(-0.15, 0.15)
                duree = max(1, round(duree_base * (1 + jitter)))
                contraintes.append(
                    CompatibiliteRessourceTache(tache=tache_id, ressource=ressource_id, duree=duree)
                )

            if precedent_id is not None and random.random() < 0.6:
                contraintes.append(Precedence(avant=precedent_id, apres=tache_id))

            precedent_id = tache_id
            taches_du_lot.append(tache_id)

            if any(mot in type_poste_nom for mot in _MOTS_CLES_CHANGEMENT_SERIE):
                taches_par_type_changement_serie.setdefault(type_poste_nom, []).append(
                    (tache_id, ressources_par_type[type_poste_nom][0])
                )

            if len(taches) >= n_operations:
                break

        # Échéance sur la dernière tâche du lot (livraison) — buffer généreux
        # au-dessus d'une estimation grossière de la chaîne du lot, pour
        # rester plausible sans viser une preuve de faisabilité serrée (ces
        # instances ne sont pas le banc synthétique à optimum connu).
        if taches_du_lot and random.random() < 0.7:
            duree_estimee_lot = len(taches_du_lot) * 3  # estimation grossière, jours
            contraintes.append(
                Echeance(tache=taches_du_lot[-1], echeance=duree_estimee_lot + random.randint(5, 20))
            )

        if len(taches) >= n_operations:
            break

    # Capacité : ~15% des ressources traitent plusieurs opérations en
    # parallèle (four/équipe polyvalente...).
    for ressource_id in ressources:
        if random.random() < 0.15:
            contraintes.append(ContrainteCapacite(ressource=ressource_id, capacite=random.randint(2, 3)))

    # Indisponibilité récurrente : ~20% des ressources ont un jour de
    # maintenance hebdomadaire fixe.
    for ressource_id in ressources:
        if random.random() < 0.20:
            jour_maintenance = random.randint(0, 6)
            contraintes.append(
                ContrainteDisponibiliteRessource(
                    ressource=ressource_id, jours_semaine_indisponibles=[jour_maintenance]
                )
            )

    # Changement de série : entre tâches de lots différents partageant un
    # type de poste propice au retoolage, dans l'ordre où elles ont été
    # générées (tache_avant = la plus ancienne).
    for type_poste_nom, occurrences in taches_par_type_changement_serie.items():
        if len(occurrences) < 2:
            continue
        for (tache_avant, ressource_id), (tache_apres, _r) in zip(occurrences, occurrences[1:]):
            if random.random() < 0.5:
                contraintes.append(
                    ContrainteChangementSerie(
                        ressource=ressource_id,
                        tache_avant=tache_avant,
                        tache_apres=tache_apres,
                        duree_setup=random.randint(1, 3),
                    )
                )

    # Incompatibilité : quelques paires de tâches (traçabilité produit),
    # tirées parmi les occurrences déjà collectées ci-dessus — reste rare
    # pour ne pas sur-contraindre l'instance.
    toutes_occurrences = [tache_id for occs in taches_par_type_changement_serie.values() for tache_id, _r in occs]
    n_incompatibilites = min(len(toutes_occurrences) // 6, 5)
    for _ in range(n_incompatibilites):
        if len(toutes_occurrences) < 2:
            break
        tache_a, tache_b = random.sample(toutes_occurrences, 2)
        contraintes.append(ContrainteIncompatibilite(tache=tache_a, tache_incompatible=tache_b))

    objectifs: list[Objectif] = [
        MinimiserMakespan(),
        MinimiserRetards(fonction_penalite="lineaire", seuil_grace=1),
        EquilibrerCharge(methode="ecart_max"),
    ]

    return InstanceTRCO(
        taches=taches, ressources=list(ressources.values()), contraintes=contraintes, objectifs=objectifs
    )


def vers_donnees_brutes(instance: InstanceTRCO, nom_secteur: str) -> dict[str, Any]:
    """Dérive une représentation « donnée brute » (vocabulaire ERP,
    `code_operation`/`poste_id`/`duree_jours`, à plat) à partir d'une
    `InstanceTRCO` déjà validée — format dédié à ce générateur, **distinct**
    de `adapters.erp_reference.schema_erp.PayloadERP` : ce dernier ne porte
    qu'une seule ressource compatible par opération et aucune des extensions
    du DSL (échéance, capacité, disponibilité, changement de série,
    incompatibilité, priorité, taille de lot) — le reformuler pour les
    porter casserait sa fidélité au vocabulaire ERP de référence qu'il
    documente (§ CLAUDE.md, Étape 4/8). Non ré-ingérable tel quel par
    `adapters.csv_import`/`adapters.erp_reference` (`TYPES_CONTRAINTE_SUPPORTES`
    s'y limite à precedence/compatibilite_ressource_tache/competence_requise)
    — seule l'instance TRCO jumelle (`vers_donnees_brutes` en est dérivée,
    jamais l'inverse) reste la source ré-exécutable par le pipeline PRISME.

    `poste_id` d'une ressource suit la convention `<TYPE>_<n>` de ce
    générateur (`_ressources_pour_type`) : `type_poste` est dérivé de
    `Ressource.competences[0]` (mis en majuscules), absent si aucune
    compétence déclarée."""
    precedents_par_tache: dict[str, list[str]] = {}
    compatibilites_par_tache: dict[str, list[dict[str, Any]]] = {}
    competence_par_tache: dict[str, str] = {}
    echeance_par_tache: dict[str, int] = {}
    taille_lot_par_tache: dict[str, dict[str, int]] = {}
    capacite_par_ressource: dict[str, int] = {}
    disponibilite_par_ressource: dict[str, dict[str, Any]] = {}
    changements_serie: list[dict[str, Any]] = []
    incompatibilites: list[dict[str, Any]] = []

    for c in instance.contraintes:
        if c.type == "precedence":
            precedents_par_tache.setdefault(c.apres, []).append(c.avant)
        elif c.type == "compatibilite_ressource_tache":
            compatibilites_par_tache.setdefault(c.tache, []).append(
                {"poste_id": c.ressource, "duree_jours": c.duree}
            )
        elif c.type == "competence_requise":
            competence_par_tache[c.tache] = c.competence
        elif c.type == "echeance":
            echeance_par_tache[c.tache] = c.echeance
        elif c.type == "taille_lot":
            taille_lot_par_tache[c.tache] = {"lot_min": c.lot_min, "lot_max": c.lot_max}
        elif c.type == "capacite":
            capacite_par_ressource[c.ressource] = c.capacite
        elif c.type == "disponibilite_ressource":
            disponibilite_par_ressource[c.ressource] = {
                "jours_indisponibles": c.jours_indisponibles,
                "jours_semaine_indisponibles": c.jours_semaine_indisponibles,
            }
        elif c.type == "changement_serie":
            changements_serie.append(
                {
                    "poste_id": c.ressource,
                    "operation_avant": c.tache_avant,
                    "operation_apres": c.tache_apres,
                    "duree_setup_jours": c.duree_setup,
                }
            )
        elif c.type == "incompatibilite":
            incompatibilites.append({"operation": c.tache, "operation_incompatible": c.tache_incompatible})

    operations = []
    for t in instance.taches:
        operation: dict[str, Any] = {
            "code_operation": t.id,
            "operations_precedentes": precedents_par_tache.get(t.id, []),
            "competence_requise": competence_par_tache.get(t.id),
            "ressources_compatibles": compatibilites_par_tache.get(t.id, []),
        }
        if t.priorite is not None:
            operation["priorite"] = t.priorite
        if t.quantite is not None:
            operation["quantite"] = t.quantite
            operation.update(taille_lot_par_tache.get(t.id, {}))
        if t.id in echeance_par_tache:
            operation["echeance_jours"] = echeance_par_tache[t.id]
        operations.append(operation)

    postes = []
    for r in instance.ressources:
        poste: dict[str, Any] = {
            "code_poste": r.id,
            "type_poste": r.competences[0].upper() if r.competences else None,
            "competences": r.competences,
        }
        if r.id in capacite_par_ressource:
            poste["capacite_simultanee"] = capacite_par_ressource[r.id]
        if r.id in disponibilite_par_ressource:
            poste.update(disponibilite_par_ressource[r.id])
        postes.append(poste)

    return {
        "secteur": nom_secteur,
        "operations": operations,
        "postes": postes,
        "changements_serie": changements_serie,
        "incompatibilites": incompatibilites,
    }


def sauvegarder(instance: InstanceTRCO, nom_secteur: str, taille_str: str) -> tuple[Path, Path]:
    repertoire_trco = Path("data/instances_trco_metier_complexe")
    repertoire_trco.mkdir(parents=True, exist_ok=True)
    chemin_trco = repertoire_trco / f"{nom_secteur}_{taille_str}.json"
    with open(chemin_trco, "w", encoding="utf-8") as f:
        json.dump(instance.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

    repertoire_brut = Path("data/donnees_brutes_metier_complexe")
    repertoire_brut.mkdir(parents=True, exist_ok=True)
    chemin_brut = repertoire_brut / f"{nom_secteur}_{taille_str}.json"
    with open(chemin_brut, "w", encoding="utf-8") as f:
        json.dump(vers_donnees_brutes(instance, nom_secteur), f, indent=2, ensure_ascii=False)

    return chemin_trco, chemin_brut


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secteur", type=str, help="Nom du secteur (fichier YAML sans extension)")
    parser.add_argument("--taille", type=int, default=60, help="Nombre de tâches à générer (défaut: 60)")
    parser.add_argument("--tous", action="store_true", help="Générer pour tous les secteurs configurés")
    parser.add_argument("--graine", type=int, default=None, help="Graine aléatoire (reproductibilité)")
    args = parser.parse_args()

    if not args.tous and not args.secteur:
        parser.error("Vous devez spécifier --secteur <nom> ou --tous")

    taille_str = "small" if args.taille < 50 else "medium" if args.taille < 150 else "large"
    secteurs = lister_configurations_disponibles() if args.tous else [args.secteur]

    for nom_secteur in sorted(secteurs):
        try:
            config = charger_configuration(nom_secteur)
            instance = generer_instance_metier_complexe(config, args.taille, graine=args.graine)
        except Exception as erreur:  # noqa: BLE001 — un secteur en échec ne doit pas arrêter les autres
            print(f"[{nom_secteur}] ERREUR : {erreur}")
            continue

        chemin_trco, chemin_brut = sauvegarder(instance, nom_secteur, taille_str)
        n_echeances = sum(1 for c in instance.contraintes if c.type == "echeance")
        n_capacite = sum(1 for c in instance.contraintes if c.type == "capacite")
        n_disponibilite = sum(1 for c in instance.contraintes if c.type == "disponibilite_ressource")
        n_changement = sum(1 for c in instance.contraintes if c.type == "changement_serie")
        n_incompat = sum(1 for c in instance.contraintes if c.type == "incompatibilite")
        n_taille_lot = sum(1 for c in instance.contraintes if c.type == "taille_lot")
        flexibilite = len([c for c in instance.contraintes if c.type == "compatibilite_ressource_tache"]) / max(
            1, len(instance.taches)
        )
        print(
            f"[{nom_secteur}] {len(instance.taches)} tâches, {len(instance.ressources)} ressources, "
            f"flexibilité moy. {flexibilite:.1f} ressources/tâche — "
            f"{n_echeances} échéances, {n_capacite} capacités, {n_disponibilite} indisponibilités, "
            f"{n_changement} changements série, {n_incompat} incompatibilités, {n_taille_lot} tailles de lot"
        )
        print(f"  TRCO : {chemin_trco}")
        print(f"  Brut : {chemin_brut}")


if __name__ == "__main__":
    main()
