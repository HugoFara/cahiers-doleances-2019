# Journal des décisions

Toute décision qui engage la lecture du corpus est consignée ici : périmètre,
segmentation, grille de thèmes, règles d'anonymisation, normalisation. Datée,
justifiée, attribuée, avec ce qu'il faudrait faire pour revenir dessus.

Ce journal est destiné à être **publié avec le corpus**. Une décision non écrite
n'est pas contestable, et un corpus dont on ne peut pas contester les choix se
lit comme un fait alors qu'il est un montage.

Format d'une entrée : date · décision · périmètre · motif · alternatives écartées
· conséquence mesurée · réversibilité · auteur.

---

## 2026-09-10 — L'unité d'analyse est la doléance, découpée par signaux de texte

**Décision.** Le corpus est découpé en *doléances* — ce qu'a écrit une personne —
par cinq signaux repérés dans le texte : ligne entièrement datée, formule
d'appel, formule de politesse suivie d'une signature, filet de séparation,
numérotation explicite de registre. Table `doleance`, module `segmentation/`.

**Périmètre.** Toutes les pages `page_extraction` non marquées `needs_ocr`.

**Motif.** L'unité précédente était la page (`extraction/without_ocr` crée une
contribution par page). Une page de registre porte souvent plusieurs
contributeurs et une doléance longue court sur deux pages : tout comptage à ce
niveau porte sur un agrégat multi-auteurs, et « combien de personnes demandent X »
n'a pas de réponse juste.

**Alternatives écartées.** La page (statu quo, mélange les auteurs) ; le cahier
entier (pire) ; un découpage par LLM (coûteux, non déterministe, et surtout non
mesurable tant qu'il n'y a pas de jeu de référence).

**Conséquence mesurée.** Sur les 2 855 pages de
`topic-builder/data/cahiers/dataset.csv` : 3 243 doléances, 11 % des pages
contiennent plus d'un contributeur repérable. C'est un **plancher** : les règles
ne lisent que le texte, elles ne voient ni le blanc vertical ni le changement
d'écriture, qui sont les deux vrais séparateurs d'un registre.

**Réversibilité.** Bonne, et garantie par un invariant testé : le découpage
partitionne les lignes sans en supprimer aucune, recoller les doléances redonne
le texte d'entrée. `python -m segmentation --force` rejoue tout.
*Limite levée le 2026-09-10 (voir l'entrée « Les couches interprétatives sont
versionnées ») : `doleance.run_id` rattache chaque découpage à son run, deux
découpages coexistent.*

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-10 — Le corpus analysé exclut les pages manuscrites

**Décision.** `export_dataset.py` et `segmentation/` écartent par défaut les
pages marquées `needs_ocr`, c'est-à-dire celles dont le score `wordfreq` est
inférieur à 0,3 — en pratique les pages manuscrites, dont l'extraction sans OCR
ne rend que du bruit.

**Périmètre.** Tout le corpus analysé à ce jour, y compris la livraison PoC
d'août 2026.

**Motif.** Technique et subi : sans OCR, le texte de ces pages n'est pas
exploitable et ferait dériver la découverte de thèmes.

**Conséquence.** Le corpus analysé est **la partie dactylographiée seulement** :
lettres de maires, contributions d'associations, textes tapés, courriers
formels. L'écriture ordinaire — celle de la personne qui passe à la mairie et
écrit trois lignes dans le registre — est hors champ. C'est vraisemblablement le
biais le plus lourd du projet à ce stade, et il porte précisément sur la
population que ces cahiers étaient censés faire entendre.

**Chiffré le 2026-09-10** (mesure sur les 516 cahiers de `data/raw/pdfs`,
5 365 pages, module `couverture/`) :

| Échelle | Écarté | |
|---|---|---|
| pages | 2 510 / 5 365 | **47 %** |
| cahiers touchés | 445 / 516 | 86 % |
| communes touchées | 402 / 459 | 88 % |
| cahiers entièrement écartés | 47 | |
| **communes sans aucune page lisible** | **37** | |

