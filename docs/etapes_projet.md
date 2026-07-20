# Étapes du Projet PRISME

Ce document liste **toutes les étapes** du projet PRISME de bout en bout, leur statut actuel, et ce qui reste à faire.

---

## 📊 Vue d'ensemble

| # | Étape | Status | Priorité | Temps estimé |
|---|-------|--------|----------|--------------|
| 1 | DSL T-R-C-O | ✅ Terminé | - | - |
| 2 | Feasibility Checker | ✅ Terminé | - | - |
| 3 | Synthetic Bench | ✅ Terminé | - | - |
| 4 | Générateur Single-Shot | ✅ Terminé | - | - |
| 5 | Cascade de Validation | ✅ Terminé | - | - |
| 6 | Boucle de Réparation | ❌ Skippée | Moyenne | 2-3 jours |
| 7 | Store + Sandbox | ✅ Terminé | - | - |
| 8 | API + Adaptateurs ERP | ✅ Terminé | - | - |
| 9 | Documentation Technique | 🚧 Partiel | Haute | 1 semaine |
| 10 | Dashboard (Phase 10) | ✅ Terminé | - | - |
| 11 | Déploiement Production | ⏳ Pas commencé | Haute | 1 semaine |
| 12 | Monitoring & Observabilité | ⏳ Pas commencé | Moyenne | 3-4 jours |

**Légende** :
- ✅ Terminé et testé
- 🚧 En cours ou partiel
- ❌ Skippé volontairement
- ⏳ Pas encore commencé

---

## 🔍 Détail des étapes

### ✅ Étape 1 : DSL T-R-C-O (Terminé)

**Objectif** : Définir le langage canonique pour exprimer les problèmes de scheduling.

**Livrables** :
- `dsl/schema/taches.py` - Modèle Tâche
- `dsl/schema/ressources.py` - Modèle Ressource
- `dsl/schema/contraintes.py` - Union discriminée de contraintes
- `dsl/schema/objectifs.py` - Objectifs d'optimisation
- `dsl/schema/instance.py` - Agrégat racine `InstanceTRCO`
- `dsl/schema/planning.py` - Modèle Planning (output)
- `dsl/validation/charger_instance.py` - Validation Pydantic v2

**Ce qui a été fait** :
- ✅ Contraintes : `precedence`, `compatibilite_ressource_tache`
- ✅ Objectif : `minimiser_makespan`
- ✅ Validation cross-axes (IDs uniques, références valides)
- ✅ Extra `forbid` sur tous les modèles
- ✅ Exemples valides : 3 fichiers JSON dans `dsl/examples/valid/`

**Ce qui manque** :
- ⏳ Contraintes avancées : capacité, calendriers, setup times
- ⏳ Objectifs multi-critères : équilibrage charge, retards
- ⏳ Documentation DSL complète (référence API)

**Tests** :
- `tests/unit/test_dsl_validation.py` - 15 tests, tous passent

---

### ✅ Étape 2 : Feasibility Checker (Terminé)

**Objectif** : Vérifier qu'un planning respecte toutes les contraintes sans lancer OR-Tools.

**Livrables** :
- `validation_engine/feasibility_checker.py`
- Fonction `verifier_faisabilite(instance, planning) -> ResultatFaisabilite`

**Ce qui a été fait** :
- ✅ Vérification précédences (avant → après)
- ✅ Vérification compatibilité ressource-tâche (durée correcte)
- ✅ Vérification unicité affectation (1 tâche = 1 ressource)
- ✅ Vérification non-chevauchement sur ressources
- ✅ Vérification cohérence temporelle (debut + duree = fin)
- ✅ Pure, jamais d'exception (retourne violations)

**Tests** :
- `tests/unit/test_feasibility_checker.py` - 12 tests, tous passent

---

### ✅ Étape 3 : Synthetic Bench (Terminé)

**Objectif** : Générer des instances avec optimum connu pour valider l'optimalité des solveurs.

