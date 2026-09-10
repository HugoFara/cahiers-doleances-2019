# Typologie : ce qu'est une doléance avant ce qu'elle dit

> **Ces étiquettes sont des règles de forme.** Elles lisent des formules d'appel,
> des signatures et des marques de première personne. Elles ne voient ni la mise
> en page, ni l'écriture, ni le papier — c'est-à-dire aucun des indices sur
> lesquels un archiviste tranche réellement. Ni leur précision ni leur rappel ne
> sont mesurés : `confirmed` est NULL partout et attend une relecture humaine.

C'est la **couche 2** du [plan](../docs/plan_post_ocr.md) : les métadonnées qui
conditionnent l'interprétation de tout comptage. « 34 % des contributions
demandent X » ne veut rien dire si les 34 % mêlent un mot d'habitant, une motion
de conseil municipal, un tract recopié dans onze communes et le courrier par
lequel la mairie transmet le cahier.

## Deux axes, pas une étiquette

`typologie` porte **une ligne par axe** (`axis` = `support` ou `auteur`) plutôt
qu'une colonne par axe. Les deux questions sont indépendantes — une pétition peut
être portée par une association ou par des habitants sans organisation, un
courrier peut venir d'un particulier comme d'un maire — et un axe de plus (type
de revendication, ton) s'ajoutera sans migration de colonne.

Table à part et non colonnes sur `doleance`, pour la même raison que `pii_span`
et `duplicate_member` : c'est une **lecture** du corpus, produite par des règles
faillibles, versionnée par un run, et qui se retire sans toucher au squelette.

**`indetermine` est une valeur, pas une absence.** Elle est écrite en base comme
les autres : « on a regardé et rien ne tranche » et « on n'a pas regardé » sont
deux états différents, et le premier est le plus fréquent de ce corpus.

## Ce que le corpus donne, au 10 septembre 2026

Sur les 1 002 doléances du découpage servi, 754 741 mots. La part en **mots**
compte autant que la part en doléances : elle dit le poids réel dans un comptage
de thèmes, où un texte long produit plus de détections qu'un texte court.

| Support | Doléances | Part | Mots | Part |
|---|---:|---:|---:|---:|
| `registre` | 565 | 56 % | 458 158 | 61 % |
| `courrier` | 193 | 19 % | 149 413 | 20 % |
| `illisible` | 181 | 18 % | 83 065 | 11 % |
| `apparat` | 24 | 2 % | 1 587 | 0 % |
| `lettre_type` | 21 | 2 % | 24 167 | 3 % |
| `formulaire` | 8 | 1 % | 3 767 | 0 % |
| `petition` | 8 | 1 % | 32 141 | 4 % |
| `deliberation` | 2 | 0 % | 2 443 | 0 % |

| Auteur | Doléances | Part | Mots | Part |
|---|---:|---:|---:|---:|
| `indetermine` | 690 | 69 % | 292 126 | 39 % |
| `individu` | 245 | 24 % | 365 312 | 48 % |
| `institution` | 47 | 5 % | 41 022 | 5 % |
| `collectif` | 20 | 2 % | 56 281 | 7 % |

### Trois résultats que ces chiffres portent

**Une doléance sur cinq n'est pas une contribution.** 181 `illisible` et 24
`apparat`, soit **20 % des doléances**, sont des pages de couverture, des
en-têtes de mairie, des tampons, des manuscrits que le score de qualité a laissé
passer, et les mots par lesquels une commune transmet son cahier au préfet. Elles
étaient jusqu'ici comptées comme des contributions citoyennes. Le seuil est
volontairement bas — moins de la moitié de jetons vraisemblables — et une liste
de revendications télégraphique reste très au-dessus.

`illisible` dit aussi quelque chose de l'étape précédente : `needs_ocr` écarte
2 510 pages manuscrites, mais **il en laisse passer**. Certaines de ces 181
doléances font plusieurs centaines de mots de fragments de caractères.

