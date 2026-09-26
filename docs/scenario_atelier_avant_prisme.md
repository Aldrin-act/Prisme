# Scénario industriel — un atelier qui ordonnance à la main

*Situation de référence, avant toute solution d'optimisation. Entreprise fictive, données
construites pour être cohérentes et rejouables.*

---

## A. Présentation de l'entreprise

### L'activité

**ATLAS MÉTAL INDUSTRIE** (AMI) est une PME industrielle installée en zone industrielle à
Casablanca. Elle fait de la **sous-traitance mécanique** : on lui envoie un plan, elle fabrique la
pièce ou l'ensemble. Trois familles de clients :

- **l'agroalimentaire** — châssis de convoyeurs, trémies, tables de tri, tout en inox 304 ;
- **la pharmacie et la cosmétique** — mobilier et équipements inox poli miroir, exigences de
  finition très élevées ;
- **l'automobile de rang 2** — pièces de tôlerie en série (supports, platines), avec contrat cadre,
  délais fermes et pénalités de retard.

AMI ne vend pas de catalogue : chaque commande est une fabrication à la demande, sur plan client.
C'est ce qui rend son atelier difficile à planifier — deux commandes ne se ressemblent jamais
complètement.

### Les produits

| Famille | Exemple de produit | Matière | Taille de lot typique |
| --- | --- | --- | --- |
| Convoyage agroalimentaire | Châssis de convoyeur soudé | Inox 304, 2 mm | 20 à 60 |
| Stockage / vrac | Trémie pliée et soudée | Inox 304, 2 mm | 40 à 80 |
| Mobilier technique | Table de tri poli miroir | Inox 304, 1,5 mm | 4 à 12 |
| Série automobile | Support moteur peint | Acier DC01, 3 mm | 150 à 400 |
| Mécanique | Carter usiné | Aluminium / acier barre | 5 à 30 |

### Les moyens

- **84 salariés**, dont **58 en production**.
- **14 machines**, regroupées en cinq secteurs : découpe, pliage, usinage, soudure, finition, plus
  une zone de montage.
- **Deux équipes** : équipe A de 6 h à 14 h, équipe B de 14 h à 22 h, du lundi au vendredi. Le
  samedi matin (6 h – 12 h) est ouvert en heures supplémentaires, sur accord du directeur de
  production, et reste exceptionnel.
- Un **seul technicien de maintenance**, Saïd, en journée.

### Le volume de travail

L'atelier reçoit **15 à 20 commandes nouvelles par semaine** et porte en permanence **60 à 80
ordres de fabrication ouverts**, à des stades d'avancement différents. Chaque ordre de fabrication
compte en moyenne **4 à 5 opérations**, ce qui représente de l'ordre de **300 opérations en attente
ou en cours** à un instant donné.

### Qui décide, et avec quoi

L'ordonnancement repose sur **une seule personne** : Nadia, responsable ordonnancement, treize ans
de maison. Elle construit et maintient le planning de l'atelier dans un classeur Excel,
`PLANNING_ATELIER_S25.xlsx` : un onglet par semaine, une ligne par machine, une colonne par
demi-journée. Elle travaille avec le chef d'atelier, Brahim, qui lui remonte l'avancement réel, et
avec le service commercial, qui lui fait remonter les urgences clients.

Quand Nadia est absente, personne ne sait reconstruire le planning dans le même délai. Cette
dépendance est connue dans l'entreprise et acceptée faute de mieux.

---

## B. Commandes reçues

On se place le **lundi de la semaine 25**, à 6 h du matin. On appelle **J1** ce lundi, **J2** le
mardi, etc. Six commandes sont en portefeuille et doivent toutes passer dans l'atelier cette
semaine ou la suivante.

| Réf. | Client | Produit | Qté | Priorité | Délai demandé | Motif de la priorité |
| --- | --- | --- | --- | --- | --- | --- |
| CMD-2425 | AUTOPARTS | Reprise de supports rebutés | 15 | Urgente | J+2 | Lot refusé au contrôle client, à reprendre avant le prochain enlèvement |
| CMD-2415 | AUTOPARTS | Supports moteur peints | 250 | Critique | J+5 | Contrat cadre, pénalité contractuelle par jour de retard |
| CMD-2423 | PHARMA-CAST | Tables de tri inox poli | 8 | Haute | J+7 | Chantier client planifié, pose déjà programmée |
| CMD-2412 | AGRO-NORD | Châssis de convoyeur inox | 40 | Haute | J+8 | Ligne du client arrêtée en attente des châssis |
| CMD-2418 | HYDROMEC | Carters usinés | 12 | Normale | J+11 | Réapprovisionnement de stock client |
| CMD-2421 | AGRO-NORD | Trémies inox | 60 | Normale | J+13 | Projet d'extension, pas d'urgence affichée |

### Le détail des opérations

Chaque commande se décompose en une **gamme** : une suite d'opérations dans un ordre imposé. Pour
chaque opération, l'atelier connaît les machines capables de la faire et une durée estimée pour le
lot complet.

| Commande | Op. | Opération | Machines compatibles | Durée estimée (lot) |
| --- | --- | --- | --- | --- |
| CMD-2425 | 1 | Décapage + reprise de soudure | SOU-01 *ou* SOU-03 | 3 h |
| CMD-2425 | 2 | Peinture poudre | FIN-01 | 4 h |
| CMD-2425 | 3 | Contrôle final | FIN-02 | 1 h |
| CMD-2415 | 1 | Découpe tôle acier 3 mm | DEC-01 (6 h) *ou* DEC-02 (9 h) | 6 h / 9 h |
| CMD-2415 | 2 | Pliage | PLI-01 (10 h) *ou* PLI-02 (14 h) | 10 h / 14 h |
| CMD-2415 | 3 | Soudure MIG acier | SOU-01 (18 h) *ou* SOU-03 (20 h) | 18 h / 20 h |
| CMD-2415 | 4 | Peinture poudre RAL 7016 | FIN-01 | 12 h |
| CMD-2415 | 5 | Contrôle + emballage | FIN-02 | 4 h |
| CMD-2423 | 1 | Découpe laser inox 1,5 mm | DEC-01 | 3 h |
| CMD-2423 | 2 | Pliage petits panneaux | PLI-02 (4 h) *ou* PLI-03 (6 h) | 4 h / 6 h |
| CMD-2423 | 3 | Soudure TIG inox | SOU-02 (10 h) *ou* SOU-03 (11 h 30) | 10 h / 11 h 30 |
| CMD-2423 | 4 | Polissage miroir | FIN-02 | 9 h |
| CMD-2423 | 5 | Montage + emballage | MON-01 | 4 h |
| CMD-2412 | 1 | Découpe laser inox 2 mm | DEC-01 | 5 h |
| CMD-2412 | 2 | Pliage | PLI-01 (6 h) *ou* PLI-02 (7 h) | 6 h / 7 h |
| CMD-2412 | 3 | Soudure TIG inox | SOU-02 (22 h) *ou* SOU-03 (26 h) | 22 h / 26 h |
| CMD-2412 | 4 | Ébavurage + brossage | FIN-02 | 8 h |
| CMD-2412 | 5 | Montage | MON-01 | 6 h |
| CMD-2418 | 1 | Débit de barres | DEC-02 | 2 h |
| CMD-2418 | 2 | Tournage | TOU-01 (9 h) *ou* TOU-02 (11 h) | 9 h / 11 h |
| CMD-2418 | 3 | Fraisage 4 axes | USI-02 | 14 h |
| CMD-2418 | 4 | Contrôle dimensionnel | FIN-02 | 3 h |
| CMD-2421 | 1 | Découpe laser inox 2 mm | DEC-01 | 7 h |
| CMD-2421 | 2 | Pliage grands panneaux (2,6 m) | PLI-01 | 9 h |
| CMD-2421 | 3 | Soudure TIG inox | SOU-02 (16 h) *ou* SOU-03 (19 h) | 16 h / 19 h |
| CMD-2421 | 4 | Ébavurage | FIN-02 | 6 h |

