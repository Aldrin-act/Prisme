# Déploiement de PRISME sur Railway (API + frontend + Postgres)

Trois services dans un même projet Railway, tous construits depuis le même dépôt GitHub :

| Service | Source | Construit par | Démarré par |
|---|---|---|---|
| **Postgres** | modèle Railway (« Add PostgreSQL ») | — | — |
| **Prisme** (API FastAPI) | racine du dépôt | [`railpack.json`](../railpack.json) | `uvicorn api.app:app` |
| **Prisme-Front** (TanStack Start) | `Front/prismatron-solver-forge` | [`Front/.../railpack.json`](../Front/prismatron-solver-forge/railpack.json) | `node .output/server/index.mjs` |

Ordre conseillé : Postgres → API → frontend, car chacun a besoin de l'URL du précédent.

## 1. Postgres

**+ New → Database → Add PostgreSQL.** Rien à configurer : Railway génère lui-même ses variables
(`POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL`...). Ne pas les modifier. Les tables de
PRISME sont créées automatiquement au premier démarrage de l'API.

## 2. API (service « Prisme »)

**+ New → GitHub Repo →** le dépôt PRISME. Laisser *Root Directory* vide (racine du dépôt).

Le fichier `railpack.json` de la racine s'occupe du reste : il installe les extras `llm` et `sandbox`
(que Railpack n'installe pas par défaut) et démarre `uvicorn` sur le port fourni par Railway.

**Variables** (onglet *Variables* du service Prisme) :

```env
# Base de données — référence vers le service Postgres, jamais une URL localhost
DATABASE_URL=${{Postgres.DATABASE_URL}}

# LLM — une des deux clés
KIMI_API_KEY=...
# OPENROUTER_API_KEY=...
PRISME_LLM_REFLEXION=desactivee
PRISME_LLM_CONCURRENCE_MAX=1
PRISME_LLM_TIMEOUT_SECONDES_GENERATEUR=1800
PRISME_LLM_TIMEOUT_SECONDES_DEBUGGER=1800

# Authentification — une vraie valeur longue et aléatoire, jamais celle de dev
JWT_SECRET_KEY=...

# Compte administrateur initial, créé au premier démarrage (12 caractères min.). Ensuite, changer le
# mot de passe depuis l'interface : ces variables ne l'écrasent jamais.
PRISME_ADMIN_EMAIL=admin@exemple.ma
PRISME_ADMIN_MOT_DE_PASSE=...

# URL du frontend (étape 3) — à ajouter une fois le frontend déployé
PRISME_CORS_ORIGINES=https://<domaine-du-front>.up.railway.app
```

`${{Postgres.DATABASE_URL}}` : `Postgres` est le **nom du service** Postgres dans le projet — à
adapter s'il a été renommé. Railway remplace la référence par l'URL interne
(`postgres.railway.internal:5432`).

À **ne pas** copier depuis le `.env` local :
- `POSTGRES_*`, `API_PORT`, `GREENSIG_*` : ils pointent vers `localhost`, qui sur Railway désigne le
  conteneur lui-même (symptôme : `connection to server at "127.0.0.1", port 5433 failed`) ;
- `PRISME_AUTH_DESACTIVEE` : ouvrirait l'API publique sans authentification.

**Domaine public :** *Settings → Networking → Generate Domain*. Noter l'URL obtenue
(ex. `https://prisme-production.up.railway.app`) : le frontend en a besoin. Vérification :
`<url>/docs` doit afficher la documentation de l'API.

## 3. Frontend (service « Prisme-Front »)

**+ New → GitHub Repo →** le même dépôt, puis *Settings → Source → Root Directory* :
`Front/prismatron-solver-forge`.

**Variables :**

```env
# URL publique de l'API (étape 2), sans « / » final
VITE_PRISME_API_URL=https://<domaine-de-l-api>.up.railway.app

# Cible de build : serveur Node. Sans elle, la config Lovable construit pour Cloudflare
# et le service ne démarre pas.
NITRO_PRESET=node-server
```

`VITE_PRISME_API_URL` est lue **au moment du build** et inscrite dans le code livré au navigateur :
la changer impose de **redéployer** le frontend, pas seulement de redémarrer.

**Domaine public :** *Settings → Networking → Generate Domain*, puis reporter cette URL dans
`PRISME_CORS_ORIGINES` côté API (étape 2). Sans elle, le navigateur bloque tous les appels du
frontend vers l'API (erreur CORS dans la console).

## 4. Vérifier

1. `https://<api>/docs` s'affiche.
2. Le frontend s'ouvre, la connexion fonctionne, la console du navigateur ne montre aucune erreur CORS.
3. Les logs de l'API ne mentionnent ni `localhost` ni `5433`.

## Limite connue : pas de bac à sable sur Railway

L'exécution d'un solveur et les tests en sandbox de la génération lancent un conteneur Docker
(`sandbox/runner.py`). Railway ne donne pas accès à Docker depuis un service : ces opérations
échouent avec « bac à sable injoignable ». L'API, l'ingestion, l'agent de compréhension et la
supervision fonctionnent. Pour une démonstration complète (génération validée + exécution), héberger
l'API sur une machine qui dispose de Docker (VPS, poste local).
