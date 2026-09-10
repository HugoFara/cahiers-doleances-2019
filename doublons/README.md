# Doublons : les textes qui reviennent

Les registres contiennent des tracts collés, des lettres-types diffusées par des
associations, des pétitions, et parfois le même cahier scanné deux fois.
Comptées comme autant de contributions distinctes, elles gonflent les fréquences
de thèmes : « 34 % des contributions parlent de fiscalité » peut ne mesurer que
le nombre de fois qu'un texte a été recopié.

**On ne les écrase pas pour autant.** « Ce texte apparaît dans six communes » est
un résultat en soi — une campagne organisée, ce qui est autre chose qu'une
écriture individuelle. Les groupes sont conservés, avec le nombre de communes
qu'ils touchent.

## Ce que ça donne, au 10 septembre 2026

Sur les 1 002 doléances du découpage servi, seuil 0,8 :

| | |
|---|---|
| groupes | 13 |
| doléances groupées | 33 (**3 %**) |
| textes distincts si un groupe compte pour un | 982 |

Sensibilité au seuil, sans rupture nette :

| Seuil | Groupes | Doléances groupées |
|---|---|---|
| 0,9 | 4 | 12 (1 %) |
| 0,8 | 13 | 33 (**3 %**) |
| 0,7 | 23 | 56 (6 %) |
| 0,6 | 28 | 79 (8 %) |
| 0,5 | 33 | 98 (10 %) |

## Ce que la déduplication a trouvé sans qu'on le cherche

Le plus gros groupe — 6 doléances, 6 communes, 2 217 mots — n'est pas une
contribution citoyenne. C'est la **lettre du Président de la République** qui
ouvre les registres du Grand Débat, imprimée par les organisateurs.

Onze doléances au total portent ce texte, soit environ 21 000 mots — 2,8 % du
corpus en volume. L'extraction saute les deux premières pages de chaque cahier,
ce qui l'élimine le plus souvent ; ces onze-là sont passées.

C'est la seconde utilité de la déduplication, à côté du repérage des campagnes :
elle fait remonter le texte des organisateurs mêlé à celui des citoyens. Un
thème « fiscalité » détecté dans la lettre présidentielle n'est pas une doléance.

Deuxième plus gros groupe : 5 doléances dans 5 communes, 406 mots, similarité
minimale 0,82 — celui-là ressemble à ce que la déduplication est censée trouver,
un texte qui a circulé.

## Comment

MinHash et LSH, sans dépendance nouvelle.

Comparer chaque doléance à toutes les autres serait quadratique. MinHash réduit
chaque texte à une signature de taille fixe dont la proportion de valeurs
communes estime la similarité de Jaccard ; le LSH ne présente à la comparaison
que les paires qui ont une chance d'être proches. **Les candidates sont ensuite
vérifiées exactement** sur les ensembles de fragments réels — l'estimation sert
à ne pas regarder les 500 000 autres paires.

Les groupes sont les composantes connexes du graphe des paires retenues : si A
ressemble à B et B à C, les trois sont ensemble même si A et C ont divergé.
C'est voulu pour des lettres-types qui dérivent, et `similarity_min` dit à quel
point un groupe ne tient qu'à un fil.

### Le seuil a un plancher

Le filtre LSH est réglé pour la similarité haute. La probabilité qu'une paire de
similarité `s` soit proposée vaut `1-(1-s⁴)³²` :

| s | 0,3 | 0,4 | 0,5 | 0,6 | 0,7 |
|---|---|---|---|---|---|
| proposée | 23 % | 56 % | 87 % | 99 % | 100 % |

Sous 0,5, **abaisser le seuil rendrait moins de doublons**, silencieusement. La
commande refuse donc de descendre sous `SEUIL_PLANCHER`. Pour chercher plus bas,
il faut élargir les bandes, pas baisser le seuil.

## Utilisation

```bash
uv run python -m doublons --auteur "prénom nom"
uv run python -m doublons --seuil 0.7 --auteur "prénom nom"
```

Chaque exécution crée un run de genre `doublons` : le regroupement dépend d'un
seuil, deux seuils sont deux lectures du corpus, elles doivent pouvoir coexister
(voir [database/README.md](../database/README.md)).

## Organisation

| Fichier | Rôle |
|---|---|
| `empreintes.py` | normalisation, fragments, MinHash, LSH |
| `groupes.py` | paires vérifiées, composantes connexes, seuil et plancher |
| `persistance.py` | lecture des doléances, écriture des groupes |
| `__main__.py` | la commande |

Le hachage passe par un seul Blake2b par fragment, permuté ensuite par
`a·h + b mod p` : hacher 128 fois chaque fragment coûtait 96 millions de
hachages sur ce corpus contre 750 000, soit 2 min 30 au lieu de 14 s. Les
coefficients viennent d'une graine fixe — deux exécutions doivent donner les
mêmes groupes.

## Tester

```bash
uv run --extra dev pytest doublons
```
