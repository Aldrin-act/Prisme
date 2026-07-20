# Guide : Objectifs configurables

Ce document explique comment rendre les objectifs configurables dans PRISME.

## 🎯 Trois niveaux de configurabilité

### Niveau 1 : Paramètres dans les objectifs existants

**Quoi** : Ajouter des paramètres aux objectifs actuels sans changer leur type.

**Avant** :
```json
{
  "objectifs": [
    {"type": "minimiser_makespan"}
  ]
}
```

**Après** :
```json
{
  "objectifs": [
    {
      "type": "minimiser_makespan",
      "poids": 0.7,
      "makespan_cible": 480,
      "penalite_depassement": 2.0
    }
  ]
}
```

**Fichiers à modifier** :
- `dsl/schema/objectifs.py` → Ajouter les champs paramétrables
- Compatible avec le code existant (valeurs par défaut)

---

### Niveau 2 : Nouveaux objectifs via Registry

**Quoi** : Enregistrer de nouveaux types d'objectifs sans modifier le core.

**Exemple** : Objectif personnalisé BARAA
```python
# dsl/extensions/baraa/objectifs_baraa.py
from dsl.schema.registry_objectifs import RegistryObjectifs

class MinimiserCoutTotal(BaseModel):
    type: Literal["minimiser_cout_total"] = "minimiser_cout_total"
    cout_horaire_par_ressource: dict[str, float] = {}
    # ... autres paramètres

# Enregistrement
RegistryObjectifs.enregistrer("minimiser_cout_total", MinimiserCoutTotal)
```

**Utilisation** :
```json
{
  "objectifs": [
    {
      "type": "minimiser_cout_total",
      "cout_horaire_par_ressource": {"R1": 50.0, "R2": 75.0}
    }
  ]
}
```

**Fichiers nécessaires** :
- `dsl/schema/registry_objectifs.py` (nouveau)
- `dsl/extensions/<client>/` (par client)
- `dsl/schema/instance.py` (modification pour validation dynamique)

---

### Niveau 3 : Configuration par profil client

**Quoi** : Templates de configuration pré-définis par type de client.

**Fichier** : `config/profils_objectifs.json`
```json
{
  "profil_economique": {
    "objectifs": [
      {"type": "minimiser_cout_total", "poids": 0.7, ...},
      {"type": "equilibrer_charge", "poids": 0.3}
    ]
  },
  "profil_urgence": {
    "objectifs": [
      {"type": "minimiser_retards", "poids": 0.8, ...},
      {"type": "minimiser_makespan", "poids": 0.2}
    ]
  }
}
```

**API** :
```bash
POST /ingestion/{client_id}
{
  "profil_objectifs": "profil_economique",
  # ... reste de l'instance
}
```

---

## 🛠️ Implémentation : Étapes

### Étape 1 : Modifier `instance.py` pour validation dynamique

**Fichier** : `dsl/schema/instance.py`

**Changement** :
```python
from dsl.schema.registry_objectifs import RegistryObjectifs

class InstanceTRCO(BaseModel):
    taches: list[Tache]
    ressources: list[Ressource]
    contraintes: list[dict]  # Déjà dynamique
    objectifs: list[dict]  # CHANGEMENT : dict au lieu de list[MinimiserMakespan]
    
    @model_validator(mode="before")
    def _valider_objectifs_dynamiques(cls, values):
        """Valide chaque objectif selon son type enregistré."""
        objectifs_bruts = values.get("objectifs", [])
        objectifs_valides = []
        
        for obj in objectifs_bruts:
            type_obj = obj.get("type")
            if not type_obj:
                raise ValueError("Objectif sans champ 'type'")
            
            # Obtenir la classe depuis le registry
            ClasseObjectif = RegistryObjectifs.obtenir(type_obj)
            
            # Valider via Pydantic
            objectif_valide = ClasseObjectif.model_validate(obj)
            objectifs_valides.append(objectif_valide)
        
        values["objectifs"] = objectifs_valides
        return values
```

**Migration** : Rétro-compatible si les objectifs actuels sont enregistrés dans le registry.

---

### Étape 2 : Créer le système de profils

**Fichier** : `dsl/config/profils_objectifs.py`