Soit **26 opérations** à placer, sur 14 machines, avec des équipes de 8 heures.

Ce qui se lit déjà dans ce tableau : la découpe laser DEC-01 est demandée par quatre commandes sur
six, le poste de soudure TIG inox SOU-02 par trois, le poste d'ébavurage/polissage FIN-02 par les
six, et la presse plieuse PLI-01 est la **seule** capable de plier les panneaux de 2,6 m des
trémies.

---

## C. Ressources disponibles

### Les machines

| Code | Machine | Opérations réalisables | Capacité | Contraintes propres |
| --- | --- | --- | --- | --- |
| DEC-01 | Découpe laser fibre 3 kW, table 3 × 1,5 m | Découpe acier, inox, alu | 1 tôle à la fois | Changement de gaz et de buse 20 min au passage acier ↔ inox. Nettoyage de filtre 1 h 30, planifié J4 6 h |
| DEC-02 | Poinçonneuse CN + scie à ruban | Découpe et poinçonnage acier ≤ 4 mm, débit de barres | 1 pièce à la fois | Ne traite pas l'inox poli (marquage des outils). ~50 % plus lente que le laser sur tôle |
| PLI-01 | Presse plieuse CN 100 T, tablier 3 m | Pliage toutes tôles, panneaux jusqu'à 3 m | 1 pièce à la fois | **Seule machine > 1,5 m.** Changement d'outil 45 min. Le réglage exige un régleur habilité (Karim uniquement) |
| PLI-02 | Presse plieuse CN 60 T, tablier 1,5 m | Pliage tôles ≤ 1,5 m | 1 pièce à la fois | Changement d'outil 30 min |
| PLI-03 | Plieuse manuelle 40 T | Petits pliages, prototypes | 1 pièce à la fois | Précision moindre, réservée aux petites séries. Pas de répétabilité garantie |
| TOU-01 | Tour CN 2 axes | Tournage | 1 pièce | — |
| TOU-02 | Tour CN 2 axes (plus ancien) | Tournage | 1 pièce | ~20 % plus lent que TOU-01 |
| USI-01 | Centre d'usinage 3 axes | Fraisage 3 axes | 1 pièce | Ne fait pas les pièces à reprise en 4e axe |
| USI-02 | Centre d'usinage 4 axes | Fraisage 3 et 4 axes | 1 pièce | **Seule machine 4 axes de l'atelier** |
| SOU-01 | Poste de soudure MIG | Soudure acier | 1 poste, 1 soudeur | Interdit à l'inox (contamination ferreuse) |
| SOU-02 | Poste de soudure TIG, cabine inox dédiée | Soudure inox | 1 poste, 1 soudeur | Exige un soudeur **certifié inox** |
| SOU-03 | Poste polyvalent MIG/TIG | Acier et inox | 1 poste, 1 soudeur | ~15 % plus lent. **1 h de nettoyage complet** au passage acier → inox |
| FIN-01 | Cabine de peinture poudre + four | Peinture poudre | 3 pièces simultanément dans le four, cycle 40 min | Changement de teinte 35 min. **Maintenance préventive contractuelle J3 de 12 h à 14 h**, non déplaçable |
| FIN-02 | Poste d'ébavurage, polissage et contrôle | Ébavurage, brossage, polissage miroir, contrôle dimensionnel | 1 pièce à la fois | Le polissage miroir exige une opératrice qualifiée (Fatima, équipe A uniquement) |
| MON-01 | Zone de montage et emballage | Assemblage final, conditionnement | 2 ensembles en parallèle | — |

### Les opérateurs

| Nom | Équipe | Compétences / habilitations | Remarque |
| --- | --- | --- | --- |
| Youssef | A (6 h – 14 h) | Laser DEC-01, poinçonneuse DEC-02 | — |
| Karim | A | **Réglage et conduite** PLI-01, PLI-02, PLI-03 | **Seul régleur habilité PLI-01** |
| Rachid | A | Soudure TIG inox **certifié**, soudure MIG | Certification à renouveler en octobre |
| Hassan | A | Soudure MIG acier | Non certifié inox |
| Mehdi | A | Tours CN, centres d'usinage | — |
| Fatima | A | Polissage miroir, ébavurage, contrôle dimensionnel | **Seule qualifiée polissage miroir** |
| Jamal | B (14 h – 22 h) | Laser DEC-01, poinçonneuse DEC-02 | — |
| Abdelilah | B | **Conduite** PLI-01, réglage et conduite PLI-02 | Peut faire tourner PLI-01 sur un réglage déjà fait, **pas le changer** |
| Samira | B, mi-temps 14 h – 18 h | Soudure TIG inox **certifiée** | 4 h par jour seulement |
| Omar | B | Soudure MIG acier | — |
| Nabil | B | Tours CN | Pas habilité centres d'usinage |
| Soukaina | B | Peinture poudre, contrôle, ébavurage | — |
| Saïd | Journée | Maintenance, renfort peinture | Seul technicien de maintenance |

Deux conséquences immédiates de ce tableau, et ce sont les plus douloureuses :

1. **Le poste SOU-02 ne peut tourner que 12 h par jour**, pas 16 : 8 h avec Rachid en équipe A,
   4 h avec Samira en équipe B. Or les trois commandes inox demandent **48 heures** de soudure TIG
   au total. La cabine existe, la compétence manque.
2. **PLI-01 ne peut changer d'outil qu'en équipe A**, quand Karim est là. En équipe B, la machine
   continue sur le réglage du matin ou s'arrête. Un changement de série décidé l'après-midi se
   traduit par une machine à l'arrêt jusqu'au lendemain 6 h.

### La matière

| Matière | Stock au J1 | Besoin de la semaine | Réapprovisionnement |
| --- | --- | --- | --- |
| Tôle inox 304, 2 mm (2,5 × 1,25 m) | 48 tôles | CMD-2412 : 22 — CMD-2421 : 30 — CMD-2423 : 9 → **61 tôles** | 40 tôles annoncées J4 vers 8 h |
| Tôle acier DC01, 3 mm | 90 tôles | CMD-2415 : 62 | Suffisant |
| Poudre RAL 7016 (anthracite) | 1 fût entamé | CMD-2415 + CMD-2425 | Suffisant |
| Barres acier Ø 80 | 15 barres | CMD-2418 : 12 | Suffisant |

Le stock inox est donc **insuffisant de 13 tôles** pour couvrir la semaine. La livraison de jeudi
est annoncée mais non garantie. Nadia le sait, elle a noté « attention inox » dans la marge de son
classeur.

---

## D. Contraintes que subit le planificateur

Toutes ces contraintes sont réelles, connues de l'atelier, et aucune n'est écrite dans un endroit
unique.

### Contraintes d'enchaînement

- L'ordre des opérations d'une gamme est imposé : on ne soude pas avant d'avoir plié, on ne peint
  pas avant d'avoir soudé, on ne contrôle pas avant d'avoir fini.
- Le montage final d'un ensemble attend **toutes** ses pièces : une seule pièce en retard bloque la
  livraison du lot complet.

### Contraintes de compatibilité

- Les panneaux de trémie de 2,6 m ne passent que sur **PLI-01**. Aucune solution de repli interne.
- Le fraisage en 4e axe ne passe que sur **USI-02**.
- L'inox poli ne passe pas sur la poinçonneuse **DEC-02** : les outils marquent la surface.
- L'inox ne se soude pas sur **SOU-01** : risque de contamination ferreuse, donc de corrosion chez
  le client.

### Contraintes de compétence

- Soudure TIG inox : Rachid ou Samira, personne d'autre. C'est une exigence de certification, pas
  un avis interne.
- Réglage de PLI-01 : Karim uniquement.
- Polissage miroir : Fatima uniquement, et seulement en équipe A.

