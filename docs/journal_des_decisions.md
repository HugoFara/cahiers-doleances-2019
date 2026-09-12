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

**Conséquence mesurée** (corrigée le 2026-09-10, voir plus bas). Sur les 516
cahiers du corpus, 2 855 pages lisibles : le pipeline produit **1 002 doléances**
dans 469 cahiers, soit 2,1 par cahier, moyenne de 753 mots. C'est un **plancher**
et probablement une sous-coupe : les règles ne lisent que le texte, elles ne
voient ni le blanc vertical ni le changement d'écriture, qui sont les deux vrais
séparateurs d'un registre.

*Correction : la première version de cette entrée annonçait 3 243 doléances et
11 % de pages à plusieurs contributeurs. Ce chiffre venait d'un découpage de
chaque page prise séparément, alors que le pipeline regroupe par cahier — une
doléance peut couvrir plusieurs pages, et 622 le font. Les 11 % restent vrais des
pages isolées ; les 3 243 ne sont pas la sortie du pipeline.*

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

**Réversibilité.** Immédiate côté outillage (`--keep-ocr-pages`, retiré le
2026-09-11 quand le texte de lecture a remplacé le filtre), nulle côté
qualité tant que l'HTR n'est pas là — réintégrer ces pages aujourd'hui
n'ajouterait pas des contributions, seulement du bruit d'extraction.
*2026-09-11 : l'HTR est là — voir « Le manuscrit entre dans la lecture ».*

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

**Licences, vérifiées le 2026-09-10.** Les trois sources sont sous **Licence
Ouverte 2.0** (Etalab), d'après les mentions légales de l'INSEE — qui couvrent
nommément les fichiers téléchargeables du site — et la fiche ADMIN EXPRESS de
l'IGN. Un point méritait la vérification : `geo.api.gouv.fr` ne publie aucune
licence pour son découpage administratif et api.gouv.fr cite OpenStreetMap parmi
ses partenaires, ce qui aurait signifié de l'ODbL et une obligation de partage à
l'identique. Le générateur des contours tranche : ADMIN EXPRESS pour la
métropole, OpenStreetMap seulement pour les collectivités d'outre-mer, absentes
du corpus.

La LO 2.0 impose trois obligations qui vaudront pour la publication du corpus et
pas seulement pour ce dossier : citer « Source : Insee » et « Source : IGN »,
donner la date de mise à jour des données, et **ne pas altérer le sens des
informations ni induire en erreur quant à leur interprétation**. La troisième
n'est pas une formalité ici : c'est exactement ce que la pondération par
population fait courir comme risque si elle est publiée sans dire ce qu'elle
mesure.

**Réversibilité.** Totale. Les extraits sont dans le dépôt, `python -m insee cog`
est idempotent, et changer de millésime pivot demande de rejouer une commande —
pas de rejouer une migration.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-10 — L'app dit ce que le corpus n'est pas, avant de montrer un chiffre

**Décision.** Un avertissement calculé s'affiche au-dessus des vues : part de
pages écartées, communes sans aucune page lisible et leur poids en habitants,
grille de thèmes servie parmi celles qui coexistent, mentions de source. Et le
sélecteur de commune passe du nom parsé de l'en-tête au **code INSEE**.

**Périmètre.** `gradio_app/`, les deux vues.

**Motif.** Un site de consultation est un acte éditorial : ce qu'il affiche par
défaut, et surtout ce qu'il tait, décide de la lecture. Tout ce qui a été mesuré
ici depuis une semaine vivait dans des README et des sorties de commande —
c'est-à-dire nulle part pour qui utilise l'app. « x % des contributions parlent
de y » se lit comme un sondage tant que rien ne dit le contraire. S'y ajoute une
obligation : la Licence Ouverte 2.0, sous laquelle sont les données INSEE et
IGN, impose de « ne pas induire en erreur quant à l'interprétation » des
informations.

**Ce que le sélecteur cachait, mesuré.** Il reposait sur `contribution.city`, la
graphie parsée de l'en-tête du PDF, qui manque sur un tiers des cahiers.
Conséquence : **153 communes n'avaient aucune entrée dans la liste, et 2 169
contributions sur 5 365 — 40 % — n'étaient atteignables par aucun chemin de
l'app.** Château-Gontier-sur-Mayenne et ses cent contributions en faisaient
partie. Ce n'était pas une gêne d'affichage : c'était une partie du corpus hors
d'atteinte des bénévoles qui annotent, sans que rien ne le signale.

Le rattachement INSEE existait depuis le matin et le référentiel depuis
l'après-midi ; il ne manquait que de les brancher. Le libellé prend le nom
officiel du Code officiel géographique, retombe sur la graphie, puis sur le code
— jamais rien. Les 144 contributions dont le cahier n'a pas de code à la source
ont leur propre entrée plutôt que de rester invisibles.

**Alternatives écartées.** Afficher l'avertissement en pied de page (personne ne
descend) ; l'écrire en dur (il devient faux au premier rechargement de la base et
personne ne s'en aperçoit) ; recalculer les taux dans l'app (deux
implémentations de la même règle divergent, et celle qui s'affiche à l'écran
serait la dernière corrigée — les compteurs viennent donc de `couverture.mesures`
et `insee.cog`).

**Ce qui est replié et ce qui ne l'est pas.** Les trois phrases qui doivent
accompagner tout comptage sont visibles sans clic ; les précisions et les sources
sont dans un repli. Un avertissement trop long n'est pas lu, et ne pas être lu
est le seul échec qui compte ici.

**Un second filtre manquant, trouvé en chemin.** `GRILLE_SERVIE` avait été posé
sur la vue graphe et pas sur la vue commune, qui **cumulait donc les détections
de toutes les grilles**. Invisible tant qu'une seule grille est chargée, faux dès
la deuxième — c'est-à-dire dès qu'on fera ce que le schéma a été refait pour
permettre.

**Limite assumée.** On peut savoir quelle grille est servie, pas en changer
depuis l'app. Le faire demande de sortir la taxonomie de l'état de module de
`views/graph.py` — cinq cents lignes calculées à l'import — pour la paramétrer
par run. C'est un refactoring, et le faire à moitié (un sélecteur qui n'agirait
que sur une vue) donnerait deux pages montrant deux grilles différentes sans le
dire, ce qui est pire que pas de sélecteur. Consigné au plan comme chantier
propre.

L'avertissement de la vue commune est calculé au démarrage, comme la taxonomie ;
celui de la vue graphe est recalculé à chaque requête. Ni l'un ni l'autre ne dit
ce qui n'a jamais été déposé — les communes sans cahier du tout ne sont pas dans
le corpus, donc pas dans ce compte.

**Réversibilité.** Totale, c'est de l'affichage. Le changement de sélecteur, lui,
ne se reviendrait pas sans reperdre 40 % des contributions.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-10 — Les doublons sont groupés, pas écrasés

**Décision.** Les doléances quasi identiques sont regroupées (MinHash + LSH,
similarité de Jaccard ≥ 0,8) dans `duplicate_group`, avec le nombre de communes
distinctes que chaque groupe touche. **Aucune n'est supprimée.**

**Motif.** Tracts collés, lettres-types, pétitions, cahiers scannés deux fois :
comptés comme autant de contributions, ils gonflent les fréquences de thèmes.
Mais les écraser ferait disparaître une information : un texte présent dans six
communes est une campagne organisée, ce qui n'est pas la même chose qu'une
écriture individuelle. `cities` porte cette distinction, et c'est aux lectures en
aval de décider ce qu'elles en font.

**Mesuré.** 13 groupes, 33 doléances sur 1 002 (3 %). Sensibilité douce : 1 % à
0,9, 6 % à 0,7, 10 % à 0,5.

