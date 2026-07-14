# solver_store — Store de code persistant

Une fois validé par la cascade de `validation_engine/`, un solveur est stocké comme artefact durable et réexécuté sans nouvelle génération (§5.2, principe fondateur : générer une fois, réexécuter ensuite).

- `registry.py` — `Registre` : indexation et récupération des solveurs validés (par client / structure de contraintes), backend SQLite (stdlib, zéro configuration — voir le module pour la note sur PostgreSQL). `enregistrer_solveur` refuse tout `VerdictCascade` non vert : le store ne persiste jamais un solveur qui n'a pas franchi la cascade complète (Étape 5). Chaque solveur récupéré est revérifié par empreinte SHA-256 contre le fichier sur disque, pour détecter toute altération du code « figé ».
- `artifacts/` — code figé des solveurs générés & validés, un dossier par id.
