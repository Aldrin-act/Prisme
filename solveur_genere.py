from __future__ import annotations

from ortools.sat.python import cp_model

from dsl.schema import (
    InstanceTRCO,
    Planning,
    OperationPlanifiee,
    Precedence,
    CompatibiliteRessourceTache,
    Echeance,
    ContrainteCapacite,
    ContrainteIncompatibilite,
    ContrainteDisponibiliteRessource,
    ContrainteChangementSerie,
    MinimiserMakespan,
    EquilibrerCharge,
)


def _preprocess(
    instance: InstanceTRCO,
    planning_precedent: Planning | None,
    horizon_gele_jours: int,
) -> dict:
    compatibilites = [
        c for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)
    ]

    duree_par_tache_ressource: dict[tuple[str, str], int] = {}
    compatibilites_par_tache: dict[str, list[tuple[str, int]]] = {}
    compatibilites_par_ressource: dict[str, list[tuple[str, int]]] = {}
    ressources_par_tache: dict[str, set[str]] = {}

    for c in compatibilites:
        duree_par_tache_ressource[(c.tache, c.ressource)] = c.duree
        compatibilites_par_tache.setdefault(c.tache, []).append((c.ressource, c.duree))
        compatibilites_par_ressource.setdefault(c.ressource, []).append((c.tache, c.duree))
        ressources_par_tache.setdefault(c.tache, set()).add(c.ressource)

    horizon = 0
    for tache in instance.taches:
        alternatives = compatibilites_par_tache.get(tache.id, [])
        if alternatives:
            horizon += max(duree for _, duree in alternatives)

    setups = [
        c for c in instance.contraintes if isinstance(c, ContrainteChangementSerie)
    ]
    for c in setups:
        if (
            (c.tache_avant, c.ressource) in duree_par_tache_ressource
            and (c.tache_apres, c.ressource) in duree_par_tache_ressource
        ):
            horizon += c.duree_setup

    precedences = [c for c in instance.contraintes if isinstance(c, Precedence)]
    echeances = [c for c in instance.contraintes if isinstance(c, Echeance)]

    capacite_par_ressource: dict[str, int] = {
        c.ressource: c.capacite
        for c in instance.contraintes
        if isinstance(c, ContrainteCapacite)
    }

    taches_incompatibles: dict[str, set[str]] = {}
    for c in instance.contraintes:
        if isinstance(c, ContrainteIncompatibilite):
            taches_incompatibles.setdefault(c.tache, set()).add(c.tache_incompatible)
            taches_incompatibles.setdefault(c.tache_incompatible, set()).add(c.tache)

    jours_indisponibles_par_ressource: dict[str, set[int]] = {}
    for c in instance.contraintes:
        if isinstance(c, ContrainteDisponibiliteRessource):
            jours = jours_indisponibles_par_ressource.setdefault(c.ressource, set())
            jours.update(c.jours_indisponibles)

    longueur_cycle = 7 if instance.unite_temps == 'jours' else 168

    while True:
        max_jour = max(
            (j for jours in jours_indisponibles_par_ressource.values() for j in jours),
            default=-1,
        )
        for c in instance.contraintes:
            if not isinstance(c, ContrainteDisponibiliteRessource):
                continue
            if not c.jours_semaine_indisponibles:
                continue
            jours = jours_indisponibles_par_ressource.setdefault(c.ressource, set())
            for pos in c.jours_semaine_indisponibles:
                pos = pos % longueur_cycle
                jours.update(range(pos, horizon, longueur_cycle))
        nouveau_horizon = max(horizon, max_jour + 1)
        if nouveau_horizon == horizon:
            break
        horizon = nouveau_horizon

    operations_fixees: dict[tuple[str, str], int] = {}
    if planning_precedent is not None and horizon_gele_jours > 0:
        for op in planning_precedent.operations:
            if op.debut >= horizon_gele_jours:
                continue
            duree = duree_par_tache_ressource.get((op.tache, op.ressource))
            if duree is None:
                continue
            operations_fixees[(op.tache, op.ressource)] = op.debut
            if op.debut + duree > horizon:
                horizon = op.debut + duree

    while True:
        max_jour = max(
            (j for jours in jours_indisponibles_par_ressource.values() for j in jours),
            default=-1,
        )
        for c in instance.contraintes:
            if not isinstance(c, ContrainteDisponibiliteRessource):
                continue
            if not c.jours_semaine_indisponibles:
                continue
            jours = jours_indisponibles_par_ressource.setdefault(c.ressource, set())
            for pos in c.jours_semaine_indisponibles:
                pos = pos % longueur_cycle
                jours.update(range(pos, horizon, longueur_cycle))
        nouveau_horizon = max(horizon, max_jour + 1)
        if nouveau_horizon == horizon:
            break
        horizon = nouveau_horizon

    return {
        'duree_par_tache_ressource': duree_par_tache_ressource,
        'compatibilites_par_tache': compatibilites_par_tache,
        'compatibilites_par_ressource': compatibilites_par_ressource,
        'ressources_par_tache': ressources_par_tache,
        'precedences': precedences,
        'echeances': echeances,
        'capacite_par_ressource': capacite_par_ressource,
        'taches_incompatibles': taches_incompatibles,
        'jours_indisponibles_par_ressource': jours_indisponibles_par_ressource,
        'setups': setups,
        'operations_fixees': operations_fixees,
        'horizon': horizon,
    }