**Trouvaille non cherchée.** Le plus gros groupe — 6 doléances, 6 communes,
2 217 mots — est la **lettre du Président de la République** qui ouvre les
registres, pas une contribution citoyenne. Onze doléances la portent, environ
21 000 mots, 2,8 % du corpus en volume. L'extraction saute les deux premières
pages de chaque cahier, ce qui l'élimine le plus souvent ; ces onze sont passées.
Un thème détecté dans ce texte n'est pas une doléance : à écarter avant tout
comptage.

**Limite consignée.** Le seuil ne peut pas descendre sous 0,5. Le filtre de
paires candidates est réglé pour la similarité haute — il ne propose qu'une paire
sur quatre à 0,3 de similarité — si bien qu'un seuil plus bas rendrait *moins* de
doublons, sans le dire. La commande refuse plutôt que de produire un résultat
silencieusement incomplet.

**Réversibilité.** Totale : rien n'est supprimé, et chaque exécution est un run
de plus.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-10 — Le caviardage est un rendu, pas une transformation du texte

**Décision.** `pii_span` ne contient que des **offsets de caractères**. Le texte
d'origine n'est ni copié ni modifié : le caviardage est produit à la lecture, à
partir des passages et de leur état de relecture.

**Motif.** Stocker une copie caviardée fige une politique dans les données. Toute
correction — une détection ratée, un faux positif, un changement d'arbitrage sur
les personnalités publiques — obligerait à repartir de la source, si tant est
qu'on l'ait gardée. Avec des offsets, la source fait foi et la politique reste
révisable.

**Politique de rendu, explicite parce que discutable.** Un passage **non relu est
caviardé** : tant que le doute existe, il profite à la personne. Un faux positif
relevé à la relecture ne l'est pas. Les genres `role_public` et `institution` ne
le sont pas non plus — un ministre cité dans sa fonction, l'adresse d'une mairie
ou celle du dispositif sont publics par destination, et les occulter viderait les
textes de leur objet. Le maire nommément **accusé** relève de la relecture
humaine : la règle ne sait pas faire la différence.

**Mesuré.** 4 164 passages dans 884 doléances sur 1 002 — **88 %**.

**Ce que ce chiffre n'est pas.** Il est à la fois un plancher et une
surestimation. Plancher : un nom cité sans marqueur n'est pas vu, et c'est le cas
le plus fréquent. Surestimation : une part des courriels et téléphones sont ceux
des mairies ; `institution` en isole 217, mais `accueil@ma-commune.fr` est une adresse
de mairie que rien dans sa forme ne distingue d'une adresse privée. L'OCR aggrave
la seconde — `reunionslocales@qranddebat.fr` avec un `q` pour un `g` échappe à la
règle institutionnelle tout en restant repéré comme courriel, donc sur-protégé.

**Ce qui n'est pas fait, et qui est le point dur.** La reconnaissance d'entités
nommées (le choix du modèle est une décision : la passe doit tourner en local ou
chez un sous-traitant européen, ces textes étant des opinions politiques
nominatives), la mesure du rappel (échantillon annoté à la main), l'occultation
sur l'image (demande la géométrie de l'OCR), et la réidentification contextuelle
— « je suis la seule infirmière du village » identifie sans aucun nom.

**Rien de ce module ne permet de déclarer une doléance publiable**, et la commande
le dit à chaque exécution.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-10 — Un run est attribué d'office, il n'est plus réclamé

**Décision.** `run.author` passe en `NOT NULL`. `creer_run` résout l'auteur
lui-même quand la commande ne le donne pas : `--auteur`, puis la variable
`CAHIER_DOLEANCES_AUTEUR`, puis l'identité git du dépôt, puis le compte système.
Si aucune source ne répond, la passe s'arrête au lieu d'écrire un run anonyme
(`database/auteur.py`).

**Périmètre.** Les cinq genres de runs : segmentation, analyse, doublons,
anonymisation, embeddings.

**Motif.** L'attribution est la contrepartie de la réversibilité. Une couche
qu'on peut retirer mais pas rattacher à quelqu'un ne se discute pas, elle se
subit — et c'est exactement ce que ce dépôt reproche à la synthèse officielle de
2019. Or l'auteur n'était jusqu'ici que *réclamé* : chaque commande imprimait
« run sans auteur : renseigner --auteur avant publication » et écrivait le run
quand même. Un avertissement qu'on lit une fois puis plus jamais ne tient pas
lieu de contrainte.

**Alternatives écartées.** Rendre `--auteur` obligatoire à la ligne de commande :
plus strict en apparence, mais une obligation qui gêne se contourne — on tape
`--auteur x` et le champ ment. Laisser la colonne nullable en n'ajoutant qu'un
test : le test garde le code du dépôt, pas les runs créés depuis un notebook ou
une console.

**Conséquence mesurée.** Les quatre runs de la base de développement étaient
attribués, mais par un `--auteur` tapé à la main à chaque fois ; le run d'analyse
hérité, créé avant la table, porte `inconnu`. La migration comble en `inconnu`
tout run resté anonyme — elle n'invente pas d'auteur après coup, elle écrit ce
qu'on sait. Sur un poste sans `user.name` ni `user.email`, la chaîne de repli
répond ce que git déduit du système (`login <login@hôte>`) — donc l'identité
sous laquelle les commits partent déjà.

**Réversibilité.** Bonne : la migration inverse rouvre la colonne. Les `inconnu`
posés à l'aller ne sont pas remis à NULL au retour, parce qu'un run les portait
légitimement avant.

**Ce que cela ne règle pas.** Les entrées de ce journal restent signées « Équipe
technique — *à nommer avant publication* ». La base sait maintenant qui a produit
chaque couche ; le journal, lui, attend toujours une décision sur les noms à
publier. Les deux attributions ne sont pas la même : l'une dit qui a lancé une
passe, l'autre qui a pris une décision.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-11 — Les noms cités sans marqueur sont repérés par un modèle, en local

**Décision.** La passe d'anonymisation gagne une reconnaissance d'entités
nommées (`anonymisation/ner.py`, `--ner`) : `Jean-Baptiste/camembert-ner`,
CamemBERT affiné sur WikiNER, exécuté en local sur CPU. Les personnes
deviennent des passages `nom` (caviardés), les lieux `lieu` et les
organisations `institution` (non caviardés). Chaque passage porte son
détecteur (`ner:<modèle>`) : la NER et les formes s'auditent séparément dans
le même run. Le seuil des personnes est à 0,4, celui des lieux et
organisations à 0,6.

**Périmètre.** Le repérage. Ni la politique de caviardage, ni le rappel, qui
reste à mesurer.

**Motif.** Le plan tenait la NER pour le point dur de la P3, bloquée sur la
décision d'hébergement. Elle est prise depuis ce matin pour les scans, en
local, et vaut pour les noms. Le modèle est choisi sur mesure, contre les
modèles de désidentification conseillés pendant le POC (collection OpenMed) :
sur 25 doléances tirées au sort, le plus gros d'entre eux (434M, entraîné sur
des données synthétiques de formulaires) mettait neuf fois plus de temps,
rendait des centaines d'« adresses Litecoin » et de « mots de passe », et
coupait les noms en sous-mots. CamemBERT-NER rendait des personnes entières,
84 contre 29 par la passe de formes. Le seuil bas est le sens de l'erreur du
module : un faux positif coûte un mot, un nom manqué est une fuite.

**Ce que ça donne, mesuré.** Sur les 1 002 doléances du découpage servi : 19 306
passages dans 968 doléances (97 %), contre 4 164 dans 884 pour les formes
seules. Les noms passent de 1 309 à 3 582 ; 196 doléances où aucun nom
n'était repéré en ont désormais au moins un. Téléphones, courriels, adresses
et liens : inchangés, parce qu'une première passe combinée en perdait (214
adresses sur 255, le modèle voyant un lieu là où la forme voyait une adresse)
et que la règle de combinaison a été corrigée avant de garder le run. Lieux :
9 260, organisations : 3 827, non caviardés. 8 min 40 s sur CPU.

