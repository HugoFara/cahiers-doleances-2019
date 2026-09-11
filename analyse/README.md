# Analyse : le corpus qui sort, la grille de thèmes qui revient

Une grille de thèmes est une *lecture* du corpus, pas une propriété du texte :
elle dépend du modèle, du prompt, du nombre de clusters, ou de la main qui l'a
écrite. Elle est donc chargée comme un run de genre `analyse`, daté et attribué,
et plusieurs coexistent — c'est ce qui rend le choix de l'une visible et
discutable, au lieu d'en faire la référence implicite. `taxonomie/` mesure
ensuite ce qu'une grille vaut ; l'app en sert une et permet d'en changer.

Ce paquet gère l'aller et le retour :

| Fichier | Rôle |
|---|---|
| `export_dataset.py` | le corpus vers le CSV `id,content` que lit `topic-builder` |
| `load_analysis.py` | la livraison (`taxonomy.json`, `instances.json`) vers `topic` et `instance` |
| `identifiants.py` | le format d'identifiant de document, partagé par les deux |
| `grille.py` | une grille écrite à la main, chargée sans détections |
| `mots_cles.py` | le rattachement d'une grille par mots-clés — sans modèle, étiqueté tel quel |
| `grilles/` | les grilles de cadrage versionnées, avec leur source, et leurs lexiques |

## Deux grilles, dès le départ

Le plan demande qu'au moins deux grilles coexistent pour qu'une comparaison
soit possible : une grille **émergente** (découverte par `topic-builder`) et une
grille reprenant les **thèmes du Grand Débat 2019**, étiquetée « cadrage
gouvernemental 2019 » — précisément pour que ce cadrage soit visible et
discutable au lieu d'être la référence implicite.

La seconde est dans `grilles/cadrage_gouvernemental_2019.json` : les quatre
thèmes de la Lettre aux Français du 13 janvier 2019, et sous chacun ses
questions, **reproduites mot pour mot** en description — seul le nom court de
chaque thème enfant est une étiquette éditoriale, marquée non validée tant
qu'une relecture ne l'a pas confirmée. La source est nommée, datée, et citée
dans les `notes` du run.

```bash
uv run python -m analyse.grille analyse/grilles/cadrage_gouvernemental_2019.json
```

Elle se charge comme un run de genre `analyse`, **non actif** : sans
détections, elle n'a rien à servir, mais elle apparaît dans le sélecteur de
l'app et `taxonomie/` peut la comparer aux autres. Recharger le même fichier met
la grille à jour au lieu d'en créer une seconde ; `--activer` en fait la grille
servie.

**Ses détections, pour l'instant : des mots-clés.** Rattacher chaque doléance
à l'un de ses thèmes avec un modèle attend la P3. En attendant,
`analyse/mots_cles.py` fait ce qu'un rattachement *sans* modèle sait faire :
un jeu de mots-clés par question (`grilles/cadrage_gouvernemental_2019.mots_cles.json`,
syntaxe de `recherche/`), une requête sur l'index plein texte, une instance par
doléance qui répond — verbatim sur le premier terme trouvé, résumé listant les
termes qui ont mordu.

```bash
uv run python -m analyse.mots_cles analyse/grilles/cadrage_gouvernemental_2019.mots_cles.json
uv run python -m taxonomie --run <id>      # ce que ça vaut
```

Le résultat est un **run à part, non actif**, `model = "mots-clés"`, requêtes
dans ses paramètres, thèmes de la grille copiés dedans : la grille de
`grille.py` reste sans détections, et un modèle, plus tard, se comparera au
même étalon bas. Mesuré le 2026-09-11 sur les 1 002 doléances du découpage
servi (corpus dactylographié) : **655 doléances rattachées à au moins une
question (65 %), 4 857 rattachements, 7,4 questions par doléance** — un
détecteur de vocabulaire, pas de propos : une doléance de 750 mots en moyenne
touche presque tout. Quatre requêtes ont été élaguées après mesure, dont
« cahier de doléances » et « grand débat », qui rattachaient le document à
lui-même (334 et 267 doléances) ; le lexique le consigne. Aucune détection sur
les racines : `taxonomie/` compte 4 thèmes sans détection, c'est voulu.

**Une troisième grille, celle de l'autre camp : le Vrai Débat 2019.**
`grilles/vrai_debat_2019.json` reproduit les neuf rubriques de la plateforme
lancée par des gilets jaunes en janvier 2019 (même moteur que granddebat.fr),
libellés tels quels, à plat : l'auteur d'une proposition en choisissait une
seule. Elle a ce que les deux autres n'ont pas, une **distribution de
référence** (25 000 propositions : économie 31 %, démocratie 20 %, transition
écologique 16 %, santé 10 %), donc une question à poser au corpus : les gens
qui écrivent en mairie parlent-ils de la même chose que ceux qui déposaient en
ligne ? Son lexique, `grilles/vrai_debat_2019.mots_cles.json`, suit les
périmètres ministériels des rubriques, pas le propos, et consigne ce qui a
été écarté après mesure (« maire » et « président », l'adresse de la lettre ;
« loyer », que la configuration sans accent réduit à « loi »).

