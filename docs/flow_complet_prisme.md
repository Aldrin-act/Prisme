# Flow Complet PRISME : De l'Ingestion à l'Exécution

Ce document décrit le cycle de vie complet d'une instance de scheduling dans PRISME, de l'arrivée des données ERP jusqu'au planning généré.

## 🔄 Vue d'ensemble

```
┌─────────────┐
│ Données ERP │ (CSV, JSON, texte libre, format propriétaire)
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ ÉTAPE 1 : INGESTION & TRADUCTION                            │
│ • Adaptateur (erp_reference, greensig) OU                   │
│ • Agent de compréhension (universel via LLM)                │
│ → Instance T-R-C-O canonique                                │
│ → Validation Pydantic (§6.7 garde-fou)                      │
└──────┬──────────────────────────────────────────────────────┘
       │ instance_trco: InstanceTRCO
       ▼
┌─────────────────────────────────────────────────────────────┐
│ ÉTAPE 2 : GÉNÉRATION DU SOLVEUR (première fois seulement)   │
│ • Benchmarker choisit l'algorithme (cp_sat exact, ou une     │
│   heuristique genetic/aco/tabu/... pour les grandes instances)│
│ • LLM génère le code pour cet algorithme                    │
│ • Validation statique (AST allowlist)                       │
│ • Exécution test sur instance source                        │
│ • Cascade de validation (faisabilité, optimalité, fidélité)│
│ → Code Python frozen                                        │
└──────┬──────────────────────────────────────────────────────┘
       │ solveur_validé: bytes (fichier .py)
       ▼
┌─────────────────────────────────────────────────────────────┐
│ ÉTAPE 3 : STOCKAGE                                          │
│ • Enregistrement dans solver_store/                         │
│   - artifacts/<sha256>.py (code)                            │
│   - registry PostgreSQL (métadonnées)                       │
│ • Indexé par : client_id + signature contraintes           │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ ÉTAPE 4 : EXÉCUTION (à chaque changement de données)       │
│ • Lookup solveur par signature exacte                       │
│ • Sandbox Docker : exécution isolée                         │
│   - Read-only, no network, resource limits                  │
│   - Timeout configurable                                    │
│ → Planning brut                                             │
└──────┬──────────────────────────────────────────────────────┘
       │ planning_brut: Planning | None
       ▼
┌─────────────────────────────────────────────────────────────┐
│ ÉTAPE 5 : VALIDATION OPÉRATIONNELLE (§6.7)                 │
│ • Feasibility checker : contraintes respectées ?            │
│   - Précédences                                             │
│   - Compatibilité ressource-tâche                           │
│   - Unicité d'allocation                                    │
│ → Si invalide : alerte humain, pas d'action auto           │
└──────┬──────────────────────────────────────────────────────┘
       │ planning_valide: Planning
       ▼
┌─────────────────────────────────────────────────────────────┐
│ ÉTAPE 6 : OUTPUT                                            │
│ • Canal opérationnel : /planning/{instance_id}              │
│   → JSON Planning (dates, ressources, makespan)            │
│ • Canal audit : /audit/solver/{client_id}                   │
│   → Code source Python (sur demande explicite)             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📍 Vous êtes ici

**Après l'ingestion** (Étape 1 ✅), vous avez une `InstanceTRCO` valide.

**Prochaine étape** : **Génération du solveur** (Étape 2).

---

## 🎯 Étape 2 : Génération du Solveur (détaillée)

### Principe generate-once, execute-many

> **Innovation centrale de PRISME** : Le code du solveur est généré **une seule fois** par le LLM, validé, puis **gelé et ré-exécuté** sur des données changeantes sans jamais rappeler le LLM.

### 2.1 Quand générer ?

Un nouveau solveur est généré **uniquement** si :

1. **Nouveau client** : `client_id` jamais vu
2. **Nouvelle signature de contraintes** : même client, mais nouvelles combinaisons de contraintes

**Exemples** :

```python
# Instance A : 3 tâches, precedence + compatibilite_ressource_tache
# Signature : "compatibilite_ressource_tache,precedence"
# → Génère solveur_A

# Instance B : 5 tâches, mais MÊMES types de contraintes
# Signature : "compatibilite_ressource_tache,precedence"
# → Réutilise solveur_A (pas de nouvelle génération)

# Instance C : + contrainte de capacité
# Signature : "capacite,compatibilite_ressource_tache,precedence"
# → Génère solveur_C (nouvelle signature)
```

### 2.2 Processus de génération (Étape 4 - single-shot)

**Fichiers** : `generation/tentative_unique.py`, `generation/agents/`

```python
# 1. Appel LLM avec prompt structuré
code_genere = agent_generation.generer_solveur(instance_trco)
# → Code Python utilisant OR-Tools CP-SAT

# 2. Validation statique (AST allowlist)
validation_statique.verifier(code_genere)
# → Rejette si : eval, exec, __import__, open, escape dunder