Les 2 855 pages retenues sont exactement les 2 855 documents de
`topic-builder/data/cahiers/dataset.csv` : le corpus analysé jusqu'ici, c'est
cette moitié-là. Trente-sept communes n'ont aucune voix dans l'analyse — leur
cahier existe, il a été numérisé, il ne compte pour rien.

*Corrigé le 2026-09-10 : la première version de cette entrée annonçait 24
communes muettes sur 307. Les communes y étaient comptées par la graphie de leur
en-tête, absente sur un tiers des cahiers — celles-là n'étaient comptées ni au
numérateur ni au dénominateur. Le rattachement au code INSEE donne 37 sur 459.
Les chiffres de pages et de cahiers n'ont pas bougé.*

**Le seuil tient.** `needs_ocr` se déclenche sous 0,3, ce qui est un réglage. La
distribution est bimodale (2 070 pages sous 0,2, 1 591 au-dessus de 0,9, un creux
entre), et déplacer la barre de 0,3 à 0,5 ne fait bouger la part que de 47 % à
52 %. « Environ la moitié du corpus » résiste donc à une hausse du seuil ; le
chiffre est en revanche sensible à une baisse, parce qu'on entame alors la masse
basse. Les 447 pages de la tranche 0,2-0,3 sont le vrai gris.

**Ce qu'il reste à faire.** Afficher ce taux à côté de tout comptage — il n'est
pour l'instant que dans la documentation et dans `python -m couverture`, pas dans
l'app. Réintégrer le manuscrit dès que l'HTR le permet, et refaire la comparaison
avant/après.

**Réversibilité.** Immédiate côté outillage (`--keep-ocr-pages`), nulle côté
qualité tant que l'HTR n'est pas là — réintégrer ces pages aujourd'hui
n'ajouterait pas des contributions, seulement du bruit d'extraction.

**Auteur.** Hérité du pipeline `extraction/without_ocr` (2026-08-07), explicité
ici le 2026-09-10.

---

## 2026-09-10 — Les identifiants de document portent leur niveau

**Décision.** L'id de document échangé avec l'équipe analyse est la clé primaire
de la ligne exportée, préfixée par son niveau : `42` pour une contribution, `d42`
pour une doléance. Format dans `database/identifiants.py`, partagé par l'export
et le chargement.

**Motif.** `contribution.id` et `doleance.id` sont deux séquences qui se
recouvrent. Sans marquage, une livraison portant sur des doléances serait
rechargée en désignant des contributions au hasard — silencieusement, puisque les
entiers « existent » des deux côtés.

**Alternatives écartées.** Un UUID par document (rompt la lisibilité des
livraisons déjà faites) ; une table de correspondance externe (un état de plus à
tenir synchronisé).

**Réversibilité.** Bonne : les livraisons antérieures, sans préfixe, restent
lues comme des contributions. Le garde-fou de `mesurer_correspondance` — qui
vérifie que les verbatims sont bien dans le texte visé avant de rattacher quoi
que ce soit — vaut pour les deux niveaux.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-10 — Les couches interprétatives sont versionnées et plurielles

**Décision.** Le découpage en doléances, les thèmes et les détections sont
rapportés à un `run` (table `run`, module `database/runs.py`) portant modèle,
version de prompt, paramètres appliqués, corpus, auteur et date. Dans chaque
genre — `segmentation`, `analyse` — un seul run est *actif* : c'est celui que
l'app et les exports servent. Les autres restent en base.

**Périmètre.** `doleance`, `topic`, `instance`. Les lignes antérieures ont été
rattachées par la migration à deux runs « hérités », dont le modèle, le prompt et
les paramètres sont perdus — ils n'avaient jamais été consignés.

**Motif.** Le principe d'organisation du corpus veut que les thèmes soient une
couche posée sur la provenance, pas la structure du corpus. La base ne le
permettait pas : `load_analysis.py` faisait `DELETE FROM instance` à chaque
livraison et upsertait les thèmes dans une table unique. **Une seule grille
pouvait exister à la fois** — charger une grille concurrente pour la comparer
détruisait la précédente. Des grilles plurielles n'étaient pas « à faire un
jour », elles étaient interdites par le schéma.

