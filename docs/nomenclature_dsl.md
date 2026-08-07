# Nomenclature du DSL T-R-C-O

## 📖 Vocabulaire officiel

Le DSL PRISME utilise une **terminologie française précise** pour tous les concepts d'ordonnancement. Ce vocabulaire doit être respecté dans tout le code, la documentation et les interfaces utilisateur.

---

## 🎯 Les 4 axes du DSL

### T — Tâches

**Terme officiel** : `Tache` (sans accent dans le code)

**Définition** : Une opération à ordonnancer.

**Synonymes acceptés** :
- ✅ Tâche
- ✅ Opération
- ❌ **PAS** : Job, Task (anglicisme), Activité

**Identifiants** : Préfixe recommandé `T` ou `OP`
- Exemples : `T1`, `T2`, `OP10`, `OP20`

**Exemple** :
```json
{
  "id": "T1",
  "nom": "Découpe de la pièce A",
  "priorite": 2
}
```

---

### R — Ressources

**Terme officiel** : `Ressource`

**Définition** : Une ressource, un poste de travail, une équipe ou tout moyen de production pouvant exécuter des tâches.

**Synonymes acceptés** :
- ✅ Ressource
- ✅ Poste (de travail)
- ✅ Équipe
- ✅ Atelier
- ⚠️ Ressource (acceptable mais moins général)
- ❌ **PAS** : Resource (anglicisme), Opérateur individuel (hors périmètre)

**Identifiants** : Préfixe recommandé `R`, `E` (équipe), ou `POST`
- Exemples : `R1`, `R2`, `E10`, `POST_A`

**Exemples** :
```json
{
  "id": "R1",
  "nom": "Découpeuse laser",
  "competences": ["decoupe", "gravure"]
}
```

```json
{
  "id": "E10",
  "nom": "Équipe de maintenance",
  "competences": ["mecanique", "electricite"]
}
```

**❌ À éviter** :
```json
// NE PAS UTILISER "machine" dans les identifiants
{"id": "R1"}  // ❌ Préférer "R1"
{"id": "RESSOURCE_A"}  // ❌ Préférer "RESSOURCE_A" ou "R_A"
```

---

### C — Contraintes

**Terme officiel** : `Contrainte`

**Types disponibles** :

1. **Précédence** (`precedence`)
   - La tâche `avant` doit finir **avant** que `apres` commence

2. **Compatibilité Ressource-Tâche** (`compatibilite_ressource_tache`)
   - Définit quelles ressources peuvent exécuter quelles tâches, avec la durée par couple

3. **Échéance** (`echeance`)
   - Date limite de fin pour une tâche

4. **Compétence Requise** (`competence_requise`)
   - Compétence nécessaire pour exécuter une tâche

5. **Disponibilité Ressource** (`disponibilite_ressource`)
   - Jours (relatifs, jamais une date calendaire) où une ressource est indisponible — aucune
     opération ne peut s'y dérouler ces jours-là. Un calendrier global d'atelier (jours fériés
     communs) s'exprime en déclarant cette contrainte identiquement pour chaque ressource.

6. **Taille de Lot** (`taille_lot`)
   - Borne (`lot_min`/`lot_max`) la quantité (`Tache.quantite`) attendue pour une tâche —
     validation statique de la donnée d'entrée, sans aucun effet sur les décisions du solveur.

> Cette liste est en retard sur `dsl/schema/contraintes.py` pour `capacite`/`incompatibilite`
> (préexistant, pas corrigé ici) — voir le schéma directement pour la liste exhaustive à jour.

**Exemple** :
```json
{
  "type": "compatibilite_ressource_tache",
  "tache": "T1",
  "ressource": "R1",  // ✅ "ressource", pas "machine"
  "duree": 60
}
```

---

### O — Objectifs

**Terme officiel** : `Objectif`

**Types de base** :
- `minimiser_makespan` : Minimiser la durée totale
- `equilibrer_charge` : Équilibrer la charge entre ressources
- `minimiser_retards` : Minimiser les retards par rapport aux échéances
- `maximiser_utilisation` : Maximiser l'utilisation des ressources
- `minimiser_changements` : Minimiser les changements entre ressources

**Exemple** :
```json
{
  "type": "minimiser_makespan",
  "poids": 0.7,
  "makespan_cible": 480
}
```

---

## 🔤 Conventions de nommage des identifiants

### Préfixes recommandés

| Type | Préfixe | Exemples | Notes |
|------|---------|----------|-------|
| Tâche | `T`, `OP` | `T1`, `T2`, `OP10`, `OP20` | `OP` pour opération |
| Ressource | `R`, `E`, `POST` | `R1`, `E10`, `POST_A` | `E` pour équipe, `POST` pour poste |
| Identifiant neutre | Libre | `DECOUPE_001` | Si pas de préfixe, le contexte doit être clair |

### Règles de construction