**Alternatives écartées.** Un LLM par consigne (Ollama sur le GPU) : plus
souple, non déterministe, et le GPU transcrit le manuscrit jusqu'à minuit.
Les modèles OpenMed : ci-dessus. Caviarder aussi les lieux : viderait les
textes de leur objet, un lieu n'est pas une donnée personnelle en soi ; le
lieu qui identifie à lui seul relève de la réidentification contextuelle, à
traiter autrement.

**Ce que ça ne règle pas.** Le rappel, sans échantillon annoté. Les
personnalités publiques nommées (« Macron ») sont des personnes pour le
modèle et sont caviardées comme les autres : la règle « dans leur rôle, on ne
cache pas » reste à consigner, et c'est la relecture qui les rend pour
l'instant. L'occultation sur l'image, sans géométrie.

**Réversibilité.** Un run ; le précédent (formes seules) reste en base,
comparable. Désactiver le nouveau ramène à l'ancien.

**Auteur.** Équipe technique, *à nommer avant publication*.

---

## 2026-09-10 — Une grille de thèmes se mesure avant de se refaire

**Décision.** Trois familles de mesures sur toute grille (`taxonomie/`) :
réutilisation (documents par thème, thèmes par document, singletons), hiérarchie
(racines, isolés, cycles, profondeur, largeur, noms dupliqués), et **couverture**
— la part du texte réellement citée par les verbatims, dont le complément est le
« hors grille ».

**Motif.** Les 32 passes successives de `factorize`/`structure` du RECIPE de
topic-builder corrigeaient un symptôme sans instrument pour dire si la passe
suivante améliorait quoi que ce soit. Comparer deux grilles était impossible.

**Mesuré sur la livraison d'août.** 6 788 thèmes, 1 380 documents. **3 392
thèmes — 76 % de ceux qui sont attestés — ne le sont que par un seul document.**
Un thème attesté une fois est la paraphrase de ce document : la grille ne
généralise pas, elle réécrit le corpus. Et **2 343 thèmes (35 %) n'ont aucune
détection** ; le détail par niveau dit où : 2 % des feuilles sont inutilisées
contre 99,6 % des parents. Le labelling n'attache que des feuilles, les parents
n'existent que pour la navigation.

**Ce qui n'est pas mesurable, et pourquoi c'est une information.** La couverture
demande de retrouver les verbatims dans le texte des documents. La livraison
d'août ne s'y prête pas : ses identifiants désignent un autre corpus, ce que le
garde-fou de `load_analysis` avait déjà établi. La mesure fonctionne dès qu'une
livraison passe par `export_dataset.py` — vérifié sur une livraison fabriquée
depuis le seed. C'est un argument de plus pour ne plus accepter de livraison dont
les identifiants ne sont pas les nôtres.

**Limite.** Ces mesures comparent des grilles entre elles ; aucune ne dit
laquelle est juste. Cela reste le rôle du jeu de référence annoté, qui n'existe
pas encore.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-10 — Une doléance est d'abord un genre de document, pas un contenu

**Décision.** Deux axes posés sur chaque doléance avant tout comptage de thèmes :
le **support** (`registre`, `courrier`, `petition`, `formulaire`, `deliberation`,
`lettre_type`, `apparat`, `illisible`) et l'**auteur** (`individu`, `collectif`,
`institution`, `indetermine`). Table `typologie`, une ligne par axe, versionnée
par un run ; module `typologie/`.

**Périmètre.** Les 1 002 doléances du découpage servi.

**Motif.** C'est la couche 2 du plan, et elle conditionne l'interprétation de
tout ce qui vient après. « 34 % des contributions demandent X » ne veut rien dire
si les 34 % mêlent un mot d'habitant, une motion de conseil municipal, un tract
recopié dans onze communes et le courrier par lequel la mairie transmet le
cahier. Une contribution syndicale et un mot manuscrit n'ont pas le même poids,
et les confondre fausse tous les comptages.

**Alternatives écartées.** Des colonnes sur `doleance` : ce sont des règles
faillibles, pas des propriétés du texte, et elles doivent se retirer et se
comparer comme les autres couches. Une étiquette unique croisant les deux axes :
elle obligerait à inventer des cases que le corpus ne porte pas — une pétition
peut être portée par une association ou par des habitants sans organisation.
Renseigner à la main sur un échantillon d'abord : c'était l'option du plan, mais
les règles de forme donnent une base sur tout le corpus, et l'échantillon annoté
servira à les *mesurer* plutôt qu'à les remplacer.

**Conséquence mesurée.** Trois résultats, sur 1 002 doléances et 754 741 mots.

*Une doléance sur cinq n'est pas une contribution.* 181 `illisible` et 24
`apparat` — pages de couverture, en-têtes de mairie, tampons, manuscrits que le
score de qualité a laissé passer, et les mots par lesquels une commune transmet
son cahier au préfet. Elles étaient comptées comme des contributions citoyennes.
Corollaire : `needs_ocr` écarte 2 510 pages manuscrites mais **il en laisse
passer**, certaines de plusieurs centaines de mots de fragments de caractères.

*La première personne est minoritaire en nombre, majoritaire en volume.* 24 % des
doléances portent une marque de première personne et pèsent 48 % des mots ; les
69 % d'indéterminé n'en pèsent que 39 %. Ce sont, pour l'essentiel, des listes de
revendications sans sujet grammatical — « Rétablissement de l'ISF ». Rien dans
leur forme ne dit qui les écrit, et aucune règle de texte n'y accèdera.

*Huit pétitions pèsent quatre fois l'apparat entier.* 8 doléances `petition` font
32 141 mots (4 % du corpus), contre 7 797 pour les 24 `apparat`, 8 `formulaire`
et 2 `deliberation` réunis. Les compter comme 8 contributions les efface ; les
compter comme 8 textes de 4 000 mots les surpondère dans toute découverte de
thèmes. Cette couche rend l'arbitrage visible ; elle ne le tranche pas.

**Réversibilité.** Bonne : table à part, run versionné, `python -m typologie`
crée un run de plus sans écraser le précédent ni ses relectures.

**Ce que cela ne règle pas.** Ni la précision ni le rappel de ces règles ne sont
mesurés — il y faut l'échantillon annoté, et `confirmed` reste NULL partout. Le
vrai support (manuscrit, tract collé, feuille volante) se voit sur l'image et
demande la géométrie de l'OCR, la même qui manque pour occulter les données
personnelles sur les scans. Et « individu » ici veut dire « le texte parle à la
première personne », ce qui n'est pas la même chose qu'un auteur individuel.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-10 — Un dossier par passe, et l'app n'en fonde aucune

**Décision.** Trois corrections de structure, sans changer une ligne de
logique. `gradio_app/communes.py` va dans `insee/` : `couverture/` et
`insee/rattachement.py` l'importaient depuis l'app, qui fondait ainsi deux
passes au lieu de les consommer — c'était le seul cycle du dépôt. `gradio_app`
s'importe en paquet partout et se lance par `python -m gradio_app.app` : lancée
par `python gradio_app/app.py`, elle importait ses modules à plat et pytest en
paquet, deux régimes pour le même code, portés par une rustine
`try/except ModuleNotFoundError`. Et l'échange avec l'analyse
(`export_dataset.py`, `load_analysis.py`, `identifiants.py`) sort de
`database/` pour former `analyse/` : six genres de run, cinq paquets, et c'est
celui-là qui manquait.

**Motif.** La convention la plus lisible du dépôt est *un dossier par lecture du
corpus, du nom de son genre de run*, chaque dossier ne dépendant que de
`database/`. Les trois écarts la contredisaient chacun à sa façon : une
dépendance dans le mauvais sens, un module à deux noms, une passe sans dossier.