**La première personne est minoritaire en nombre, majoritaire en volume.** 24 %
des doléances portent une marque de première personne, mais elles pèsent **48 %
des mots** : quelqu'un qui raconte sa situation écrit long. Les 69 %
d'indéterminé ne pèsent que 39 % des mots — ce sont, pour l'essentiel, des listes
de revendications sans sujet grammatical (« Rétablissement de l'ISF »,
« Suppression de la taxe d'habitation »). Rien dans leur forme ne dit qui les
écrit, et aucune règle de texte n'y accèdera : il y faudrait la mise en page.

**Huit pétitions pèsent plus que tout le reste de l'apparat.** 8 doléances
`petition` font 32 141 mots — 4 % du corpus — quand les 24 `apparat`, les 8
`formulaire` et les 2 `deliberation` réunis en font 7 797. Compter les pétitions
comme 8 contributions les efface ; les compter comme 8 textes de 4 000 mots les
surpondère dans toute découverte de thèmes. C'est exactement le genre d'arbitrage
que cette couche existe pour rendre visible, et qu'elle ne tranche pas.

## Les règles, et où elles s'appliquent

**La position compte.** Une formule d'appel ouvre un texte, une formule de
politesse le ferme, une signature d'élu est en bas. Cherchées partout, ces formes
se retrouvent au milieu d'une citation : « Monsieur le Maire ne répond jamais »
n'ouvre pas un courrier. Les 500 premiers et les 600 derniers caractères sont
donc examinés séparément — même raisonnement que
`anonymisation.detecteurs.signatures`.

**La casse compte.** `re.IGNORECASE` s'applique aussi aux classes de caractères.
La première version de ces règles annonçait 17 % de coupures de presse dans le
corpus parce que `Le Monde` cherché sans casse trouvait « tout le monde », et 10 %
d'organisations parce que `association\s+[A-ZÀ-Ÿ]` sans casse capturait « dans
une association ou ». Les motifs qui s'appuient sur une majuscule sont écrits
sensibles à la casse.

**L'ordre des règles fait partie de la décision.** Il va du plus contraint au plus
général, et chaque valeur sort d'une seule branche : un comptage par support est
une partition, pas une somme de recouvrements.

1. `illisible` l'emporte sur tout — aucune règle de forme ne veut rien dire sur
   du bruit d'extraction, et l'axe auteur passe alors d'office à `indetermine` ;
2. `apparat` passe avant `courrier` : c'en est un, mais son objet est de
   transmettre le cahier, pas de contribuer. **La brièveté est exigée** (250 mots),
   et c'est elle qui fait le plus de travail : neuf doléances portent une formule
   de transmission au milieu de plusieurs milliers de mots de contributions,
   parce que le découpage n'a pas vu la rupture entre la couverture et la suite.
   Les classer `apparat` jetterait le contenu avec l'emballage. Le seuil est pris
   dans un trou du corpus — 24 textes sous 140 mots, les 9 autres au-dessus de 330 ;
3. `lettre_type`, puis `formulaire`, `petition`, `deliberation`, `courrier` ;
4. `registre` par défaut — ce qui est écrit à même le cahier.

**Un en-tête de mairie ne conclut à rien seul.** Les communes ont fourni les
cahiers : leur papier à en-tête se retrouve en tête de contributions d'habitants.
Il faut une signature d'élu ou une mention du conseil municipal.

## Le seul signal qui ne vient pas du texte

`lettre_type` vient de la couche [`doublons/`](../doublons/README.md) : un texte
recopié dans **au moins deux communes** est une lettre-type ou un tract. Le même
texte deux fois dans une seule commune est plus souvent un cahier scanné en
double, ce qui ne dit rien du support.

Cette dépendance est **facultative** : sans run de déduplication servi, la passe
tourne et `lettre_type` n'est simplement jamais conclu. Le run employé — ou son
absence — est consigné dans les paramètres du run de typologie, pour qu'on sache
lequel des deux cas on lit.

## Utilisation

```bash
uv run python -m typologie
uv run python -m typologie --auteur "prénom nom"
```

Chaque appel crée un run de plus : deux jeux de règles peuvent coexister et se
comparer, et l'on ne détruit pas les relectures humaines du précédent pour en
essayer un autre. Le run servi est le dernier créé.

## Ce qui manque, et ne se code pas

- **La validation.** Aucune de ces étiquettes n'est vérifiée. Précision et rappel
  demandent un échantillon annoté à la main — l'outillage existe
  ([`reference/`](../reference/README.md)), le travail humain non. `confirmed`
  attend cette relecture.
- **Le vrai support.** Manuscrit ou dactylographié, tract collé, article de
  presse, feuille volante insérée : cela se voit sur l'image, pas dans le texte.
  Il y faut la géométrie de l'OCR, qui est aussi ce qui manque pour occulter les
  données personnelles sur les scans.
- **Le type d'auteur au sens strict.** « Individu » ici veut dire « le texte
  parle à la première personne », ce qui n'est pas la même chose. Un élu peut
  écrire à titre personnel, un secrétaire de mairie peut recopier le mot d'un
  habitant.