### Contraintes de capacité

- Chaque machine ne traite qu'une pièce à la fois, sauf la cabine de peinture (3 pièces par cycle
  de four) et la zone de montage (2 ensembles).
- Le four de peinture impose un **cycle indivisible de 40 min** : on ne sort pas une pièce en cours
  de cuisson pour en passer une plus urgente.

### Contraintes de disponibilité et de maintenance

- Maintenance préventive contractuelle de la cabine FIN-01, **J3 de 12 h à 14 h**. Si elle est
  décalée, le contrat de garantie du four tombe.
- Nettoyage de filtre du laser DEC-01, **J4 de 6 h à 7 h 30**.
- Fermeture de l'atelier de 22 h à 6 h et le week-end. Une opération commencée à 20 h avec 4 h de
  travail ne finit pas à minuit : elle s'arrête à 22 h et reprend le lendemain 6 h.

### Contraintes de changement de série

- Passage acier → inox sur le laser : 20 min de changement de gaz et de buse.
- Changement d'outil sur PLI-01 : 45 min, et Karim doit être présent.
- Changement de teinte sur la cabine de peinture : 35 min de purge.
- Passage acier → inox sur SOU-03 : **1 h de nettoyage complet** du poste.

Ces temps ne se voient pas dans les durées d'opération. Ils apparaissent seulement quand on décide
de l'**ordre** des travaux — et c'est exactement pour ça qu'ils se perdent facilement.

### Contraintes commerciales

- CMD-2415 est sous contrat cadre avec pénalité par jour de retard.
- CMD-2412 bloque une ligne de production chez AGRO-NORD : chaque jour compte pour le client, même
  si le contrat ne prévoit pas de pénalité.
- CMD-2423 doit être livrée avant une date de chantier fixée avec un poseur extérieur : arriver un
  jour trop tard, c'est faire décaler toute une intervention.
- AGRO-NORD est à la fois le client des châssis (urgents) et des trémies (non urgentes). Les deux
  commandes se disputent le même poste de soudure TIG et la même presse.

### Contrainte de matière

Aucune découpe inox au-delà de 48 tôles avant la livraison de J4. C'est une limite dure : pas de
tôle, pas de pièce.

---

## E. Comment le planning est construit, aujourd'hui

### La chaîne de décision

```text
                     Commandes (mail, ERP, appel du commercial)
                                    |
                                    v
                       Lecture et analyse manuelle
                    (carnet de commandes, délais, priorités)
                                    |
                                    v
                    Recherche des gammes de fabrication
                  (classeur papier + fichiers Excel produits)
                                    |
                                    v
                    Vérification des ressources disponibles
          (planning machines, habilitations affichées, congés, maintenance)
                                    |
                                    v
                       Vérification du stock matière
                        (ERP + appel au magasinier)
                                    |
                                    v
                        Affectation machine par machine
                     (choix humain, de mémoire et d'habitude)
                                    |
                                    v
                Construction du planning dans le classeur Excel
                    (une ligne par machine, une demi-journée
                              par colonne)
                                    |
                                    v
                        Passage en revue avec le chef
                      d'atelier — corrections manuelles
                                    |
                                    v
                            Validation et diffusion
                    (impression A3 affichée + PDF par mail)
                                    |
                                    v
                               Production
                                    |
                                    v
                          Aléa --> retour à l'analyse
```

### Étape par étape

**1. Réception et lecture des commandes.** Lundi 6 h 30, Nadia ouvre trois sources : le module
commercial de l'ERP (références, quantités, délais contractuels), sa boîte mail (les urgences
signalées par les commerciaux le vendredi soir), et un post-it laissé par le chef d'atelier. Aucune
de ces trois sources ne dit la même chose sur les priorités. La hiérarchie réelle, elle la
reconstruit de tête.

**2. Recherche des gammes.** Pour chaque commande, il faut savoir quelles opérations, dans quel
ordre, sur quelles machines, et combien de temps. Les gammes des produits récurrents sont dans un
classeur papier ; celles des produits récents dans des fichiers Excel dispersés dans un dossier
partagé. Pour les tables de tri PHARMA-CAST, Nadia retrouve deux versions de la gamme, avec des
durées différentes. Elle prend la plus récente, sans certitude que ce soit la bonne.

**3. Vérification des ressources.** Elle croise quatre choses : le planning des machines de la
semaine précédente (pour savoir ce qui déborde), le tableau des habilitations opérateurs (affiché
au mur, mis à jour au feutre), le planning de congés (autre fichier, tenu par les RH), et le cahier
de maintenance de Saïd (cahier papier, dans son atelier). Il n'existe aucun lien automatique entre
ces quatre supports.

**4. Vérification de la matière.** L'ERP annonce 52 tôles inox. Nadia appelle le magasinier, qui en
compte 48 : quatre ont été prises la semaine passée pour une retouche non saisie. Elle retient 48.
Ce genre d'écart est habituel et c'est pour ça qu'elle appelle systématiquement.

**5. Affectation des machines.** C'est le cœur du travail, et c'est entièrement une décision
humaine. Pour chaque opération, plusieurs machines conviennent souvent ; Nadia choisit selon des
règles qu'elle n'a jamais écrites : *les urgences d'abord*, *la machine la plus rapide pour les
grosses séries*, *on regroupe l'inox pour éviter les changements de gaz*, *on ne met pas un réglage
de presse l'après-midi*. Ces règles sont bonnes, mais elles ne sont ni tracées ni transmissibles.

**6. Construction du planning.** Elle remplit le classeur Excel case par case : ligne DEC-01,
colonne « lundi matin », elle tape `2415-OP1`. Environ deux heures de saisie pour la semaine. Le
fichier ne vérifie rien : il accepte deux ordres de fabrication sur la même case, une soudure inox
placée sur SOU-01, une opération de pliage programmée avant la découpe. C'est à elle de ne pas se
tromper.

**7. Passage en revue.** À 11 h, réunion debout de vingt minutes avec Brahim, le chef d'atelier.
Il corrige ce que le fichier ignore : « les trémies, elles font 2,60 m, elles ne passent que sur la
100 T », « Samira finit à 18 h, ta soudure de nuit ne tiendra pas ». Trois cases sont déplacées à
la main. Le planning tel qu'affiché n'a pas été vérifié : il a été **relu**.

**8. Validation et diffusion.** À 12 h, le planning est imprimé en A3 et affiché à l'entrée de
l'atelier, puis envoyé en PDF aux chefs d'équipe et au commercial. À partir de cet instant, la
version papier affichée et le fichier Excel vont commencer à diverger — dès la première
modification en cours de semaine.

### Ce que Nadia doit avoir en tête simultanément

Pour placer **une seule** opération correctement, il faut vérifier : la machine est-elle capable de
la faire, est-elle libre à ce moment, l'opération précédente est-elle terminée, l'opérateur
habilité est-il présent sur cette plage, y a-t-il un changement de série à prévoir avant, la
matière est-elle arrivée, la machine n'est-elle pas en maintenance, et le délai client sera-t-il
tenu au bout de la chaîne. **Huit vérifications, pour une opération, répétées 26 fois** — et la
26e remet en cause les 25 premières dès qu'un poste est saturé.

---

## F. Planning initial

Voici le planning que Nadia affiche le lundi à 12 h. Il tient, mais de justesse.