**Livrables** :
- `validation_engine/synthetic_bench/construction_inverse.py`
- `validation_engine/synthetic_bench/catalogue.py`
- `validation_engine/synthetic_bench/stockage.py`
- `scripts/generer_banc_synthetique.py`

**Ce qui a été fait** :
- ✅ Construction inverse : planning → instance
- ✅ Catalogue : 34 instances (1 → 80 tâches)
- ✅ Jobs en chaîne sur ressources dédiées (optimum prouvable)
- ✅ Sauvegarde JSON : `validation_engine/synthetic_bench/instances/`
- ✅ Régénérable à tout moment

**Tests** :
- `tests/unit/test_synthetic_bench.py` - 8 tests, tous passent

---

### ✅ Étape 4 : Générateur Single-Shot (Terminé)

**Objectif** : Générer du code CP-SAT via LLM en un seul appel (pas de boucle de réparation).

**Livrables** :
- `generation/client_llm.py` - Client unifié (Anthropic, OpenAI, Mistral)
- `generation/agents/` - Agents spécialisés (génération, compréhension)
- `generation/validation_statique.py` - AST allowlist
- `generation/executer.py` - Exec isolé du code généré
- `generation/tentative_unique.py` - Orchestration single-shot

**Ce qui a été fait** :
- ✅ Support 3 providers : `PRISME_LLM_PROVIDER`
- ✅ AST allowlist : ortools, dsl, collections, typing seulement
- ✅ Rejet : eval, exec, __import__, open, dunder escapes
- ✅ Génération → validation statique → exécution → cascade
- ✅ Gestion erreurs (runtime exceptions swallowed)

**Ce qui manque** :
- ⏳ Boucle de réparation (Étape 6)
- ⏳ Few-shot learning avec exemples réussis
- ⏳ Mesure taux de succès en production (jamais lancé avec vrai LLM)

**Tests** :
- `tests/unit/test_agent_comprehension.py` - 3 tests (mock LLM)
- `tests/generation_stability/` - (à créer)

---

### ✅ Étape 5 : Cascade de Validation (Terminé)

**Objectif** : Valider un solveur sur 3 dimensions : faisabilité, optimalité, fidélité.

**Livrables** :
- `validation_engine/cascade.py`
- Fonction `evaluer_cascade(solveur) -> VerdictCascade`
- `validation_engine/stability_test.py`

**Ce qui a été fait** :
- ✅ Brique 1 : Faisabilité (toutes instances réelles)
- ✅ Brique 2 : Optimalité (synthetic bench, makespan = optimum)
- ✅ Brique 3 : Fidélité (reference_cases, affectations identiques)
- ✅ Verdict : VERT (3 OK) / ORANGE (partiel) / ROUGE (échec)
- ✅ Diagnostic par instance (quelle brique a échoué)
- ✅ Test de stabilité : N runs → même makespan

**Tests** :
- `tests/unit/test_cascade.py` - 10 tests, tous passent
- `tests/property_based/` - (à créer)

---

### ❌ Étape 6 : Boucle de Réparation (Skippée)

**Objectif** : Retry intelligente en cas d'échec de génération avec feedback diagnostic.

**Livrables prévus** :
- `generation/loop.py` - Boucle bornée (max tentatives)
- `generation/failures/diagnostic.py` - Attribution de cause
- `generation/failures/strategies.py` - Stratégies de réparation

**Pourquoi skippée** :
- Décision de priorisation (Étape 8 avant Étape 6)
- Le single-shot suffit pour la démo
- Complexité élevée pour gain incertain

**Ce qui reste à faire** :
```python
def generer_avec_reparation(instance, max_tentatives=3):
    for i in range(max_tentatives):
        code = generer_single_shot(instance)
        verdict = cascade(code)
        
        if verdict.vert:
            return code  # Succès
        
        # Diagnostic
        feedback = diagnostiquer(verdict)
        
        # Enrichir prompt avec feedback
        # TODO: implémenter stratégies de réparation
    
    return None  # Échec après N tentatives
```

**Temps estimé** : 2-3 jours
**Priorité** : Moyenne (nice-to-have, pas bloquant)

