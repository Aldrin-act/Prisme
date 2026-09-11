# Benchmark Agent de Compréhension

Ce dossier contient le jeu de données synthétiques pour tester et évaluer l'agent de compréhension ERP → T-R-C-O.

## 📂 Contenu

```
agent_comprehension_bench/
├── README.md                    # Ce fichier
├── catalogue_traductions.json   # 60 paires (input, output attendu)
└── rapport_tests.json          # Résultats des tests (généré)
```

## 🎯 Objectif

Mesurer la capacité de l'agent à traduire correctement différents formats de données brutes (CSV, JSON ERP, texte libre) vers le format canonique T-R-C-O de PRISME.

## 📊 Catalogue généré

**60 exemples** répartis en :

| Format | Nombre | Difficulté | Caractéristiques |
|--------|--------|------------|------------------|
| CSV | 15 | Simple | Une ressource/tâche, pas de précédence |
| JSON ERP | 15 | Moyen | Work orders, précédences en chaîne, priorités |
| Texte libre | 15 | Moyen | Langage naturel français, précédences implicites |
| JSON simple | 15 | Complexe | Multi-ressources, vrai FJSP flexible |

### Caractéristiques couvertes

- ✅ Une ressource par tâche (30 cas)
- ✅ Multi-ressources (15 cas FJSP flexible)
- ✅ Absence de précédences (15 cas)
- ✅ Précédences en chaîne (15 cas)
- ✅ Précédences implicites dans texte (15 cas)
- ✅ Priorités (15 cas)
- ✅ Langage naturel français (15 cas)

## 🔧 Scripts disponibles

### 1. Génération du catalogue

```bash
# Régénérer le catalogue avec 15 exemples par format
python -m scripts.generer_jeu_donnees_comprehension

# Le fichier catalogue_traductions.json sera créé/écrasé
```

**Configuration** : Modifier `n_par_format` dans `main()` pour changer le nombre d'exemples par format.

### 2. Test de l'agent

```bash
# Mode simulation (validation structure JSON seulement)
python -m scripts.tester_agent_comprehension

# Mode réel avec LLM (nécessite MISTRAL_API_KEY)
# TODO: Implémenter l'appel LLM dans tester_exemple_simule()
```

**Output** :
- Affichage console : taux de succès global et par format/difficulté
- `rapport_tests.json` : détails complets de chaque test

### 3. Démonstration visuelle

```bash
# Voir 4 exemples complets avec output formaté
python -m scripts.demo_agent_simple
```

## 📈 Utilisation

### Phase 1 : Validation du catalogue (✅ fait)

```bash
# 1. Générer le catalogue
python -m scripts.generer_jeu_donnees_comprehension

# 2. Vérifier la structure (mode simulation)
python -m scripts.tester_agent_comprehension
```

**Résultat attendu** : 100% de succès en mode simulation (structure JSON valide).

### Phase 2 : Test avec LLM réel (🚧 à faire)

**Prérequis** :
- Variable d'environnement `MISTRAL_API_KEY` (fournisseur unique)
- Extra `.[llm]` installé (`uv sync --extra llm`)

**Modifications nécessaires** dans `tester_agent_comprehension.py` :

```python
def tester_exemple_reel(exemple: dict[str, Any]) -> ResultatTest:
    """Teste avec un vrai appel LLM."""
    from adapters.agent_comprehension import comprendre_donnees_erp
    from generation.agents.client_llm import construire_modele_comprehension

    modele = construire_modele_comprehension()

    # Appeler l'agent
    resultat = comprendre_donnees_erp(
        modele=modele,
        donnees_brutes=exemple["donnees_brutes"]
    )
    
    # Comparer avec l'attendu
    identique, differences = comparer_instances(
        exemple["instance_trco_attendue"],
        resultat.instance_brute
    )
    
    # Valider avec Pydantic
    try:
        charger_instance(resultat.instance_brute)
        instance_valide = True
    except Exception as e:
        instance_valide = False
    
    return ResultatTest(...)
```

**Puis lancer** :

```bash
export MISTRAL_API_KEY=...
uv run python -m scripts.tester_agent_comprehension
```

**Métriques attendues** :
- **Taux de succès structurel** : % d'instances T-R-C-O valides (Pydantic)
- **Taux d'exactitude** : % d'instances identiques à l'attendu
- **Coût estimé** : ~60 × $0.05 = $3 pour tout le catalogue

### Phase 3 : Analyse et amélioration

**Analyser les échecs** :

```bash
# Lire le rapport
cat validation_engine/agent_comprehension_bench/rapport_tests.json | jq '.resultats[] | select(.succes == false)'
```

**Identifier les patterns** :
- Quel format échoue le plus ?
- Quelle difficulté pose problème ?
- Quelles caractéristiques sont mal gérées ?

**Améliorer** :
1. Affiner le prompt système dans `adapters/agent_comprehension/prompt_system.py`
2. Ajouter des exemples few-shot pour les cas difficiles
3. Améliorer les instructions sur les cas ambigus
4. Régénérer et re-tester

## 🔄 Cycle de développement

```
1. Générer catalogue
   ↓
2. Tester avec LLM
   ↓
3. Analyser échecs
   ↓
4. Améliorer prompts/agent
   ↓
5. Retour à 2
```