**Alternatives écartées.** Laisser `communes.py` dans l'app et y faire pointer
`couverture/` : c'est l'état qu'on corrige. Un `conftest.py` qui ajoute
`gradio_app/` au `sys.path` pour que les tests suivent le régime plat : ça
aurait officialisé la rustine au lieu de la retirer. Nommer le paquet
`livraison/` plutôt qu'`analyse/` : le genre de run s'appelle `analyse`, le
dossier porte le même nom, c'est la règle.

**Réversibilité.** Totale : trois `git mv` et des imports. `load_analysis` perd
son dossier par défaut, qui pointait sur `analyse/analysis_v4`, absent de toute
machine — une livraison se nomme.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-10 — La grille gouvernementale existe, sans détections

**Décision.** La deuxième grille que le plan demande depuis le début est écrite
et chargée : `analyse/grilles/cadrage_gouvernemental_2019.json`, les quatre
thèmes de la Lettre aux Français du 13 janvier 2019 et, sous chacun, ses
questions **reproduites mot pour mot** en description. Seul le nom court de
chaque thème enfant est une étiquette éditoriale, marquée non validée. La
source est nommée, datée, et citée dans les `notes` du run. Elle se charge par
`analyse/grille.py` en run de genre `analyse`, **non actif**.

**Périmètre.** La définition de la grille, pas ses détections. Elle apparaît
dans le sélecteur de l'app — qui a désormais deux entrées — et la vue l'affiche
vide en disant pourquoi.

**Motif.** Le plan la veut *étiquetée comme telle*, « cadrage gouvernemental
2019 », précisément pour que ce cadrage soit visible et discutable au lieu
d'être la référence implicite de toute lecture. Sa définition ne dépend d'aucun
modèle ; c'était la seule partie du chantier des grilles qui n'attendait pas la
décision d'hébergement, et elle donne au sélecteur de l'app la raison d'exister
qu'il n'avait pas.

**Alternatives écartées.** Reprendre le questionnaire de granddebat.fr plutôt
que la lettre : le site n'existe plus, et ses formulations reprenaient celles de
la lettre, qui est la source primaire et reste en ligne. Reformuler les questions
en thèmes : c'est ce que la grille émergente fait déjà à sa manière ; ici la
valeur est de reproduire le cadrage tel quel. Nommer le deuxième thème
« organisation de l'État et des collectivités publiques », comme le corps de la
lettre : la phrase qui nomme les quatre thèmes dit « services publics », et
c'est le nom que le Grand Débat a retenu.

**Réversibilité.** Totale : un run non actif, supprimable avec ses 24 thèmes.

**Ce que cela ne règle pas.** Les détections. Rattacher chaque doléance à l'un
de ces thèmes demande un modèle — LLM ou embeddings — et donc la P3. Un
rattachement lexical sur l'index plein texte est possible avant, à condition de
l'étiqueter comme tel pour que `taxonomie/` mesure de combien il est mauvais.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-11 — La grille gouvernementale a des détections par mots-clés, dites telles quelles

**Décision.** Les doléances sont rattachées aux 20 questions de la Lettre aux
Français par un **détecteur lexical** : un jeu de mots-clés par question
(`analyse/grilles/cadrage_gouvernemental_2019.mots_cles.json`), une requête
sur l'index plein texte de `recherche/`, une instance par doléance qui répond.
Le résultat est un run `analyse` à part, **non actif**, `model = "mots-clés"`,
requêtes dans ses paramètres. La grille chargée hier reste sans détections.

**Périmètre.** Les détections de cette grille, sur le découpage servi. Pas la
grille elle-même, pas le découpage.

**Motif.** Une grille sans détections n'est pas discutable — on ne peut pas
dire ce qu'elle voit du corpus. Un modèle attend la P3. Un détecteur de
vocabulaire ne l'attend pas, et il donne deux choses : une lecture immédiate
du corpus par le cadrage de 2019, et l'**étalon bas** auquel un modèle devra
se comparer — s'il ne fait pas mieux que des mots-clés, il n'apporte rien. À
condition d'être étiqueté comme tel : `model`, `detector` et le résumé de
chaque instance le disent.

**Ce que ça vaut, mesuré** (`taxonomie/`, 2026-09-11, 1 002 doléances
dactylographiées) : 655 doléances rattachées (65 %), 4 857 rattachements, 7,4
questions par doléance — une doléance de 750 mots en moyenne mentionne
presque tout. Texte couvert par les verbatims : 19 %, mécanique (fenêtre de
260 caractères). Aucun verbatim introuvable. Les racines n'ont pas de
détections, par construction.

**Choix du lexique, et ce qui a été élagué après mesure.** Les mots-clés sont
éditoriaux, non validés. Quatre retraits, consignés dans le fichier : « cahier
de doléances » et « grand débat » (le document se nomme lui-même — 334 et 267
doléances sur la participation citoyenne), « consultation » (médicale aussi),
« Europe » / « européen » seuls (141 et 169, toute l'Union), « assemblées »
seul (166). Restent des termes larges assumés — « impôt », « taxe »,
« département », « région » — parce que les questions le sont.

**Alternatives écartées.** Mettre les détections dans le run de la grille :
un modèle, ensuite, aurait dû soit les écraser, soit cohabiter sans qu'on
sache d'où vient quoi. Pondérer, exiger deux termes, exclure des négations :
ce serait un demi-modèle sans en avoir la mesure ; l'étalon bas doit rester
bas et lisible.

**Réversibilité.** Totale : un run non actif, supprimable. Le lexique se
rejoue en une commande sur le corpus complet une fois le manuscrit transcrit.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-11 — La grille du Vrai Débat est la troisième, pour avoir un point de comparaison

**Décision.** Une troisième grille de cadrage, `analyse/grilles/vrai_debat_2019.json` :
les neuf rubriques de la plateforme lancée par des gilets jaunes le 30 janvier
2019 (Démocratie et institutions ; Transition écologique, agriculture,
transport ; Justice, police, armée ; Europe, affaires étrangères, outre-mer ;
Santé, solidarité, handicap ; Économie, finances, travail, comptes publics ;
Éducation, jeunesse, recherche ; Sport, culture ; Expression libre), libellés
et ordre reproduits, à plat. Son lexique de mots-clés et son run de
rattachement, non actif, suivent exactement le modèle du cadrage
gouvernemental. Les quatre « blocs » de l'analyse LERASS / Triangle n'y sont
pas : ce sont des résultats, pas une grille.

**Périmètre.** Une grille et ses détections lexicales. Rien de ce qui est
servi ne change.

**Motif.** Une grille sans point de comparaison ne dit rien du corpus. Celle-ci
est la seule des trois à venir avec une **distribution de référence** :
25 000 propositions, économie 31 %, démocratie 20 %, écologie 16 %, santé
10 %, les cinq autres autour de 5 %. Elle pose donc une question que
l'association se pose vraiment : les gens qui écrivent en mairie parlent-ils
de la même chose que ceux qui déposaient en ligne ? Et elle vient de l'autre
camp que la Lettre aux Français, ce qui rend le cadrage gouvernemental
discutable par contraste, au lieu de le laisser seul.

**Ce qu'elle a contre elle, dit d'avance.** Ses rubriques sont des
périmètres ministériels, pas des problèmes : la taxe carbone et le prix du
carburant, les deux camps de 2018, tombent dans la même case ; la fiscalité
n'a pas de rubrique à elle ; les services publics de proximité, vraisemblable
premier sujet de nos trois départements ruraux, sont éclatés sur quatre
rubriques ; le logement n'en a aucune (placé en expression libre, choix
consigné dans le lexique). Elle classait des propositions d'une phrase, une
rubrique par proposition ; nos doléances font 750 mots.