---

### ✅ Étape 7 : Store + Sandbox (Terminé)

**Objectif** : Stockage persistant des solveurs + exécution isolée dans Docker.

**Livrables** :
- `solver_store/registry.py` - Registre PostgreSQL
- `solver_store/artifacts/` - Code Python frozen
- `sandbox/runner.py` - Orchestration Docker
- `sandbox/container/` - Dockerfile + harness
- `sandbox/executer_dans_conteneur.py` - Harness in-container

**Ce qui a été fait** :
- ✅ PostgreSQL (via `DATABASE_URL`) : un schéma par instance
- ✅ Artifacts sur disque (SHA-256, jamais dans BDD)
- ✅ Index : client_id + signature contraintes
- ✅ Refuse solveurs non-verts (§6.7)
- ✅ Sandbox Docker :
  - Image `prisme-sandbox` (Debian + Python 3.11 + OR-Tools)
  - `--rm`, `--network none`, read-only rootfs
  - uid 10001 (non-root)
  - CPU/mem/PID limits, timeout force-kill
- ✅ Harness enregistre module dans `sys.modules` (fix dataclasses)

**Tests** :
- `tests/integration/test_registry.py` - 6 tests (skip si pas Postgres)
- `tests/integration/test_sandbox_*.py` - 4 tests (skip si pas Docker)
- `tests/integration/test_sandbox_securite.py` - Prouve isolation

**Bug fixés (Phase PH0-T4)** :
- ✅ Dataclasses crash corrigé (`sys.modules` registration)
- ✅ Tests Docker passent en vrai (pas juste en mock)

---

### ✅ Étape 8 : API + Adaptateurs ERP (Terminé)

**Objectif** : API REST + couche anti-corruption pour ERP propriétaires.

**Livrables** :
- `api/app.py` - FastAPI
- `api/routes/ingestion.py` - POST /ingestion/
- `api/routes/execution.py` - POST /execution/{instance_id}
- `api/routes/planning.py` - GET /planning/{instance_id}
- `api/routes/audit.py` - GET /audit/solver/{client_id}
- `api/routes/diagnostics.py` - Diagnostic d'échecs
- `api/routes/supervision.py` - Vues dashboard
- `adapters/erp_reference/` - Adaptateur démo (format pauvre)
- `adapters/greensig/` - Adaptateur client réel (si applicable)
- `adapters/agent_comprehension/` - Adaptateur LLM universel

**Ce qui a été fait** :
- ✅ Routes CRUD complètes
- ✅ Validation §6.7 : `input_validation/` avant ingestion
- ✅ Lookup solveur : par `client_id` + signature **exacte**
- ✅ Canaux séparés : opérationnel (/planning) vs audit (/audit)
- ✅ Adaptateur référence : format legacy → InstanceTRCO
- ✅ Agent de compréhension : universel via LLM
- ✅ Dependency injection : `api/dependencies.py`

**Tests** :
- `tests/integration/test_api_bout_en_bout.py` - Flow complet
- `tests/integration/test_api_adapters.py` - Adaptateurs

**Bug fixés (Phase PH0-T4)** :
- ✅ `demo_bout_en_bout.py` passe en vrai end-to-end

---

### 🚧 Étape 9 : Documentation Technique (Partielle)

**Objectif** : Documentation complète pour développeurs et utilisateurs.

**Livrables prévus** :
- `docs/architecture.md` - Architecture globale
- `docs/dsl_reference.md` - Référence complète DSL
- `docs/api_reference.md` - Documentation API (OpenAPI)
- `docs/deployment.md` - Guide déploiement
- `docs/contributing.md` - Guide contribution
- `README.md` - Vue d'ensemble projet

