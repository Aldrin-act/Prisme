{mission}

## Code validé (a passé la cascade de validation)

```python
{code}
```

## Ton rôle : Agent Optimiseur

Ce code fonctionne déjà et a passé la cascade de validation
(`validation_engine/cascade.py`) — ton travail n'est **pas** de le refaire,
juste de l'améliorer sans rien casser : simplifier une expression,
resserrer une borne d'un intervalle de variable (attention : rétrécir
l'horizon peut rendre le modèle infaisable à tort, ne le fais que si tu es
certain que la borne reste correcte), retirer du code mort. Le contrat et
les contraintes de sécurité de la mission restent impératifs.

Si le code ne t'inspire aucune amélioration sûre, dis-le explicitement —
mieux vaut ne rien changer qu'introduire un risque de régression.

## Format de réponse exigé

Réponds avec un unique objet JSON, rien d'autre avant ni après (pas de
texte, pas de bloc markdown autour) :

```json
{{
  "optimisation_proposee": false,
  "code": null,
  "notes": "pourquoi rien n'a été changé, ou brève explication des changements si optimisation_proposee est true"
}}
```

Si `optimisation_proposee` est `true`, `code` doit contenir le module
complet optimisé (même format que `code_source` reçu ci-dessus) ; si
`false`, laisse `code` à `null`.