**Mesuré** (`taxonomie/`, 2026-09-11, 1 002 doléances dactylographiées) :
639 rattachées (64 %), 3 158 rattachements, **4,9 rubriques par doléance**,
45 % des doléances rattachées en touchent six ou plus, 13 % du texte couvert.
Par rubrique : démocratie 512, économie 509, écologie 398, santé 394,
expression libre 346, éducation 298, Europe 277, justice 251, sport et
culture 173. Ce n'est pas encore comparable aux parts du Vrai Débat, une
rubrique par proposition là-bas ; ça le deviendra avec un rattachement qui
choisit une rubrique dominante, et c'est alors le premier résultat
publiable du projet.

**Élagué après mesure.** « maire » (531 doléances) et « président » (345) :
l'adresse de la lettre, pas un thème. Et quatre mots que la configuration de
recherche sans accent confond avec un autre : « loyer » se réduit à « loi »,
« aidants » à « aide », « environnement » à « environ », « voile » à
« voilà ». C'est une limite de l'étalon bas à connaître : un lexique se
vérifie radical par radical, pas mot par mot.

**Alternatives écartées.** Les quatre blocs LERASS comme grille : ce sont
les conclusions d'une analyse, les adopter reviendrait à en importer le
résultat. Fusionner les deux cadrages en une grille : on perdrait la
comparaison, qui est tout l'intérêt.

**Réversibilité.** Totale : deux runs non actifs, supprimables.

**Auteur.** Équipe technique, *à nommer avant publication*.

---

## 2026-09-10 — La recherche est indifférente aux accents, et ses extraits sont caviardés

**Décision.** Le corpus est cherchable en plein texte au niveau de la doléance,
par un index GIN sur `to_tsvector('francais_sans_accent', text)`. Cette
configuration est une copie de `french` dont la correspondance des mots passe par
`unaccent`. Les extraits rendus sont **caviardés** des passages personnels
repérés.

**Périmètre.** `recherche/`, l'onglet Recherche de l'app, migration
`b1c5f8e34a72`.

**Motif de la configuration sans accent.** Personne ne tape les accents dans un
champ de recherche. Mesuré sur les 1 002 doléances, en tapant les termes sans
accent : « impot » trouve **22 doléances avec `french`, 309 avec la
configuration sans accent** ; « depute » 14 contre 260 ; « ecole » 18 contre 138.
Le mécanisme mérite d'être noté parce qu'il n'est pas intuitif : le radicaliseur
français supprime déjà la voyelle accentuée **finale** — « santé » et « sante »
se rejoignent sans rien faire, et le terme « sante » donne 181 des deux côtés —
mais il conserve les accents **intérieurs**, ceux d'impôt, école, député,
référendum. S'y ajoute l'OCR, qui abîme les accents pour son compte : le corpus
contient `qüe`, `qùè`, `qüé`, `qùe` pour « que ».

**Effet de bord assumé.** La configuration confond « retraite » et « retraité ».
Le radicaliseur les confondait déjà — même racine — elle n'ajoute que les
variantes abîmées.

**Motif du caviardage.** La recherche est le premier endroit où le corpus se lit
**en vrac**, hors du cahier qui lui donnait son contexte. Un extrait rendu à qui
interroge n'est pas la même chose qu'un texte lu par un bénévole qui annote une
commune — c'est pourquoi la vue par commune, elle, reste en clair. L'ordre des
opérations est l'inverse de l'intuition et il est structurant : on caviarde le
texte entier **puis** on y découpe la fenêtre, parce que les passages sont des
offsets dans le texte d'origine. Un terme qui ne se trouvait que dans un passage
occulté disparaît donc de l'extrait, et le résultat s'ouvre sur le début du
texte. C'est le bon sens de l'erreur.

**Alternatives écartées.** `ts_headline` de PostgreSQL, qui fabrique l'extrait
côté base : il rend une chaîne, pas des positions, et le caviardage par offsets
ne s'y applique donc pas. Une colonne `tsvector` générée plutôt qu'un index
d'expression : elle aurait dû figurer au modèle, monté sur SQLite par les tests.
`pgvector` : l'extension n'est pas installée sur la base, et la recherche
vectorielle répond de toute façon à une autre question.

**Ce que la recherche a immédiatement montré.** Interroger les mots de la lettre
présidentielle rend cinq résultats qui sont **la lettre du Président de la
République**, recopiée dans six communes — pas des contributions citoyennes.
Sans le marqueur emprunté à `doublons/`, une recherche les présenterait comme les
textes les plus pertinents du corpus. Le champ vaut `None` quand la déduplication
n'a pas tourné, ce qui veut dire « on ne sait pas » et non « texte unique ».

**Limites consignées.** La recherche ne voit que la moitié dactylographiée du
corpus. L'OCR défait la correspondance exacte — `mairie^ferney-voltaire.fr` avec
un accent circonflexe pour l'arobase, `giiecs jaunes` pour « gilets jaunes » — et
un mot mal océrisé n'est trouvé par aucune requête. Enfin, alembic ne sait pas
comparer un index d'expression : il est nommé dans `INDEX_HORS_COMPARAISON`, sans
quoi `alembic check` échouerait à chaque exécution sur une base pourtant à jour.

**Réversibilité.** Totale : la migration se redescend, l'index et la
configuration se recréent, rien n'est écrit dans les données.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-10 — Les vecteurs ont leur table avant d'avoir leur modèle

**Décision.** `pgvector` est installé sur la base et une table `embedding`
rattache chaque vecteur à une doléance **et à un run** de genre `embeddings`.
`compose.yaml` passe de `postgres:16` à `pgvector/pgvector:pg16`. Aucun vecteur
n'est produit : le modèle n'est pas choisi.

**Périmètre.** `compose.yaml`, migration `c2d7a91b46f8`, `database/models.py`,
`database/runs.py`.

**Motif.** Séparer ce qui se décide de ce qui ne se décide pas. *Où* vivent les
vecteurs est une question de schéma, tranchable aujourd'hui ; *quel modèle* les
produit est une décision d'hébergement qui relève de la priorité 3 — ces textes
sont des opinions politiques nominatives, la passe doit tourner en local ou chez
un sous-traitant européen. Poser la table maintenant évite qu'au moment du choix
du modèle on improvise en plus un schéma.

**Une table, pas une colonne.** Un vecteur dépend d'un modèle, de sa version et
du découpage du texte qu'on lui a donné : c'est une lecture du corpus, pas une
propriété de la doléance. Même raisonnement que pour `duplicate_member` et
`pii_span`, et deux passes doivent pouvoir coexister pour être comparées.

**La dimension n'est pas déclarée, et c'est un choix.** Elle dépend du modèle.
pgvector accepte un vecteur non contraint mais **refuse de l'indexer** : une
recherche vectorielle fera un parcours complet tant que la dimension n'est pas
fixée. Sur mille doléances c'est sans conséquence. L'alternative — fixer 1024 ou
1536 aujourd'hui — reviendrait à présupposer le modèle dans le schéma, sans le
dire nulle part. Le jour où il est choisi, une migration fixe la dimension et
pose l'index HNSW.

**Vérifié.** Insertion par l'ORM, distance cosinus, relecture en liste Python,
puis rollback : la plomberie tient de bout en bout. Migration montée et
redescendue ; le downgrade laisse l'extension, comme celui d'`unaccent` — la
retirer sous les pieds d'un autre objet casserait ce dernier.

**Le piège de l'image, consigné parce qu'il ne se voit pas.** L'extension n'est
pas dans `postgres:16`. Changer d'image ne perd aucune donnée — le volume est
externe et la version majeure identique — mais la version de **glibc** change,
donc celle des collations, et PostgreSQL avertit que les index texte peuvent être
mal ordonnés. Il faut `REINDEX DATABASE` puis `ALTER DATABASE … REFRESH COLLATION
VERSION`, dans les deux sens. La commande est dans `compose.yaml` ; sans elle,
une base continue de fonctionner en donnant des résultats subtilement faux, ce
qui est la pire des pannes.