✅ **Autorisé** : `[A-Za-z0-9_-]` (lettres, chiffres, tirets, underscores)
❌ **Interdit** : Espaces, caractères spéciaux, accents

**Exemples valides** :
```json
"T1"
"OP10"
"R_LASER_01"
"EQUIPE-MAINTENANCE"
"POST_ASSEMBLAGE_A"
```

**Exemples invalides** :
```json
"T 1"  // ❌ Espace
"OP#10"  // ❌ Caractère spécial
"Découpe"  // ❌ Accent (dans l'ID, OK dans le nom)
```

---

## 📝 Terminologie dans les paramètres

### Paramètres liés aux ressources

**✅ À utiliser** :
```json
{
  "cout_horaire_par_ressource": {"R1": 50.0, "R2": 75.0},
  "emission_co2_par_ressource_par_heure": {"R1": 5.0},
  "ressources_cibles": ["R1", "R2"],
  "ressources_prioritaires": ["R1"],
  "penalite_inactivite_par_ressource": {"R1": 10.0}
}
```

**❌ À éviter** :
```json
{
  "cout_horaire_par_machine": {...},  // ❌ Utiliser "ressource"
  "machines_cibles": [...],  // ❌ Utiliser "ressources"
  "ressource_ids": [...],  // ❌ Utiliser "ressource_ids" ou "ressources"
}
```

### Exceptions acceptables

Dans certains contextes métier spécifiques, **"machine"** peut être utilisé dans les **noms descriptifs** (pas les identifiants) :

✅ Acceptable :
```json
{
  "id": "R1",
  "nom": "Ressource de découpe laser CNC",  // ✅ "Machine" dans le nom
  "type": "machine"  // ✅ Type descriptif
}
```

❌ Non acceptable :
```json
{
  "id": "RESSOURCE_1",  // ❌ Dans l'identifiant
  "machine": "R1"  // ❌ Dans un champ de relation
}
```

---

## 🌍 Nomenclature multilingue (API internationale)

Si l'API doit supporter plusieurs langues, utiliser des **alias de mapping** :

```python
# api/i18n/aliases.py
ALIASES_CHAMPS = {
    "en": {
        "ressource": "resource",
        "tache": "task",
        "contrainte": "constraint",
        "objectif": "objective",
    },
    "fr": {
        "ressource": "ressource",
        "tache": "tache",
        "contrainte": "contrainte",
        "objectif": "objectif",
    }
}
```

**Format interne (canonical)** : Toujours français
**Formats externes** : Traduits selon la locale du client

---

## 📋 Checklist de cohérence

Avant de commiter du code, vérifier :

- [ ] Tous les identifiants de ressources utilisent `R`, `E`, ou `POST` (pas `M` ou `MACHINE`)
- [ ] Les paramètres utilisent `*_par_ressource` (pas `*_par_machine`)
- [ ] Les listes utilisent `ressources` au pluriel (pas `ressource`)
- [ ] Le vocabulaire français est respecté partout (tâche, ressource, contrainte, objectif)
- [ ] Les identifiants respectent `[A-Za-z0-9_-]+` (pas d'espaces, pas d'accents)
- [ ] La documentation utilise le vocabulaire officiel
- [ ] Les commentaires de code sont en français et cohérents

---

## 🔄 Migration des exemples existants

Si vous trouvez du code utilisant l'ancienne nomenclature :

### Avant (ancien)
```json
{
  "machines": [
    {"id": "R1", "name": "Cutting machine"}
  ],
  "cost_per_machine": {
    "R1": 50.0
  }
}
```

### Après (correct)
```json
{
  "ressources": [
    {"id": "R1", "nom": "Découpeuse"}
  ],
  "cout_par_ressource": {
    "R1": 50.0
  }
}
```

---

## 📚 Références

- **DSL complet** : [dsl/schema/](../dsl/schema/)
- **Exemples** : [dsl/examples/](../dsl/examples/)
- **Note de cadrage** : `PRISME_Note_de_Cadrage (2).md` (§4 — Le DSL T-R-C-O)
- **CLAUDE.md** : Section "Architecture — data flow"

---

## ✅ Résumé visuel

```
┌──────────────────────────────────────────────────┐
│         VOCABULAIRE OFFICIEL PRISME              │
├──────────────────────────────────────────────────┤
│                                                   │
│  ✅ Tâche (T1, OP10)                             │
│  ✅ Ressource (R1, E10, POST_A)                  │
│  ✅ Contrainte (precedence, compatibilite_...)   │
│  ✅ Objectif (minimiser_makespan, equilibrer_...)│
│                                                   │
│  ❌ Task, Job (anglicismes)                      │
│  ❌ Ressource (identifiants M1, M2...)             │
│  ❌ Resource (anglicisme)                        │
│  ❌ Constraint, Objective (anglicismes)          │
│                                                   │
└──────────────────────────────────────────────────┘
```

**Règle d'or** : Quand vous hésitez, demandez-vous : "Est-ce que c'est cohérent avec le DSL T-R-C-O ?"