**Ce qui a été fait** :
- ✅ `CLAUDE.md` - Instructions pour Claude Code (200 lignes)
- ✅ `CONTRIBUTING.md` - Workflow développement
- ✅ `docs/nomenclature_dsl.md` - Vocabulaire officiel
- ✅ `docs/objectifs_configurables.md` - Objectifs paramétrables
- ✅ `docs/flow_complet_prisme.md` - Flow end-to-end
- ✅ `docs/etapes_projet.md` - Ce document
- ✅ `validation_engine/agent_comprehension_bench/README.md`
- ✅ `scripts/README_MIGRATION.md`

**Ce qui manque** :
- ⏳ Référence DSL complète (tous les modèles Pydantic)
- ⏳ Documentation API générée (Swagger)
- ⏳ Tutoriels : premiers pas, cas d'usage avancés
- ⏳ Architecture decision records (ADRs)
- ⏳ Guide opérationnel : incidents, runbooks

**Priorité** : Haute (bloquant pour adoption)
**Temps estimé** : 1 semaine

---

### ✅ Étape 10 : Dashboard (Phase 10, Terminé)

**Objectif** : Interface web React pour ingestion, validation, exécution, diagnostics.

**Livrables** :
- `dashboard/` - React + Vite
- Ingestion avec prévisualisation
- Validation humaine (human-in-the-loop)
- Visualisation plannings
- Diagnostic en live

**Ce qui a été fait** :
- ✅ Setup React/Vite
- ✅ Ingestion avec formulaire
- ✅ Affichage instances
- ✅ Lancement exécution
- ✅ Visualisation diagnostics
- ✅ UI/UX responsive

**Comment lancer** :
```bash
cd dashboard
npm install
npm run dev
# → http://localhost:5173
```

---

### ⏳ Étape 11 : Déploiement Production (Pas commencé)

**Objectif** : Infrastructure production-ready avec CI/CD complet.