```python
from pathlib import Path
import json

CHEMIN_PROFILS = Path(__file__).parent / "profils_objectifs.json"

class GestionnaireProfils:
    """Gère les profils d'objectifs pré-définis."""
    
    def __init__(self):
        self._profils = self._charger_profils()
    
    def _charger_profils(self) -> dict:
        with open(CHEMIN_PROFILS) as f:
            return json.load(f)
    
    def obtenir_profil(self, nom: str) -> list[dict]:
        """Récupère les objectifs d'un profil."""
        if nom not in self._profils:
            raise ValueError(f"Profil inconnu: {nom}")
        return self._profils[nom]["objectifs"]
    
    def liste_profils(self) -> list[str]:
        """Liste tous les profils disponibles."""
        return sorted(self._profils.keys())
    
    def enregistrer_profil(self, nom: str, objectifs: list[dict]) -> None:
        """Enregistre un nouveau profil."""
        self._profils[nom] = {"objectifs": objectifs}
        # Persister dans le fichier JSON
        with open(CHEMIN_PROFILS, "w") as f:
            json.dump(self._profils, f, indent=2)

# Instance globale
gestionnaire_profils = GestionnaireProfils()
```

---

### Étape 3 : Intégrer dans l'API

**Fichier** : `api/routes/ingestion.py`

```python
from dsl.config.profils_objectifs import gestionnaire_profils

@router.post("/{client_id}")
def ingerer_instance(
    client_id: str,
    payload: dict,  # Au lieu de InstanceTRCO directement
    etat: EtatAPI = Depends(obtenir_etat),
) -> dict[str, str]:
    # Si un profil est spécifié, l'appliquer
    if "profil_objectifs" in payload:
        nom_profil = payload.pop("profil_objectifs")
        objectifs_profil = gestionnaire_profils.obtenir_profil(nom_profil)
        
        # Fusionner avec les objectifs existants ou remplacer
        if "objectifs" not in payload:
            payload["objectifs"] = objectifs_profil
        else:
            # Les objectifs explicites overrident le profil
            pass
    
    # Validation normale
    instance = valider_payload_trco(payload)
    instance_id = etat.enregistrer_instance(client_id, instance)
    
    return {
        "instance_id": instance_id,
        "structure_contraintes": structure_contraintes(instance)
    }
```

---

### Étape 4 : Interface Dashboard

**Fichier** : `dashboard/src/components/ConfigObjectifs.tsx`

```typescript
interface Objectif {
  type: string;
  poids: number;
  [key: string]: any;  // Paramètres spécifiques
}

function ConfigurateurObjectifs() {
  const [objectifs, setObjectifs] = useState<Objectif[]>([]);
  const [typesDisponibles, setTypesDisponibles] = useState<string[]>([]);
  
  useEffect(() => {
    // Charger les types d'objectifs depuis l'API
    fetch("/api/objectifs/types")
      .then(r => r.json())
      .then(types => setTypesDisponibles(types));
  }, []);
  
  const ajouterObjectif = (type: string) => {
    // Obtenir le schéma de cet objectif
    fetch(`/api/objectifs/schema/${type}`)
      .then(r => r.json())
      .then(schema => {
        const nouvelObjectif: Objectif = {
          type,
          poids: 1.0,
          ...schema.defaults  // Valeurs par défaut
        };
        setObjectifs([...objectifs, nouvelObjectif]);
      });
  };
  
  return (
    <div>
      <h2>Configuration des objectifs</h2>
      
      {/* Sélecteur de profil */}
      <ProfileSelector 
        onSelectProfile={(profil) => {
          setObjectifs(profil.objectifs);
        }}
      />
      
      {/* Liste des objectifs configurés */}
      {objectifs.map((obj, idx) => (
        <ObjectifEditor
          key={idx}
          objectif={obj}
          onChange={(updated) => {
            const newObjs = [...objectifs];
            newObjs[idx] = updated;
            setObjectifs(newObjs);
          }}
          onDelete={() => {
            setObjectifs(objectifs.filter((_, i) => i !== idx));
          }}
        />
      ))}
      
      {/* Ajouter un objectif */}
      <select onChange={(e) => ajouterObjectif(e.target.value)}>
        <option>Ajouter un objectif...</option>
        {typesDisponibles.map(type => (
          <option key={type} value={type}>{type}</option>
        ))}
      </select>
      
      {/* Prévisualisation JSON */}
      <pre>{JSON.stringify(objectifs, null, 2)}</pre>
    </div>
  );
}
```

---

## 📊 Exemple complet : Flux utilisateur

### 1. Configuration dans le Dashboard

