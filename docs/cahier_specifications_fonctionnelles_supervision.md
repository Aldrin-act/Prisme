# Cahier de spécifications fonctionnelles — Agent de Supervision

> Périmètre : le module de supervision (§2, MT7 du plan directeur) — `supervision/`,
> `api/routes/supervision.py`, page `Supervision` du frontend. Document rédigé à partir du code
> réellement en place à ce jour, pas du plan directeur ni d'une version antérieure.
>
> **Écart avec `Section_7.6.3_La_page_de_supervision.md`** : ce document (à la racine du dépôt)
> décrit encore la détection comme "trois détecteurs déterministes, purs et sans appel LLM". Ce
> n'est plus le cas : la détection elle-même passe désormais par un appel LLM
> (`supervision/agent.py::detecter_signaux_llm`), Python ne fait plus que rassembler les faits
> bruts et vérifier après coup ce que le modèle en tire. Voir §3 et §4.1 ci-dessous pour le
> fonctionnement réel. Section_7.6.3 n'a pas été modifié — à traiter séparément.

## 1. Présentation générale

### 1.1 Objectif

Détecter automatiquement des situations qui méritent l'attention d'un humain sur le parc
d'instances d'un client (solveur devenu inutilisable, planning périmé, exécutions en échec
répété), et **proposer** une action corrective sans jamais l'appliquer seule. L'agent complète le
pipeline : il ne remplace ni la génération, ni l'exécution, ni le diagnostic — il déclenche ceux-ci
sur décision humaine explicite.

### 1.2 Principe fondateur applicable

Humain dans la boucle (note de cadrage, principe non négociable) : à chaque décision à risque, le
système alerte et propose, un humain décide. L'agent de supervision en est l'implémentation directe
pour le cycle de vie des solveurs et des exécutions.

### 1.3 Rattachement

- Backend : `supervision/agent.py` (appels LLM), `supervision/detecteurs.py` (assemblage des faits
  + validation), `supervision/orchestrateur.py` (cycle complet + persistance),
  `supervision/planificateur.py` (déclenchement périodique optionnel),
  `supervision/prompts/{detection,supervision}.md` (prompts).
- API : `api/routes/supervision.py`.
- Frontend : `Front/prismatron-solver-forge/src/routes/_authenticated/supervision.tsx`.

## 2. Acteurs