```bash
uv run python -m analyse.grille analyse/grilles/vrai_debat_2019.json
uv run python -m analyse.mots_cles analyse/grilles/vrai_debat_2019.mots_cles.json
```

Le fichier porte aussi une clé `reference` : la distribution mesurée par la
source chez elle (titre, source, parts par thème), vérifiée au chargement
(chaque part vise un thème) et copiée dans les paramètres du run de la grille
et de ses rattachements. C'est ce que l'onglet « Lecture » de l'app trace en
grisé à côté des parts du corpus.

Mesuré le 2026-09-11 sur les mêmes 1 002 doléances dactylographiées : **639
rattachées (64 %), 3 158 rattachements, 4,9 rubriques par doléance**, 45 %
des doléances rattachées touchent six rubriques ou plus, texte couvert 13 %.
Les rubriques par volume de doléances : démocratie 512, économie 509,
écologie 398, santé 394, expression libre 346, éducation 298, Europe 277,
justice 251, sport et culture 173. La comparaison avec les parts du Vrai
Débat n'est pas directe (une rubrique par proposition là-bas, 4,9 par
doléance ici) ; elle le deviendra avec un rattachement qui choisit.

## Exporter le corpus pour l'analyse

`analyse/export_dataset.py` écrit le CSV `id,content` attendu par
`topic-builder`, à deux niveaux (`--niveau`) :

- `contribution` (défaut) : une ligne par contribution, pages concaténées dans
  l'ordre. Le texte est le texte de lecture (`database/pages.py`) :
  transcription du run `transcription` actif si la page en a une, squelette
  sinon ; une page manuscrite sans transcription n'a pas de texte et n'est pas
  exportée. **Une contribution, c'est une page** : plusieurs contributeurs
  peuvent s'y côtoyer, et une doléance longue y est coupée en deux.
- `doleance` : lit `doleance`, une ligne par contributeur, telle que
  `segmentation/` l'a découpée. C'est la bonne unité d'analyse.

**L'`id` du document est la clé primaire de la ligne exportée** — `42` pour une
contribution, `d42` pour une doléance. La livraison de l'analyse renvoie ses
labels indexés par cet id, ce qui rend le rapprochement immédiat au retour (voir
plus bas). Le préfixe n'est pas cosmétique : les deux tables ont des id
auto-incrémentés qui se recouvrent, sans marquage une livraison sur les doléances
serait rechargée en désignant des contributions au hasard. Le format est dans
`analyse/identifiants.py`, partagé par l'export et le chargement.

## Charger la livraison de l'équipe analyse

`analyse/load_analysis.py` lit un dossier de livraison (`taxonomy.json` +
`instances.json`) et remplit `topic` et `instance` sous un run de genre
`analyse`. Chaque chargement est une grille de plus, ou la mise à jour de celle
que ce dossier a déjà produite.

`instance.contribution_id` est résolu quand l'id de document de la livraison
correspond à une contribution existante — c'est le cas des livraisons produites
depuis `export_dataset.py`. Sinon (livraisons antérieures, numérotées `doc 73` par
l'équipe analyse) il reste NULL et l'instance n'est rattachée que par
`external_doc_id`, comme avant. Le script affiche le nombre d'instances rattachées.

Quand la livraison porte sur des doléances (ids `d42`), `instance.doleance_id` est
résolu **et** `contribution_id` est repris de la doléance : les vues de l'app
joignent sur `contribution_id`, elles continuent de fonctionner sans connaître le
nouveau niveau.

**La livraison d'août ne décrit pas ce corpus.** `load_analysis.py` vérifie que
les verbatims d'une livraison se retrouvent bien dans le texte visé, et refuse le
rattachement en dessous de 30 % : c'est ce garde-fou qui laisse
`instance.contribution_id` à NULL. Mesuré le 10 septembre 2026, la raison est
plus profonde qu'un décalage d'identifiants — sur les 9 579 extraits de cette
livraison, **3,8 % seulement** se retrouvent dans les 6,4 millions de caractères
de `page_extraction`, et **24 % de son vocabulaire y est absent**. Elle porte sur
une autre extraction, ou un autre périmètre. Aucun rattachement par verbatim ne
la sauvera : il faut refaire l'analyse sur le corpus actuel.

## Commandes

```bash
uv run python -m analyse.export_dataset --output data/dataset.csv                    # corpus -> CSV topic-builder
uv run python -m analyse.export_dataset --niveau doleance --output data/dataset.csv  # au niveau doléance
uv run python -m analyse.load_analysis <dossier>                                     # charger une livraison (met à jour sa grille)
uv run python -m analyse.load_analysis <dossier> --nouveau-run --label "v5"          # charger en grille de plus
uv run python -m analyse.grille analyse/grilles/cadrage_gouvernemental_2019.json     # charger une grille écrite à la main
```
