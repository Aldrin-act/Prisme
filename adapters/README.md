# adapters — Couche anti-corruption ERP (§5.4)

PRISME ne se connecte jamais directement aux bases de production des clients. Chaque ERP dispose d'un adaptateur qui traduit son format propriétaire vers le T-R-C-O canonique.

- `erp_reference/` — l'unique adaptateur réel construit pour la preuve de concept.
  - `schema_erp.py` — le format brut simulé (`PayloadERP`, `OperationERP`, `PosteERP`) : volontairement pauvre et dans un vocabulaire différent de T-R-C-O (un ERP legacy typique n'a qu'un poste par opération, jamais de choix de routage flexible).
  - `translator.py` — `traduire(payload: PayloadERP) -> InstanceTRCO` : la traduction proprement dite.
  - `mapping/regles.md` — la table de correspondance champ par champ.

  L'architecture démontre l'extensibilité aux autres ERP sans multiplier les connecteurs (§7) : un nouvel ERP n'ajoute qu'un nouveau `schema_erp.py` + `translator.py`, jamais de changement en aval.
