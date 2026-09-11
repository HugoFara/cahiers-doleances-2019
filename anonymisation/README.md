# Anonymisation : repérer, pas déclarer anonyme

> **Ce module ne rend rien publiable.** Il repère des formes et, avec `--ner`,
> des noms cités au fil du texte. Son rappel n'est pas mesuré, et rien n'est
> occulté sur les images. Aucune de ses sorties ne permet de dire qu'une
> doléance peut être mise en ligne.

## Des offsets, jamais une copie caviardée

`pii_span` ne contient que des positions de caractères. Le texte d'origine reste
intact et fait foi ; le caviardage est **produit à la lecture**. C'est ce qui
permet de corriger une détection, d'en ajouter une, ou de changer la politique de
caviardage sans avoir abîmé la source.

`confirmed` est la file de relecture : NULL tant qu'un humain n'a pas tranché,
vrai pour une donnée personnelle réelle, faux pour un faux positif. Un passage
**non relu est caviardé** — tant que le doute existe, il profite à la personne.

## Ce qui est repéré, au 10 septembre 2026

Sur les 1 002 doléances du découpage servi : **4 164 passages dans 884 doléances,
soit 88 % d'entre elles.**

| Genre | Passages | Caviardé |
|---|---|---|
| `role_public` | 1 460 | non |
| `nom` | 1 309 | oui |
| `telephone` | 417 | oui |
| `email` | 320 | oui |
| `adresse` | 255 | oui |
| `institution` | 217 | non |
| `url` | 186 | oui |

Ces nombres sont **à la fois un plancher et une surestimation**, et il faut tenir
les deux :

- **plancher**, parce qu'un nom cité au fil du texte — « j'ai parlé à Bernard,
  du service technique » — n'est pas vu. C'est le cas le plus fréquent, et il
  demande une reconnaissance d'entités nommées ;
- **surestimation**, parce qu'une part des courriels et téléphones repérés sont
  ceux des mairies et du dispositif lui-même. `institution` en isole 217, mais la
  règle ne peut pas tout : `accueil@ma-commune.fr` est l'adresse d'une mairie et rien
  dans sa forme ne la distingue d'une adresse privée.

## Ce que l'inspection du corpus a montré

**L'OCR défait la règle institutionnelle.** On trouve `reunionslocales@qranddebat.fr`
(un `q` pour un `g`) et `niairie.ma-commune@wanadoo.fr` (`ni` pour `m`). La forme
« adresse électronique » est toujours reconnue — donc le passage est repéré et
caviardé — mais le classement institutionnel tombe. C'est le bon sens de
l'erreur : la donnée est protégée, elle est seulement sur-protégée.

**Les téléphones sont surtout ceux des mairies.** `04.99.00.12.34` est le standard
d'une mairie. Rien dans la forme d'un numéro français ne distingue une ligne de
mairie d'une ligne privée, et le module n'essaie pas de deviner.

**La règle de signature produit des faux positifs**, par construction :
« Hôtel de la Préfecture » et « Liste non exhaustive » ont été pris pour des
noms. Un faux positif coûte un mot illisible, un nom manqué est une fuite.

## Les règles

| Genre | Repéré par |
|---|---|
| `email` | forme d'adresse électronique |
| `institution` | adresse portant `mairie`, `prefecture`, `granddebat`, `.gouv.fr`… |
| `telephone` | numéro français, tous séparateurs (`06 12`, `06.12`, `+33 6`) |
| `iban` | IBAN français |
| `url` | `http(s)://` ou `www.` |
| `adresse` | numéro + type de voie, borné aux mots qui ouvrent une proposition |
| `nom` | civilité (`M.`, `Mme`, `Monsieur`) suivie de mots capitalisés |
| `nom` | ligne courte en fin de doléance, sans ponctuation de phrase |
| `role_public` | **fonctions**, pas noms : Président de la République, ministre, préfet, maire, député |

`role_public` liste des **rôles** et non des personnes : la liste ne vieillit pas
avec les titulaires. Un ministre cité dans sa fonction n'a pas à être occulté —
l'occulter viderait les textes de leur objet. Le maire nommément **accusé**
relève de la relecture humaine : la règle ne sait pas faire la différence.

## Les entités nommées, depuis le 11 septembre 2026