| Acteur | Rôle |
|---|---|
| Opérateur / responsable client | Consulte les propositions de son client, les accepte ou les refuse. |
| Administrateur | Idem, sur tous les clients ; peut filtrer l'analyse manuelle par client ou l'exécuter sur tous à la fois. |
| Boucle périodique (système) | Optionnelle, désactivée par défaut — déclenche `analyser_et_proposer` pour chaque client connu, à intervalle régulier, sans intervention humaine pour le *déclenchement* (jamais pour l'action elle-même). |

## 3. Vue d'ensemble du fonctionnement

```
Déclenchement (manuel "Analyser maintenant" | boucle périodique)
        │
        ▼
Assemblage des faits bruts (instances, solveurs actifs, historique d'exécutions du client)
        │
        ▼
Appel LLM n°1 — détection (detecter_signaux_llm)
  → le modèle compare instance_id / dates / historique d'échecs et décide seul
    quel signal s'applique à quelle instance ; rien n'est précalculé côté Python
        │
        ▼
Validation déterministe (detecter_signaux)
  → tout identifiant recopié par le LLM (instance_id, id_solveur_disponible, execution_id)
    qui ne correspond à aucune donnée réellement fournie est écarté silencieusement
        │
        ▼
Déduplication (orchestrateur) — un signal déjà couvert par une proposition en attente
n'est pas resoumis
        │
        ▼
Appel LLM n°2 — rédaction/priorisation (proposer_actions), un seul appel pour
tous les signaux nouveaux, jamais un par signal
  → si le modèle ignore/déforme une référence, un résumé de repli pré-écrit par type
    de signal prend le relais (le signal n'est jamais perdu)
        │
        ▼
Persistance (PropositionSupervision, statut "en attente")
        │
        ▼
Décision humaine explicite (Accepter / Refuser, page Supervision)
        │
        ▼ (si acceptée)
Dispatch vers la route de production existante — génération, exécution ou diagnostic
(jamais une réimplémentation)
```

## 4. Fonctionnalités détaillées

### F1 — Déclenchement de l'analyse

- **F1.1 Manuel** : bouton "Analyser maintenant" (page Supervision). Un admin peut restreindre à un
  client précis (champ optionnel) ou laisser vide pour analyser tous les clients connus. Un compte
  non-admin analyse toujours son propre client uniquement.
- **F1.2 Périodique (optionnel)** : `supervision/planificateur.py` — un thread démon, actif
  seulement si `PRISME_SUPERVISION_ACTIVE` est positionné (jamais par défaut, pour ne jamais se
  déclencher pendant les tests ou un `uvicorn --reload` occasionnel). Intervalle configurable
  (`PRISME_SUPERVISION_INTERVALLE_SECONDES`, 3600s par défaut). Parcourt tous les clients connus,
  un échec sur l'un n'interrompt jamais les suivants.

### F2 — Détection des signaux

Un seul appel LLM par client couvre toutes les instances à la fois (jamais un appel par instance).
Trois signaux possibles, mutuellement compatibles sauf le premier avec le second :

**F2.1 — Signature orpheline** (`signature_orpheline`)
Aucun solveur actif enregistré pour ce client n'a d'`instance_id` égal à celui de l'instance
examinée. Depuis que le registre lie un solveur à l'instance qui l'a fait générer (plus de partage
par structure de contraintes entre instances), ce signal se déclenche pour toute instance qui n'a
jamais eu son propre solveur généré, ou dont l'unique solveur a été désactivé. Rend le signal
suivant sans objet pour la même instance.

**F2.2 — Instance à replanifier** (`instance_a_replanifier`)
Un solveur actif existe bien avec l'`instance_id` de cette instance (le sien, jamais celui d'une
autre), mais :
- soit l'instance n'apparaît dans aucune exécution connue → raison `jamais_executee` ;
- soit sa date de modification est postérieure à sa plus récente exécution → raison
  `modifiee_apres_derniere_execution`.

**F2.3 — Échecs répétés** (`echecs_repetes`)
Les trois dernières exécutions de l'instance (triées par date) ont toutes échoué. Indépendant des
deux signaux précédents — peut se cumuler avec l'un d'eux sur la même instance.

### F3 — Rédaction et priorisation des propositions

Second appel LLM, un seul pour tous les signaux nouvellement détectés d'un même client. Pour
chaque signal : un résumé en une ou deux phrases destiné à un humain non technicien, et une
priorité (`haute` / `moyenne` / `basse`) — haute si ça bloque une exécution/décision immédiate,
moyenne si ça dégrade sans bloquer, basse si c'est purement informatif. Si le modèle omet ou
déforme une référence, un résumé de repli pré-écrit par type de signal est utilisé à la place
(jamais de signal perdu silencieusement).

### F4 — Consultation des propositions

