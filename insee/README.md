# INSEE : rattacher les contributions à leur commune

`contribution.city` est une graphie parsée de l'en-tête du PDF. C'est ce qui a
obligé l'app à regrouper les orthographes après coup — « AHUILLE » et
« AHUILLÉ », « FONTENAY SUR CONIE » et « FONTENAY-SUR-CONIE ». Le code INSEE est
la clé qui manquait : stable, officielle, et elle porte le département.

## Ce que ça change, chiffré

Sur les 516 cahiers de `data/raw/pdfs` :

| | Par graphie | Par code INSEE |
|---|---|---|
| communes identifiées | 310 (307 après regroupement) | **459** |
| cahiers sans commune | 182 (35 %) | 2 |
| communes sans aucune page lisible | 24 | **37** |

**Un tiers du corpus n'avait aucune commune** avec le parsing d'en-tête, et 180
de ces 182 cahiers portaient pourtant leur code INSEE dans leur nom de fichier.
Ces communes ne manquaient pas seulement à l'affichage : elles n'étaient comptées
ni au numérateur ni au dénominateur des mesures de couverture. Les 24 communes
muettes annoncées le 10 septembre étaient en réalité 37.

Les deux seuls cahiers sans code n'ont pas de commune **à la source** : leur code
est `00000` dans le nom de fichier, et leur en-tête est vide ou illisible. On ne
leur en invente pas.

## Deux sources, qui se contrôlent

Le code est présent deux fois, ce qui est une chance :

- dans le **nom du fichier** — `CC_<code postal>_<AAMMJJ>_<INSEE>_MD_<id>.pdf` ;
- dans l'**en-tête du PDF** — `BOURG-EN-BRESSE - 01053`, où le parsing existant
  le voyait déjà et le jetait (`CITY_PATTERN` capture le nom et ignore le groupe
  de cinq chiffres qui suit).

`python -m insee auditer` les croise. Sur le corpus :

```
 339 (66%) — code confirmé par le nom de fichier ET l'en-tête
 174 (34%) — code lu dans le nom de fichier seul (en-tête illisible)
   1 ( 0%) — les deux sources se contredisent
   2 ( 0%) — aucun code (commune non renseignée à la source)
```

L'unique désaccord vaut d'être raconté : l'en-tête portait `GHANA Y - 01420` —
Chanay, mal océrisé, suivi de son **code postal** et non de son code INSEE. Le
nom de fichier disait 01082, le vrai code de Chanay. La règle « le fichier
l'emporte » donne la bonne réponse, et le signalement a désigné exactement le
cahier à regarder. C'est pour cela que le rattachement se fait sur le nom de
fichier : il vient du système qui a déposé le cahier, l'en-tête est un champ
rempli à la main puis passé dans une extraction de texte.

## Le référentiel : millésime 2019, et pas un autre

`population`, `latitude` et `longitude` sont désormais renseignées depuis des
extraits versionnés dans [`referentiel/`](referentiel/SOURCES.md). Le millésime
pivot est **2019** — celui du dépôt des cahiers, février-avril 2019 — et c'est
la seule décision de ce module qui ne soit pas évidente.

Un code INSEE est une clé **datée** : il désigne une commune à un millésime
donné. Prendre le millésime courant paraît naturel et c'est le piège. Une
commune absorbée depuis dans une commune nouvelle n'a plus de ligne : sa
population deviendrait NULL sans bruit, ou pire, celle de la commune fusionnée —
et la pondération serait fausse sans qu'aucun test ne le voie. `city.code` reste
donc celui de 2019 ; `current_code` porte le code actuel comme une **annotation**,
pas comme une correction. C'est le même principe que partout ailleurs ici : la
provenance est le squelette, le reste s'y rattache sans le modifier.

Trois cas du corpus le justifient, et aucun n'a été cherché :

| Code | Commune | Ce qui s'est passé |
|---|---|---|
| `01144` | Dommartin | absorbée par Bâgé-Dommartin le **1ᵉʳ janvier 2018**, un an *avant* les cahiers |
| `01205` | Lancrans | absorbée par Valserhône le **1ᵉʳ janvier 2019**, six semaines avant |
| `01039` | Béon | commune de plein exercice en 2019, absorbée par Culoz-Béon en 2023 |