`--ner` ajoute un modèle de reconnaissance d'entités nommées, **en local et sur
CPU** : la décision d'hébergement prise pour les scans (journal du 2026-09-11)
vaut pour les données personnelles. Le modèle est `Jean-Baptiste/camembert-ner`
(CamemBERT affiné sur WikiNER) ; ses étiquettes deviennent des genres de
`pii_span` : personne -> `nom` (caviardé), lieu -> `lieu` et organisation ->
`institution` (non caviardés). Le détecteur de chaque passage dit d'où il vient
(`ner:<modèle>`), pour auditer séparément.

**Pourquoi ce modèle.** Comparé sur 25 doléances tirées au sort (139 000
caractères) aux modèles de désidentification multilingues conseillés pendant le
POC (collection OpenMed, entraînés sur des données synthétiques de
formulaires) : le plus gros (434M) mettait 119 s contre 13 s, rendait 319
« adresses Litecoin » et 172 « mots de passe » sur des cahiers de doléances, et
coupait les noms en sous-mots ; CamemBERT-NER rendait 84 personnes en spans
entiers là où la passe de formes en marquait 29. Le seuil est bas exprès,
0,4 pour les personnes (0,6 pour les lieux et organisations, qui ne sont pas
caviardés) : un faux positif coûte un mot illisible, un nom manqué est une
fuite.

**Mesuré le 11 septembre 2026**, sur les mêmes 1 002 doléances : **19 306
passages dans 968 doléances (97 %)**, contre 4 164 dans 884 pour les formes
seules. 8 min 40 s sur CPU.

| Genre | Formes seules | Avec le modèle | Caviardé |
|---|---|---|---|
| `lieu` | — | 9 260 | non |
| `institution` | 217 | 3 827 | non |
| `nom` | 1 309 | **3 582** | oui |
| `role_public` | 1 460 | 1 459 | non |
| `telephone` | 417 | 417 | oui |
| `email` | 320 | 320 | oui |
| `adresse` | 255 | 255 | oui |
| `url` | 186 | 186 | oui |

Le modèle ajoute 2 328 noms que les formes ne voyaient pas, et **196 doléances
où aucun nom n'était repéré en ont désormais au moins un**. Les formes ne
perdent rien : la première passe combinée perdait 214 adresses sur 255,
« rue des Lilas » étant un lieu pour le modèle ; depuis, un lieu ou une
organisation du modèle qui chevauche une forme est écarté (`passe.combiner`).
La moyenne des noms du modèle fait 12 caractères, 71 sur 2 328 font moins de
trois : des débris d'OCR, qui coûtent un mot illisible chacun.

Ce que la NER ne règle pas : le **rappel** reste inconnu tant que l'échantillon
annoté n'existe pas ; les personnalités publiques citées par leur nom sont
caviardées comme les autres (« Macron » est une personne pour le modèle),
c'est la relecture qui les rend, ou une règle à consigner ; et l'OCR abîme les
noms comme le reste.

## Ce qui manque, et qui n'est pas dans ce module

1. **La mesure du rappel**, qui demande un échantillon annoté à la main — le même
   travail humain que pour [`reference/`](../reference/README.md).
2. **L'occultation sur l'image.** Sans coordonnées de ligne, le scan reste en
   clair même quand la transcription est caviardée. C'est le [préalable du
   plan](../docs/plan_post_ocr.md) : demander à l'OCR le texte ligne par ligne
   avec sa géométrie.
3. **La réidentification contextuelle.** « Je suis la seule infirmière du
   village » identifie sans aucun nom. Aucune règle de forme n'y accède, et un
   lieu cité n'est pas caviardé.

## Utilisation

```bash
uv run alembic upgrade head
uv run python -m anonymisation --auteur "prénom nom"
uv sync --extra ner && uv run python -m anonymisation --ner    # + entités nommées
```

L'extra `ner` installe torch (roues CPU, depuis l'index PyTorch) et
transformers ; le modèle se télécharge au premier appel. Sur le corpus, la
passe avec NER prend une vingtaine de minutes sur CPU et commite toutes les
100 doléances.

Chaque exécution crée un run de genre `anonymisation` : changer de détecteurs
crée une lecture de plus, et n'écrase pas les relectures humaines de la
précédente.

## Organisation

| Fichier | Rôle |
|---|---|
| `detecteurs.py` | les règles, texte -> passages ; sans base de données |
| `ner.py` | le modèle d'entités nommées, texte -> passages ; découpage en morceaux à offsets exacts |
| `passe.py` | lecture des doléances, écriture des offsets |
| `rendu.py` | caviardage à la lecture, et la politique qui décide |
| `__main__.py` | la commande et son avertissement |

## Tester

```bash
uv run --extra dev pytest anonymisation
```
