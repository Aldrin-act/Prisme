# Bouton d'Import CSV Local - Documentation

## Vue d'ensemble

Un nouveau bouton **CSV Local** a été ajouté au dialogue d'ingestion de l'interface frontend pour permettre l'import d'instances TRCO depuis des fichiers CSV présents sur le serveur.

## Emplacement

Le bouton se trouve dans la boîte de dialogue "Nouvelle instance" :
- **Route** : Accessible via n'importe quelle page avec le bouton "+ Nouvelle instance"
- **Dialogue** : `IngestionDialog` component
- **Onglet** : "CSV Local" (entre "Fichiers CSV" et "Fichier JSON")

## Fonctionnalités

### Interface Utilisateur

L'onglet CSV Local propose :
1. **Champ Client** : Associé automatiquement au compte de l'utilisateur (modifiable pour les admins)
2. **Champ de chemin** : Input pour saisir le chemin du dossier CSV côté serveur
3. **Exemples prédéfinis** : Liste de dossiers CSV disponibles pour faciliter la saisie
4. **Bouton d'import** : Déclenche la conversion et l'ingestion

### Chemins Disponibles

Exemples de dossiers CSV fournis :
```
data/donnees_brutes/csv/industrie_manufacturiere/assemblage_electronique
data/donnees_brutes/csv/industrie_manufacturiere/atelier_mecanique
data/donnees_brutes/csv/services/centre_appels
data/donnees_brutes/csv/industrie_manufacturiere/imprimerie
data/donnees_brutes/csv/industrie_manufacturiere/production_agroalimentaire
data/donnees_brutes/csv/services/maintenance_industrielle
```

## Utilisation

### Étape par étape

1. **Ouvrir le dialogue d'ingestion**
   - Cliquer sur le bouton "+ Nouvelle instance" dans n'importe quelle page

2. **Sélectionner l'onglet CSV Local**
   - Cliquer sur l'onglet "CSV Local" dans la liste des onglets

3. **Saisir le chemin du dossier**
   - Entrer le chemin complet du dossier CSV sur le serveur
   - Ou copier un des exemples fournis

4. **Lancer l'import**
   - Cliquer sur "Importer depuis le serveur"
   - Attendre la confirmation

5. **Résultat**
   - Une fois réussie, l'instance est créée avec son ID
   - Les statistiques sont affichées (tâches, ressources, contraintes, objectifs)

### Capture d'écran du workflow

```
┌─────────────────────────────────────────────────────────┐
│  Nouvelle instance                                    │
├─────────────────────────────────────────────────────────┤
│  [Saisie T-R-C-O] [Import ERP] [Fichier Excel]        │
│  [Fichiers CSV] [CSV Local] [Fichier JSON]            │ ← Nouvel onglet
├─────────────────────────────────────────────────────────┤
│  Client                                                 │
│  ┌───────────────────────────────────────────────────┐ │
│  │ demo_client                                       │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  Chemin du dossier CSV (côté serveur)                 │
│  ┌───────────────────────────────────────────────────┐ │
│  │ data/donnees_brutes/csv/services/centre_appels   │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  Exemples de dossiers disponibles:                    │
│    - data/donnees_brutes/csv/industrie_.../assemblage │
│    - data/donnees_brutes/csv/industrie_.../atelier   │
│    - data/donnees_brutes/csv/services/centre_appels  │
│                                                         │
│  [Annuler]  [Importer depuis le serveur]              │
└─────────────────────────────────────────────────────────┘
```

## Backend

### Endpoint API Utilisé

```
POST /adapters/csv-local/ingerer
Content-Type: application/json

{
  "client_id": "demo_client",
  "chemin_dossier": "data/donnees_brutes/csv/services/centre_appels"
}
```

### Réponse

```json
{
  "instance_id": "550e8400-e29b-41d4-a716-446655440000",
  "structure_contraintes": "precedence+compatibilite_ressource_tache",
  "statistiques": {
    "taches": 8,
    "ressources": 4,
    "contraintes": 15,
    "objectifs": 1
  },
  "chemin_source": "data/donnees_brutes/csv/services/centre_appels"
}
```

## Code Ajouté

### 1. Client API (`src/integrations/prisme/client.ts`)

```typescript
importerCsvLocal: (clientId: string, cheminDossier: string) =>
  apiFetch<Types.ReponseImportCsvLocal>(`${PRISME_CONFIG.routes.adapters}/csv-local/ingerer`, {
    method: "POST",
    body: JSON.stringify({ client_id: clientId, chemin_dossier: cheminDossier }),
  }),
```

### 2. Type TypeScript (`src/integrations/prisme/types.ts`)

```typescript
export interface ReponseImportCsvLocal {
  instance_id: string;
  structure_contraintes: string;
  statistiques: {
    taches: number;
    ressources: number;
    contraintes: number;
    objectifs: number;
  };
  chemin_source: string;
}
```

### 3. Hook React Query (`src/integrations/prisme/hooks.ts`)

```typescript
export function useImporterCsvLocal() {
  return useMutation({
    mutationFn: ({ clientId, cheminDossier }: { clientId: string; cheminDossier: string }) =>
      prismeClient.importerCsvLocal(clientId, cheminDossier),
  });
}
```

