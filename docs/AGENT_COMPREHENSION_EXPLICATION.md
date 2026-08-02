# 🤖 Agent de compréhension - Fonctionnement détaillé

## 📋 Table des matières
1. [Vue d'ensemble](#vue-densemble)
2. [Architecture technique](#architecture-technique)
3. [Flux de traitement](#flux-de-traitement)
4. [La RÈGLE ABSOLUE](#la-règle-absolue)
5. [Exemple concret de transformation](#exemple-concret)
6. [Validation en aval](#validation-en-aval)
7. [Avertissements et justifications](#avertissements-et-justifications)

---

## 🎯 Vue d'ensemble

### Rôle de l'agent
L'agent de compréhension est un **agent LLM spécialisé** qui traduit automatiquement des **données brutes** (n'importe quel format : CSV, JSON, texte libre, Excel) vers le **format T-R-C-O canonique** de PRISME.

### Pourquoi existe-t-il ?
Pour les ERP **sans adaptateur dédié** écrit à la main :
- ✅ **Adaptateur dédié** : Code Python déterministe (ex: `erp_reference/translator.py`)
- ✅ **Agent de compréhension** : LLM qui comprend n'importe quel format

### Cas d'usage
```
Cas 1 : ERP standard connu
├─ Utiliser l'adaptateur dédié (rapide, déterministe)
└─ POST /adapters/erp_reference/ingerer

Cas 2 : Format inconnu / propriétaire / texte libre
├─ Utiliser l'agent de compréhension (flexible, intelligent)
└─ POST /sources/{source_id}/generer-instance
```

---

## 🏗️ Architecture technique

### Fichiers clés

```
adapters/agent_comprehension/
├── agent.py                  # Point d'entrée principal
├── prompts/
│   └── comprehension.md      # Instructions détaillées pour le LLM
└── exploration_bdd.py        # Aide à l'exploration de bases de données

api/routes/
└── sources.py                # Route API pour utiliser l'agent

docs/dsl/
└── modele_ingestion_client.md  # Règles du format T-R-C-O
```

### Fonction principale

```python
def comprendre_donnees_erp(
    modele: BaseChatModel,
    donnees_brutes: str
) -> ResultatComprehension:
    """
    Entrée : Données brutes (n'importe quel format)
    Sortie : Instance T-R-C-O + avertissements + justifications
    """
```

### Structure de sortie

```python
@dataclass(frozen=True)
class ResultatComprehension:
    reponse_brute: str              # Réponse JSON brute du LLM
    instance_brute: dict[str, Any]  # Instance T-R-C-O proposée
    avertissements: tuple[str, ...]  # Incertitudes à vérifier
    justifications: tuple[Justification, ...]  # Citations sources
```

---

## 🔄 Flux de traitement

### Étape par étape

```
┌─────────────────────────────────────────────────────────────┐
│ 1. DONNÉES BRUTES                                           │
│    (CSV, JSON, texte libre, Excel...)                       │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. PROMPT SYSTÈME                                           │
│    "Tu es un analyste d'intégration de données..."          │
│    + Règles DSL (modele_ingestion_client.md)                │
│    + RÈGLE ABSOLUE sur les compétences                      │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. LLM (avec structured output)                             │
│    Analyse les données et génère :                          │
│    - instance T-R-C-O                                       │
│    - avertissements                                         │
│    - justifications                                         │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. VALIDATION DÉTERMINISTE (§6.7)                           │
│    ✓ Identifiants uniques                                   │
│    ✓ Chaque tâche a ≥1 compatibilité                        │
│    ✓ Références cohérentes                                  │
│    ✓ Compétences requises ⊆ compétences ressources          │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ├─ SUCCÈS → Instance validée
                  └─ ÉCHEC → HTTP 422 avec détails erreurs
```

### Code simplifié

```python
# 1. Construire le prompt
gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
regles_dsl = CHEMIN_REGLES_DSL.read_text(encoding="utf-8")
prompt = gabarit.format(
    regles_dsl=regles_dsl,
    donnees_brutes=donnees_brutes
)

# 2. Appeler le LLM avec structured output
structure = modele.with_structured_output(_SchemaComprehension)
sortie = structure.invoke([
    SystemMessage(content=_PROMPT_SYSTEME),
    HumanMessage(content=prompt)
])

# 3. Valider avec le garde-fou déterministe
instance = valider_payload_trco(resultat.instance_brute)  # Lève 422 si invalide

# 4. Enregistrer dans l'état
instance_id = etat.enregistrer_instance(client_id, instance, source_id=source_id)
```

---

## ⚠️ La RÈGLE ABSOLUE

### Énoncé de la règle

> **Un champ qui indique seulement où/par qui une opération a été historiquement exécutée
> (ex. `poste_id`, `code_poste`, `station_id`) n'est JAMAIS une compétence.**
>
> **Ne t'en sers JAMAIS pour produire une contrainte `compatibilite_ressource_tache`.**

### Pourquoi cette règle ?

**Problème** : Confusion entre historique et compétence
```json
{
  "operations": [{
    "code_operation": "SOUDURE_001",
    "poste_id": "POSTE_SOUDURE_3"  ← Simple historique d'affectation
  }]
}
```

❌ **Mauvaise interprétation** :
- "Cette opération a été faite sur POSTE_SOUDURE_3 historiquement"
- "Donc POSTE_SOUDURE_3 peut faire la soudure"
- → Crée une compatibilité basée sur l'historique

✅ **Bonne interprétation** :
- "Je vois un historique d'affectation"
- "Mais aucune compétence explicite"
- → Ne crée PAS de compatibilité
- → Signale dans `avertissements`

### Cas acceptables

L'agent PEUT créer des compatibilités seulement si :

1. **Compétence explicite sur la tâche** :
```json
{
  "operation": {
    "code_operation": "SOUDURE_001",
    "competence_requise": "soudure"  ← Explicite !
  }
}
```

2. **Compétence explicite sur la ressource** :
```json
{
  "poste": {
    "code_poste": "POSTE_SOUDURE_3",
    "competences": ["soudure", "brasage"]  ← Explicite !
  }
}
```

3. **Les deux ensemble** (meilleur cas) :
```json
{
  "operations": [{
    "code_operation": "SOUDURE_001",
    "poste_id": "POSTE_SOUDURE_3",
    "competence_requise": "soudure"  ← Explicite
  }],
  "postes": [{
    "code_poste": "POSTE_SOUDURE_3",
    "competences": ["soudure"]  ← Explicite
  }]
}
```

### Conséquence de la règle

Si les données n'ont QUE des `poste_id` sans compétences :

```
Données brutes (sans compétences)
        ↓
Agent de compréhension
        ↓
Instance avec 0 tâches, 0 ressources
        ↓
Validation rejette : "taches : List should have at least 1 item"
```

**C'est le comportement voulu** : mieux vaut un rejet honnête qu'une compatibilité inventée.

---

## 📝 Exemple concret de transformation

### Données brutes (AVANT enrichissement)

```json
{
  "operations": [
    {
      "code_operation": "DECOUP_001",
      "duree_jours": 1,
      "poste_id": "DECOUPEUSE_LASER"
    },
    {
      "code_operation": "SOUDURE_001",
      "duree_jours": 2,
      "poste_id": "POSTE_SOUDURE_1",
      "operation_precedente": "DECOUP_001"
    }
  ],
  "postes": [
    {"code_poste": "DECOUPEUSE_LASER"},
    {"code_poste": "POSTE_SOUDURE_1"}
  ]
}
```

### ❌ Résultat de l'agent (SANS compétences)

```json
{
  "instance": {
    "taches": [],      ← Vide !
    "ressources": [],  ← Vide !
    "contraintes": [],
    "objectifs": [{"type": "minimiser_makespan"}]
  },
  "avertissements": [
    "Aucune compétence explicite trouvée pour l'opération DECOUP_001. Le champ 'poste_id' est un simple historique d'affectation, pas une compétence.",
    "Aucune compétence explicite trouvée pour l'opération SOUDURE_001. Le champ 'poste_id' est un simple historique d'affectation, pas une compétence.",
    "Instance vide : aucune tâche ni ressource n'a pu être créée en respectant la règle absolue."
  ],
  "justifications": []
}
```

→ **Validation rejette avec HTTP 422**

### Données brutes (APRÈS enrichissement)

```json
{
  "operations": [
    {
      "code_operation": "DECOUP_001",
      "duree_jours": 1,
      "poste_id": "DECOUPEUSE_LASER",
      "competence_requise": "decoupeuse_laser"  ← Ajouté
    },
    {
      "code_operation": "SOUDURE_001",
      "duree_jours": 2,
      "poste_id": "POSTE_SOUDURE_1",
      "operation_precedente": "DECOUP_001",
      "competence_requise": "soudure"  ← Ajouté
    }
  ],
  "postes": [
    {
      "code_poste": "DECOUPEUSE_LASER",
      "competences": ["decoupeuse_laser"]  ← Ajouté
    },
    {
      "code_poste": "POSTE_SOUDURE_1",
      "competences": ["soudure"]  ← Ajouté
    }
  ]
}
```

### ✅ Résultat de l'agent (AVEC compétences)

```json
{
  "instance": {
    "taches": [
      {"id": "DECOUP_001", "nom": "Découpe laser"},
      {"id": "SOUDURE_001", "nom": "Soudure"}
    ],
    "ressources": [
      {"id": "DECOUPEUSE_LASER", "nom": "Découpeuse laser", "competences": ["decoupeuse_laser"]},
      {"id": "POSTE_SOUDURE_1", "nom": "Poste de soudure 1", "competences": ["soudure"]}
    ],
    "contraintes": [
      {"type": "precedence", "avant": "DECOUP_001", "apres": "SOUDURE_001"},
      {"type": "compatibilite_ressource_tache", "tache": "DECOUP_001", "ressource": "DECOUPEUSE_LASER", "duree": 1},
      {"type": "compatibilite_ressource_tache", "tache": "SOUDURE_001", "ressource": "POSTE_SOUDURE_1", "duree": 2},
      {"type": "competence_requise", "tache": "DECOUP_001", "competence": "decoupeuse_laser"},
      {"type": "competence_requise", "tache": "SOUDURE_001", "competence": "soudure"}
    ],
    "objectifs": [{"type": "minimiser_makespan"}]
  },
  "avertissements": [],
  "justifications": [
    {
      "contrainte": "precedence: DECOUP_001 → SOUDURE_001",
      "raison": "champ \"operation_precedente\": \"DECOUP_001\" sur l'opération SOUDURE_001"
    },
    {
      "contrainte": "competence_requise: DECOUP_001 (decoupeuse_laser)",
      "raison": "champ \"competence_requise\": \"decoupeuse_laser\" sur l'opération DECOUP_001"
    },
    {
      "contrainte": "competence_requise: SOUDURE_001 (soudure)",
      "raison": "champ \"competence_requise\": \"soudure\" sur l'opération SOUDURE_001"
    }
  ]
}
```

→ **Validation réussit, instance enregistrée !**

---

## ✅ Validation en aval

### Garde-fou déterministe (§6.7)

L'instance proposée par l'agent passe par **exactement la même validation** que n'importe quel autre payload T-R-C-O :

```python
# api/input_validation.py
def valider_payload_trco(payload: dict) -> InstanceTRCO:
    """
    Validation stricte :
    1. Parse avec Pydantic (schéma strict)
    2. Vérifie identifiants uniques
    3. Vérifie références cohérentes
    4. Vérifie chaque tâche a ≥1 compatibilité
    5. Vérifie compétences requises ⊆ compétences ressources

    Lève HTTPException(422) si invalide
    """
    try:
        return InstanceTRCO(**payload)  # Validation Pydantic
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
```

### Règles de validation

| Règle | Description | Exemple d'erreur |
|-------|-------------|------------------|
| **Identifiants uniques** | Pas de doublons dans `taches` ou `ressources` | `taches : 'T1' apparaît 2 fois` |
| **Références valides** | Contraintes référencent des IDs existants | `precedence : tâche 'T99' inconnue` |
| **≥1 compatibilité** | Chaque tâche a au moins 1 compatibilité ressource-tâche | `tache 'T1' : aucune compatibilité` |
| **Compétences cohérentes** | Si `competence_requise`, ressource compatible doit l'avoir | `T1 requiert 'soudure', mais R1 n'a que ['decoupe']` |
| **Schéma strict** | Pas de champs en trop | `Extra inputs are not permitted` |

### Ce que la validation NE détecte PAS

❌ Erreurs **sémantiques** (sens métier) :
- "L'agent a mal compris le workflow métier"
- "Cette durée semble incorrecte"
- "Cette précédence est inversée"

→ **C'est pour ça qu'il y a des `avertissements` et `justifications`** : un humain doit vérifier.

---

## 📊 Avertissements et justifications

### Avertissements

Liste de chaînes signalant les **incertitudes** :

```json
{
  "avertissements": [
    "Durée convertie de 120 minutes à 1 jour (arrondi)",
    "Tâche 'VALIDATION' : aucune compétence explicite, basé sur le nom",
    "Plusieurs ressources semblent pouvoir faire la même chose, choix arbitraire"
  ]
}
```

**Rôle** : Alerter l'humain sur ce qui mérite vérification **avant** d'exécuter le planning.

### Justifications

Liste de citations **exactes** des champs sources :

```json
{
  "justifications": [
    {
      "contrainte": "precedence: T1 → T2",
      "raison": "champ \"operation_precedente\": \"T1\" sur l'opération T2"
    },
    {
      "contrainte": "echeance: T3 (5 jours)",
      "raison": "champ \"date_limite\": \"2024-01-15\" converti en 5 jours depuis le début"
    },
    {
      "contrainte": "competence_requise: T1 (soudure)",
      "raison": "champ \"competence_requise\": \"soudure\" sur l'opération T1"
    }
  ]
}
```

**Rôle** : Permettre à l'humain de **vérifier la déduction** sans relire tout le fichier source.

**Important** : Seulement pour `precedence`, `echeance`, `competence_requise` (pas `compatibilite_ressource_tache`, trop nombreuses).

---

## 🔧 Utilisation pratique

### Via l'API

```bash
# 1. Créer une source de données
POST /sources
{
  "donnees_brutes": "...",  # Votre JSON/CSV/texte
  "nom": "Données ERP janvier 2024"
}

# Réponse : {"source_id": "abc123"}

# 2. Générer une instance T-R-C-O
POST /sources/abc123/generer-instance

# Réponse :
{
  "instance_id": "xyz789",
  "structure_contraintes": "3_precedences-2_echeances",
  "avertissements": ["..."],
  "justifications": [{"contrainte": "...", "raison": "..."}]
}
```

### Rejouer la conversion

La source est **réutilisable** :
```bash
# Même source, nouvelle tentative (après affinement du prompt, par exemple)
POST /sources/abc123/generer-instance

# Nouvelle instance créée, l'ancienne reste intacte
```

### Vérifier les avertissements

**Dans l'interface** : Affichage des avertissements + justifications pour validation humaine

**Workflow recommandé** :
1. Générer l'instance
2. Lire les avertissements
3. Si OK → Exécuter
4. Si NOK → Corriger les données brutes, regénérer

---

## 🆚 Agent vs Adaptateur dédié

| Critère | Agent de compréhension | Adaptateur dédié |
|---------|----------------------|------------------|
| **Flexibilité** | ✅ Accepte n'importe quel format | ❌ Format fixe |
| **Rapidité** | ❌ Appel LLM (1-3s) | ✅ Code Python (<100ms) |
| **Déterminisme** | ❌ Peut varier légèrement | ✅ 100% déterministe |
| **Traçabilité** | ✅ Justifications citant sources | ⚠️ Code à lire |
| **Coût** | ❌ Tokens LLM | ✅ Gratuit |
| **Maintenance** | ✅ Pas de code à maintenir | ❌ Code à maintenir |
| **Fiabilité** | ⚠️ Dépend du LLM | ✅ Testé |

### Quand utiliser quoi ?

**Adaptateur dédié** :
- ✅ ERP standard avec format fixe
- ✅ Besoin de performance
- ✅ Intégration production continue

**Agent de compréhension** :
- ✅ Format inconnu/propriétaire
- ✅ Données textuelles/semi-structurées
- ✅ Exploration/prototypage
- ✅ Import ponctuel

---

## 📚 Ressources

- **Code source** : `adapters/agent_comprehension/agent.py`
- **Prompts** : `adapters/agent_comprehension/prompts/comprehension.md`
- **Règles DSL** : `docs/dsl/modele_ingestion_client.md`
- **API** : `api/routes/sources.py`
- **Tests** : `tests/unit/test_agent_comprehension.py`
- **Script demo** : `scripts/demo_agent_comprehension.py`

---

## ✨ En résumé

L'agent de compréhension est :

1. **Un traducteur intelligent** : Données brutes → Format T-R-C-O
2. **Strict sur les compétences** : Refuse les historiques d'affectation
3. **Transparent** : Justifie chaque déduction
4. **Prudent** : Signale les incertitudes
5. **Validé** : Passe par le même garde-fou que le reste

**La philosophie** : Mieux vaut un rejet honnête qu'une compatibilité inventée.