```text
Légende  A = équipe A (6h-14h)    B = équipe B (14h-22h)    .  = poste libre
         (R) = réglage / changement de série     [M] = maintenance
         Les codes sont les ordres de fabrication : 2415 = CMD-2415

Poste  |   J1 A   J1 B  |   J2 A   J2 B  |   J3 A   J3 B  |   J4 A   J4 B  |   J5 A   J5 B
-------+----------------+----------------+----------------+----------------+---------------
DEC-01 |   2415   2412  |   2421     .   |     .      .   |  [M]2421   .   |     .      .
       |     (R)  2423  |  (arrêt matière)|               |                |
DEC-02 |   2418     .   |     .      .   |     .      .   |     .      .   |     .      .
PLI-01 |(R)2415   2415  |(R)2412     .   |     .    2421  |   2421   2421  |   2421     .
PLI-02 |     .      .   |   2423     .   |     .      .   |     .      .   |     .      .
PLI-03 |     .      .   |     .      .   |     .      .   |     .      .   |     .      .
TOU-01 |   2418     .   |   2418     .   |     .      .   |     .      .   |     .      .
TOU-02 |     .      .   |     .      .   |     .      .   |     .      .   |     .      .
USI-01 |     .      .   |     .      .   |     .      .   |     .      .   |     .      .
USI-02 |     .      .   |   2418   2418  |     .      .   |     .      .   |     .      .
SOU-01 |   2425     .   |   2415   2415  |   2415     .   |     .      .   |     .      .
SOU-02 |     .      .   |     .      .   |   2412   2412  |   2412   2412  |   2423   2423
       |                |                |  (Rachid)(Samira)|            |   2423
SOU-03 |     .      .   |     .      .   |     .      .   |     .      .   |     .      .
FIN-01 |     .  (R)2425 |     .      .   |   2415  [M]2415|     .      .   |     .      .
FIN-02 |     .    2425  |     .    2418  |     .    2415  |   2415   2412  |   2412     .
MON-01 |     .      .   |     .      .   |     .      .   |     .      .   |   2412     .
```

### Les livraisons prévues

| Commande | Fin de fabrication prévue | Délai | Marge |
| --- | --- | --- | --- |
| CMD-2425 | J1, 19 h | J+2 | 1 jour d'avance |
| CMD-2418 | J2, 17 h | J+11 | 9 jours d'avance |
| CMD-2415 | J4, 8 h | J+5 | 1,5 jour d'avance |
| CMD-2412 | J5, 14 h | J+8 | 3 jours d'avance |
| CMD-2423 | J7, 11 h | J+7 | **1 h d'avance** |
| CMD-2421 | J8, 12 h | J+13 | 5 jours d'avance |

Ce tableau dit deux choses.

D'abord, **CMD-2423 (les tables de tri) n'a aucune marge**. Elle finit une heure avant son délai.
Le moindre incident sur la chaîne inox la fait basculer en retard. Nadia le sait, mais elle n'a pas
trouvé mieux : le poste de soudure TIG est occupé par les châssis AGRO-NORD jusqu'à J4 au soir,
et le polissage miroir n'est possible qu'en équipe A avec Fatima.

Ensuite, **CMD-2418 (les carters) est fabriquée neuf jours avant son délai**. Pas parce que c'est
utile, mais parce que le centre 4 axes était libre le mardi et qu'« une machine qui tourne, c'est
toujours mieux ». Cette pièce va occuper de la place au magasin, immobiliser de la matière et de la
main-d'œuvre, et surtout : ces heures de contrôle sur FIN-02 le mardi soir auraient pu servir aux
tables de tri. C'est un choix invisible dans le planning, et il coûte cher plus tard.

### Ce que le planning ne montre pas

- Le poste SOU-02 est chargé à **48 h sur 5 jours** pour une capacité humaine de 12 h/jour, soit
  60 h. Il est à **80 % de sa capacité réelle**, sans aucune réserve pour un aléa.
- Le poste FIN-02 reçoit **31 h** de travail, dont 9 h de polissage qui ne peuvent avoir lieu qu'en
  équipe A.
- Les postes PLI-03, TOU-02, USI-01 et SOU-03 ne travaillent **pas une seule heure** de la semaine.
  Quatre machines à l'arrêt pendant que trois autres saturent.

---

## G. La complexité du travail de planification

### Trop de données à croiser

Pour construire ce planning, Nadia a consulté **huit sources** sur **quatre supports différents** :
l'ERP (commandes, stocks), des fichiers Excel (gammes, planning, congés), du papier (classeur de
gammes, cahier de maintenance), et de l'oral (le magasinier, les commerciaux, le chef d'atelier).
Aucune de ces sources ne se met à jour depuis une autre. Chaque information recopiée est une
occasion de se tromper.

### La combinatoire, concrètement

Prenons seulement le **choix des machines**, sans même parler de l'ordre des travaux. Certaines
opérations n'ont qu'une machine possible, d'autres deux. En multipliant les choix commande par
commande, on obtient **1 024 façons différentes d'affecter ces 26 opérations** aux machines.

Ajoutons maintenant l'**ordre de passage**. Sur le seul poste FIN-02, six opérations se succèdent :
il y a 720 ordres possibles. Rien qu'en combinant les 1 024 affectations avec ces 720
ordonnancements, on dépasse **700 000 plannings possibles** — et on n'a pas encore touché à l'ordre
sur le laser, sur les presses ni sur les postes de soudure.

Un humain n'en explore pas 700 000. Il en explore **un**, celui que son expérience lui suggère,
qu'il corrige deux ou trois fois. Le planning affiché lundi n'est donc pas le meilleur planning :
c'est **le premier planning acceptable trouvé**. Personne dans l'entreprise ne sait de combien il
est loin du meilleur, parce que personne n'a de point de comparaison.

Et ce calcul portait sur six commandes. L'atelier en porte **soixante à quatre-vingts** en
permanence. À cette échelle, le nombre de combinaisons n'a plus de sens humain ; on ne planifie
plus, on réagit.

### Les conflits qu'il faut arbitrer à la main

- **AGRO-NORD contre AGRO-NORD** : les châssis urgents et les trémies non urgentes du même client
  se disputent PLI-01 et SOU-02. Avancer l'un retarde l'autre.
- **Machine libre contre compétence absente** : la cabine SOU-02 est disponible 16 h par jour, les
  soudeurs certifiés couvrent 12 h. Le planning Excel, lui, montre une machine libre — l'erreur est
  facile à faire.
- **Rapide contre disponible** : PLI-01 plie les supports en 10 h, PLI-02 en 14 h. Mettre les
  supports sur PLI-02 libère la 100 T pour les trémies, mais consomme 4 h de plus et décale la
  soudure MIG.