Les deux premiers cahiers ont été déposés sous un code qui ne désignait déjà
plus une commune de plein exercice : le système de dépôt travaillait sur un
référentiel périmé. Ils restent rattachés à ce code — c'est le fait de
provenance — avec `cog_type = COMD` et leur commune parente. Un quatrième cas,
`28012`, a gardé son code et changé de nom : « Commune nouvelle d'Arrou » est
devenue « Vald'Yerre » en 2023.

**Le double compte.** La population d'une commune déléguée est comprise dans
celle de sa parente. Valserhône *et* Lancrans sont toutes deux dans le corpus :
sommer les deux compterait deux fois 1 054 habitants. `population_totale` refuse
de le faire et la commande le signale, plutôt que de laisser une note dans un
coin de documentation.

## Ce que la pondération change

Compter les communes met une commune de 90 habitants au même rang qu'une de
16 000. La part en habitants dit tout autre chose :

| Département | Communes | Habitants |
|---|---|---|
| 01 Ain | 210/393 — 53 % | 465 512/643 350 — **72 %** |
| 28 Eure-et-Loir | 132/365 — 36 % | 294 027/433 233 — **68 %** |
| 53 Mayenne | 116/242 — 48 % | 176 837/307 445 — **58 %** |
| 39 Jura | 1/494 — 0 % | 646/260 188 — 0 % |

L'écart systématique entre les deux colonnes dit où penche le manque : **les
communes absentes du corpus sont les petites**. Le même calcul appliqué aux 37
communes sans aucune page lisible donne le contrepoint — elles ne pèsent que
36 697 habitants sur 937 022, soit **4 %** là où elles sont 8 % des communes.

Rien de tout cela ne dit que le corpus est représentatif. Il dit quelle part de
la population a un cahier quelque part, ce qui est une autre question, et la
seule à laquelle ces chiffres répondent.

## Licences

Les trois sources sont sous **Licence Ouverte 2.0**, vérifié aux sources et
consigné dans [`referentiel/SOURCES.md`](referentiel/SOURCES.md) — y compris le
point qui n'était pas acquis, les coordonnées : elles viennent d'ADMIN EXPRESS
(IGN) et non d'OpenStreetMap, dont la licence ODbL aurait imposé un partage à
l'identique. Toute publication du corpus devra porter « Source : Insee » et
« Source : IGN », avec les millésimes.

## Ce qui reste NULL

`city.name` est la graphie la plus riche rencontrée dans le corpus, pas le nom
officiel — `official_name` est là pour celui-ci, et les deux cohabitent parce
qu'ils ne disent pas la même chose. Trois communes du corpus n'ont pas de
coordonnées : elles ont disparu depuis 2019 et la source géométrique est au
millésime courant. On ne leur prête pas le centre de la commune qui les a
absorbées.

## Utilisation

```bash
uv run alembic upgrade head        # crée la table city et ses colonnes COG
uv run python -m insee rattacher   # remplit city et contribution.city_code
uv run python -m insee cog         # nom officiel, population, coordonnées
uv run python -m insee auditer     # croise les deux sources (rouvre les PDF)
```

`cog` ne sort **pas** sur le réseau : il lit les extraits versionnés. Les
reconstruire est une opération distincte, et délibérée, parce qu'elle réécrit
des fichiers du dépôt :

```bash
uv run python -m insee referentiel --departements 01 28 39 53
```

`rattacher` est idempotent et ne lit que la base : il ne dépend pas de la
présence des PDF d'origine. `auditer` en a besoin, d'où la séparation — le
rattachement ne doit pas devenir impossible parce que les fichiers sont ailleurs.

Le remplissage n'est **pas** dans la migration : une migration est une archive,
elle fige un schéma, pas une expression régulière et une politique de
rapprochement qui, elles, évolueront.

## Organisation

| Fichier | Rôle |
|---|---|
| `codes.py` | lecture du code dans chaque source, département, rapprochement |
| `rattachement.py` | remplissage de `city` et des clés étrangères |
| `cog.py` | lecture des extraits, enrichissement de `city`, pondération |
| `telecharger.py` | reconstruction des extraits depuis l'INSEE — seul accès réseau |
| `referentiel/` | les extraits versionnés et [leur provenance](referentiel/SOURCES.md) |
| `__main__.py` | les quatre commandes |

## Tester

```bash
uv run --extra dev pytest insee
```

Le fixture SQLite de `test_rattachement.py` active `PRAGMA foreign_keys=ON`.
Elles sont désactivées par défaut, et sans elles un test ne voit pas qu'une
contribution est écrite avant la commune qu'elle désigne — ce que PostgreSQL
refuse. C'est exactement le bug qu'a eu ce module.
