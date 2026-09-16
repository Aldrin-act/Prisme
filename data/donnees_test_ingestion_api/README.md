# Données de test — onglet « API » de la page Données

`atelier_menuiserie.json` est déjà au format **T-R-C-O canonique** (pas un
format ERP propriétaire) — contrairement aux jeux de données de
`donnees_brutes_metier_complexe/`, il n'a besoin d'aucune interprétation par
l'agent de compréhension : la conversion passe par le chemin déterministe
(`adapters.json_import.traduire`, bouton « Convertir sans IA » sur la page
Données), garantie de réussir à chaque fois, sans appel LLM.

Vérifié bout en bout avant d'être livré ici (voir aucune commande à
rejouer, juste pour mémoire) — via le chemin réel de l'app
(`adapters.json_import.traduire`, pas juste le schéma Pydantic brut) :
- conversion sans avertissement (`resultat.avertissements == ()`) ;
- un planning naïf (compatibilité + précédence seulement, sans même
  résoudre la capacité/disponibilité/échéance) est déjà déclaré **légal**
  par `validation_engine.feasibility_checker.verifier_faisabilite` —
  zéro violation, stable sur 5 exécutions répétées.

Une première version incluait aussi une contrainte `changement_serie` :
retirée après vérification — le solveur minimal de dev utilisé pour ce test
ne la modélise pas et produisait un planning qui la violait (un vrai
solveur CP-SAT généré l'aurait respectée, mais autant garder cet exemple
vérifiable de bout en bout avec les outils à disposition plutôt que de se
fier à un raisonnement non vérifié).

## Contenu

8 tâches, 6 ressources, 5 types de contraintes différents en une seule
instance (`precedence`, `compatibilite_ressource_tache`, `echeance`,
`capacite`, `disponibilite_ressource`) — un atelier de menuiserie fictif
avec deux lots de production en parallèle.

## Utiliser avec l'onglet « API »

L'onglet ne fait qu'un appel HTTP et prend la réponse telle quelle — il faut
donc servir ce fichier quelque part avant de pouvoir en donner l'URL :

```bash
cd data/donnees_test_ingestion_api
python -m http.server 8888
```

Puis, dans PRISME → **Données → Source en cours → onglet API** :
- URL : `http://localhost:8888/atelier_menuiserie.json`
- Méthode : GET
- Authentification : Aucune

Cliquer sur « Appeler l'API » remplit le champ « Données brutes » avec le
contenu du fichier — vérifiable avant d'« Enregistrer la source », puis
« Convertir sans IA » pour une conversion instantanée et déterministe.