**Ce que ça ne fait pas.** Aucune recherche vectorielle n'existe. Le plein texte
trouve un mot ; la vectorielle trouverait un voisinage, et se tromperait sans le
dire quand le voisinage n'existe pas. Les deux répondent à des questions
différentes et la seconde demandera sa propre mesure.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-10 — Chaque étiquette renvoie à sa page source

**Décision.** Toute étiquette affichée par l'app porte un lien vers la page du
cahier qui la porte : thème détecté, résultat de recherche, et la visionneuse
PDF de la vue commune, qui s'ouvre désormais sur la page de la contribution
plutôt qu'en couverture. Module `gradio_app/source.py`, ancre `#page=N`.

**Périmètre.** Les deux surfaces de l'app et la commande `python -m recherche`,
qui affiche la page dans ses résultats.

**Motif.** Le plan le demandait depuis le début — « renvoyer un verbatim vers son
emplacement sur le scan, d'un clic ». Sans ce chemin, une étiquette est à prendre
ou à laisser : rien ne permet d'aller vérifier ce que le texte dit vraiment, ni
de voir ce que l'extraction a perdu. C'est le minimum qu'un corpus d'archives
doive à qui le lit, et c'est aussi ce qui rend une annotation contestable —
laquelle est le principe de tout ce dépôt.

**Alternatives écartées.** Attendre la géométrie de l'OCR pour encadrer le
passage exact sur l'image : c'est le bon objectif, mais il dépend d'une étape qui
n'est pas faite, et la page est déjà cent fois mieux que rien. Rendre le lien
inconditionnel : un lien mort vaut moins qu'un libellé nu, donc l'étiquette reste
affichée sans lien quand S3 est muet et qu'aucune copie locale ne répond.

**Conséquence mesurée.** `doleance.start_page` est renseigné pour les 1 002
doléances — aucune n'est sans page. Sur une recherche « éoliennes » (46
doléances), les vingt résultats montrés portent tous une référence cliquable de
la forme « doléance 192 · p. 3-4 ». Les thèmes de la vue commune sont câblés de
la même façon mais restent invisibles : `instance.contribution_id` est NULL pour
la livraison d'août.

**Réversibilité.** Totale : c'est de l'affichage, aucune donnée n'est écrite.

**Ce que cela ne règle pas.** La granularité s'arrête à la page. Encadrer le
passage sur l'image demande les coordonnées des lignes, que l'extraction actuelle
ne produit pas — c'est la même chose qui manque pour occulter les données
personnelles sur les scans, et c'est à demander à l'étape OCR/HTR.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-10 — On change de grille de thèmes depuis l'app

**Décision.** La vue graphe sert n'importe quelle grille de thèmes présente en
base, choisie dans un sélecteur. La logique de grille sort de l'état de module de
`views/graph.py` et devient une classe `Grille` (`views/grille.py`) qui reçoit
des lignes et ne connaît ni SQLAlchemy ni Plotly ; `views/graph.py` n'en garde
que le dessin et le service, avec un cache par run.

**Périmètre.** La vue graphe (`/graphe`). La vue commune sert toujours la grille
active.

**Motif.** La base est faite pour que plusieurs grilles coexistent : c'est ce qui
rend le choix de l'une visible et donc discutable. L'app annonçait laquelle était
servie sans permettre d'en essayer une autre, ce qui rendait cette pluralité
théorique. Il fallait activer l'autre run en base et redémarrer.

**Alternatives écartées.** Recharger la page avec un paramètre d'URL : plus
simple, mais l'état de module aurait été recalculé à chaque changement, et
surtout rien n'aurait été testable. Passer la grille en argument à chaque
fonction sans classe : vingt-cinq signatures à rallonger pour le même résultat.

**Conséquence mesurée.** Cette vue était **la seule du dépôt sans aucun test** —
un état construit à l'import depuis une connexion PostgreSQL ne se monte pas dans
un test. Elle en a maintenant vingt-quatre, et le premier essai sur une petite
grille a fait tomber une erreur que la grille livrée masquait : `_html_apercu`
indexait la liste triée des hauteurs d'une strate sans la tester, et levait
`IndexError` dès qu'une strate était vide. Les trois strates de la grille d'août
sont peuplées, le bug était donc invisible — et certain dès qu'on ouvre une
grille plus petite, ce que l'app permet désormais. C'est l'argument du
refactoring en une ligne : ce n'est pas le sélecteur qui valait le coût, c'est de
pouvoir enfin regarder ce que ce code fait.

**Réversibilité.** Totale : aucune donnée n'est écrite, c'est de la lecture et de
l'affichage.

**Ce que cela ne règle pas.** Une grille est lue une fois puis gardée en mémoire :
recharger une livraison demande toujours un redémarrage. Le sélecteur n'apparaît
que s'il y a plusieurs grilles en base — avec une seule, il n'offrirait aucun
choix. Et il n'y en a qu'une aujourd'hui : la grille émergente d'août. La
deuxième que le plan demande — « cadrage gouvernemental 2019 », reprenant les
thèmes du Grand Débat — reste à construire, et c'est elle qui donnera au
sélecteur son intérêt.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-11 — L'app lit le corpus par une grille, et montre ce que la grille rate

**Décision.** Un onglet « Lecture » : pour la grille choisie, la part des
doléances par thème (rattachées, puis en rubrique dominante), la part
**hors grille**, la distribution de référence de la grille quand elle en a
une, et dessous les doléances qu'aucun thème ne voit, les plus longues
d'abord, caviardées. La vue thèmes (l'arbre) reste, pour la grille
émergente. Les grilles gagnent une clé `reference` facultative, vérifiée au
chargement et copiée dans les paramètres des runs.

**Périmètre.** L'app et le format des grilles. Aucune détection ne change.

**Motif.** L'arbre montre la *grille* : comment son auteur a rangé ses
catégories. Il sert celui qui a produit la grille, et sur une grille plate
il n'a rien à montrer que neuf points. La question utile est « qu'est-ce
que la grille fait voir du corpus, et qu'est-ce qu'elle rate ». Le hors
grille lisible est la vue la plus honnête qu'on puisse donner d'une grille,
et la matière première de l'atelier avec l'association : on y lit ce que ni
le gouvernement ni les gilets jaunes n'avaient prévu comme rubrique.

