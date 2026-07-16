# dashboard — Tableau de bord & humain dans la boucle (§2.3, §9 Étape 9)

Interface qui matérialise le fil directeur du projet : le système propose, l'humain décide.

- Ingestion d'une instance et déclenchement humain de l'exécution. Un aléa atelier (panne,
  commande urgente, retard...) n'a pas de mécanisme dédié : il se traduit dans les contraintes
  de l'instance (ex. retirer la ressource en panne), qui est ré-ingérée puis réexécutée — le
  processus exact dépend du client, volontairement pas figé dans le noyau.
- Validation humaine du planning proposé avant application.
- Restitution de la boucle d'amélioration diagnostique (`diagnostics/`) sous décision humaine.

## Développement

React + Vite. Aucun temps réel (ni WebSocket ni SSE) : le frontend interroge l'API PRISME par
polling. Suppose l'API démarrée séparément (`uv run uvicorn api.app:app --reload`, port 8000,
CORS ouvert pour `localhost:5173` en dev).

```bash
npm install       # une seule fois
npm run dev       # serveur de dev Vite, http://localhost:5173
npm run build     # build de production dans dist/
```

`src/api.js` centralise l'URL de base de l'API — à adapter si l'API ne tourne pas sur
`http://localhost:8000`.