```
1. Utilisateur ouvre "Configuration des objectifs"
2. Sélectionne un profil de base : "profil_economique"
3. Ajuste les paramètres :
   - Coûts horaires des ressources
   - Pénalités de retard
4. Sauvegarde la configuration pour "client_baraa"
```

### 2. Ingestion avec objectifs configurés

```bash
POST /ingestion/client_baraa
{
  "taches": [...],
  "ressources": [...],
  "contraintes": [...],
  "profil_objectifs": "profil_economique"
  # OU
  "objectifs": [
    {
      "type": "minimiser_cout_total",
      "poids": 0.7,
      "cout_horaire_par_ressource": {"R1": 50.0, "R2": 75.0}
    }
  ]
}
```

### 3. Génération du solveur

Le générateur LLM reçoit l'instance avec objectifs configurés et génère un solveur qui :
- Optimise selon les objectifs spécifiés
- Applique les poids relatifs
- Respecte les contraintes paramétrées

### 4. Réutilisation

Le solveur généré est **figé** avec ses objectifs. Pour changer d'objectifs :
- Soit régénérer un nouveau solveur (rare)
- Soit utiliser un solveur multi-objectifs paramétrable (avancé)

---

## 🔄 Migration depuis l'existant

### Étape 1 : Compatibilité ascendante

```python
# Ancien code (toujours supporté)
instance = InstanceTRCO(
    taches=[...],
    ressources=[...],
    contraintes=[...],
    objectifs=[MinimiserMakespan()]  # ← Fonctionne encore
)

# Nouveau code (avec paramètres)
instance = InstanceTRCO(
    taches=[...],
    ressources=[...],
    contraintes=[...],
    objectifs=[
        {"type": "minimiser_makespan", "poids": 0.7, "makespan_cible": 480}
    ]
)
```

### Étape 2 : Migration des données existantes

```python
def migrer_objectifs_anciens(instance_ancienne: dict) -> dict:
    """Migre les objectifs de l'ancien format vers le nouveau."""
    objectifs_anciens = instance_ancienne.get("objectifs", [])
    objectifs_nouveaux = []
    
    for obj in objectifs_anciens:
        if isinstance(obj, dict):
            # Déjà au nouveau format
            objectifs_nouveaux.append(obj)
        else:
            # Ancien format (objet Pydantic)
            objectifs_nouveaux.append({
                "type": obj.type,
                "poids": 1.0  # Valeur par défaut
            })
    
    instance_ancienne["objectifs"] = objectifs_nouveaux
    return instance_ancienne
```

---

## ✅ Checklist d'implémentation

- [ ] Créer `dsl/schema/objectifs_parametrables.py`
- [ ] Créer `dsl/schema/registry_objectifs.py`
- [ ] Modifier `dsl/schema/instance.py` pour validation dynamique
- [ ] Créer `dsl/config/profils_objectifs.py` + JSON
- [ ] Modifier `api/routes/ingestion.py` pour supporter les profils
- [ ] Ajouter endpoint `/api/objectifs/types` (liste types disponibles)
- [ ] Ajouter endpoint `/api/objectifs/schema/{type}` (schéma d'un type)
- [ ] Créer composant Dashboard `ConfigurateurObjectifs.tsx`
- [ ] Tests unitaires pour chaque nouvel objectif
- [ ] Tests d'intégration bout-en-bout
- [ ] Documentation utilisateur (ce fichier)
- [ ] Migration des données existantes

---

## 🚀 Extensions futures

### Objectifs adaptatifs

```python
class ObjectifAdaptatif(BaseModel):
    """Objectif qui ajuste ses paramètres selon le contexte."""
    type: Literal["objectif_adaptatif"] = "objectif_adaptatif"
    
    regle_adaptation: str  # "si retard > 2h alors poids_makespan = 0.9"
```

### Apprentissage par feedback

```python
class HistoriqueObjectifs:
    """Stocke les objectifs utilisés + résultats pour apprentissage."""
    
    def enregistrer_resultat(self, objectifs: list, planning: Planning, satisfaction: float):
        # Apprentissage des pondérations optimales
        pass
```

### API de suggestion

```
GET /api/objectifs/suggerer?client_id=baraa&contexte=production_urgent

→ {
    "objectifs_suggeres": [
        {"type": "minimiser_retards", "poids": 0.8, ...}
    ],
    "raison": "Historique du client montre priorité aux délais en urgence"
}
```
