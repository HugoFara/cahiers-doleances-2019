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

## Ce qui reste NULL, et pourquoi

`city.name` est la graphie la plus riche rencontrée dans le corpus, pas le nom
officiel. `population`, `latitude` et `longitude` sont vides : elles demandent le
**Code officiel géographique** de l'INSEE, qui n'est pas dans ce dépôt. Sans
elles, pas de pondération par population — donc pas de mesure de
représentativité au sens statistique — et pas de carte. C'est la prochaine
dépendance externe à régler.

## Utilisation

```bash
uv run alembic upgrade head        # crée la table city
uv run python -m insee rattacher   # remplit city et contribution.city_code
uv run python -m insee auditer     # croise les deux sources (rouvre les PDF)
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
| `__main__.py` | les deux commandes |

## Tester

```bash
uv run --extra dev pytest insee
```

Le fixture SQLite de `test_rattachement.py` active `PRAGMA foreign_keys=ON`.
Elles sont désactivées par défaut, et sans elles un test ne voit pas qu'une
contribution est écrite avant la commune qu'elle désigne — ce que PostgreSQL
refuse. C'est exactement le bug qu'a eu ce module.
