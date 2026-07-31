# PRISME

**Génération de solveurs d'ordonnancement pilotée par IA**
Projet de Fin d'Études — EIGSI Casablanca × BARAA Consult

FJSP (Flexible Job-Shop Scheduling), algorithme choisi par instance (CP-SAT exact ou heuristique) — code généré une fois, ré-exécuté en bac à sable.

| | |
|---|---|
| Problème traité | Ordonnancement industriel (FJSP) |
| Génération | Pipeline multi-agents LLM |
| Exécution | Conteneur Docker éphémère |
| Interface | API FastAPI + tableau de bord |

---

## 1. Contexte & problématique

Le **Flexible Job-Shop Scheduling Problem** (FJSP) est NP-difficile : affecter des tâches à des ressources dans le temps, sous contraintes de précédence, de compatibilité et de délais. Deux approches existantes, deux impasses :

- **Solveur écrit à la main** — fiable, mais coûteux : il faut un expert en recherche opérationnelle par client, pour une structure de contraintes qui change à chaque nouvel atelier.
- **IA appelée à chaque exécution** — flexible, mais risqué : coût et latence à chaque run, code non reproductible, aucune trace auditable de ce qui tourne réellement en production.

---

## 2. Le principe fondateur

> **« Générer une fois. Ré-exécuter plusieurs fois. »**

L'IA écrit le code du solveur **une seule fois**, hors-ligne, à un évènement rare — nouveau client, nouvelle structure de contraintes. Une fois validé, ce code est **figé**, stocké, puis rejoué sur des données qui changent, sans jamais rappeler l'IA.

- **Le code persiste** *(performance)* — rare, offline, validé une fois par une cascade de tests, puis jamais réécrit.
- **L'exécution est jetable** *(sécurité)* — chaque run tourne dans un conteneur neuf, détruit ensuite ; aucune persistance, aucune dérive.

**Humain dans la boucle :** à chaque décision risquée — déclencher un recalcul, diagnostiquer un mauvais planning, un échec de génération — le système alerte et propose ; jamais d'action autonome.

---

## 3. Architecture globale

```
ERP propriétaire → Adaptateur (anti-corruption) → Garde-fou T-R-C-O (§6.7)
                 → Solveur figé, bac à sable (§7) → Planning / Audit
```

Le DSL **T-R-C-O** traverse toute la chaîne : format d'échange avec l'ERP, entrée de la génération IA, et cadre de validation — le même contrat partout.

---

## 4. Le DSL T-R-C-O

Un vocabulaire fini et typé — pour que l'IA ne puisse écrire que ce qu'on peut vérifier.

- **T — Tâches** : identifiant, nom, priorité informative.
- **R — Ressources** : identifiant, compétences portées.
- **C — Contraintes** : précédence · compatibilité ressource-tâche (durée) · échéance · compétence requise.
- **O — Objectifs** : 5 objectifs paramétrables et pondérables — makespan, charge, retards, utilisation, changements.

Pydantic v2, `extra="forbid"` — un identifiant borné (`Identifiant`) restreint la **surface de génération** de l'IA : c'est un contrôle de sécurité autant qu'un schéma de données.

---

## 5. Génération — pipeline multi-agents

Huit agents spécialisés, une boucle de réparation bornée :

```
Analyste → Benchmarker → Architecte → Développeur → Testeur →
   ┌─ Boucle bornée (10 tentatives max) ─────────────┐
   │  Reviewer ⇄ Debugger → Validation (cascade)      │
   └───────────────────────────────────────────────────┘
→ Documentation
```

**Benchmarker** — toujours appelé, avant l'Architecte : choisit l'algorithme dans un catalogue (CP-SAT exact, ou génétique/ACO/tabu/recuit simulé/dispatching/greedy) selon la taille et la structure de l'instance, jamais un choix fixé en dur.

Bornée, hors-ligne, diagnostique (§6.6) : après épuisement des tentatives, l'échec remonte tel quel à un humain — jamais d'acharnement automatique silencieux.

**Suivi en direct** depuis le tableau de bord via flux SSE, porté par un job en mémoire serveur — un rechargement de page rejoue l'historique exact, la génération continue même déconnecté.

---

## 6. Cascade de validation

Le code n'est jamais jugé sur sa forme — seulement sur les plannings qu'il produit.

1. **Faisabilité** — chaque instance : le planning produit respecte-t-il toutes les contraintes T-R-C-O ? Aucune exception n'est levée, chaque anomalie devient une violation nommée.
2. **Optimalité** — comparaison à un banc synthétique construit à l'envers : l'optimum est connu par construction arithmétique, sans avoir besoin d'un solveur de référence.
3. **Fidélité** — comparaison à des cas de référence réels : même affectation tâche→ressource, même makespan (comparaison partielle, pas un chronométrage strict).

Chaque instance reçoit un **diagnostic** nommant précisément la brique en échec — jamais un simple « ça ne marche pas ».

---

## 7. Sécurité — risque n°1 du projet