**Alternatives écartées.** Dupliquer la base par grille (ingérable, et les
comparaisons deviennent des jointures inter-bases) ; garder une seule grille et
archiver les JSON de livraison à côté (l'archive n'est pas interrogeable, la
comparaison redevient manuelle).

**Conséquences.**
- `topic.external_id` n'est plus unique dans la table mais dans un run. Les noms
  de thèmes non plus : toute lecture qui s'appuie dessus doit filtrer sur le run,
  ce que fait désormais la vue graphe de l'app.
- `python -m segmentation --force` est remplacé par `--nouveau-run` : on ne
  détruit plus un découpage pour en essayer un autre, on en pose un à côté.
- Recharger la même livraison la met à jour ; `--nouveau-run` en fait une grille
  de plus.

**Vérifié.** Sur une base Postgres jetable : la migration rattache les lignes
héritées sans en laisser d'orpheline, le downgrade rétablit la forme antérieure,
et deux grilles de 6 788 thèmes coexistent pendant que l'app n'en sert qu'une.

**Réversibilité.** Bonne dans le sens de l'ajout. Le downgrade échoue
délibérément si deux grilles coexistent : rétablir l'unicité globale de
`topic.external_id` demanderait de choisir laquelle supprimer, et ce choix
n'appartient pas à une migration.

**Ce qui reste ouvert.** Les runs hérités portent `author = "inconnu"`. Les runs
créés depuis portent l'auteur passé en ligne de commande, et les commandes
signalent son absence — mais rien ne l'impose encore.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-10 — L'étalon est versionné sans le texte des cahiers

**Décision.** Le jeu de référence annoté vit en deux fichiers : le fichier de
travail, qui porte le texte des cahiers ligne à ligne et reste dans `/data`
(ignoré par git) ; l'étalon figé, où chaque ligne est réduite à une empreinte
SHA-256 tronquée, commité dans `reference/etalon/`.

**Motif.** L'étalon doit être versionné — c'est la référence contre laquelle
tout est mesuré, elle doit voyager avec le code et son évolution doit être
lisible. Mais il porte 200 à 300 contributions citoyennes verbatim : le commiter
tel quel publierait des écrits nominatifs de personnes privées dans un dépôt
public, ce que tout le reste du plan s'emploie à éviter. L'empreinte tranche :
elle ne permet pas de relire le texte, elle permet de vérifier qu'il n'a pas
changé.

**Conséquence utile.** Le contrôle d'alignement n'est pas qu'une précaution de
confidentialité. Si l'extraction évolue et que les lignes se décalent, un étalon
désaligné produirait des scores parfaitement crédibles et parfaitement faux —
`evaluer` refuse alors de mesurer plutôt que de mentir.

**Réversibilité.** Le fichier de travail est régénérable depuis la base tant que
le corpus n'a pas bougé ; les annotations, elles, ne le sont pas. Sauvegarder les
fichiers de travail hors dépôt.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-10 — L'échantillon de référence est stratifié, pas uniforme

**Décision.** Les cahiers à annoter sont tirés par strates selon le nombre de
doléances que le découpage servi y trouve (une / deux / trois et plus), avec un
plancher de 10 cahiers par strate non vide. Le poids de chaque strate est
conservé et `evaluer` affiche systématiquement deux chiffres : celui de la
population (pondéré) et celui de l'échantillon (non pondéré).

**Motif.** 89 % des pages ne portent qu'une doléance repérable. Un tirage
uniforme donnerait un étalon qui ne dit rien des cas qui comptent — ceux où
plusieurs contributeurs se succèdent, exactement ceux où le découpage peut
échouer.

**Ce qu'il faut savoir en lisant les scores.** L'échantillon n'est **pas**
représentatif du corpus, délibérément. Le chiffre non pondéré mesure la
performance sur les cas difficiles ; seul le chiffre pondéré vaut pour le
corpus. Publier le premier pour le second serait une erreur de lecture, et c'est
pour l'éviter que les deux sont affichés côte à côte plutôt qu'un seul.

