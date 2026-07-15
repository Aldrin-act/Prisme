# dashboard — Tableau de bord & humain dans la boucle (§2.3, §9 Étape 9)

Interface qui matérialise le fil directeur du projet : le système alerte, l'humain décide.

- Alerte sur aléa atelier (panne, commande urgente, retard) et déclenchement humain du recalcul.
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