**Livrables prévus** :
- `docker-compose.yml` - Orchestration locale
- `k8s/` - Manifests Kubernetes
- `.github/workflows/deploy.yml` - CD pipeline
- `terraform/` ou `pulumi/` - Infrastructure as Code
- Configuration secrets (Vault, AWS Secrets Manager)
- Reverse proxy (Nginx, Traefik)
- SSL/TLS (Let's Encrypt)

**Ce qui manque** :
- ⏳ Docker Compose multi-services
- ⏳ Helm charts Kubernetes
- ⏳ CD automatique (staging → prod)
- ⏳ Gestion secrets sécurisée
- ⏳ Load balancing
- ⏳ Auto-scaling

**Stack suggérée** :
```yaml
Services:
  - api: FastAPI (Gunicorn + Uvicorn workers)
  - postgres: PostgreSQL 15+
  - redis: Cache + job queue
  - nginx: Reverse proxy + SSL
  - dashboard: Static build (React)
  
Infra:
  - Kubernetes (GKE, EKS, AKS)
  - Cloud storage (S3) pour artifacts
  - Cloud SQL managé (Postgres)
```

**Priorité** : Haute (pour mise en production)
**Temps estimé** : 1 semaine

---

### ⏳ Étape 12 : Monitoring & Observabilité (Pas commencé)

**Objectif** : Visibilité sur le système en production (métriques, logs, traces, alertes).

**Livrables prévus** :
- `observability/` - Config Prometheus, Grafana, Loki
- Métriques métier :
  - Taux de succès génération
  - Latence exécution sandbox
  - Coût LLM mensuel
  - Nombre solveurs enregistrés
- Logs structurés (JSON)
- Distributed tracing (OpenTelemetry)
- Alertes (PagerDuty, Slack)
- Dashboards Grafana

**Stack suggérée** :
- **Métriques** : Prometheus + Grafana
- **Logs** : Loki ou ELK
- **Traces** : Jaeger ou Tempo
- **Alertes** : Alertmanager → Slack/PagerDuty
- **APM** : Sentry pour erreurs Python

**Métriques clés** :
```python
# Génération
generation_success_rate         # %
generation_duration_seconds     # histogram
generation_cost_dollars         # counter

# Exécution
execution_duration_seconds      # histogram
execution_failures_total        # counter
sandbox_timeout_total          # counter

# Validation
feasibility_violations_total    # counter
cascade_verdict_distribution    # gauge (vert/orange/rouge)

# Infrastructure
postgres_connections_active     # gauge
docker_containers_running       # gauge
api_request_duration_seconds    # histogram
```

**Priorité** : Moyenne (important post-déploiement)
**Temps estimé** : 3-4 jours

---

## 🗺️ Roadmap Recommandée

### Phase 1 : Compléter les fondations (2 semaines)

**Semaine 1** :
1. ✅ Créer jeu de données agent compréhension (fait)
2. 🚧 Tester génération avec LLM réel (taux de succès)
3. 🚧 Compléter documentation DSL
4. 🚧 Créer tutoriel "Premiers pas"

**Semaine 2** :
1. 🚧 Implémenter boucle de réparation (Étape 6)
2. 🚧 Tests property-based pour cascade
3. 🚧 Documentation API complète
4. 🚧 Guide déploiement

### Phase 2 : Production-ready (2 semaines)

**Semaine 3** :
1. ⏳ Docker Compose multi-services
2. ⏳ CI/CD complet (deploy staging)
3. ⏳ Secrets management
4. ⏳ SSL/TLS + domaines

**Semaine 4** :
1. ⏳ Kubernetes manifests
2. ⏳ Auto-scaling config
3. ⏳ Monitoring stack
4. ⏳ Runbooks incidents

### Phase 3 : Amélioration continue (ongoing)

- Étendre DSL (nouvelles contraintes)
- Améliorer taux succès génération (prompts, few-shot)
- Optimiser performance (cache, indexes DB)
- A/B testing différents modèles LLM
- Features dashboard avancées

---

## 📈 Métriques de Succès

### Techniques

| Métrique | Objectif | Actuel | Status |
|----------|----------|--------|--------|
| Taux succès génération | > 80% | ❓ Non mesuré | ⏳ |
| Latence exécution sandbox | < 5s (p95) | ~2s | ✅ |
| Disponibilité API | > 99.5% | N/A (pas prod) | ⏳ |
| Couverture tests | > 80% | ~70% | 🚧 |
| Taux conformité cascade | > 95% vert | ❓ Non mesuré | ⏳ |

### Fonctionnelles

| Métrique | Objectif | Actuel | Status |
|----------|----------|--------|--------|
| Formats ERP supportés | ≥ 3 | 2 (ref + universel) | 🚧 |
| Types contraintes | ≥ 5 | 2 (prec + compat) | 🚧 |
| Taille max instance | 200 tâches | 80 (bench) | 🚧 |
| Délai mise en prod | < 4 semaines | ∞ (pas prod) | ⏳ |

---

## 🎯 Prochaines Actions Immédiates

### Si votre focus est **Recherche/IA** :
1. Tester génération avec LLM réel
2. Mesurer taux de succès sur synthetic bench
3. Implémenter boucle de réparation
4. Améliorer prompts (few-shot learning)

### Si votre focus est **Engineering/Système** :
1. Docker Compose complet
2. Setup Kubernetes local (Minikube)
3. CI/CD pipeline
4. Monitoring stack (Prometheus + Grafana)

### Si votre focus est **Produit/UX** :
1. Compléter dashboard (nouvelles features)
2. Tutoriels utilisateur
3. Tests utilisateurs
4. Roadmap features métier

### Si votre focus est **Documentation** :
1. Référence DSL complète
2. Guide déploiement
3. ADRs (Architecture Decision Records)
4. Vidéos démo

---

## 📚 Références

- [CLAUDE.md](../CLAUDE.md) - Instructions développement
- [PRISME_Note_de_Cadrage (2).md](<../PRISME_Note_de_Cadrage (2).md>) - Spec détaillée
- [flow_complet_prisme.md](flow_complet_prisme.md) - Flow end-to-end
- [nomenclature_dsl.md](nomenclature_dsl.md) - Vocabulaire officiel

---

**Dernière mise à jour** : 2026-07-20  
**Version** : 1.0  
**Statut global** : 70% complet (7/10 étapes principales terminées)
