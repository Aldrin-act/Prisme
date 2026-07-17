# Modèle d'ingestion T-R-C-O — à remettre au client

Format **déterministe** : un JSON à structure fixe, validé automatiquement par le schéma
(`dsl/schema/`), sans aucune IA impliquée dans la conversion. Le client (ou son ERP) remplit ce
gabarit directement — c'est l'alternative à un mapping assisté par LLM quand le client peut
produire lui-même le format canonique.

Pour quelqu'un qui préfère ne pas écrire de JSON à la main, la même structure existe en tableur :
[`gabarit_ingestion_trco.xlsx`](gabarit_ingestion_trco.xlsx) (régénérable via
`scripts/generer_gabarit_ingestion.py`). Il ajoute un onglet "Besoins additionnels" pour noter en
langage libre tout ce qui sort du périmètre minimal ci-dessous (calendriers, équilibrage de
charge, priorités...) — examiné à la main, jamais converti automatiquement.

## Les 4 sections à fournir

### `taches` (au moins une)

| Champ | Type | Obligatoire | Règle |
|---|---|---|---|
| `id` | texte | oui | 1 à 64 caractères, lettres/chiffres/`_`/`-` uniquement, unique parmi les tâches |
| `nom` | texte | non | libre, pour lisibilité humaine seulement |

### `ressources` (au moins une)

| Champ | Type | Obligatoire | Règle |
|---|---|---|---|
| `id` | texte | oui | même règle que pour `taches.id`, unique parmi les ressources |
| `nom` | texte | non | libre |

### `contraintes` (peut être vide, mais voir règle 3 ci-dessous)

Deux types possibles, chacun avec son propre champ `type` :

**Précédence** — la tâche `avant` doit finir avant que `apres` ne commence :
```json
{"type": "precedence", "avant": "<id-tache>", "apres": "<id-tache>"}
```

**Compatibilité ressource-tâche** — la tâche `tache` peut s'exécuter sur la ressource `ressource`,
en `duree` minutes (propre à ce couple tâche-ressource : deux ressources compatibles pour la même
tâche peuvent avoir des durées différentes) :
```json
{"type": "compatibilite_ressource_tache", "tache": "<id-tache>", "ressource": "<id-ressource>", "duree": <entier > 0>}
```

### `objectifs` (au moins un)

Un seul type supporté aujourd'hui :
```json
{"type": "minimiser_makespan"}
```

## Règles de validation automatiques (rejet avant tout calcul)

1. Un identifiant ne peut pas être répété au sein d'un même axe (deux tâches `id: "T1"` : rejeté).
2. Toute contrainte doit référencer des tâches/ressources réellement déclarées dans le fichier.
3. **Chaque tâche doit avoir au moins une compatibilité ressource-tâche** — sans ça, sa durée est
   inconnue et elle ne peut pas être planifiée.
4. Aucun champ en dehors de ceux listés ci-dessus n'est toléré (schéma strict — un champ en trop
   fait rejeter tout le fichier, pas seulement ce champ).

## Gabarit à remplir

```json
{
  "taches": [
    {"id": "<id-tache-1>", "nom": "<description optionnelle>"}
  ],
  "ressources": [
    {"id": "<id-ressource-1>", "nom": "<description optionnelle>"}
  ],
  "contraintes": [
    {"type": "precedence", "avant": "<id-tache>", "apres": "<id-tache>"},
    {"type": "compatibilite_ressource_tache", "tache": "<id-tache>", "ressource": "<id-ressource>", "duree": 30}
  ],
  "objectifs": [
    {"type": "minimiser_makespan"}
  ]
}
```

## Exemple rempli (atelier à 3 tâches)

Voir [`dsl/examples/valid/atelier_trois_taches.json`](../../dsl/examples/valid/atelier_trois_taches.json).

## Comment soumettre le fichier

```bash
curl -X POST http://localhost:8000/ingestion/<identifiant-client> \
  -H "Content-Type: application/json" \
  -d @mon_fichier.json
```

Réponse en cas de succès : `{"instance_id": "...", "structure_contraintes": "..."}` — l'instance est
mise en attente d'exécution, elle n'est pas encore planifiée.

## En cas d'erreur

Le serveur répond `422` avec le détail précis de chaque violation :

```json
{
  "detail": [
    {"loc": ["contraintes", 2, "duree"], "msg": "...", "type": "..."}
  ]
}
```

`loc` pointe l'emplacement exact dans le fichier envoyé (section, index, champ) — c'est ce qu'il
faut corriger et renvoyer, rien d'autre n'est modifié côté serveur.