def _construire_modele(
    instance: InstanceTRCO, tables: dict
) -> tuple[cp_model.CpModel, dict]:
    modele = cp_model.CpModel()

    duree_par_tache_ressource = tables['duree_par_tache_ressource']
    compatibilites_par_tache = tables['compatibilites_par_tache']
    compatibilites_par_ressource = tables['compatibilites_par_ressource']
    ressources_par_tache = tables['ressources_par_tache']
    precedences = tables['precedences']
    echeances = tables['echeances']
    capacite_par_ressource = tables['capacite_par_ressource']
    taches_incompatibles = tables['taches_incompatibles']
    jours_indisponibles_par_ressource = tables['jours_indisponibles_par_ressource']
    setups = tables['setups']
    operations_fixees = tables['operations_fixees']
    horizon = tables['horizon']

    debut: dict[str, object] = {}
    fin: dict[str, object] = {}
    presence: dict[tuple[str, str], object] = {}
    intervalle_par_couple: dict[tuple[str, str], object] = {}
    intervalles_par_ressource: dict[str, list[object]] = {}
    demandes_par_ressource: dict[str, list[int]] = {}

    for tache in instance.taches:
        tid = tache.id
        debut[tid] = modele.NewIntVar(0, horizon, f'debut_{tid}')
        fin[tid] = modele.NewIntVar(0, horizon, f'fin_{tid}')
        for ressource, duree in compatibilites_par_tache.get(tid, []):
            var_presence = modele.NewBoolVar(f'presence_{tid}_{ressource}')
            presence[(tid, ressource)] = var_presence
            intervalle_par_couple[(tid, ressource)] = modele.NewOptionalIntervalVar(
                debut[tid],
                duree,
                fin[tid],
                var_presence,
                f'intervalle_{tid}_{ressource}',
            )
            intervalles_par_ressource.setdefault(ressource, []).append(
                intervalle_par_couple[(tid, ressource)]
            )
            demandes_par_ressource.setdefault(ressource, []).append(1)

    for tache in instance.taches:
        alternatives = [
            presence[(tache.id, ressource)]
            for ressource in ressources_par_tache.get(tache.id, set())
        ]
        if alternatives:
            modele.AddExactlyOne(alternatives)

    for ressource, jours in jours_indisponibles_par_ressource.items():
        capacite = capacite_par_ressource.get(ressource, 1)
        for jour in sorted(jours):
            if jour >= horizon:
                continue
            intervalle_indispo = modele.NewIntervalVar(
                jour, 1, jour + 1, f'indispo_{ressource}_{jour}'
            )
            intervalles_par_ressource.setdefault(ressource, []).append(intervalle_indispo)
            demandes_par_ressource.setdefault(ressource, []).append(capacite)

    toutes_ressources = (
        set(intervalles_par_ressource.keys())
        | set(capacite_par_ressource.keys())
        | set(jours_indisponibles_par_ressource.keys())
    )
    for ressource in sorted(toutes_ressources):
        intervalle = intervalles_par_ressource.get(ressource, [])
        if not intervalle:
            continue
        capacite = capacite_par_ressource.get(ressource, 1)
        if capacite == 1:
            modele.AddNoOverlap(intervalle)
        else:
            modele.AddCumulative(
                intervalle,
                demandes_par_ressource.get(ressource, [1] * len(intervalle)),
                capacite,
            )

    ids_connus = set(debut.keys())
    for c in precedences:
        if c.avant in ids_connus and c.apres in ids_connus:
            modele.Add(fin[c.avant] <= debut[c.apres])

    for c in echeances:
        if c.tache in ids_connus:
            modele.Add(fin[c.tache] <= c.echeance)

    for c in instance.contraintes:
        if not isinstance(c, ContrainteIncompatibilite):
            continue
        ressources_communes = (
            set(ressources_par_tache.get(c.tache, set()))
            & set(ressources_par_tache.get(c.tache_incompatible, set()))
        )
        for ressource in ressources_communes:
            if (
                (c.tache, ressource) in presence
                and (c.tache_incompatible, ressource) in presence
            ):
                modele.Add(
                    presence[(c.tache, ressource)]
                    + presence[(c.tache_incompatible, ressource)]
                    <= 1
                )

    for c in setups:
        if (
            (c.tache_avant, c.ressource) not in presence
            or (c.tache_apres, c.ressource) not in presence
        ):
            continue
        p_avant = presence[(c.tache_avant, c.ressource)]
        p_apres = presence[(c.tache_apres, c.ressource)]
        ordre = modele.NewBoolVar(
            f'ordre_{c.tache_avant}_{c.tache_apres}_{c.ressource}'
        )
        modele.Add(
            debut[c.tache_apres] >= fin[c.tache_avant] + c.duree_setup
        ).OnlyEnforceIf([p_avant, p_apres, ordre])
        modele.Add(
            debut[c.tache_avant] >= fin[c.tache_apres]
        ).OnlyEnforceIf([p_avant, p_apres, ordre.Not()])

    for (tache, ressource), debut_precedent in operations_fixees.items():
        if (tache, ressource) in presence:
            modele.Add(presence[(tache, ressource)] == 1)
            modele.Add(debut[tache] == debut_precedent)

    objectifs_makespan = [
        o for o in instance.objectifs if isinstance(o, MinimiserMakespan)
    ]
    objectifs_equilibrage = [
        o for o in instance.objectifs if isinstance(o, EquilibrerCharge)
    ]

    makespan = modele.NewIntVar(0, horizon, 'makespan')
    if instance.taches:
        modele.AddMaxEquality(makespan, [fin[t.id] for t in instance.taches])

    termes_objectif: list[object] = []

    for obj in objectifs_makespan:
        poids = getattr(obj, 'poids', 1)
        makespan_cible = getattr(obj, 'makespan_cible', None)
        penalite_depassement = getattr(obj, 'penalite_depassement', None)
        if makespan_cible is not None and penalite_depassement is not None:
            depassement = modele.NewIntVar(0, horizon, 'depassement_makespan')
            modele.AddMaxEquality(
                depassement, [0, makespan - makespan_cible]
            )
            termes_objectif.append(poids * makespan + penalite_depassement * depassement)
        else:
            termes_objectif.append(poids * makespan)

    somme_durees_toutes = sum(duree_par_tache_ressource.values())

    for idx, obj in enumerate(objectifs_equilibrage):
        poids = getattr(obj, 'poids', 1)
        methode = getattr(obj, 'methode', 'ecart_max')
        ressources_cibles = getattr(obj, 'ressources_cibles', None) or []
        if not ressources_cibles:
            ressources_cibles = sorted(
                {r for (_, r) in duree_par_tache_ressource}
            )

        charges: list[object] = []
        for ressource in ressources_cibles:
            if ressource not in compatibilites_par_ressource:
                continue
            charge = modele.NewIntVar(
                0, somme_durees_toutes, f'charge_{idx}_{ressource}'
            )
            modele.Add(
                charge
                == sum(
                    duree * presence[(tache, ressource)]
                    for (tache, duree) in compatibilites_par_ressource[ressource]
                )
            )
            charges.append(charge)

        if charges:
            # En CP-SAT, variance et gini sont approchés volontairement par ecart_max :
            # une linéarisation exacte serait disproportionnée pour du code généré.
            # Minimiser l'écart max tire aussi variance/gini vers le bas en pratique.
            charge_max = modele.NewIntVar(
                0, somme_durees_toutes, f'charge_max_{idx}'
            )
            charge_min = modele.NewIntVar(
                0, somme_durees_toutes, f'charge_min_{idx}'
            )
            modele.AddMaxEquality(charge_max, charges)
            modele.AddMinEquality(charge_min, charges)
            termes_objectif.append(poids * (charge_max - charge_min))

    objectifs_reconnus = objectifs_makespan + objectifs_equilibrage
    if not termes_objectif and not objectifs_reconnus:
        termes_objectif.append(1 * makespan)

    if termes_objectif:
        objectif_principal = sum(termes_objectif)
    else:
        objectif_principal = 1 * makespan

    terme_priorite = 0
    nb_priorisees = 0
    for tache in instance.taches:
        if tache.priorite is not None:
            terme_priorite += (6 - tache.priorite) * fin[tache.id]
            nb_priorisees += 1

    if nb_priorisees:
        echelle = 5 * nb_priorisees * horizon + 1
    else:
        echelle = 1

    modele.Minimize(objectif_principal * echelle + terme_priorite)

    return modele, {
        'debut': debut,
        'presence': presence,
    }


