# Jeu de référence : l'étalon annoté à la main

Sans étalon, on ne peut pas dire qu'un découpage vaut mieux qu'un autre — on
peut seulement constater qu'il coupe plus ou moins. Les runs permettent
désormais de faire coexister deux couches ; ce module fournit ce à quoi on les
compare.

## Ce que l'étalon annote

Où commence chaque doléance. L'annotateur lit les lignes d'un cahier et marque
celles qui ouvrent une nouvelle contribution. Rien d'autre pour l'instant : les
thèmes viendront sur les mêmes cahiers, une fois le découpage stabilisé.

## Deux fichiers, et pourquoi

| Fichier | Contenu | Git |
|---|---|---|
| `data/reference/<nom>.csv` | le texte des cahiers, ligne à ligne, à annoter | **ignoré** |
| `reference/etalon/<nom>.csv` | les mêmes lignes, texte remplacé par une empreinte | commité |
| `reference/etalon/<nom>.json` | graine, strates et poids du tirage | commité |

Le fichier de travail porte des écrits nominatifs de personnes privées : il n'a
rien à faire dans un dépôt public, et `/data` est ignoré pour cette raison. Mais
l'étalon doit être versionné — c'est la référence contre laquelle tout est
mesuré, elle doit voyager avec le code. D'où la séparation : `figer` remplace
chaque ligne par une empreinte SHA-256 tronquée, insensible à l'espacement. On
ne peut pas en relire le texte ; on peut vérifier qu'il n'a pas changé.

Cette vérification n'est pas décorative. Si l'extraction évolue et que les lignes
se décalent, un étalon désaligné produirait des scores parfaitement crédibles et
parfaitement faux. `evaluer` refuse de mesurer dans ce cas plutôt que de mentir.

## Le tirage est stratifié

Un tirage uniforme donnerait presque exclusivement des cahiers d'une seule
doléance — 89 % des pages n'en portent qu'une d'après le découpage actuel — et
l'étalon ne dirait rien des cas qui comptent : ceux où plusieurs contributeurs se
succèdent. On stratifie donc sur le nombre de doléances trouvées, avec un
plancher par strate.

La contrepartie, c'est que l'échantillon n'est plus représentatif : le **poids**
de chaque strate est conservé dans le sidecar JSON, et `evaluer` affiche les deux
chiffres — celui de la population (pondéré, ce que vaut le découpage sur le
corpus) et celui de l'échantillon (non pondéré, ce qu'il vaut sur les cas
difficiles). Ne jamais publier le second pour le premier.

La strate vient du découpage servi : c'est un instrument de tirage, pas une
vérité. L'étalon, lui, ne dépend d'aucun run.

## Les deux mesures

**Précision / rappel / F1 sur les frontières** — exact. Une frontière posée une
ligne trop loin compte comme un faux positif *et* un faux négatif. Sévère, mais
c'est ce qui dit si les règles repèrent les bons signaux.

**WindowDiff** — tolérant. Une fenêtre glisse sur le texte et compte les endroits
où le nombre de frontières diffère ; une frontière décalée d'une ligne est à
peine pénalisée. C'est ce qui dit si le corpus est découpé au bon endroit *à peu
près*, ce qui suffit à la plupart des usages en aval. **Plus bas est meilleur**,
0 = parfait.

Les deux sont utiles parce qu'elles se contredisent utilement : des règles qui
trouvent les bonnes zones mais calent mal les frontières auront un F1 médiocre et
un WindowDiff correct. C'est une information, pas une contradiction.

La première ligne d'un cahier ouvre forcément une doléance : elle est exclue du
calcul, la prédire est gratuit et gonflerait tous les scores.

## Utilisation

```bash
# 1. tirer l'échantillon (a besoin d'un découpage servi pour stratifier)
uv run python -m reference --nom v1 tirer --taille 60

# 2. annoter data/reference/v1.csv : 1 dans `debut_doleance` sur la première
#    ligne de chaque doléance. Un tableur suffit ; 1, x, oui et vrai sont acceptés.

# 3. figer l'étalon (retire le texte, garde les empreintes)
uv run python -m reference --nom v1 figer

# 4. mesurer le découpage servi
uv run python -m reference --nom v1 evaluer
```

Le tirage est reproductible : même graine, même échantillon. La graine est
consignée dans le sidecar.

Le fichier de travail est pré-rempli avec un `1` sur la première ligne de chaque
cahier, et **rien d'autre** : pré-remplir avec la prédiction du découpage
biaiserait l'étalon vers ce qu'on cherche justement à évaluer.

## Organisation

| Fichier | Rôle |
|---|---|
| `echantillon.py` | strates, tirage reproductible, poids |
| `etalon.py` | fichier de travail, passage aux empreintes, garde-fou d'alignement |
| `evaluation.py` | frontières, précision/rappel/F1, WindowDiff, agrégation pondérée |
| `__main__.py` | les trois commandes |
| `etalon/` | les étalons figés, commités |

## Tester

```bash
uv run --extra dev pytest reference
```