`GET /supervision/propositions` (filtre `en_attente` optionnel) — page Supervision : tableau avec
signal, priorité, résumé, instance concernée (ou "instance supprimée" si elle n'existe plus),
statut (en attente / acceptée / refusée).

### F5 — Décision (Accepter / Refuser)

`POST /supervision/propositions/{id}/decision`. Deux issues possibles, jamais une troisième. Le
clic "Accepter" **est** la décision humaine explicite qui autorise l'action — pas un simple accusé
de réception.

### F6 — Déclenchement de l'action associée (sur acceptation uniquement)

| Signal | Action suggérée | Route réutilisée |
|---|---|---|
| `signature_orpheline` | `regenerer_solveur` | déclenche une génération (`POST /generation/{instance_id}/demarrer`, job suivi comme n'importe quelle génération manuelle) |
| `instance_a_replanifier` | `executer` | déclenche une exécution (`executer_pour_instance`, même fonction que `POST /execution/{instance_id}`) |
| `echecs_repetes` | `diagnostiquer` | lance un diagnostic sur la plus récente exécution en échec qui a produit un planning exploitable (les échecs sans planning — solveur introuvable, crash sandbox — ne sont pas diagnosticables, essai du plus récent au plus ancien) |

Si l'instance associée a été supprimée entre-temps, l'acceptation échoue explicitement (422),
jamais une action silencieusement avortée.

## 5. Modèle de données — `PropositionSupervision`

| Champ | Type | Rôle |
|---|---|---|
| `id` | str | Identifiant de la proposition. |
| `client_id` | str | Client concerné. |
| `type_signal` | `signature_orpheline` \| `instance_a_replanifier` \| `echecs_repetes` | |
| `action_suggeree` | `regenerer_solveur` \| `executer` \| `diagnostiquer` | Dérivée mécaniquement du type de signal (§F6), jamais choisie par le LLM. |
| `resume` | str | Texte destiné à l'humain (F3). |
| `priorite` | `haute` \| `moyenne` \| `basse` | |
| `details` | liste de str | Détail technique (ex. `structure=...`, `solveur_disponible=...`) — trace, jamais relu par le pipeline. |
| `instance_id` | str \| None | `None` si l'instance a été supprimée depuis. |
| `execution_ids` | liste de str | Uniquement pour `echecs_repetes`. |
| `structure_contraintes`, `signature_objectifs` | str | Capturés au moment de la détection, informatifs. |
| `decision` | `acceptee` \| `refusee` \| `None` | `None` = en attente. |
| `horodatage_decision`, `commentaire` | | Renseignés à la décision. |

## 6. Interfaces

### 6.1 API (`api/routes/supervision.py`, préfixe `/supervision`)

| Route | Rôle |
|---|---|
| `GET /instances`, `/executions`, `/solveurs` | Vues lecture seule, filtrées par client (admin voit tout). |
| `GET /sante` | Disponibilité API + sandbox Docker. |
| `POST /analyser` | Déclenche F1.1. |
| `GET /propositions` | F4. |
| `POST /propositions/{id}/decision` | F5 + F6. |

### 6.2 IHM — page Supervision

Bandeau de déclenchement (champ client optionnel pour l'admin + bouton "Analyser maintenant"),
tableau des propositions triées par date de création décroissante, badges de signal/priorité/statut,
boutons Accepter/Refuser sur les lignes en attente, retour en `toast` du résultat de l'action
déclenchée (ex. "Génération démarrée (job ...)"). État vide explicite ("Aucune proposition —
lancez une analyse...") plutôt qu'un tableau vide silencieux.

## 7. Règles non fonctionnelles

- **Jamais d'action automatique** : aucune proposition n'est appliquée sans le clic explicite
  "Accepter", que ce soit après une analyse manuelle ou une passe périodique.
- **Jamais de réimplémentation d'action** : régénérer/exécuter/diagnostiquer appellent exactement
  les mêmes fonctions que les routes de production correspondantes, jamais une version simplifiée
  ou parallèle.
- **Un solveur ne sert que l'instance pour laquelle il a été généré** — condition désormais
  vérifiée deux fois : par le prompt de détection (§F2), et par une revérification déterministe
  côté Python qui écarte toute proposition où le LLM aurait associé le solveur d'une *autre*
  instance (par erreur ou hallucination).
- **Aucun fait n'est jamais halluciné sans filet** : tout identifiant (`instance_id`,
  `id_solveur_disponible`, `execution_id`) absent des données réellement fournies au LLM est
  silencieusement écarté avant persistance — jamais propagé jusqu'à l'humain.
- **Boucle périodique désactivée par défaut** — opt-in explicite requis, jamais un comportement
  surprise en développement ou en CI.

## 8. Limites connues / hors périmètre

- La détection porte sur des signaux internes au pipeline (solveur/instance/exécution), pas sur un
  écart mesuré entre le planning et la réalité terrain (dérive de production) — cette seconde
  capacité, envisagée au plan directeur, supposerait plusieurs cycles de production réels non
  disponibles à ce jour.
- La latence/fiabilité de l'analyse dépend entièrement du fournisseur LLM configuré
  (`generation/agents/client_llm.py`) — un fournisseur lent ou instable ralentit ou fait échouer
  une passe d'analyse, sans rapport avec la logique de supervision elle-même.