def _resoudre(modele: cp_model.CpModel) -> tuple[int, cp_model.CpSolver]:
    solveur = cp_model.CpSolver()
    solveur.parameters.max_time_in_seconds = 10
    solveur.parameters.num_search_workers = 8
    solveur.parameters.linearization_level = 2
    solveur.parameters.random_seed = 0
    solveur.parameters.log_search_progress = False
    statut = solveur.Solve(modele)
    return statut, solveur


def _extraire_planning(
    solveur: cp_model.CpSolver,
    variables: dict,
    _tables: dict,
) -> Planning | None:
    debut = variables['debut']
    presence = variables['presence']

    operations = []
    for (tache, ressource), var_presence in presence.items():
        if solveur.Value(var_presence) == 1:
            operations.append(
                OperationPlanifiee(
                    tache=tache,
                    ressource=ressource,
                    debut=int(solveur.Value(debut[tache])),
                )
            )

    operations.sort(key=lambda op: (op.debut, op.tache, op.ressource))
    return Planning(operations=operations)


def resoudre(
    instance: InstanceTRCO,
    planning_precedent: Planning | None = None,
    horizon_gele_jours: int = 0,
) -> Planning | None:
    if not instance.taches:
        return Planning(operations=[])

    tables = _preprocess(instance, planning_precedent, horizon_gele_jours)

    for tache in instance.taches:
        if not tables['compatibilites_par_tache'].get(tache.id):
            return None

    modele, variables = _construire_modele(instance, tables)
    statut, solveur = _resoudre(modele)

    if statut not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    return _extraire_planning(solveur, variables, tables)
