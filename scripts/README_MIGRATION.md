# Guide d'utilisation du script de migration

## 🎯 Objectif

Le script `migrer_nomenclature.py` corrige automatiquement tous les fichiers du projet pour utiliser la nomenclature officielle du DSL T-R-C-O :

**Ressource → Ressource**

## 🚀 Utilisation rapide

### 1. Prévisualisation (recommandé en premier)

```bash
# Voir ce qui serait modifié sans rien changer
uv run python -m scripts.migrer_nomenclature --dry-run
```

**Sortie** :
```
🔍 247 fichiers à analyser...

📝 dsl/examples/exemple_atelier.json
   3 correction(s)
   L12: "R1" → "R1"
   L15: "R2" → "R2"
   L23: "machines" → "ressources"

📝 api/routes/execution.py
   5 correction(s)
   L45: machine_id → ressource_id
   ...

✅ Migration terminée !
📊 42 fichier(s) modifié(s)
🔧 156 correction(s) au total

⚠️  Mode DRY-RUN : aucun fichier n'a été modifié
   Relancez sans --dry-run pour appliquer les changements

📄 Rapport généré : rapport_migration.md
```

### 2. Vérifier le rapport

```bash
# Un rapport Markdown est généré automatiquement
cat rapport_migration.md
```

### 3. Appliquer les modifications

```bash
# Application réelle AVEC backup (recommandé)
uv run python -m scripts.migrer_nomenclature --backup

# OU sans backup si confiant
uv run python -m scripts.migrer_nomenclature
```

---

## 📋 Options disponibles

| Option | Description | Exemple |
|--------|-------------|---------|
| `--dry-run` | Simulation sans modification | `--dry-run` |
| `--backup` | Créer des backups avant modification | `--backup` |
| `--path <chemin>` | Cibler un dossier spécifique | `--path dsl/examples/` |
| `--rapport <fichier>` | Générer un rapport personnalisé | `--rapport mon_rapport.md` |
| `--silencieux` | Pas d'affichage progressif | `--silencieux` |

---

## 🔍 Ce qui est corrigé

### 1. Identifiants

| Avant | Après |
|-------|-------|
| `"R1"`, `"R2"` | `"R1"`, `"R2"` |
| `"RESSOURCE_LASER"` | `"RESSOURCE_LASER"` |
| `"ressource_a"` | `"ressource_a"` |

### 2. Noms de champs (JSON)

| Avant | Après |
|-------|-------|
| `"machines": [...]` | `"ressources": [...]` |
| `"ressource_id": "..."` | `"ressource_id": "..."` |
| `"ressource_ids": [...]` | `"ressource_ids": [...]` |
| `"cout_par_machine"` | `"cout_par_ressource"` |

### 3. Variables Python

| Avant | Après |
|-------|-------|
| `ressource = [...]` | `ressources = [...]` |
| `machine_id: str` | `ressource_id: str` |
| `Ressource` (type) | `Ressource` |
| `param_par_machine` | `param_par_ressource` |

### 4. Commentaires et documentation

| Avant | Après |
|-------|-------|
| `# Liste des ressource` | `# Liste des ressources` |
| `La ressource M1` | `La ressource R1` |

---

## 📊 Exemple de rapport généré

```markdown
# Rapport de migration de nomenclature

Date: 2026-07-20 14:30:00
Mode: DRY-RUN (simulation)

## Résumé

- Fichiers modifiés : **42**
- Corrections appliquées : **156**
- Erreurs : **0**

## Corrections par type

- `id_machine_simple` : 47 occurrence(s)
- `champ_machines` : 23 occurrence(s)
- `variable_machines` : 18 occurrence(s)
- `champ_par_machine` : 15 occurrence(s)
...

## Détail par fichier

### dsl/examples/exemple_atelier.json

3 correction(s) :

- L12: `"R1"` → `"R1"`
- L15: `"R2"` → `"R2"`
- L23: `"machines"` → `"ressources"`

...
```

---

## 🎯 Scénarios d'usage

### Scénario 1 : Première migration complète

```bash
# 1. Prévisualisation
uv run python -m scripts.migrer_nomenclature --dry-run

# 2. Vérifier le rapport
cat rapport_migration.md

# 3. Commit actuel (au cas où)
git add -A
git commit -m "Avant migration nomenclature"

# 4. Application avec backup
uv run python -m scripts.migrer_nomenclature --backup

# 5. Vérifier les changements
git diff

# 6. Tests
uv run pytest

# 7. Commit
git add -A
git commit -m "Migration nomenclature: Ressource → Ressource"
```

### Scénario 2 : Migration ciblée (nouveaux fichiers)

```bash
# Migrer uniquement les exemples
uv run python -m scripts.migrer_nomenclature --path dsl/examples/ --dry-run

# Si OK, appliquer
uv run python -m scripts.migrer_nomenclature --path dsl/examples/
```