**Limite.** La strate vient du découpage servi : elle dépend donc de ce qu'on
évalue. Cela ne biaise pas les mesures — l'étalon reste indépendant — mais un
découpage très différent redistribuerait les strates, et les poids d'un
échantillon tiré sous l'ancien ne vaudraient plus. Retirer un échantillon si le
découpage change radicalement.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-10 — La commune est identifiée par son code INSEE, lu dans le nom du fichier

**Décision.** `contribution.city_code` référence une table `city` clé INSEE. Le
code est lu dans le **nom du fichier** (`CC_<cp>_<AAMMJJ>_<INSEE>_MD_<id>.pdf`).
L'en-tête du PDF, qui le porte aussi, sert à auditer et non à rattacher.

**Motif.** La commune n'était qu'une graphie parsée de l'en-tête. Sur les 516
cahiers, ce parsing échoue **182 fois (35 %)** — et 180 de ces cahiers portent
pourtant leur code dans leur nom de fichier. Conséquence mesurée : 307 communes
identifiées par graphie contre **459 par code**. Un tiers des communes du corpus
était invisible, y compris dans les mesures de couverture publiées le matin même.

**Pourquoi le nom de fichier et pas l'en-tête.** Les deux sources concordent sur
339 cahiers (66 %), le nom de fichier est seul disponible sur 174 (34 %), et
elles se contredisent une fois. Ce désaccord unique tranche la question : l'en-tête
portait `GHANA Y - 01420`, c'est-à-dire Chanay mal océrisé suivi de son **code
postal**, quand le nom de fichier portait 01082, son vrai code INSEE. Le nom de
fichier vient du système qui a déposé le cahier ; l'en-tête est un champ rempli à
la main puis passé dans une extraction de texte.

**Ce qui n'est pas rattaché.** Deux cahiers portent `00000` : leur commune n'est
pas renseignée **à la source**, l'un étant remis sans commune et l'autre ayant un
en-tête illisible. Leur `city_code` reste NULL — on ne leur invente pas une
commune.

**Ce qui reste NULL.** `city.name` est la graphie la plus riche rencontrée, pas
le nom officiel. `population`, `latitude` et `longitude` sont vides : elles
demandent le Code officiel géographique, absent du dépôt. Sans population, pas de
mesure de représentativité pondérée ; sans coordonnées, pas de carte. C'est la
prochaine dépendance externe à régler.

**Réversibilité.** Totale : `rattacher` est idempotent et ne dépend que des noms
de fichiers déjà en base. Rien d'irremplaçable n'est produit ici.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-10 — Le référentiel géographique est figé au millésime 2019

**Décision.** Population, nom officiel et coordonnées des communes viennent
d'extraits versionnés dans `insee/referentiel/`, alignés sur le **Code officiel
géographique au 1ᵉʳ janvier 2019**. `city.code` reste le code lu dans le nom du
fichier et ne change jamais ; `city.current_code` porte le code actuel comme une
annotation. Les populations sont les **populations légales millésimées 2017**.

**Périmètre.** Les 459 communes du corpus, et les 1 646 communes des quatre
départements qu'il touche (01, 28, 39, 53).

**Motif.** Un code INSEE est une clé *datée* : il désigne une commune à un
millésime donné. Les codes du corpus ont été attribués par le système qui a
déposé les cahiers en février-avril 2019. Prendre le millésime courant paraît
naturel et c'est le piège — une commune absorbée depuis dans une commune
nouvelle n'y a plus de ligne, sa population deviendrait NULL sans bruit, ou
pire, celle de la commune fusionnée, et la pondération par population serait
fausse sans qu'aucun test ne le voie. C'est aussi le principe qui commande tout
le reste : la provenance est le squelette, le référentiel actuel une couche
posée dessus.

**Pourquoi les populations *millésimées 2017*.** L'INSEE publie les populations
légales avec deux dates, un millésime de recensement et des limites communales.
Les millésimées 2017 sont publiées « dans les limites territoriales des communes
au 1ᵉʳ janvier 2019 » — exactement la géographie de nos codes. Les millésimées
2016, celles qui étaient légalement *en vigueur* quand les cahiers ont été
écrits, portent les limites de 2018 et ne recouvrent donc pas nos codes. Le
recensement de 2017 est au passage plus proche de février 2019 que celui de 2016.