**Ce que ça montre, sur les mots-clés du Vrai Débat** (1 002 doléances
dactylographiées) : 36 % hors grille ; en rattachement multiple, démocratie
51 %, économie 51 %, écologie 40 %, santé 39 % ; en rubrique dominante,
**économie 40 %, démocratie 10 %, écologie 6 %, santé 2 %**, contre 31 / 20 /
16 / 10 sur la plateforme. La dominante se lit avec sa règle : le thème qui
a le plus de termes qui mordent, ce qui avantage les lexiques les plus
fournis (l'économie a le plus de termes). C'est un artefact du détecteur
autant qu'un fait du corpus, et c'est écrit sous le graphique ; un modèle
qui choisit une rubrique rendra la comparaison honnête.

**Une première version comptait les instances** : les mots-clés n'en font
qu'une par thème et par doléance, tout était à égalité, et la première
rubrique de la grille dominait 51 % des doléances. Corrigé avant d'être
montré ; consigné parce que c'est le genre d'erreur qu'un graphique rend
crédible.

**Deux croisements de plus, le soir même.** La co-occurrence thème ×
thème, rapportée au hasard *parmi les doléances rattachées* (rapportée au
découpage entier, le hors grille gonflait tout d'un même facteur, 1,6 à
2,8, et la matrice ne disait rien). Résultat : 1,05 à 1,76, et ce sont les
petites rubriques (sport, justice, Europe) qui vont le plus ensemble, parce
qu'elles n'apparaissent que dans les longues lettres qui parlent de tout.
La longueur est le premier facteur, avant tout propos ; la vue le dit sous
le graphique. Et les thèmes par **taille de commune** (population du COG
2019, strates 500 / 2 000 / 10 000 ; 159, 395, 310, 103 doléances, 35 sans
commune) : le **hors grille tombe de 47 % dans les communes de moins de
500 habitants à 15 % dans celles de 10 000 et plus**. Le détecteur, et
vraisemblablement toute grille lexicale, voit les villes mieux que les
villages, dont les doléances sont plus courtes et parlent d'un seul
sujet. C'est le résultat le plus utile de la journée pour l'association :
la voix que les cahiers devaient faire entendre est celle que la grille
capte le moins.

**Alternatives écartées.** Une carte par commune : demande les contours
communaux, et une choroplèthe sur 459 communes dont 37 muettes est surtout
jolie.

**Réversibilité.** Un onglet, une clé facultative.

**Auteur.** Équipe technique, *à nommer avant publication*.

---

## 2026-09-11 — Le manuscrit est transcrit en local, pas par une API

**Décision.** La passe complète de transcription du manuscrit (2 510 pages
`needs_ocr`) tourne sur un modèle à poids ouverts, `ornith-1.5:9b` servi par
Ollama sur un GPU que l'équipe contrôle : **aucun scan ne quitte nos
machines**. Mistral OCR n'est pas retenu pour cette passe ; il ne le sera, s'il
l'est, qu'en synchrone, sur un compte payant avec opt-out de l'entraînement et
*Zero Data Retention* accordés — jamais en batch — et après validation par un
DPO. Run de genre `transcription`, format JPEG à 300 DPI, paramètres et
modèle portés par le run.

**Périmètre.** Le choix du backend OCR et de l'hébergement des scans. Pas la
qualité de la transcription, qui reste à mesurer sur l'étalon (`reference/`).

**Motif.** Un nom au bas d'une opinion politique est une donnée de l'article 9
du RGPD, et c'est très exactement le contenu de ces pages. Confier les scans
à une API fait de l'éditeur un sous-traitant (art. 28) : contrat de
traitement, base légale documentée, registre — l'alignement avec les Archives
que le plan demande avant de figer quoi que ce soit. Et les conditions de
Mistral, lues le 2026-09-11, écartent d'elles-mêmes le mode batch : sur le
plan gratuit « input and output data are used by default to train our
models, unless you opt out » ; les fichiers batch restent stockés jusqu'à
suppression et le *Zero Data Retention* « does not apply to … batch
processing files, /v1/files » ; le ZDR n'existe qu'en pay-as-you-go, sur
demande motivée, « at our discretion ». Le rabais de 50 % et la rétention
vont ensemble. Le modèle local, lui, tranche la question d'office — c'est
l'option que le plan listait dès le 2026-09-10.

**Ce qui a déjà été envoyé.** Avant cette décision, **33 pages** de scans
bruts sont parties à l'API Mistral : 31 pour l'essai du 2026-09-10 (une page
seule, 15 typées et 15 manuscrites tirées au sort), 2 pour l'essai du mode
batch le 2026-09-11 — celles-ci en fichier, supprimé de la plateforme le jour
même. Le compte était en plan gratuit ; l'opt-out de l'entraînement est à
vérifier dans la console. C'est consigné pour que ce soit contestable.

**Alternatives écartées.** *Mistral en batch* : moitié prix (~5 $ pour le
manuscrit) et géométrie ligne à ligne — le préalable de l'occultation sur
l'image —, mais rétention des fichiers et pas de ZDR. *Mistral en synchrone
avec ZDR* : possible, plein tarif (~10 $), reste conditionné au DPO ; c'est la
voie à rouvrir si la géométrie devient nécessaire à la P3, en second run à
côté de celui-ci. *glm-ocr en local* : le défaut du module, plus rapide, mais
sur 3 pages jugées image sous les yeux il lit moins bien (« quand chose » pour
« grand chose », artefacts LaTeX) et boucle sur une page vide — 35 000
caractères. Ornith lit les trois pages juste, wordfreq 0,97 contre 0,83.

**Conséquence mesurée.** 6 à 20 s par page sur GPU, 8 à 14 h pour le
manuscrit, 0 €. Deux limites d'ornith, à traiter en aval : c'est un modèle de
langue autant que de vision — il ajoute des guillemets, normalise « ① » en
« 1) », et **sur une page vide il écrit une ligne de commentaire** (« L'image
ne contient aucun texte ») au lieu de rien, même consigné de ne rien produire.
Et pas de géométrie : `layout` reste NULL.

**Réversibilité.** Totale : un run, supprimable avec ses lignes. Une deuxième
passe — autre modèle, ou Mistral sous les conditions ci-dessus — coexiste en
base et se compare sur l'étalon ; c'est pour cela que le squelette n'est
jamais écrasé.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-11 — Le manuscrit entre dans la lecture, page par page, sans écraser

**Décision.** Le corpus se lit désormais par un **texte de lecture** unique
(`database/pages.py`), choisi page par page : la transcription du run
`transcription` actif si la page en a une, sinon le squelette
(`page_extraction.text`) si la page n'est pas `needs_ocr`, sinon rien.
Segmentation, export vers l'analyse, couverture et app passent tous par là.
Le squelette n'est pas modifié ; l'option `--keep-ocr-pages` disparaît — il
n'y a plus de « bruit à réintégrer », il y a des pages lisibles ou non.

**Périmètre.** Tout ce qui lit le texte des pages. Pas la transcription
elle-même (run 18, en cours), pas le découpage — qui reste le même, appliqué à
plus de texte.

**Motif.** La transcription est une couche (journal du 2026-09-10, « Les
couches interprétatives sont versionnées ») ; elle doit pouvoir être remplacée
par une autre — autre modèle, ou Mistral sous conditions — sans rien réécrire.
Une lecture unique, branchée sur le run actif, donne ça : activer un run change
la lecture de tout le monde d'un coup, le désactiver ramène au squelette seul.
Et la mesure de couverture change de sens sans changer de code : « écartée »
veut dire manuscrite *sans transcription*, et l'app le dit.

**Deux règles de lecture, à connaître.**
- Une transcription prime sur le squelette même sur une page typée : c'est le
  but du périmètre `suspect` (formulaires remplis à la main que `needs_ocr`
  manque), et la transcription corrige aussi la couche texte des archives,
  corrompue sur les en-têtes (essai du 2026-09-10).
- Un commentaire de modèle sur une page vide (« Cette image ne contient aucun
  texte », court, sur une page/image/document dit vide, vierge, sans texte) est
  lu comme un texte vide. Mesuré sur ornith-1.5 le 2026-09-11 : le modèle écrit
  cette phrase malgré la consigne. Sans la règle, ce serait une doléance de
  plus, signée par le modèle.

**Conséquences.** Le run de découpage note le run de transcription qu'il a lu
(`parameters.run_transcription`) : deux découpages ne se comparent qu'à texte
de lecture égal. L'étalon (`reference/`) dépend du texte de lecture : figé sous
un run de transcription, il s'évalue sous le même — le garde-fou d'alignement
le signale sinon. Un découpage complet est à relancer en nouveau run une fois
la passe finie, pour mesurer avant/après.

**Réversibilité.** Désactiver le run de transcription : la lecture redevient
celle du squelette, à l'identique.

**Auteur.** Équipe technique — *à nommer avant publication*.

---

## 2026-09-11 — Le compte rendu du POC est lu : ce que la branche garde, renverse, ou laisse à trancher

