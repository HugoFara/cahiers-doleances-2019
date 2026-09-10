# Taxonomie : ce que vaut une grille de thèmes

Le reproche fait à la grille livrée — 6 788 thèmes pour 1 380 documents — n'est
pas qu'elle soit grosse. C'est qu'on ne savait pas si elle était bonne. Les 32
passes successives de `factorize` et `structure` du
[RECIPE](../topic-builder/data/cahiers_chabin/RECIPE.md) traitent un symptôme à
la main, sans instrument pour dire si la passe suivante améliore quoi que ce
soit.

Aucune mesure ici ne dit « la grille est bonne ». Elles disent ce qu'elle fait,
ce qui permet de comparer deux grilles et de savoir dans quel sens on va.

## Ce que dit la grille livrée (`analyse_poc_2026-08-11`)

### Réutilisation

| | |
|---|---|
| thèmes | 6 788, dont **2 343 (35 %) sans aucune détection** |
| documents | 1 380 · 6,9 thèmes chacun |
| thèmes attestés **une seule fois** | 3 392 — **76 % des thèmes attestés** |

Trois thèmes sur quatre ne servent qu'une fois. **Un thème attesté par un seul
document est la paraphrase de ce document, pas un thème** : la grille ne
généralise pas, elle réécrit le corpus. C'est cela que mesuraient mal les 32
passes de factorisation.

Et un tiers de la grille n'est jamais employé. Le détail par niveau montre où :

| Niveau | Thèmes | Sans détection |
|---|---|---|
| 0 (feuilles) | 4 543 | 108 (**2 %**) |
| 1 à 7 (parents) | 2 245 | 2 235 (**99,6 %**) |

Le labelling n'attache que des feuilles. Les 2 245 thèmes parents produits par
`structure` n'existent que pour la navigation — ce qui est légitime, l'app
remonte bien les détections des enfants, mais il faut le savoir avant de compter
quoi que ce soit sur un parent.

### Hiérarchie

| | |
|---|---|
| racines | 371 |
| thèmes hors de tout arbre (ni parent ni enfant) | 185 |
| thèmes dans un cycle | 0 |
| profondeur maximale | 7 |
| enfants d'un même parent, au plus | 51 |
| noms portés par plusieurs thèmes | 0 |

371 racines pour une taxonomie, c'est beaucoup : l'arbre est un buisson. Aucun
cycle en revanche — la protection de la vue graphe de l'app est prudente, pas
nécessaire sur cette livraison. Et aucun nom dupliqué, ce qui compte : le nom est
la clé de jointure au chargement.

### Couverture (« hors grille »)

**Non mesurable sur cette livraison** : aucune de ses instances n'est rattachée à
un document de notre corpus, ses identifiants désignant un autre corpus (c'est ce
que détecte le garde-fou de `load_analysis`). La mesure fonctionne dès qu'une
livraison est produite par `export_dataset.py` — vérifié sur une livraison
fabriquée à partir du seed : 9 % du texte couvert, 91 % hors grille.

C'est le chiffre qui manque à tout comptage. Sans lui, « 34 % des contributions
parlent de fiscalité » ne dit pas sur quelle part du corpus il porte.

## Les mesures

**Réutilisation.** Documents par thème et thèmes par document. Deux détections du
même thème dans un même document ne comptent qu'une fois : sinon un thème cité
trois fois dans un texte passerait pour réutilisé.

**Hiérarchie.** Racines, isolés, cycles, profondeur, largeur, noms dupliqués. Un
thème dont le `parent_id` pointe hors du run est une racine de fait.

**Couverture.** Part des caractères d'un document réellement citée par ses
verbatims. Les extraits chevauchants sont fusionnés — sinon la couverture
dépasserait 100 %. Un verbatim **introuvable** dans son document n'est pas compté
comme couvrant : c'est une reformulation du modèle, pas une citation, et leur
proportion dit à quel point la grille cite ou paraphrase.

La comparaison de textes y est plus permissive que dans `load_analysis` : les
accents sautent aussi. Les deux fonctions ne servent pas à la même chose — là-bas
il s'agit de décider si toute une livraison parle bien de notre corpus, et la
sévérité protège ; ici un extrait qui ne diffère que par un accent est une
citation, le compter introuvable gonflerait le taux de paraphrase.

## Utilisation

```bash
uv run python -m taxonomie            # la grille servie
uv run python -m taxonomie --run 4    # une grille précise
```

Plusieurs grilles peuvent coexister (voir
[database/README.md](../database/README.md)) : c'est ce qui rend la comparaison
possible, et c'est à cela que ces mesures servent.

## Organisation

| Fichier | Rôle |
|---|---|
| `mesures.py` | réutilisation, hiérarchie, couverture — sans base de données |
| `__main__.py` | lecture de la grille servie et rapport |

## Tester

```bash
uv run --extra dev pytest taxonomie
```
