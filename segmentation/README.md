# Segmentation : du cahier aux doléances

Découpe le texte des cahiers en **doléances individuelles** — ce qu'a écrit une
personne — et les stocke dans la table `doleance`.

## Pourquoi

L'unité d'analyse était mal posée. `extraction/without_ocr` crée une
contribution *par page*, et `export_dataset.py` envoie donc *un document = une
page* à l'analyse. Or une page de registre porte souvent plusieurs
contributeurs, et une doléance longue court sur plusieurs pages. Toute
statistique de thèmes calculée à ce niveau porte sur un agrégat multi-auteurs :
« combien de personnes demandent X » n'a pas de réponse juste.

Le découpage se fait par **cahier** (`page_extraction.pdf_name`), pas par
contribution : une contribution ne couvrant qu'une page, une doléance à cheval
sur deux pages en traverserait deux.

Et il est **versionné**. Le découpage est un acte interprétatif — c'est une
heuristique qui décide qu'une page porte trois auteurs — il appartient donc à la
couche annotation, pas au squelette du corpus. Chaque doléance porte le `run`
qui l'a produite (voir [database/README.md](../database/README.md)) : deux
découpages peuvent coexister et se comparer, au lieu que le second écrase le
premier.

## Ce que le découpage sait faire, et ce qu'il ne sait pas

Les règles ne lisent que le texte, parce que c'est tout ce qu'on a. Les deux
meilleurs séparateurs d'un registre — le blanc vertical et le changement
d'écriture — sont dans la géométrie de la page, que l'extraction ne rend pas.
D'où [le préalable du plan](../docs/plan_post_ocr.md) : demander à l'OCR le
texte **ligne par ligne avec sa bounding box**.

En attendant, cinq signaux, tous dans `config.py` :

| Signal | Déclencheur | Exemple |
|---|---|---|
| `date` | une ligne *entièrement* datée | `Le 21 février 2019` |
| `apostrophe` | une formule d'appel courte | `Monsieur le Préfet,` |
| `cloture` | une formule de politesse, puis la signature | `Veuillez agréer…` |
| `separateur` | un filet tracé à la main | `----------` |
| `numerotation` | une numérotation explicite de registre | `Contribution n° 12` |

Deux garde-fous, tous deux couverts par des tests :

- un signal ne coupe que si la doléance en cours pèse déjà
  `MIN_CARACTERES_DOLEANCE` — sinon l'en-tête d'une lettre, qui enchaîne date et
  formule d'appel, se découperait lui-même ;
- les puces (`1.`, `2°`, `-`) ne coupent pas : les doléances énumèrent leurs
  demandes, couper à chaque puce les émietterait.

**Invariant** : le découpage partitionne les lignes, il n'en supprime aucune.
Recoller les doléances redonne exactement le texte d'entrée. C'est ce qui permet
de rejouer un découpage plus fin plus tard sans avoir perdu de texte.

**Mesure sur le corpus réel** (516 cahiers, 2 855 pages lisibles) : le pipeline
produit **1 002 doléances** dans 469 cahiers, soit 2,1 par cahier, dont 622 à
cheval sur plusieurs pages. Les signaux qui coupent : apostrophe 188, clôture
160, date 126, filet 59.

Moyenne de **753 mots par doléance** — c'est long pour ce qu'a écrit une
personne, et cela dit probablement que le découpage **sous-coupe**. C'est un
plancher assumé : ce qui n'est pas marqué dans le texte n'est pas vu, et sans
géométrie de ligne le blanc vertical et le changement d'écriture sont invisibles.
Seul le [jeu de référence](../reference/README.md) pourra chiffrer l'écart.

> Une mesure antérieure annonçait « 3 243 doléances, 11 % des pages portent plus
> d'un contributeur ». Elle avait été obtenue en découpant chaque page
> *séparément*, ce que le pipeline ne fait pas : il regroupe par cahier, si bien
> qu'une doléance peut couvrir plusieurs pages. Les 11 % restent vrais des pages
> prises isolément ; les 3 243 ne sont pas la sortie du pipeline.

## Organisation

| Fichier | Rôle |
|---|---|
| `config.py` | les signaux de rupture et les seuils |
| `decoupage.py` | le découpage, sans base de données — testable sur des chaînes |
| `persistance.py` | la navette `page_extraction` -> `doleance`, rapportée à un run |
| `__main__.py` | le script de découpage par lot |
| `tests/` | tests unitaires des règles et de la persistance |

## Lancer le découpage

```bash
uv run alembic upgrade head    # crée les tables doleance et run
uv run python -m segmentation --auteur "prénom nom"
```

Complète le run de découpage **actif** — les cahiers qu'il ne couvre pas encore —
et en crée un s'il n'y en a pas. Relancer la commande reprend là où elle s'était
arrêtée, sans rien réécrire.

```bash
uv run python -m segmentation --nouveau-run "règles v2" --auteur "prénom nom"
```

Crée un run et y redécoupe tout le corpus. Le précédent reste en base, intact et
comparable : on ne détruit plus un découpage pour en essayer un autre. C'est le
nouveau run qui devient servi — par l'export, et par tout ce qui lit la couche.

`--auteur` reste facultatif à la ligne de commande, mais le run est attribué
d'office : à défaut d'argument, l'auteur est lu dans la variable
`CAHIER_DOLEANCES_AUTEUR`, puis dans la configuration git du dépôt. La colonne
est `NOT NULL` — il n'existe plus de run anonyme. Les pages `needs_ocr` sont écartées, comme à l'export
(`--keep-ocr-pages` pour les inclure) — c'est une décision consignée au
[journal](../docs/journal_des_decisions.md), pas un détail technique.

## Exporter les doléances vers l'analyse

```bash
uv run python -m analyse.export_dataset --niveau doleance --output topic-builder/data/cahiers/dataset.csv
```

L'export ne sert que le découpage actif : deux découpages du même corpus
doubleraient les documents. Les identifiants sont préfixés `d` (`d42`), pour qu'une
livraison sur les doléances ne soit pas rechargée comme si ses ids désignaient
des contributions — les deux tables ont des id qui se recouvrent. Voir
`analyse/identifiants.py`.

## Tester

```bash
uv run --extra dev pytest segmentation
```
