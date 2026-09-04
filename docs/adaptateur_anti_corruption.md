# L'adaptateur : couche anti-corruption

Un adaptateur ne fait qu'une chose : traduire une représentation propre à un système ou un
secteur — un tableur, un flux JSON d'un progiciel de gestion, une extraction ERP réelle — vers
le modèle pivot, sans jamais laisser cette représentation d'origine s'infiltrer plus loin dans
la chaîne. C'est une couche anti-corruption au sens propre : elle isole le noyau du système (le
modèle pivot, la génération, la validation) du vocabulaire, des conventions et des
incohérences propres à chaque source, si bien qu'aucun agent en aval n'a jamais à connaître le
format d'où proviennent les données qu'il traite.

Chaque adaptateur du dépôt expose une unique fonction de traduction en entrée du module, qui
reçoit les données brutes de sa source et renvoie une instance conforme au modèle pivot —
jamais une variante du modèle pivot adaptée à cette source. C'est le corollaire direct du
principe de neutralité sectorielle : si une source ne peut pas s'exprimer dans le vocabulaire
existant, c'est le modèle pivot qui doit être étendu, de façon générique et valable pour tous
les secteurs, jamais l'adaptateur qui invente un raccourci propre à un seul client.

Deux adaptateurs — les imports tabulaires CSV et JSON — vont plus loin : lorsqu'une donnée
requise, typiquement une durée, n'est pas déclarée dans la source, ils peuvent l'estimer plutôt
que de rejeter l'import, mais ne le font jamais silencieusement. La traduction renvoie alors, à
côté de l'instance produite, la liste explicite des champs complétés par estimation plutôt que
déclarés — un avertissement que l'utilisateur peut choisir d'ignorer, mais qui ne peut pas se
perdre dans l'instance elle-même.