- **Urgent contre rentable** : la reprise CMD-2425 ne rapporte rien (c'est un rebut à corriger) mais
  passe devant tout le monde, parce qu'un camion client attend.

### Comparer des scénarios est pratiquement impossible

Nadia aimerait savoir ce que donnerait le planning si elle mettait les supports moteur sur la
petite presse, ou si elle faisait venir Samira à temps plein trois jours. Pour le savoir, il
faudrait **recopier tout le classeur, tout replacer à la main et tout revérifier** : une demi-journée
de travail par scénario, sans garantie que la deuxième version soit juste. Elle ne le fait donc pas.
Elle décide sur son intuition, et l'entreprise n'a aucune trace de l'alternative qui n'a pas été
essayée.

### Pourquoi ça se dégrade avec la taille

Quand le nombre de commandes augmente, trois choses se produisent en même temps. Le nombre de
combinaisons explose, alors que le temps de réflexion disponible n'augmente pas. Le nombre de
conflits entre commandes augmente plus vite que le nombre de commandes, parce qu'elles se
concentrent sur les mêmes goulots. Et la moindre modification a des répercussions plus lointaines,
donc plus difficiles à voir. Le planificateur ne devient pas moins bon : le problème devient trop
grand pour être tenu de tête.

---

## H. La perturbation

### 1. Ce qui était prévu

**J3, mercredi, 15 h 40.** Le planning affiché prévoit : PLI-01 plie les panneaux de trémie de
CMD-2421 de 14 h à 20 h, conduite par Abdelilah sur le réglage inox que Karim a monté le matin. En
parallèle, Samira soude les châssis CMD-2412 sur SOU-02 jusqu'à 18 h, la cabine de peinture finit
les supports CMD-2415 qui partent au contrôle dans la soirée.

Tout est conforme au planning depuis lundi. C'est même une bonne semaine.

### 2. Ce qui se passe réellement

À 15 h 40, en milieu de série, PLI-01 s'arrête. Le tablier descend anormalement lentement, puis
plus du tout, et une flaque d'huile apparaît sous la machine côté gauche. Abdelilah coupe
l'alimentation et appelle Brahim.

À 16 h, Saïd intervient. À 17 h 20, son diagnostic est posé : **fuite sur le vérin hydraulique de
l'axe gauche**, plus une carte codeur de position à remplacer par précaution. Le vérin n'est pas en
stock. Le fournisseur est à Aïn Sebaâ, il est 17 h 20, son standard est fermé.

Estimation de Saïd, sous réserve : devis demandé jeudi matin, pièce livrée sous trois jours
ouvrés au mieux, une demi-journée de remontage et de réglage. **PLI-01 est indisponible jusqu'au
lundi suivant, dans le meilleur des cas.**

À ce moment précis, 1 h 40 de pliage de trémies a été faite. Il en reste 7 h 20 à faire.

### 3. Les tâches impactées

| Tâche | État | Impact |
| --- | --- | --- |
| CMD-2421 OP2 — pliage trémies | Interrompue à 1 h 40 / 9 h | **Bloquée totalement.** Panneaux de 2,6 m, aucune autre presse de l'atelier ne les prend |
| CMD-2421 OP3 — soudure TIG | Non commencée | Ne peut pas commencer : rien à souder |
| CMD-2421 OP4 — ébavurage | Non commencée | Décalée d'autant |
| CMD-2412 OP2 — pliage châssis | Terminée J2 | Non impactée… en apparence (voir ci-dessous) |
| CMD-2415, CMD-2418, CMD-2425 | Terminées ou en finition | Non impactées |

**Et le lendemain matin, un deuxième coup.** J4, 6 h 30, Fatima démarre l'ébavurage des châssis
CMD-2412 et bloque le poste : sur les 40 châssis, **6 ont un angle de pliage hors tolérance**. Le
défaut vient d'une dérive de réglage sur PLI-01 le mardi — sans doute le tout début de la panne. Ces
six châssis doivent être repliés. **Sur PLI-01.** Qui est en panne.

CMD-2412, la commande qui bloque une ligne de production chez AGRO-NORD, avait trois jours de marge.
Elle n'en a plus.

### 4. Les commandes retardées

| Commande | Fin prévue | Situation après la panne | Délai |
| --- | --- | --- | --- |
| CMD-2421 (trémies) | J8, 12 h | Pliage bloqué jusqu'à J+6 minimum → fin repoussée au-delà de J11 | J+13, encore tenable mais la marge fond |
| CMD-2412 (châssis) | J5, 14 h | 34 châssis sur 40 livrables ; 6 immobilisés pour retouche | J+8, **menacé sur le lot complet** |
| CMD-2423 (tables) | J7, 11 h | Non touchée directement, mais **elle n'avait qu'une heure de marge** et tout décalage sur SOU-02 ou FIN-02 la fait basculer | J+7, **en danger** |

### 5. Les ressources devenues indisponibles

- **PLI-01** : hors service pour au moins trois jours ouvrés.
- **Karim** : son habilitation principale porte sur une machine à l'arrêt. Il peut aider sur PLI-02,
  qui n'a pas de travail programmé.
- **SOU-02 et les soudeurs certifiés** : pas indisponibles, mais **privés de travail** à partir de
  J6. Les trémies devaient les occuper 16 h. Le goulot le plus précieux de l'atelier va tourner à
  vide, non par manque de commandes mais parce que la pièce d'avant n'existe pas.
- **Saïd** : mobilisé sur le dépannage, donc indisponible pour le renfort peinture prévu J4.

### 6. Les décisions que le responsable doit prendre

Aucune de ces décisions n'est évidente, et toutes doivent être prises avant le lendemain midi.

1. **Livrer CMD-2412 en deux fois** (34 châssis maintenant, 6 après réparation), ou attendre pour
   livrer complet ? Livrer partiel, c'est un deuxième transport à payer et un client à convaincre.
   Attendre, c'est laisser sa ligne arrêtée plus longtemps.
2. **Sous-traiter le pliage des trémies** chez le plieur d'Aïn Sebaâ ? Un jour de transport aller,
   un jour de pliage, un jour de retour ; un surcoût ; et un risque réel sur la tolérance d'angle,
   qui est justement le défaut qu'on vient de découvrir en interne.
3. **Redécouper les panneaux en deux parties** pour les faire passer sur PLI-02, avec une soudure
   supplémentaire ? Cela change le produit : accord client obligatoire, et environ 6 h de soudure
   TIG en plus sur SOU-02 — le poste déjà le plus tendu.
4. **Que met-on sur SOU-02 à partir de J6** puisque les trémies n'arriveront pas ? Avancer les
   tables de tri PHARMA-CAST paraît évident, mais leur polissage dépend de Fatima en équipe A : on
   gagnerait sur la soudure pour bloquer au polissage.
5. **Ouvre-t-on le samedi matin ?** Cela coûte des heures supplémentaires et suppose que les bonnes
   personnes acceptent de venir — Karim et Fatima, pas n'importe qui.
6. **Demande-t-on à Samira de passer à temps plein** quelques jours ? Cela ferait passer SOU-02 de
   12 h à 16 h par jour. C'est la décision qui débloquerait le plus de capacité, et c'est celle à
   laquelle personne ne pense dans l'urgence, parce que la contrainte de compétence n'apparaît
   nulle part dans le planning.
7. **Qui prévient qui, et quand ?** AGRO-NORD sur les châssis, AGRO-NORD encore sur les trémies,
   PHARMA-CAST par précaution, les chefs d'équipe pour demain matin 6 h.

---

## I. La réaction de l'entreprise

Voilà comment ça se passe, concrètement, heure par heure.

**J3, 15 h 40 — Constat.** Abdelilah arrête la machine et va chercher Brahim. Aucune procédure
écrite : il cherche quelqu'un.

**J3, 16 h — Diagnostic.** Saïd démonte le carter, confirme la fuite. Personne ne sait encore
combien de temps ça va durer, donc personne ne peut encore décider quoi que ce soit.

**J3, 17 h 20 — Verdict et premier appel.** Trois jours minimum. Saïd appelle le fournisseur : le
standard est fermé. Brahim appelle Nadia, qui est partie à 16 h 30.

**J3, 17 h 45 — Inventaire manuel de l'impact.** Nadia revient. Elle imprime le planning de la
semaine et surligne au feutre toutes les cases où apparaît PLI-01. Elle en trouve cinq. Puis elle
remonte chaque gamme concernée pour voir ce qui dépend de ces cinq cases — et c'est là que le
travail devient long : le planning dit *quelle machine à quel moment*, il ne dit pas *quelles
commandes s'écroulent si cette machine tombe*. Cette information n'existe nulle part : il faut la
reconstituer gamme par gamme.

**J3, 18 h 30 — Recherche d'une machine de repli.** Elle vérifie les caractéristiques de PLI-02
(1,5 m de tablier) et de PLI-03 (40 T, manuelle). Panneaux de 2,6 m : ça ne passe pas. La
vérification est rapide, mais il fallait la faire, et il fallait se souvenir que la longueur de
tablier est le critère bloquant.

**J3, 19 h — Elle rentre.** Rien n'est décidé. La production de J4 commencera à 6 h sur un planning
qu'on sait déjà faux.

**J4, 6 h 30 — Le deuxième problème.** Fatima découvre les six châssis hors tolérance. Elle prévient
Brahim, qui met les six pièces de côté. Le planning affiché continue d'annoncer un montage complet
de CMD-2412 pour J5 à 14 h.

**J4, 8 h 10 — Devis fournisseur.** Le vérin est disponible, livraison annoncée lundi matin,
montage possible lundi après-midi. La reprise de PLI-01 est confirmée à J+7.

**J4, 9 h — Réunion de crise.** Nadia, Brahim, Saïd, le commercial d'AGRO-NORD et le directeur de
production. Quarante minutes. Décisions prises : on livre 34 châssis vendredi et les 6 restants la
semaine suivante, AGRO-NORD est prévenu dans la matinée ; on renonce à sous-traiter le pliage des
trémies (délai et risque qualité équivalents à l'attente) ; on avance les tables de tri
PHARMA-CAST sur la soudure TIG ; on rouvre la question du samedi matin vendredi, selon
l'avancement. La question de Samira à temps plein n'est pas évoquée.

**J4, 9 h 40 à 11 h 30 — Reconstruction du planning.** Deux heures de travail. Nadia reprend le
classeur, vide les cases PLI-01 de J3 à J5, décale les opérations de trémies vers la semaine
suivante, insère la soudure des tables de tri sur SOU-02 à partir de J5, reprend les affectations de
FIN-02 — et se heurte au polissage miroir : avancer les tables sur la soudure ne sert à rien si
Fatima n'a pas d'heures disponibles en équipe A. Elle déplace l'ébavurage des châssis en équipe B,
sur Soukaina, pour libérer Fatima. À 11 h 30, une version tient debout. Elle n'a **pas** vérifié
l'effet sur la semaine 26 : elle n'a pas le temps, et les commandes de la semaine 26 sont déjà
placées dans un autre onglet.

**J4, 11 h 45 — Vérification croisée.** Brahim relit. Il trouve une erreur : la soudure des tables
de tri a été placée jeudi 20 h – 22 h, alors que Samira part à 18 h et que Rachid est en équipe A.
Deux heures de soudure programmées sur un poste sans soudeur habilité. Correction à la main. Sans
cette relecture, l'erreur partait en production.

**J4, 12 h 15 — Diffusion.** Nouvelle impression A3, ancien planning décroché et jeté, PDF envoyé.
C'est la **troisième version** du planning de la semaine — il y en avait déjà eu une le mardi pour
la matière inox.

**J4, 14 h — Information des clients.** Le commercial appelle AGRO-NORD pour la livraison partielle
des châssis. Il ne dit rien des trémies, parce que le délai J+13 n'est pas encore officiellement
dépassé, et que personne n'a calculé la nouvelle date de fin. PHARMA-CAST n'est pas prévenu : on
espère tenir.

**J5 et suite — Le planning vit sa vie.** Vendredi, la livraison inox de jeudi arrive incomplète
(28 tôles sur 40). Le lundi suivant, le vérin arrive à 10 h et non à 8 h, et Saïd doit finir un
autre dépannage avant. PLI-01 redémarre mardi matin. À ce stade, le planning affiché a cessé de
décrire l'atelier : les chefs d'équipe travaillent « au plus urgent », en demandant à Brahim.

---

## J. Les conséquences

Rien de ce qui suit n'est chiffré, parce que **l'entreprise ne le mesure pas aujourd'hui**. C'est
justement un résultat du scénario : les difficultés sont visibles à l'œil nu et invisibles dans les
indicateurs. Chaque conséquence est donc donnée avec l'indicateur qui permettrait de la mesurer.

### Retards

**Observé dans le scénario.** CMD-2412 passe d'une livraison complète en une fois à une livraison
partielle plus un reliquat la semaine suivante. CMD-2421 voit sa date de fin repoussée sans que la
nouvelle date soit calculée. CMD-2423 finit sa semaine en danger alors qu'elle n'a jamais été
touchée par la panne.

**Indicateur de mesure.** Taux de commandes livrées complètes à la date promise (OTD-C), et retard
en jours par commande livrée, pondéré par la priorité client. Aujourd'hui : la date promise existe
dans l'ERP, la date réelle de fin de fabrication n'est pas enregistrée de façon fiable, donc
l'indicateur n'est pas calculable.

### Temps d'attente des pièces

**Observé.** Les panneaux de trémie déjà pliés attendent quatre jours devant un poste de soudure
disponible. Les carters CMD-2418, fabriqués neuf jours trop tôt, attendent au magasin.

**Indicateur.** Temps d'écoulement d'un ordre de fabrication (de la première à la dernière
opération), et part de ce temps passée en attente et non en usinage. Le rapport des deux dit
directement combien de temps les pièces passent à ne rien faire.

### Surcharge de certains postes

**Observé.** SOU-02 est chargé à 80 % de sa capacité humaine réelle avant tout incident, sans
aucune réserve. FIN-02 concentre les six commandes.

**Indicateur.** Taux d'occupation par machine, calculé sur la capacité **réellement ouvrable** —
c'est-à-dire en tenant compte de la présence des opérateurs habilités, pas des 16 h théoriques de
deux équipes. C'est cette distinction qui manque le plus : le planning actuel raisonne en heures
machine, l'atelier fonctionne en heures machine **et** compétence.

### Sous-utilisation d'autres postes

**Observé.** PLI-03, TOU-02, USI-01 et SOU-03 ne travaillent pas une heure de la semaine. SOU-03
aurait pu absorber une partie de la soudure inox.

**Indicateur.** Nombre de machines sous un seuil d'occupation (par exemple 20 %) sur la période, et
heures machine disponibles non consommées.

### Déséquilibre entre ressources

**Observé.** Dans la même semaine, quatre machines à l'arrêt et trois saturées. Ce n'est pas un
manque de capacité globale, c'est une mauvaise répartition.

**Indicateur.** Écart entre le poste le plus chargé et le moins chargé, ou écart-type des taux
d'occupation sur l'ensemble des postes. Un chiffre unique qui résume si la charge est étalée ou
concentrée.

### Temps passé à planifier et à replanifier

**Observé.** Environ deux heures pour construire le planning initial, vingt minutes de revue, puis
deux heures de reconstruction après la panne, plus une heure et demie d'analyse d'impact la veille
au soir. Et il y avait déjà eu une reprise le mardi pour la matière.

**Indicateur.** Heures de travail consacrées à la planification et à la replanification par
semaine, et part due aux aléas. Aucun système ne l'enregistre aujourd'hui : ce temps est absorbé
dans la journée de travail de Nadia et n'apparaît dans aucun coût.

### Instabilité du planning

**Observé.** Trois versions du planning en quatre jours. À partir du vendredi, plus personne ne
s'appuie sur le document affiché.

**Indicateur.** Nombre de versions diffusées par semaine, et proportion d'opérations dont la date ou
la machine a changé entre deux versions. C'est la mesure de la « nervosité » du planning : un
planning qui change tout le temps cesse d'être un plan et devient un compte rendu.

### Risque d'erreur

**Observé.** Deux erreurs réelles évitées de justesse par la relecture humaine : les trémies
placées sur une presse trop courte lundi, et deux heures de soudure programmées sans soudeur
habilité jeudi. Le classeur Excel n'en a signalé aucune.

**Indicateur.** Nombre d'incohérences détectées lors de la relecture, et nombre d'incohérences
passées en production. Le second chiffre est le plus important, et c'est celui que personne ne
collecte, parce qu'une erreur partie en production est traitée comme un aléa, pas comme une erreur
de planification.

### Difficulté à respecter les priorités affichées

**Observé.** Les carters HYDROMEC, priorité normale à J+11, sont fabriqués avant les tables de tri
PHARMA-CAST, priorité haute à J+7, parce qu'une machine était libre. La priorité est écrite sur la
commande et n'est pas utilisée dans la décision.

**Indicateur.** Corrélation entre la priorité affichée et l'ordre réel de passage en production ;
ou plus simplement, nombre de commandes de priorité basse terminées avant une commande de priorité
supérieure non encore commencée.

### Perte de connaissance

**Observé.** Les règles de décision de Nadia (grouper l'inox, ne pas régler la presse l'après-midi,
réserver le laser aux grosses séries) ne sont écrites nulle part. Les arbitrages de la réunion de
crise ne sont pas consignés : dans un mois, personne ne saura pourquoi on n'a pas sous-traité.

**Indicateur.** Part des décisions d'ordonnancement documentées avec leur motif ; et, plus
brutalement, délai de reconstruction d'un planning complet par une personne autre que le
planificateur habituel.

---

## K. Les points de friction

| Étape | Difficulté | Conséquence | Indicateur mesurable |
| --- | --- | --- | --- |
| Réception des commandes | Priorités venant de trois sources contradictoires (ERP, mail, oral) | La hiérarchie réelle des urgences n'existe que dans la tête du planificateur | Écart entre priorité déclarée dans l'ERP et ordre réel de passage |
| Recherche des gammes | Gammes réparties entre papier et Excel, deux versions trouvées pour un même produit | Durées estimées incertaines, planning bâti sur des données non fiables | Part des gammes disposant d'une version unique et datée |
| Vérification des ressources | Machines, habilitations, congés et maintenance dans quatre supports non reliés | Une opération peut être planifiée sur un poste sans opérateur habilité | Nombre d'opérations planifiées sans opérateur habilité présent |
| Vérification de la matière | Stock ERP faux de 4 tôles, corrigé par un appel téléphonique | Risque de lancer une découpe sans matière | Écart entre stock théorique et stock réel à l'inventaire |
| Affectation des machines | 1 024 affectations possibles pour 6 commandes, une seule explorée | Le planning retenu est le premier acceptable, pas le meilleur | Écart entre le temps de fin obtenu et une borne de référence calculée |
| Saisie du planning | Excel n'impose aucune règle : ni capacité, ni ordre des opérations, ni compatibilité | Les erreurs ne sont détectées que par relecture humaine, ou pas du tout | Nombre d'incohérences détectées en relecture / parties en production |
| Revue avec le chef d'atelier | La validation repose sur la mémoire de deux personnes | Dépendance forte à deux individus, non transmissible | Délai de reconstruction du planning par un tiers |
| Équilibrage de la charge | Aucune vue de la charge par poste au moment de décider | Quatre machines à l'arrêt, trois saturées la même semaine | Écart-type des taux d'occupation entre postes |
| Prise en compte des compétences | La capacité est raisonnée en heures machine, pas en heures machine + compétence | Le poste TIG apparaît disponible 16 h/jour alors qu'il l'est 12 h | Capacité théorique vs capacité réellement ouvrable, par poste |
| Comparaison de scénarios | Une demi-journée de recopie manuelle par variante | Aucune alternative n'est évaluée, les décisions ne sont pas comparées | Nombre de scénarios réellement évalués avant décision |
| Détection de l'aléa | L'arrêt machine se propage par la parole, sans procédure | Plus d'une heure avant que le planificateur soit informé | Délai entre l'arrêt effectif et l'information du planificateur |
| Analyse de l'impact | Le planning dit quelle machine, pas quelles commandes dépendent d'elle | 1 h 30 de reconstitution manuelle, et un impact (la retouche) découvert 15 h plus tard | Délai entre l'aléa et la connaissance complète des commandes touchées |
| Replanification | 2 h de ressaisie, sans vérification de l'effet sur la semaine suivante | Le problème est repoussé dans un onglet qu'on regardera lundi | Heures de replanification par aléa ; nombre d'aléas par semaine |
| Diffusion des mises à jour | Papier affiché, PDF par mail, Excel maître : trois supports à resynchroniser | Les équipes travaillent sur des versions différentes | Nombre de versions actives simultanément dans l'atelier |
| Information des clients | Nouvelle date de fin non calculée pour les trémies, PHARMA-CAST non prévenu | Le client apprend le retard après coup, ou le jour même | Délai entre la détection d'un risque de retard et l'information du client |
| Traçabilité des décisions | Les arbitrages de la réunion de crise ne sont consignés nulle part | Impossible d'expliquer ou de réévaluer une décision plus tard | Part des décisions d'ordonnancement documentées avec leur motif |

---

## L. Indicateurs à mettre en place

Aucun de ces indicateurs n'est suivi aujourd'hui. Le tableau dit ce qu'il faudrait mesurer, et
pourquoi c'est aujourd'hui impossible ou approximatif.

| Indicateur | Définition | Ce qu'il révèle | Pourquoi il n'est pas mesuré aujourd'hui |
| --- | --- | --- | --- |
| OTD complet | Part des commandes livrées complètes à la date promise | Performance vue par le client | La date réelle de fin de fabrication n'est pas enregistrée |
| Retard pondéré | Somme des jours de retard × poids de priorité | Si les retards touchent les clients importants | Ni les retards ni les poids ne sont formalisés |
| Temps d'écoulement | Durée entre la 1re et la dernière opération d'un ordre | Fluidité de l'atelier | Les débuts et fins d'opération ne sont pas horodatés |
| Part d'attente | Temps d'attente / temps d'écoulement | Combien de temps les pièces ne font rien | Même cause |
| Occupation par poste | Heures travaillées / heures réellement ouvrables du poste | Où sont les goulots | La capacité ouvrable dépend des habilitations, non modélisées |
| Déséquilibre de charge | Écart-type des taux d'occupation entre postes | Si la charge est étalée ou concentrée | Dépend de l'indicateur précédent |
| Postes inactifs | Nombre de postes sous 20 % d'occupation | Capacité payée et non utilisée | Dépend de l'indicateur précédent |
| Temps de planification | Heures/semaine passées à planifier et replanifier | Coût caché de l'ordonnancement manuel | Absorbé dans le temps de travail, jamais déclaré |
| Nervosité du planning | Nombre de versions/semaine et part d'opérations déplacées | Si le planning est un plan ou un constat | Les versions successives ne sont pas conservées |
| Délai de réaction | De l'aléa à la diffusion d'un planning révisé | Capacité de l'entreprise à absorber un imprévu | Ni l'heure de l'aléa ni celle de la diffusion ne sont tracées |
| Erreurs de planification | Incohérences détectées en relecture / passées en production | Fiabilité du processus lui-même | Les erreurs passées en production sont classées « aléas » |
| Respect des priorités | Commandes de priorité basse terminées avant des priorités hautes non commencées | Si la priorité commerciale sert à quelque chose | La priorité n'est pas utilisée comme donnée de décision |
| Scénarios évalués | Nombre d'alternatives comparées avant une décision | Qualité du processus de décision | Il n'y en a qu'une, donc l'indicateur vaut 1 par construction |
| Rebut et retouche | Part de pièces à reprendre, et heures machine consommées par les reprises | Coût de la qualité, et charge imprévue induite | Les reprises ne sont pas rattachées à l'ordre de fabrication d'origine |
| Recours aux heures supplémentaires | Heures samedi + sous-traitance d'urgence | Ce que coûte l'absorption des aléas | Suivi en paie, jamais rapproché des aléas qui l'ont causé |
| Ruptures matière | Nombre d'opérations bloquées faute de matière | Qualité du lien achats / production | Pas de trace du blocage, l'opération est juste décalée |

---

## M. Chronologie complète

```text
=== J1 — LUNDI ===
06:00  Ouverture de l'atelier, équipe A. Production sur planning de la semaine 24.
06:30  Nadia dépouille les commandes : ERP, mails du week-end, post-it du chef d'atelier.
07:15  Recherche des gammes. Deux versions trouvées pour les tables de tri PHARMA-CAST.
08:00  Croisement planning machines / habilitations / congés / cahier de maintenance.
08:45  Vérification matière. ERP : 52 tôles inox. Magasinier : 48. Retient 48.
09:00  Affectation des 26 opérations, machine par machine. Décisions de mémoire.
10:00  Saisie dans PLANNING_ATELIER_S25.xlsx, case par case.
11:00  Revue avec Brahim. 3 corrections à la main, dont les trémies sorties de PLI-02.
12:00  Validation. Impression A3 affichée, PDF envoyé aux chefs d'équipe.
06:45  (en parallèle) PLI-01 : réglage acier par Karim, puis pliage des supports CMD-2415.
14:00  Équipe B. Abdelilah poursuit le pliage sur le réglage du matin.
18:00  CMD-2425 (reprise) sortie de peinture.
19:00  CMD-2425 contrôlée et terminée. Livrable. 1 jour d'avance.
22:00  Fermeture.

=== J2 — MARDI ===
06:00  Karim change l'outil de PLI-01 pour l'inox (45 min), puis châssis CMD-2412.
06:00  Laser : découpe des trémies CMD-2421.
10:00  Laser arrêté : les 17 tôles inox disponibles sont consommées. Reste bloqué jusqu'à J4.
10:20  Nadia rééquilibre le planning pour tenir compte de la rupture matière.
       >>> VERSION 2 DU PLANNING <<<
14:00  Usinage 4 axes des carters CMD-2418, à 9 jours de leur délai, parce que la machine est libre.
17:00  CMD-2418 contrôlée et terminée.
22:00  Fermeture.

=== J3 — MERCREDI ===
06:00  Rachid démarre la soudure TIG des châssis CMD-2412 sur SOU-02.
06:00  Peinture des supports CMD-2415 dans la cabine FIN-01.
12:00  Maintenance préventive contractuelle de FIN-01 (2 h, non déplaçable).
14:00  Équipe B. Samira reprend la soudure TIG jusqu'à 18 h. Peinture relancée.
14:00  PLI-01 : Abdelilah démarre le pliage des trémies CMD-2421.
15:40  *** PANNE DE PLI-01 *** Tablier bloqué, fuite d'huile. Machine consignée.
15:45  Abdelilah cherche Brahim dans l'atelier.
16:00  Saïd démonte le carter et commence le diagnostic.
17:20  Diagnostic : vérin hydraulique + carte codeur. 3 jours ouvrés minimum. Fournisseur fermé.
17:30  Brahim appelle Nadia, déjà partie.
17:45  Nadia revient, imprime le planning et surligne les 5 cases PLI-01.
18:00  Reconstitution manuelle, gamme par gamme, des commandes dépendantes.
18:30  Vérification des presses de repli : PLI-02 (1,5 m), PLI-03 (40 T). Panneaux 2,6 m : refusé.
19:00  Nadia rentre. Aucune décision prise. L'atelier redémarrera à 6 h sur un planning faux.
22:00  Fermeture.

=== J4 — JEUDI ===
06:00  Équipe A. Le planning affiché est celui d'avant la panne.
06:30  *** Fatima découvre 6 châssis CMD-2412 hors tolérance de pliage. ***
       La retouche exige PLI-01. CMD-2412 perd ses 3 jours de marge.
08:00  Livraison inox annoncée : elle n'arrivera que vendredi, et incomplète.
08:10  Devis fournisseur : vérin livré lundi matin. PLI-01 opérationnelle mardi au mieux.
09:00  Réunion de crise (40 min) : Nadia, Brahim, Saïd, commercial, directeur de production.
       Décisions : livraison partielle de CMD-2412 (34 + 6) ; pas de sous-traitance du pliage ;
       avancement des tables PHARMA-CAST sur la soudure TIG ; samedi rediscuté vendredi.
       Non évoqué : faire passer Samira à temps plein, qui débloquerait 4 h/jour de TIG.
09:40  Reconstruction du planning. 2 h de ressaisie.
11:30  Version terminée. L'effet sur la semaine 26 n'est pas vérifié, faute de temps.
11:45  Relecture par Brahim : 2 h de soudure TIG programmées sans soudeur habilité. Corrigé.
12:15  Diffusion. >>> VERSION 3 DU PLANNING <<<
14:00  Le commercial prévient AGRO-NORD pour la livraison partielle des châssis.
       Rien n'est dit sur les trémies : la nouvelle date de fin n'a pas été calculée.
       PHARMA-CAST n'est pas prévenu.
22:00  Fermeture.

=== J5 — VENDREDI ===
06:00  Ébavurage des châssis en équipe B pour libérer Fatima sur le polissage.
10:00  Livraison inox : 28 tôles sur 40 annoncées. Les trémies restent partiellement bloquées.
14:00  34 châssis CMD-2412 expédiés. 6 immobilisés en attente de PLI-01.
16:00  Point sur le samedi : ouverture abandonnée, Karim n'est pas disponible.
22:00  Fermeture. Les chefs d'équipe travaillent désormais « au plus urgent ».

=== J+6 — LUNDI SUIVANT ===
10:00  Le vérin arrive (annoncé 8 h). Saïd termine un autre dépannage avant.
14:00  Remontage de PLI-01.

=== J+7 — MARDI SUIVANT ===
06:00  Karim règle PLI-01 et redémarre. Priorité : les 6 châssis à repiler.
09:00  Reprise du pliage des trémies CMD-2421.
       Le planning affiché ne décrit plus l'atelier depuis quatre jours.
```

---

## N. Version courte pour une présentation orale de deux minutes

> ATLAS MÉTAL INDUSTRIE est un sous-traitant de tôlerie et de mécano-soudure à Casablanca :
> quatre-vingts personnes, quatorze machines, deux équipes, et une soixantaine d'ordres de
> fabrication ouverts en permanence. Chaque commande est différente : un plan client, une suite
> d'opérations imposée, des machines compatibles, des durées estimées.
>
> Lundi matin, la responsable ordonnancement a six commandes à placer, soit vingt-six opérations.
> Elle croise huit sources d'information sur quatre supports : l'ERP, des fichiers Excel, des
> classeurs papier, et des conversations. Puis elle remplit son planning à la main, case par case,
> dans un fichier qui ne vérifie rien : ni les capacités, ni l'ordre des opérations, ni les
> compétences. Il lui faut deux heures, et le chef d'atelier corrige trois erreurs à la relecture.
>
> Rien que pour affecter ces vingt-six opérations aux machines, il existe plus de mille
> combinaisons possibles — et des centaines de milliers si on compte l'ordre de passage. Elle en
> explore une. Le planning affiché n'est pas le meilleur : c'est le premier qui tient debout.
> Résultat visible dès le lundi : quatre machines ne travailleront pas une heure de la semaine
> pendant que trois autres saturent, et une commande prioritaire finit une heure avant son délai.
>
> Mercredi 15 h 40, la grande presse plieuse tombe en panne. C'est la seule machine capable de
> plier les panneaux de deux mètres soixante. Trois jours de réparation.
>
> Et là, on découvre le vrai problème : l'entreprise ne sait pas dire quelles commandes sont
> touchées. Le planning indique quelle machine travaille quand, pas ce qui s'écroule si cette
> machine s'arrête. Il faut une heure et demie, planning surligné au feutre, pour reconstituer les
> dépendances. La responsable rentre chez elle sans avoir rien décidé ; l'atelier redémarre le
> lendemain à six heures sur un planning qu'on sait déjà faux. Le jeudi matin, on découvre un
> deuxième impact : six châssis à repiler, sur la machine en panne. Deux heures de ressaisie, une
> réunion de crise, une troisième version du planning en quatre jours — et une décision qui
> aurait libéré quatre heures par jour sur le poste le plus chargé n'est même pas évoquée, parce
> que la contrainte de compétence n'apparaît nulle part dans le planning.
>
> Personne n'a mal travaillé. Le problème est simplement devenu trop grand pour être tenu de tête :
> trop de contraintes, trop de sources, trop de combinaisons, et aucun moyen de comparer deux
> scénarios autrement qu'en recopiant tout à la main.

---

*Fin du scénario. Aucune solution n'est proposée à ce stade : ce document décrit la situation de
référence, celle à laquelle toute amélioration devra être comparée.*