### 4. Composant UI (`src/components/ingestion/ingestion-dialog.tsx`)

- Import du hook `useImporterCsvLocal`
- État local `cheminDossierCsvLocal`
- Fonction `soumettreCsvLocal()`
- Nouvel onglet "CSV Local" dans `<TabsList>`
- Contenu `<TabsContent value="csvlocal">` avec formulaire

## Cas d'Usage

### 1. Import Rapide de Données de Test

Pour les développeurs qui veulent tester rapidement avec des données existantes :

```
1. Ouvrir dialogue "Nouvelle instance"
2. Onglet "CSV Local"
3. Copier : data/donnees_brutes/csv/industrie_manufacturiere/assemblage_electronique
4. Importer
```

### 2. Import en Masse pour Démo

Pour préparer une démo avec plusieurs instances :

```
1. Importer assemblage_electronique
2. Importer atelier_mecanique
3. Importer centre_appels
→ 3 instances créées en quelques clics
```

### 3. Intégration Scripts Automatisés

Pour des workflows automatisés qui placent des CSV sur le serveur :

```
1. Script externe dépose CSV dans data/donnees_brutes/csv/custom/
2. Utilisateur importe via l'interface avec le chemin custom
3. Instance créée et prête pour génération de solveur
```

## Avantages vs Autres Méthodes

| Méthode | Avantages | Inconvénients |
|---------|-----------|---------------|
| **CSV Local** (nouveau) | ✓ Pas de upload<br>✓ Rapide<br>✓ Idéal pour tests<br>✓ Réutilisable | ✗ Nécessite accès serveur<br>✗ Fichiers doivent être pré-positionnés |
| **Fichiers CSV** (existant) | ✓ Upload depuis n'importe où<br>✓ Accessible partout | ✗ Upload lent<br>✗ Répétitif pour tests |
| **Fichier Excel** (existant) | ✓ Format familier<br>✓ Un seul fichier | ✗ Upload requis<br>✗ Conversion nécessaire |
| **JSON** (existant) | ✓ Format programmatique | ✗ Moins lisible<br>✗ Upload requis |

## Validation et Sécurité

### Côté Frontend
- ✓ Validation du chemin non vide
- ✓ Gestion des erreurs API
- ✓ Affichage clair des erreurs de validation

### Côté Backend
- ✓ Vérification existence du dossier
- ✓ Vérification présence des 3 fichiers CSV
- ✓ Validation format UTF-8
- ✓ Validation colonnes requises
- ✓ Validation Pydantic de l'instance TRCO

## Limites et Précautions

⚠️ **Production** : En production, il est recommandé de :
1. Restreindre les chemins autorisés (whitelist)
2. Logger tous les accès
3. Limiter aux administrateurs ou services internes
4. Valider que le chemin ne contient pas de `..` (traversal)

## Fichiers Modifiés

```
Front/prismatron-solver-forge/
├── src/
│   ├── integrations/prisme/
│   │   ├── client.ts           ← Fonction importerCsvLocal
│   │   ├── types.ts            ← Type ReponseImportCsvLocal
│   │   └── hooks.ts            ← Hook useImporterCsvLocal
│   └── components/ingestion/
│       └── ingestion-dialog.tsx ← Onglet CSV Local

api/routes/
└── adapters.py                  ← Endpoint /csv-local/ingerer
```

## Testing

### Test Manuel

1. Démarrer l'API : `uv run uvicorn api.app:app --reload`
2. Démarrer le frontend : `cd Front/prismatron-solver-forge && npm run dev`
3. Naviguer vers la page Instances
4. Cliquer sur "+ Nouvelle instance"
5. Sélectionner l'onglet "CSV Local"
6. Entrer un chemin valide
7. Cliquer sur "Importer depuis le serveur"
8. Vérifier la création de l'instance

### Test avec DevTools

```javascript
// Dans la console du navigateur
// Vérifier que le hook est disponible
console.log(window.__REACT_DEVTOOLS_GLOBAL_HOOK__)
```

## Support et Documentation

- **Documentation backend** : `README_CSV_BACKEND.md`
- **Documentation API** : `docs/api_csv_local.md`
- **Documentation CSV** : `data/donnees_brutes/csv/README.md`
- **Endpoint API** : http://localhost:8000/docs (Swagger)

## Changelog

### Version 1.0.0 (2026-08-02)

**Ajout**
- ✨ Nouvel onglet "CSV Local" dans le dialogue d'ingestion
- ✨ Hook React Query `useImporterCsvLocal`
- ✨ Fonction client API `importerCsvLocal`
- ✨ Type TypeScript `ReponseImportCsvLocal`
- ✨ Endpoint backend `POST /adapters/csv-local/ingerer`

**Documentation**
- 📝 Guide utilisateur complet
- 📝 Exemples de chemins prédéfinis
- 📝 Notes de sécurité et limitations

---

**Date de création** : 2026-08-02
**Auteur** : Claude Code
**Statut** : ✅ Implémenté et testé
