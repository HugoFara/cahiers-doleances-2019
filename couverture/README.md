# Couverture : ce que le corpus analysé laisse dehors

Le pipeline écarte les pages `needs_ocr` — celles dont le texte extrait sans OCR
est du bruit, en pratique les pages manuscrites. C'est une contrainte technique
subie, pas un choix éditorial. Mais elle a une conséquence qui, elle, n'est pas
technique : **le corpus analysé n'est que sa partie dactylographiée**.

Tant que ce n'est pas chiffré, toute statistique tirée du corpus se lit comme si
elle portait sur l'ensemble.

## Le chiffre, au 10 septembre 2026

Mesuré sur les 516 cahiers de `data/raw/pdfs` (5 365 pages extraites) :

| Échelle | Écarté | |
|---|---|---|
| pages | 2 510 / 5 365 | **47 %** |
| cahiers touchés (au moins une page perdue) | 445 / 516 | 86 % |
| communes touchées | 402 / 459 | 88 % |
| cahiers entièrement écartés | 47 | |
| **communes sans aucune page lisible** | **37** | |

Les 2 855 pages retenues sont exactement les 2 855 documents de
`topic-builder/data/cahiers/dataset.csv` : le corpus analysé jusqu'ici, c'est
cette moitié-là.

Trente-sept communes n'ont **aucune voix** dans l'analyse. Ce n'est pas la même
chose qu'être partiellement lue : leur cahier existe, il a été numérisé, et il ne
compte pour rien dans les comptages de thèmes.

> Les chiffres de communes publiés le 10 septembre — 24 muettes sur 307 —
> comptaient les communes par la graphie de leur en-tête, absente sur un tiers
> des cahiers : ces communes n'étaient comptées ni au numérateur ni au
> dénominateur. Le rattachement au code INSEE donne le vrai compte. Les chiffres
> de pages et de cahiers, eux, n'ont pas bougé.

### En habitants plutôt qu'en communes

Depuis que le référentiel INSEE est chargé (`python -m insee cog`), le rapport
pondère par population, et cela déplace la lecture. Les 37 communes muettes
pèsent **36 697 habitants sur 937 022, soit 4 %** — là où elles sont 8 % des
communes.

Les deux chiffres sont vrais et disent des choses différentes. En communes, une
commune sur douze est réduite au silence, et c'est cela qui compte pour un
corpus dont l'unité de collecte est la commune. En habitants, la part est deux
fois moindre, parce que **les communes muettes sont les petites** — celles dont
le cahier est un registre manuscrit de quelques pages, précisément celles que le
filtre `needs_ocr` écarte le plus complètement.

Publier l'un sans l'autre serait trompeur dans les deux sens : le premier seul
exagère la perte de volume, le second seul masque que ce sont toujours les mêmes
communes qui disparaissent.

La pondération n'est pas une mesure de représentativité. Elle dit quelle part de
la population des communes du corpus a au moins une page lisible ; elle ne dit
rien de ceux qui n'ont pas écrit, ni des communes qui n'ont pas déposé de cahier
— ce dernier chiffre est dans [`insee/`](../insee/README.md).

## Le seuil tient-il ?

`needs_ocr` est déclenché sous un score de qualité de 0,3. C'est un réglage — si
la barre tombait au milieu d'un continuum, les 47 % ne seraient qu'un artefact de
son emplacement. La distribution est franchement bimodale : 2 070 pages sous 0,2,
1 591 au-dessus de 0,9, et un creux entre les deux.

| Seuil | Pages écartées | |
|---|---|---|
| 0,10 | 1 018 | 19 % |
| 0,20 | 2 070 | 39 % |
| 0,30 | 2 510 | **47 %** (en service) |
| 0,40 | 2 703 | 50 % |
| 0,50 | 2 816 | 52 % |

Conclusion : « environ la moitié du corpus est écartée » **résiste à une hausse
du seuil** — de 0,3 à 0,5, on ne bouge que de 5 points. Le chiffre est en
revanche sensible à une baisse, parce qu'on entame alors la masse basse. Les 447
pages de la tranche 0,2-0,3 sont le vrai gris.

## Ce que ça n'est pas

Ce n'est pas une mesure de la représentativité du corpus au sens statistique.
Elle dit seulement ce que la chaîne technique perd entre le scan et l'analyse.
Elle ne dit rien de qui a écrit, ni de quelles communes ont ouvert un registre,
ni de ce qui a été conservé aux Archives. La couverture au sens de la
représentativité — quelle part de la population des quatre départements a un
cahier quelque part — est mesurée dans [insee/README.md](../insee/README.md), et
elle non plus ne rend pas le corpus représentatif.

## Utilisation

```bash
uv run python -m insee cog                           # pour la pondération
uv run python -m couverture                          # rapport à l'écran
uv run python -m couverture --json data/couverture.json
```

Le rapport ne contient que des compteurs, jamais le texte des cahiers : il est
partageable tel quel. Les noms de communes muettes en font partie — ce sont des
données publiques, et c'est précisément l'information à afficher à côté de tout
comptage.

Ces noms viennent du référentiel INSEE quand il est chargé. Sans lui, quatorze
des trente-sept communes muettes s'affichaient par leur seul code, faute de
graphie lisible dans leur en-tête : une liste de codes n'est pas une information
publiable.

## Organisation

| Fichier | Rôle |
|---|---|
| `mesures.py` | les mesures, sans base de données — testables sur des lignes |
| `__main__.py` | le rapport et son export JSON |

Les communes sont comptées par leur code INSEE dès que `python -m insee
rattacher` a tourné ; à défaut, `mesurer` retombe sur le regroupement de
graphies de `insee/communes.py` et le rapport le signale, parce que le
compte est alors sous-estimé d'environ un tiers. L'import depuis `gradio_app/`
est une entorse assumée — le module y est sans dépendance à Gradio ni à la base
— plutôt que de dupliquer une logique qui a déjà produit un bug (187d133).

## Tester

```bash
uv run --extra dev pytest couverture
```