### Scénario 3 : Vérification avant PR

```bash
# Vérifier qu'il ne reste plus d'anciennes nomenclatures
uv run python -m scripts.migrer_nomenclature --dry-run --silencieux

# Si rien trouvé : OK pour PR
# Si corrections détectées : relancer sans --dry-run
```

---

## ⚠️ Fichiers exclus automatiquement

Le script **n'analyse PAS** :
- `node_modules/`
- `__pycache__/`
- `.git/`
- `venv/`, `.venv/`
- `uv.lock`
- Le script lui-même (`migrations/`)

---

## 🔧 Personnalisation

### Ajouter une règle de migration

Éditez `scripts/migrer_nomenclature.py` et ajoutez dans les règles appropriées :

```python
REGLES_IDENTIFIANTS.append(
    RegleMigration(
        nom="mon_cas_special",
        pattern=re.compile(r'"SPECIAL_M(\d+)"'),
        remplacement=lambda m: f'"SPECIAL_R{m.group(1)}"',
        description='Cas spécial SPECIAL_M → SPECIAL_R',
        categories=["identifiants", "special"],
    )
)
```

### Exclure des fichiers supplémentaires

Dans `migrer()`, ajoutez à la liste `exclure` :

```python
exclure = exclure or [
    # ... existant
    "**/mon_dossier_special/**",
    "**/*_legacy.py",
]
```

---

## 🐛 Résolution de problèmes

### Erreur : "File not found"

**Cause** : Chemin invalide dans `--path`

**Solution** : Vérifier le chemin relatif depuis la racine du projet

```bash
# ❌ Incorrect
uv run python -m scripts.migrer_nomenclature --path /chemin/absolu

# ✅ Correct
uv run python -m scripts.migrer_nomenclature --path dsl/examples/
```

### Erreur : "Permission denied"

**Cause** : Fichier en lecture seule ou verrouillé

**Solution** : Fermer les éditeurs, déverrouiller le fichier

```bash
# Vérifier les permissions
ls -la le_fichier.json

# Rendre modifiable
chmod u+w le_fichier.json
```

### Corrections manquées

**Cause** : Pattern non couvert par les règles

**Solution** : Ajouter une règle personnalisée (voir Personnalisation)

---

## 📚 Références

- [docs/nomenclature_dsl.md](../docs/nomenclature_dsl.md) - Vocabulaire officiel
- [docs/objectifs_configurables.md](../docs/objectifs_configurables.md) - Objectifs avec bonne nomenclature
- [CLAUDE.md](../CLAUDE.md) - Architecture T-R-C-O

---

## ✅ Checklist post-migration

Après avoir lancé le script :

- [ ] Rapport généré et vérifié
- [ ] Tests passent (`uv run pytest`)
- [ ] Lint propre (`uv run ruff check .`)
- [ ] Format correct (`uv run ruff format --check .`)
- [ ] API démarre (`uv run uvicorn api.app:app`)
- [ ] Dashboard démarre (`cd dashboard && npm run dev`)
- [ ] Commit avec message clair
- [ ] PR créée avec référence au rapport de migration

---

## 💡 Conseils

1. **Toujours faire un dry-run d'abord**
2. **Lire le rapport avant d'appliquer**
3. **Utiliser --backup la première fois**
4. **Tester après chaque migration**
5. **Commiter souvent** (avant/après migration)
6. **Relancer périodiquement** pour attraper les nouveaux fichiers

---

## 🎓 Exemple complet

```bash
# Workflow complet recommandé
cd /path/to/Prisme

# 1. Sauvegarder l'état actuel
git status
git add -A
git commit -m "Snapshot avant migration nomenclature"

# 2. Dry-run pour voir ce qui va changer
uv run python -m scripts.migrer_nomenclature --dry-run

# 3. Lire le rapport
less rapport_migration.md

# 4. Si tout semble OK, appliquer avec backup
uv run python -m scripts.migrer_nomenclature --backup

# 5. Vérifier les changements
git diff --stat
git diff dsl/examples/  # Vérifier un dossier spécifique

# 6. Tests
uv run pytest tests/unit/
uv run ruff check .

# 7. Si OK, commit
git add -A
git commit -m "feat: Migre nomenclature Ressource → Ressource

- M1, M2, M3 → R1, R2, R3
- ressource → ressources
- *_par_machine → *_par_ressource
- 156 corrections dans 42 fichiers

Voir rapport_migration.md pour le détail"

# 8. Vérifier qu'il ne reste rien
uv run python -m scripts.migrer_nomenclature --dry-run --silencieux
# Devrait afficher : 0 fichier(s) modifié(s)

# 9. Push
git push origin feature/migration-nomenclature
```

---

**Créé par** : Scripts PRISME  
**Version** : 1.0.0  
**Dernière mise à jour** : 2026-07-20