# 3. Exécution test sur instance source
planning_test = executer.executer_code(code_genere, instance_trco)
# → Exception si crash, None si infeasible

# 4. Cascade de validation (Étape 5)
verdict = cascade.evaluer_cascade(lambda inst: executer_code(code_genere, inst))
# → VerdictCascade avec diagnostics par brique
```

### 2.3 Cascade de validation (3 briques)

**Fichier** : `validation_engine/cascade.py`

| Brique | Teste quoi | Critère succès |
|--------|------------|----------------|
| **Faisabilité** | Toutes instances réelles | Planning légal (contraintes respectées) |
| **Optimalité** | Synthetic bench (10-80 tâches) | Makespan = optimum connu (construction inverse) |
| **Fidélité** | Reference cases (3 cas) | Mêmes affectations tâche→ressource, même makespan |

**Verdict** :
- ✅ **VERT** : 3 briques OK → solveur enregistrable
- ⚠️ **ORANGE** : faisabilité OK, optimalité/fidélité partielle → alerte
- ❌ **ROUGE** : faisabilité échouée → rejet

**Important** : Le registre **refuse** d'enregistrer un solveur non-vert (§6.7).

### 2.4 Boucle de réparation (Étape 6 - actuellement skippée)

**Status** : Délibérément non implémentée (décision de priorisation).

**Concept** :
```python
for tentative in range(MAX_TENTATIVES):
    code = generer()
    verdict = cascade(code)
    
    if verdict.vert:
        return code  # Succès
    
    # Diagnostic : quelle brique a échoué ?
    feedback = diagnostiquer(verdict)
    
    # Réparation ciblée
    code = reparer(code, feedback)

return None  # Échec après N tentatives
```

**Fichiers à créer** :
- `generation/loop.py` : boucle bornée
- `generation/failures/` : diagnostic d'échecs

---

## 🚀 Comment tester la génération

### Option 1 : Avec un solveur de référence (déjà fait)

```bash
# Enregistrer le solveur minimal (hand-written)
uv run python -m scripts.enregistrer_solveur_reference

# Tester le flow complet end-to-end
uv run python -m scripts.demo_bout_en_bout
```

**Ce qui se passe** :
1. Charge une instance exemple
2. Lookup solveur (trouve le référence)
3. Exécute dans sandbox Docker
4. Valide feasibility
5. Retourne Planning JSON

### Option 2 : Mesurer le taux de succès du générateur LLM

```bash
# Nécessite : PRISME_LLM_PROVIDER et clé API
export PRISME_LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-...

# Lance N générations sur des instances variées
uv run python -m scripts.mesurer_taux_succes_generation
```

**Actuellement** : Non lancé en production (coût LLM).

**Ce script fait** :
1. Charge le synthetic bench
2. Pour chaque instance : génère un solveur
3. Exécute la cascade
4. Mesure : % vert, % orange, % rouge
5. Coût estimé : ~$1-5 selon modèle et taille

### Option 3 : Génération manuelle d'un cas

```python
from generation.tentative_unique import generer_et_valider
from dsl.validation.charger_instance import charger_instance_depuis_fichier

# Charger instance
instance = charger_instance_depuis_fichier("dsl/examples/valid/atelier_trois_taches.json")

# Générer
resultat = generer_et_valider(instance, client_id="test_manuel")

if resultat.succes:
    print(f"✅ Solveur généré : {resultat.verdict}")
    print(f"Code : {resultat.code_genere[:200]}...")
else:
    print(f"❌ Échec : {resultat.erreur}")
```

---

## 📊 Étapes suivantes et leur statut

| Étape | Nom | Status | Fichiers clés |
|-------|-----|--------|---------------|
| 1 | Ingestion + validation | ✅ Fait | `api/routes/ingestion.py`, `adapters/` |
| 2 | Feasibility checker | ✅ Fait | `validation_engine/feasibility_checker.py` |
| 3 | Synthetic bench | ✅ Fait | `validation_engine/synthetic_bench/` |
| 4 | Générateur single-shot | ✅ Fait | `generation/tentative_unique.py` |
| 5 | Cascade validation | ✅ Fait | `validation_engine/cascade.py` |
| 6 | Boucle réparation | ❌ Skippée | `generation/loop.py` (à créer) |
| 7 | Store + sandbox | ✅ Fait | `solver_store/`, `sandbox/` |
| 8 | API + exécution | ✅ Fait | `api/routes/execution.py` |
| 9 | Dashboard | ✅ Fait (Phase 10) | `dashboard/` |

---

## 🎯 Que faire maintenant ?

### Scénario A : Vous voulez tester le flow complet SANS générer de code

**Utilisez le solveur de référence** (hand-written, déjà enregistré) :

```bash
# 1. Enregistrer le solveur minimal
uv run python -m scripts.enregistrer_solveur_reference

# 2. Lancer la démo bout en bout
uv run python -m scripts.demo_bout_en_bout

# 3. Tester l'API
uv run uvicorn api.app:app --reload