**Alternatives écartées.** Le millésime courant seul (perd les communes
disparues, fausse la pondération) ; un millésime mixte, codes 2019 et
populations actuelles (le pire des deux : les populations ne correspondent plus
aux périmètres) ; télécharger le référentiel à la volée plutôt que le versionner
(un chiffre publié doit rester vérifiable même si une URL bouge chez le
producteur).

**Conséquence mesurée.** Quatre cas dans le corpus, aucun cherché :

| Code | Commune | Ce qui s'est passé |
|---|---|---|
| `01144` | Dommartin | absorbée par Bâgé-Dommartin le 1ᵉʳ janvier **2018**, un an avant les cahiers |
| `01205` | Lancrans | absorbée par Valserhône le 1ᵉʳ janvier **2019**, six semaines avant |
| `01039` | Béon | commune de plein exercice en 2019, absorbée par Culoz-Béon en 2023 |
| `28012` | Commune nouvelle d'Arrou | même code, renommée « Vald'Yerre » en 2023 |

Les deux premiers cahiers ont été déposés sous un code qui ne désignait déjà
plus une commune de plein exercice : le système de dépôt travaillait sur un
référentiel périmé. Ils restent rattachés à ce code, avec `cog_type = COMD` et
leur commune parente — c'est le fait de provenance, on ne le corrige pas.

**Le double compte, consigné parce qu'il ne se voit pas.** La population d'une
commune déléguée est comprise dans celle de sa parente. Valserhône *et* Lancrans
sont dans le corpus : les sommer compterait deux fois 1 054 habitants. La règle
est appliquée dans le code (`populations_sans_double_compte`) et signalée par la
commande, plutôt que laissée à la vigilance de qui lira les chiffres.

**Ce que la pondération apprend.** La part du corpus en communes et sa part en
habitants divergent systématiquement — 53 % des communes de l'Ain mais 72 % de
ses habitants, 36 % / 68 % en Eure-et-Loir, 48 % / 58 % en Mayenne. **Les
communes absentes du corpus sont les petites.** Le même calcul sur les 37
communes sans aucune page lisible donne le contrepoint : 36 697 habitants sur
937 022, soit 4 %, là où elles sont 8 % des communes. Les deux chiffres sont
vrais ; publier l'un sans l'autre serait trompeur dans les deux sens.

**Ce que ça ne dit pas.** Ni l'un ni l'autre ne rend le corpus représentatif. Ils
disent quelle part de la population a un cahier quelque part, et quelle part de
celle-ci a au moins une page lisible. Ils ne disent rien de qui a écrit, ni des
communes qui n'ont pas ouvert de registre.

**Limite du fichier de coordonnées.** Il vient de l'API Découpage administratif,
au millésime courant, et c'est assumé : une commune inchangée depuis 2019 a le
même centre, la géométrie ne dépend pas du millésime là où la population en
dépend. Trois communes du corpus disparues depuis n'y figurent pas et restent
sans coordonnées ; on ne leur prête pas le centre de la commune qui les a
absorbées.

**Réversibilité.** Totale. Les extraits sont dans le dépôt, `python -m insee cog`
est idempotent, et changer de millésime pivot demande de rejouer une commande —
pas de rejouer une migration. La licence exacte de chaque fichier reste à
confirmer auprès de son producteur avant publication (voir
`insee/referentiel/SOURCES.md`).

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## À consigner dès qu'elles seront prises

- Le choix des grilles de thèmes, et le statut donné à chacune.
- Les règles d'anonymisation : ce qui est occulté, ce qui ne l'est pas
  (personnalités publiques dans leur rôle), le seuil de rappel accepté.
- L'arbitrage précision géographique / protection pour les très petites communes
  — la pondération par population montre que ce sont elles qui manquent le plus
  au corpus, ce qui rend l'arbitrage plus coûteux qu'il n'y paraissait.
- La normalisation orthographique, si une version normalisée est ajoutée pour la
  recherche — et la garantie que la version de référence, elle, n'est pas touchée.
- Le périmètre publié : ce qui est mis en ligne, ce qui reste consultable sur
  place seulement.
