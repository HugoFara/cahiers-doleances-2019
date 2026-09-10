# Recherche : atteindre le corpus autrement que commune par commune

Le corpus ne s'atteignait que par sa liste de communes. C'est ce qu'il faut pour
annoter, et c'est inutilisable pour toute autre question : « tout ce qui parle
d'éoliennes » n'avait pas de réponse.

```bash
uv run python -m recherche éoliennes
uv run python -m recherche "pouvoir d'achat" --limite 5
uv run python -m recherche 'impôt -taxe'
```

Les mots s'ajoutent, les guillemets font une expression exacte, `or` alterne, un
tiret exclut — la syntaxe de `websearch_to_tsquery`, celle que les gens
connaissent des moteurs de recherche. Elle ne lève jamais d'erreur : un opérateur
mal placé devient un mot.

## Le chiffre qui décide de la configuration

PostgreSQL propose une configuration `french`. On ne l'utilise pas telle quelle :
la recherche passe par `francais_sans_accent`, une copie de `french` dont la
correspondance des mots passe d'abord par `unaccent`. Voici pourquoi, mesuré sur
les 1 002 doléances, en tapant les termes **sans accent** — c'est-à-dire comme on
tape dans un champ de recherche :

| Terme tapé | `french` | `francais_sans_accent` |
|---|---|---|
| eolienne | 6 | **46** |
| ecole | 18 | **138** |
| impot | 22 | **309** |
| depute | 14 | **260** |
| referendum | 31 | **175** |
| securite | 16 | **180** |
| sante | 181 | 181 |

Chercher « impot » sans accent trouvait 22 doléances sur les 309 qui en parlent.

La ligne `sante` explique le mécanisme : le radicaliseur français **supprime déjà
la voyelle accentuée finale**, si bien que « santé » et « sante » se rejoignent
sans rien faire. Ce sont les accents **à l'intérieur** du mot — impôt, école,
député, référendum — qu'il conserve, et qui séparaient donc deux orthographes du
même mot.

S'y ajoute l'OCR, qui abîme les accents pour son propre compte : le corpus
contient `qüe`, `qùè`, `qüé` et `qùe` pour « que ».

**Effet de bord assumé** : la configuration confond « retraite » et « retraité ».
Le radicaliseur les confondait déjà — même racine `retrait` — la configuration
n'ajoute que les variantes abîmées.

## Un index d'expression, pas une colonne

`ix_doleance_recherche` est un index GIN sur `to_tsvector(…, text)`, pas une
colonne `tsvector` générée. Une colonne aurait dû figurer au modèle, et le modèle
est monté sur SQLite par les tests — lequel ne connaît ni `tsvector` ni
`to_tsvector`. L'index d'expression donne la même performance sans rien ajouter
au modèle : c'est un objet de base, pas une donnée.

Il a un coût : **alembic ne sait pas comparer les index d'expression**. Il voit
toujours un `drop` suivi d'un `add`, même sur une base à jour, ce qui ferait
échouer `alembic check` à chaque exécution. L'index est donc nommé dans
`INDEX_HORS_COMPARAISON`, dans `database/migrations/env.py`.

Mesuré sur 1 002 doléances : moins d'une milliseconde pour une requête de mots,
environ 250 ms pour une expression exacte entre guillemets — la recherche de
phrase vérifie les positions sur les lignes, pas dans l'index.

## Ce que la recherche montre, et ce qu'elle occulte

**Les extraits sont caviardés.** La recherche est le premier endroit où le corpus
se lit en vrac, hors du cahier qui lui donnait son contexte : un extrait rendu à
qui interroge n'est pas la même chose qu'un texte lu par un bénévole qui annote
une commune. Les passages repérés par `anonymisation/` y sont occultés, et un
passage non relu l'est aussi.

L'ordre compte, et il est l'inverse de l'intuition : on **caviarde le texte
entier, puis on y découpe la fenêtre**. Les passages sont des offsets dans le
texte d'origine ; les appliquer après avoir coupé les décalerait. Conséquence
assumée : un terme qui ne se trouvait que dans un passage occulté disparaît de
l'extrait, et le résultat s'ouvre alors sur le début du texte.

`--brut` désactive le caviardage, pour un usage interne. La commande le signale à
chaque fois.

## Les doublons sont signalés, pas masqués

Cherchez les mots de la lettre présidentielle qui ouvre les registres :

```
[0.0200] Unverre · doléance 510              ↻ même texte dans 6 communes
[0.0200] Mayenne · doléance 794              ↻ même texte dans 6 communes
[0.0200] Saint-Ouën-des-Toits · doléance 941 ↻ même texte dans 6 communes
```

Les premiers résultats sont la lettre du Président de la République, pas des
contributions citoyennes. Sans le marqueur, une recherche les présenterait comme
les textes les plus pertinents du corpus. Le groupe vient de `doublons/` ; s'il
n'a pas tourné, le champ vaut `None` — ce qui veut dire « on ne sait pas », et
non « texte unique ».

## Trois limites à connaître

- **La recherche ne voit que la moitié dactylographiée du corpus.** 47 % des
  pages sont écartées avant tout découpage ; ce qui n'a pas été océrisé n'est
  pas cherchable.
- **L'OCR défait la recherche exacte.** Le corpus contient `mairie^ferney-voltaire.fr`,
  `qüe`, `giiecs jaunes` pour « gilets jaunes ». Un mot mal océrisé n'est trouvé
  par aucune requête ; c'est un plancher, pas un défaut de la recherche.
- **Un seul découpage servi**, celui du run actif, comme les vues de thèmes ne
  servent qu'une grille. Sans ce filtre, deux découpages concurrents rendraient
  chaque doléance deux fois.

Il n'y a pas de **recherche vectorielle** : `pgvector` n'est pas installé sur la
base. Le plan la prévoit à côté de celle-ci, pas à sa place — les deux répondent
à des questions différentes.

## Organisation

| Fichier | Rôle |
|---|---|
| `config.py` | configuration SQL, limites, largeur d'extrait |
| `extraits.py` | fabrication de l'extrait — sans base, donc testé |
| `requetes.py` | la requête, le caviardage, le marquage des doublons |
| `__main__.py` | la commande |

## Tester

```bash
uv run --extra dev pytest recherche
```