Exécuter du code écrit par une IA : trois couches, aucune seule suffisante.

1. **Surface bornée** — le DSL T-R-C-O limite ce que l'IA peut même exprimer en entrée, la première ligne de défense, avant toute exécution.
2. **Allowlist statique (AST)** — seuls `ortools`, `dsl`, `collections`… sont autorisés ; `eval`/`exec`/`open` rejetés avant exécution — jamais une garantie d'isolation à elle seule.
3. **Bac à sable Docker éphémère** — `--rm`, système de fichiers en lecture seule, non-root (uid 10001), **sans réseau**, limites CPU/mémoire/PID, arrêt forcé au délai.

**Test délibéré :** du code malveillant est envoyé directement au bac à sable, en contournant l'allowlist statique — pour prouver que l'isolation Docker tient *seule*.

---

## 8. Multi-tenant & authentification

Chaque compte appartient à un client — et ne voit que ses propres données.

- **Authentification JWT** — email + mot de passe, hachage bcrypt, jeton signé à chaque connexion, vérifié sur chaque route protégée.
- **Trois rôles** — opérateur, maintenant, admin ; l'admin seul voit et gère l'ensemble des clients.
- **Cloisonnement par client** — projets, instances, exécutions, solveurs : un utilisateur non-admin ne voit et n'agit que sur les données de son propre `client_id`.
- **Gestion explicite des clients** — un client se crée et se nomme explicitement, plus de tenant implicite créé silencieusement en texte libre.

---

## 9. Ingestion des données

Quatre chemins vers le même contrat T-R-C-O — aucun n'est privilégié en interne.

- **Saisie manuelle** — formulaire T-R-C-O direct dans le tableau de bord.
- **Gabarit Excel / JSON** — fichier rempli hors-ligne, déposé tel quel.
- **Adaptateur ERP dédié** — traduction déterministe écrite à la main (GreenSIG).
- **Agent de compréhension** — pour un ERP sans adaptateur, un LLM propose une traduction, jamais une vérité : le même garde-fou déterministe tranche derrière.

**Sources réutilisables :** les données brutes se persistent une fois et se reconvertissent à volonté — un nouvel essai après un rejet ne demande jamais de tout recoller.

---

## 10. Tableau de bord

Ingestion, génération, exécution, audit — une seule interface opérateur.

| Page | Rôle |
|---|---|
| Données | Sources & ingestion |
| Instances | Détail T-R-C-O, suppression |
| Concepteur DSL | Édition assistée |
| Générateur de solveurs | Suivi live, agent par agent |
| Solveurs générés | Registre figé |
| Centre d'exécution | Déclenchement en bac à sable |
| Plannings | Vue Gantt |
| Validation | Décision humaine tracée |
| Audit | Code source, sur demande |
| Analytique | Statistiques par agent |
| Clients | Gestion des tenants (admin) |
| Alertes | Notifications opérateur |

---

## 11. État d'avancement

Neuf étapes de la feuille de route, plus le tableau de bord — complètes.

| Étape | Contenu | Statut |
|---|---|---|
| 1 — DSL | Schéma T-R-C-O typé, validation croisée | ✅ fait |
| 2 — Faisabilité | Vérificateur pur, jamais d'exception | ✅ fait |
| 3 — Banc synthétique | Instances à optimum prouvable | ✅ fait |
| 4 — Générateur single-shot | Un appel IA, sans réparation | ✅ fait |
| 5 — Cascade de validation | Faisabilité → optimalité → fidélité | ✅ fait |
| 6 — Boucle de réparation | 8 agents, 10 tentatives bornées | ✅ fait |
| 7 — Store + bac à sable | Registre Postgres, Docker éphémère | ✅ fait |
| 8 — API + adaptateurs | FastAPI, ERP, agent de compréhension | ✅ fait |
| — Tableau de bord | React, multi-tenant, temps réel | ✅ fait |

---

## 12. Stack technique

**Backend**
- Python 3.11
- FastAPI
- Pydantic v2
- OR-Tools CP-SAT
- PostgreSQL
- Docker
- uv

**Frontend**
- React 19
- TanStack Start / Router
- TanStack Query
- Tailwind CSS
- shadcn/ui
- TypeScript

---

## 13. Limites connues & perspectives

Ce qui reste ouvert, en toute transparence :

- **Périmètre d'authentification** — les routes d'audit, de diagnostics et de validation n'appliquent pas encore le même cloisonnement par client que l'ingestion et l'exécution.
- **Jobs de génération en mémoire** — l'état d'un pipeline en cours vit dans le process serveur ; un redémarrage le perd. Acceptable au stade actuel, à revoir si le volume augmente.
- **Bac à sable sous Windows** — le build de l'image Docker échoue en développement local (chemin de Dockerfile) ; fonctionne tel quel en CI Linux.
- **Prochaine étape naturelle** — étendre le suivi temps réel (SSE) déjà présent sur la génération à l'exécution elle-même.

---

## Conclusion

**PRISME — générer une fois, ré-exécuter en confiance.**

Questions & discussion.
