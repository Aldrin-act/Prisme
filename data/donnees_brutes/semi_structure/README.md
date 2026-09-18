# Données Brutes au Format Semi-Structuré (JSON, ateliers de production industrielle)

Ce répertoire contient des exports JSON **volontairement irréguliers** d'ateliers de
production industrielle — ni du T-R-C-O canonique (`format_simplifie/`), ni un export ERP à
vocabulaire fixe et reconnaissable (`json_erp/`). Aucun des deux chemins déterministes de ce
projet ne peut les interpréter : `adapters/json_import` attend les clés canoniques
`taches`/`ressources`/`contraintes` (absentes ici, vérifié directement — les trois fichiers
échouent avec `ErreurPayloadInvalide`, jamais silencieusement acceptés).

Seul l'agent de compréhension (`adapters/agent_comprehension/agent.py::comprendre_donnees_erp`)
peut en tirer une instance T-R-C-O. Toujours passer par **Données → Nouvelle source →
Génération IA** (jamais "Génération déterministe").

## Fichiers disponibles

### `signaletique_export.json` — atelier de signalétique, JSON imbriqué par commande

Opérations imbriquées sous `export_signapro.commandes[]`, jamais une liste plate. Teste le
regroupement multi-commandes, des durées en texte libre à unités mélangées, une précédence
exprimée uniquement en langage naturel (`remarque`), et la règle "compétence ≠ historique
d'affectation" (`poste_habituel` vs. `operateurs_habilites`).

### `fonderie_export.json` — fonderie métallurgique, ordres de fabrication + parc machines

Deux `work_orders`, chacun une chaîne d'étapes liées par `depends_on` (référence **locale à
l'ordre**, pas un id global — deux étapes "Fusion" dans deux ordres différents, à ne jamais
confondre). Teste en plus :

- **Durées en trois formats différents dans le même fichier** : ISO 8601 (`"PT4H"`,
  `"PT45M"`), entier nu (`30`, `25` — minutes implicites), et `null` avec une estimation
  écrite en toutes lettres dans `note`.
- **Compétence par recoupement, pas par lecture directe** : `certif_requise` sur une étape
  d'un côté, `certifs_operateurs` sur la machine correspondante de l'autre (`machines[]`) —
  il faut croiser les deux tableaux, la compétence n'est écrite nulle part sur la tâche
  elle-même de façon autonome.
- **Un champ 100% bruit à ignorer** : `historique_maintenance`, sans aucun rapport avec la
  planification — bon test que l'agent ne le confond pas avec une contrainte de disponibilité
  ressource.
- **Ambiguïté de modélisation volontaire, sans bonne réponse imposée** : chaque étape est déjà
  liée à une seule machine fixe (`machine_code`), donc la "ressource" T-R-C-O naturelle est la
  machine — mais `certifs_operateurs` parle d'un opérateur distinct de la machine, jamais
  modélisé comme une entité séparée dans cet export. Observer comment l'agent s'en sort (ignore
  la nuance opérateur/machine, la signale en avertissement, ou autre) est plus intéressant
  qu'une réponse "correcte" prédéfinie ici.

### `cellule_usinage_export.json` — cellules d'usinage CNC, files d'attente machine par cellule

La donnée la plus éloignée du DSL : aucune durée nulle part, seulement des `debut_prevu`/
`fin_prevue` (à soustraire), et une vraie **flexibilité de routage** — `AXE-4402` peut être
tourné sur `CNC-TOUR-01` (Cellule A) ou `CNC-TOUR-03` (Cellule B, machine de secours, même
réglage), donc deux `CompatibiliteRessourceTache` légitimes pour la même tâche. Teste aussi :

- **Identité de tâche ambiguë** : `AXE-4402` apparaît deux fois dans la file de la Cellule A
  (tournage puis fraisage) — une seule pièce, mais deux opérations distinctes liées par
  précédence, jamais une seule tâche répétée.
- **Compétences par personnes nommées, cette fois proprement modélisables** :
  `operateurs[].qualifications` donne directement des compétences réutilisables (contraste
  volontaire avec l'ambiguïté machine/opérateur de `fonderie_export.json`) — Nadia couvre les
  deux réglages, Julien seulement le tour, Marc aucun.

## Utilisation

Un seul outil normalisé pour les trois fichiers (`scripts/afficher_prompt_comprehension.py`) —
même prompt système, même gabarit, jamais reconstruits à la main par fichier :

```bash
# Affiche le prompt système + utilisateur réel, sans appeler le LLM (gratuit, hors ligne)
uv run python -m scripts.afficher_prompt_comprehension data/donnees_brutes/semi_structure/fonderie_export.json

# Idem, puis appelle réellement l'agent (coût réel en tokens, voir PRISME_LLM_MODEL)
uv run python -m scripts.afficher_prompt_comprehension --executer data/donnees_brutes/semi_structure/fonderie_export.json
```

(remplacer le chemin pour tester les deux autres fichiers — fonctionne aussi sur n'importe quel
autre fichier de données brutes, pas seulement ce dossier.)

Rien de ce qui précède n'est une garantie — c'est un LLM, le résultat exact varie d'un appel à
l'autre. Ce qui est vérifiable après coup, systématiquement : le garde-fou déterministe
(§6.7, `valider_payload_trco`) doit accepter ou rejeter explicitement (422), jamais laisser
passer une instance où une tâche n'a aucune compatibilité ressource-tâche déclarée.