# 4. Dans un autre terminal, appeler l'API
curl -X POST http://localhost:8000/execution/client_test_1 \
  -H "Content-Type: application/json" \
  -d @dsl/examples/valid/atelier_trois_taches.json
```

**Vous verrez** : Planning JSON avec affectations tâche→ressource et dates.

### Scénario B : Vous voulez tester la génération avec le LLM

**Prérequis** :
```bash
# Installer extra LLM
uv sync --extra llm

# Variables d'environnement
export PRISME_LLM_PROVIDER=anthropic  # ou openai, mistralai
export ANTHROPIC_API_KEY=sk-ant-...  # votre clé
```

**Tester sur 1 instance** :

```python
# test_generation_manuelle.py
from generation.tentative_unique import generer_et_valider
from dsl.examples import EXEMPLE_TROIS_TACHES

resultat = generer_et_valider(EXEMPLE_TROIS_TACHES, client_id="demo")

print(f"Succès : {resultat.succes}")
print(f"Verdict : {resultat.verdict}")

if resultat.succes:
    with open("solveur_genere.py", "w") as f:
        f.write(resultat.code_genere)
    print("Code sauvegardé : solveur_genere.py")
```

**Tester sur tout le bench** :

```bash
uv run python -m scripts.mesurer_taux_succes_generation
```

**Coût estimé** : 
- Claude Sonnet 4.5 : ~$0.05-0.10 par génération
- Synthetic bench (34 instances) : ~$2-4
- Taux de succès attendu : 60-80% (non mesuré en pratique encore)

### Scénario C : Vous voulez implémenter la boucle de réparation (Étape 6)

**Marche à suivre** :

1. **Créer** `generation/loop.py` :

```python
from generation.tentative_unique import generer_et_valider
from validation_engine.cascade import evaluer_cascade

def generer_avec_reparation(
    instance: InstanceTRCO,
    client_id: str,
    max_tentatives: int = 3
) -> ResultatGeneration | None:
    """Génère un solveur avec boucle de réparation bornée."""
    
    for i in range(max_tentatives):
        resultat = generer_et_valider(instance, client_id, tentative=i)
        
        if resultat.verdict.est_vert():
            return resultat  # Succès
        
        # Diagnostic : quelle brique a échoué ?
        feedback = diagnostiquer_echec(resultat.verdict)
        
        # Prompt de réparation
        # TODO: enrichir le prompt avec le feedback
    
    return None  # Échec après N tentatives
```

2. **Créer** `generation/failures/diagnostic.py` :

```python
def diagnostiquer_echec(verdict: VerdictCascade) -> str:
    """Analyse le verdict et retourne feedback structuré."""
    
    if not verdict.faisabilite_ok:
        return "Le solveur génère des plannings illégaux (contraintes violées)"
    
    if not verdict.optimalite_ok:
        return "Le solveur ne trouve pas les optimums connus (sous-optimal)"
    
    if not verdict.fidelite_ok:
        return "Le solveur ne reproduit pas les cas de référence"
    
    return "Échec inconnu"
```

3. **Tester** la boucle :

```bash
uv run python -m generation.loop --instance dsl/examples/valid/atelier_trois_taches.json
```

---

## 🔄 Résumé du flow POST-ingestion

**Première fois** (nouveau client ou nouvelle signature) :

```
InstanceTRCO → Génération LLM → Validation cascade → Stockage → Exécution
   (1min)          (30s)              (10s)            (1s)       (2s)
```

**Fois suivantes** (même signature, données différentes) :

```
InstanceTRCO → Lookup → Exécution sandbox → Validation feasibility → Planning
   (instant)     (0.1s)        (2s)                (0.5s)             (JSON)
```

**Human-in-the-loop** :
- Génération échouée → alerte + arrêt (pas de retry automatique infini)
- Diagnostic d'échec d'exécution → attribution cause + proposition humain

---

## 📚 Références

- [CLAUDE.md](../CLAUDE.md) - Architecture complète, sections §5, §6.7
- [PRISME_Note_de_Cadrage (2).md](<../PRISME_Note_de_Cadrage (2).md>) - Spec détaillée
- [generation/README.md](../generation/README.md) - (à créer) Doc génération
- [validation_engine/README.md](../validation_engine/README.md) - (à créer) Doc cascade

---

## 💡 Recommandations

**Pour apprendre le système** :
1. ✅ Lancez `demo_bout_en_bout.py` avec le solveur référence
2. 🔄 Examinez le code généré (si disponible) dans `solver_store/artifacts/`
3. 🔄 Testez l'API avec Postman/curl
4. 🔄 Explorez le dashboard (`cd dashboard && npm run dev`)

**Pour contribuer** :
- **Facile** : Améliorer les prompts dans `generation/agents/`
- **Moyen** : Implémenter la boucle de réparation (Étape 6)
- **Avancé** : Étendre le DSL avec nouveaux types de contraintes

---

**Dernière mise à jour** : 2026-07-20  
**Auteur** : Documentation PRISME
