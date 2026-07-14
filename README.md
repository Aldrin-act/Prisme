# PRISME

Plateforme de génération et d'exécution de solveurs d'ordonnancement pilotée par IA.
PFE — EIGSI Casablanca × BARAA Consult.

Voir [`PRISME_Note_de_Cadrage (2).md`](<./PRISME_Note_de_Cadrage (2).md>) pour le cadrage complet du projet (problème, architecture, stratégie de validation, roadmap).

## Principe fondateur

Le code du solveur est **généré une seule fois** par une boucle multi-agent (`generation/`), puis **persisté** (`solver_store/`) et **réexécuté** à chaque itération dans un conteneur éphémère (`sandbox/`), sans nouvelle sollicitation de l'IA.

## Arborescence

```
dsl/                 Modèle pivot T-R-C-O — Tâches, Ressources, Contraintes, Objectifs (Étape 1)
generation/           Boucle multi-agent generate-test-repair (Étapes 4, 6)
solver_store/         Store des solveurs générés & validés, code figé (Étape 7)
sandbox/              Exécution éphémère en conteneur jetable (Étape 7)
validation_engine/    Cascade de validation : faisabilité → banc synthétique → cas de référence (Étapes 2, 3, 5)
diagnostics/          Boucle d'amélioration — attribution code / données / DSL (Étape 9)
adapters/             Adaptateurs ERP (couche anti-corruption vers T-R-C-O) (Étape 8)
api/                  API PRISME — ingestion, exécution, canaux opérationnel/audit (Étape 8)
dashboard/            Tableau de bord, alertes, validation humaine (Étape 9)
tests/                Tests par couche : code manuel, propriétés du planning, stabilité de génération (§6)
docs/                 Documentation d'architecture et spécification du DSL
scripts/              Scripts utilitaires (dev, CI, génération de bancs synthétiques)
```

## Roadmap

Voir §8 de la note de cadrage. Ordre de construction : DSL → vérificateur de faisabilité → banc synthétique → générateur (tir unique) → cascade de validation → boucle generate-test-repair → store + sandbox → API + adaptateur ERP → tableau de bord.