**Décision.** Les huit faits du compte rendu du POC qui ne figuraient nulle
part dans le repo sont consignés en tête du plan (« Ce que le POC avait
décidé »), et deux priorités changent :
- la **grille de l'association** passe avant les détections par modèle. Le
  POC avait conclu qu'une taxonomie définie avec l'association était un
  préalable ; les deux grilles du repo, émergente et cadrage gouvernemental
  2019, n'en tiennent pas lieu. Elles restent : l'une mesure ce que le corpus
  dit de lui-même, l'autre ce que le cadrage de 2019 lui fait dire ;
- **l'endpoint Scaleway** (Qwen 3.5-35B-A3B, mis à disposition par Data For
  Good) est à retrouver avant de bâtir un hébergement de plus en local. S'il
  est encore ouvert, la question d'hébergement de la P3 a une réponse en
  Union européenne, sous contrôle associatif.

**Périmètre.** La documentation et l'ordre des chantiers. Aucun code, aucune
donnée.

**Motif.** Un plan écrit sans le mandat du commanditaire répondait à des
questions que le POC avait choisi de ne pas poser (exhaustivité, publication)
et ignorait ce qui avait été tranché (taxonomie avec l'association, données
sous NDA). Les faits sont consignés par rôle, sans recopier le document, qui
nomme des bénévoles et des liens privés.

**Ce que ça change, et ce que ça ne change pas.** La passe HTR reste
justifiée, pour une autre raison : une curation de « coups de cœur » ne doit
pas se faire dans la seule moitié dactylographiée. Le texte de lecture, les
runs, l'étalon de découpage ne bougent pas. La publication du journal « avec
le corpus » devient une hypothèse à valider avec l'association : tant que la
donnée est sous NDA, tout ce qui est écrit ici suppose un usage interne.

**Réversibilité.** Totale : c'est de la documentation.

**Auteur.** Équipe technique, *à nommer avant publication*.

---

## 2026-09-12 — Le corpus est redécoupé avec le manuscrit lu, sans anonymisation pour l'instant

**Décision.** Un nouveau run de découpage, #26 « signaux de texte, manuscrit
lu (run 18) », actif, sur le texte de lecture complet : squelette pour le
typé, transcription du run 18 pour le manuscrit (2 510 pages, plus les
pages suspectes au fur et à mesure de leur passe). Les doublons et les deux
lexiques de mots-clés sont rejoués dessus. **L'anonymisation ne l'est pas** :
pas de passe NER cette nuit, le poste ne s'y prête pas et le GPU transcrit
les pages suspectes. Tant qu'elle n'a pas tourné, les extraits de la
recherche et de l'onglet Lecture ne sont pas caviardés pour ce découpage ;
l'app tourne en usage interne, sur cette machine, et c'est consigné ici
plutôt que masqué.
*Levé le jour même : voir l'entrée suivante.*

**Avant la lecture, une règle de plus.** Onze pages du run 18 sont des
dérives du modèle (boucles, emballement jusqu'à 50 000 caractères) que le
score wordfreq ne voit pas ; `database/pages.py` les écarte à la lecture
(`est_derive`, quatre signes) et `derives()` les liste pour une seconde
passe. Voir le commit du même jour.

**Mesuré, avant / après** (avant = découpage #2, typé seul ; après = #26) :

| | avant | après |
|---|---|---|
| doléances | 1 002 | **1 531** |
| communes avec au moins une doléance | 422 | **459** (toutes) |
| mots par doléance, moyenne / médiane | 753 / 245 | 709 / 285 |
| doublons groupés | | 12 groupes, 29 doléances (2 %) |
| Vrai Débat, mots-clés : doléances hors grille | 363 (36 %) | **302 (20 %)** |
| hors grille, communes de moins de 500 habitants | 47 % | **25 %** |
| hors grille, 10 000 habitants et plus | 15 % | 6 % |
| cadrage gouvernemental, rattachements | 4 857 | 8 797 |

Le manuscrit ne fait pas que grossir le corpus : il le rééquilibre. Les 37
communes muettes ont une voix, et l'écart entre villages et villes, qui
était le résultat de la veille, se réduit de moitié sans disparaître. La
comparaison est à prendre avec deux réserves : les runs de mots-clés sont
**repris** (un run par lexique, rejoué sur le découpage actif), donc les
détections « avant » n'existent plus en base, seulement ici ; et le
découpage lit un manuscrit dont la fidélité n'est pas encore mesurée sur
l'étalon. La rubrique dominante « économie » passe de 40 % à 57 % : le
lexique le plus fourni gagne encore, c'est l'artefact déjà consigné.

**Réversibilité.** Réactiver le run #2 ramène tout le monde au typé seul ;
les runs de mots-clés se rejouent dessus en une commande.

**Auteur.** Équipe technique, *à nommer avant publication*.

---

## 2026-09-12 — L'anonymisation est rejouée sur le découpage #26, sur une machine à part

**Décision.** Run d'anonymisation #30 « formes, signatures et entités
nommées », actif, sur les 1 531 doléances du découpage #26. Même passe que
le 2026-09-11 (formes + signatures + CamemBERT-NER, seuils inchangés), mais
exécutée sur une machine dédiée, sur CPU, la base restant ici et jointe par
un tunnel SSH inverse : le poste de travail ne porte plus les passes modèle.
Les pages suspectes du run 18 (474, terminées à 2 h 23) sont dans le texte
lu, donc dans ce découpage et dans cette passe.

**Ce que ça donne, mesuré.** 27 655 passages dans 1 484 doléances (97 %) :
lieux 12 686, noms 5 949, institutions 5 464, rôles publics 2 054,
téléphones 490, adresses 460, courriels 346, liens 206. Sur le découpage #2,
la même passe donnait 19 306 passages dans 968 doléances ; le rapport suit le
nombre de doléances (× 1,53 pour × 1,43) avec un peu plus de noms par
doléance, le manuscrit signant davantage que le typé. 10 min 21 s sur 16
cœurs.

**Conséquence dans l'app.** Les extraits de la recherche et de l'onglet
Lecture sont de nouveau caviardés pour le découpage servi ; la réserve
consignée le matin même est levée. Le rappel reste non mesuré : l'étalon
annoté à la main n'existe toujours pas.

**Ménage.** Un run #27, ouvert par une tentative locale interrompue avant
toute détection (0 passage), a été supprimé.

**Réversibilité.** Les runs #3 et #23 (découpage #2) restent en base ;
activer l'un d'eux avec le découpage #2 ramène l'état d'avant.

**Auteur.** Équipe technique, *à nommer avant publication*.

---

## À consigner dès qu'elles seront prises

- Le statut donné à chaque grille de thèmes, une fois qu'elles auront leurs
  détections par un modèle (les mots-clés du 2026-09-11 sont un étalon bas,
  pas un statut).
- Le modèle d'embedding, sa dimension et son lieu d'exécution — même décision
  d'hébergement que pour la reconnaissance d'entités nommées ; pour l'OCR, elle
  est prise (2026-09-11 : en local).
- Les règles d'anonymisation : ce qui est occulté, ce qui ne l'est pas
  (personnalités publiques dans leur rôle), le seuil de rappel accepté.
- L'arbitrage précision géographique / protection pour les très petites communes
  — la pondération par population montre que ce sont elles qui manquent le plus
  au corpus, ce qui rend l'arbitrage plus coûteux qu'il n'y paraissait.
- La normalisation orthographique, si une version normalisée est ajoutée pour la
  recherche — et la garantie que la version de référence, elle, n'est pas touchée.
- Le périmètre publié : ce qui est mis en ligne, ce qui reste consultable sur
  place seulement. Depuis le 2026-09-11, la question est d'abord celle du NDA
  qui couvre la donnée remise à l'association.
- La grille de thèmes de l'association, à définir avec elle (POC, section 6).