**Objectif final** : Taux de succès structurel > 95% sur tous les formats.

## 📊 Format du catalogue

### Structure JSON

```json
{
  "metadata": {
    "total_exemples": 60,
    "formats": ["csv", "json_erp", "texte_libre", "json_simple"],
    "difficultes": ["simple", "moyen", "complexe"]
  },
  "exemples": [
    {
      "id": "csv_simple_1000",
      "format_source": "csv",
      "difficulte": "simple",
      "caracteristiques": ["une_ressource_par_tache", "pas_de_precedence"],
      "donnees_brutes": "Task,Resource,Duration_Hours\nCut,Laser,2.0",
      "instance_trco_attendue": {
        "taches": [...],
        "ressources": [...],
        "contraintes": [...],
        "objectifs": [...]
      }
    },
    ...
  ]
}
```

### Champs

- **id** : Identifiant unique (`format_difficulte_seed`)
- **format_source** : Type de données brutes
- **difficulte** : `simple` | `moyen` | `complexe`
- **caracteristiques** : Liste de tags décrivant l'exemple
- **donnees_brutes** : String raw à envoyer à l'agent
- **instance_trco_attendue** : Output T-R-C-O correct (ground truth)

## 🎓 Prochaines étapes du projet

Une fois le benchmark de l'agent validé (taux > 95%), vous pouvez passer aux phases suivantes :

### Option A : Améliorer la génération de solveurs

> Étape 6 (boucle de réparation bornée) est **implémentée** (`generation/graph.py`, StateGraph
> LangGraph avec agent Benchmarker choisissant l'algorithme par instance — cp_sat ou une
> heuristique) et câblée à l'API (`api/routes/generation.py`) — ce n'est plus un « à faire ».

**Objectif** : Mesurer et améliorer le taux de succès de la génération.

**À faire** :
1. Lancer `scripts/mesurer_taux_succes_generation.py` (mode single-shot legacy, pour itération
   rapide/économique — nécessite LLM)
2. Analyser quels types d'instances échouent (voir l'historique de tentatives par job,
   `GET /generation/jobs/{id}/historique`)
3. Améliorer les prompts dans `generation/prompts/`

### Option B : Compléter le dashboard

**Objectif** : Interface complète pour ingestion, validation humaine, exécution, diagnostics.

**À faire** :
1. Intégrer l'agent de compréhension dans le dashboard
2. Workflow d'ingestion avec prévisualisation et validation
3. Interface de diagnostic avec attribution de cause
4. Visualisation des plannings générés

**Fichiers concernés** :
- `dashboard/src/` (React/Vite)
- `api/routes/ingestion.py` (ajouter route agent)
- `api/routes/diagnostics.py` (enrichir)

### Option C : Étendre le DSL

**Objectif** : Ajouter nouveaux types de contraintes/objectifs (calendriers, setup times, etc.).

**À faire** :
1. Définir nouveaux schémas Pydantic dans `dsl/schema/`
2. Adapter la cascade de validation
3. Enrichir le générateur pour supporter ces contraintes
4. Régénérer le synthetic bench avec les nouveaux cas

**Fichiers concernés** :
- `dsl/schema/contraintes.py` (nouvelles contraintes)
- `dsl/schema/objectifs.py` (nouveaux objectifs)
- `validation_engine/cascade.py` (adapter validation)
- `generation/agents/` (enrichir prompts)

### Option D : Déploiement et scalabilité

**Objectif** : Préparer PRISME pour la production.

**À faire** :
1. PostgreSQL en production (actuellement via `DATABASE_URL`)
2. Observabilité (métriques, logs structurés, traces)
3. CI/CD complet (déploiement automatique)
4. Kubernetes / Docker Compose pour orchestration
5. Rate limiting et gestion des quotas LLM

**Fichiers concernés** :
- `.github/workflows/` (CI/CD)
- `docker-compose.yml` (à créer)
- `api/app.py` (middleware observabilité)

## 💡 Recommandations

**Pour l'apprentissage** :
1. ✅ Générez le catalogue et examinez les exemples
2. ✅ Lancez le test en mode simulation pour comprendre le flow
3. 🔄 Modifiez `tester_agent_comprehension.py` pour intégrer le LLM réel
4. 🔄 Lancez un premier test avec 5-10 exemples (économiser coûts)
5. 🔄 Analysez les premiers résultats et itérez

**Pour la suite du projet** :
- Si votre focus est **IA/LLM** : Option A (génération de solveurs)
- Si votre focus est **Frontend/UX** : Option B (dashboard)
- Si votre focus est **Modélisation** : Option C (DSL étendu)
- Si votre focus est **Ops/Infra** : Option D (déploiement)

## 📚 Références

- [CLAUDE.md](../../CLAUDE.md) - Architecture complète
- [docs/nomenclature_dsl.md](../../docs/nomenclature_dsl.md) - Vocabulaire T-R-C-O
- [adapters/agent_comprehension/](../../adapters/agent_comprehension/) - Code de l'agent
- [scripts/demo_agent_simple.py](../../scripts/demo_agent_simple.py) - Démonstration

---

**Créé le** : 2026-07-20  
**Mis à jour** : 2026-07-20  
**Statut** : Phase 1 ✅ | Phase 2 🚧 | Phase 3 ⏳
