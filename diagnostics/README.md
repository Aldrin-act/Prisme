# diagnostics — Boucle d'amélioration (§5.7)

Quand un planning est jugé mauvais (KPI dégradés et/ou signal humain), attribue la cause par élimination, dans un ordre précis, avant toute action :

1. Test du code sur instances synthétiques à vérité terrain connue → code fautif ?
2. Test des données (faisabilité) → données corrompues ?
3. Test de la spécification (cas de référence) → DSL mal décrit ?

`attribution.py` diagnostique et propose une correction ; l'humain décide d'agir (fil directeur du projet, §2, §5.7).