# Provenance des extraits

Ces trois fichiers sont des **extraits** de référentiels publics, réduits aux
départements présents dans le corpus (01, 28, 39, 53). Ils sont versionnés
plutôt que téléchargés à la volée : le chargement en base doit être reproductible
hors ligne, et une URL qui bouge chez le producteur ne doit pas casser une
mesure publiée. Ils se reconstruisent avec

```bash
uv run python -m insee referentiel --departements 01 28 39 53
```

Extraction du **2026-09-10**.

## Le millésime pivot est 2019

Les codes INSEE que portent les noms de fichiers des cahiers ont été attribués
par le système qui les a déposés, en **février-avril 2019**. Un code INSEE est
une clé datée : il désigne une commune *à un millésime donné*. Tout le
référentiel est donc aligné sur le 1ᵉʳ janvier 2019, et `city.code` ne bouge
jamais — le code actuel est une annotation, portée par `passage.csv`, pas une
correction.

## `communes_2019.csv`

`code, type, commune_parente, nom, departement, population`

- **Noms et périmètres** : Code officiel géographique au 1ᵉʳ janvier 2019, INSEE,
  fichier `communes-01012019.csv` —
  <https://www.insee.fr/fr/information/3720946>.
- **Population** : populations légales **millésimées 2017**, fichier d'ensemble,
  colonne `PMUN` — <https://www.insee.fr/fr/statistiques/4265429>.

Le millésime de population demande une explication, parce qu'il n'est pas celui
qu'on prendrait spontanément. L'INSEE publie les populations légales avec deux
dates : un millésime de recensement, et des limites communales. Les populations
**millésimées 2017** sont publiées « dans les limites territoriales des communes
au 1ᵉʳ janvier 2019 » — c'est-à-dire exactement la géographie de nos codes. Les
populations millésimées 2016, celles qui étaient légalement *en vigueur* quand
les cahiers ont été écrits, portent les limites de 2018 et ne recouvrent donc pas
nos codes. Le recensement de 2017 est au passage plus proche de février 2019 que
celui de 2016.

`PMUN` (population municipale) et non `PTOT` : la population totale ajoute les
personnes comptées à part, déjà comptées dans une autre commune.

**Attention au double compte.** `type` vaut `COM` (commune de plein exercice),
`COMD` (déléguée) ou `COMA` (associée). La population d'une commune déléguée est
**incluse** dans celle de sa `commune_parente` : sommer les deux compte deux fois
les mêmes habitants. Le corpus est concerné — voir `insee/README.md`.

## `geometrie.csv`

`code, latitude, longitude` — coordonnées du centre, API Découpage administratif
(<https://geo.api.gouv.fr>), construite sur ADMIN EXPRESS de l'IGN.

**Millésime courant, et c'est assumé** : une commune inchangée depuis 2019 a le
même centre, la géométrie ne dépend pas du millésime là où la population en
dépend. Les huit communes de 2019 disparues depuis n'y figurent pas et restent
sans coordonnées : on ne leur prête pas le centre de la commune qui les a
absorbées.

## `passage.csv`

`code_2019, code_courant, nom_courant, date_effet, evenement`

Table de passage du millésime pivot vers le millésime courant (2026), construite
depuis le fichier des mouvements de communes de l'INSEE (`v_mvt_commune_2026`),
qui recense les événements depuis 1943 —
<https://www.insee.fr/fr/information/8740222>.

Une ligne par commune de 2019 dont **le code ou le nom** a changé depuis. Les
communes inchangées n'y sont pas. `code_courant` vide signifie que la chaîne des
mouvements ne mène à aucune commune de plein exercice actuelle.

`date_effet` et `evenement` donnent le mouvement qui explique la ligne. Pour une
entité déjà déléguée ou associée au 1ᵉʳ janvier 2019, c'est son **absorption**,
antérieure au pivot : le corpus contient deux cahiers déposés sous un code qui
avait déjà cessé de désigner une commune.

## Licences — vérifié le 2026-09-10

Les trois sources sont sous **Licence Ouverte / Open Licence version 2.0**
(Etalab). Vérifié aux sources plutôt qu'admis :

| Fichier produit | Source | Licence | Où c'est écrit |
|---|---|---|---|
| `communes_2019.csv` (noms) | COG, insee.fr | LO 2.0 | mentions légales de l'INSEE |
| `communes_2019.csv` (population) | populations légales, insee.fr | LO 2.0 | idem |
| `geometrie.csv` | ADMIN EXPRESS (IGN), via geo.api.gouv.fr | LO 2.0 | fiche IGN sur data.gouv.fr |
| `passage.csv` | COG, insee.fr | LO 2.0 | mentions légales de l'INSEE |

Les [mentions légales de l'INSEE](https://www.insee.fr/fr/information/2008466)
couvrent explicitement ce que nous téléchargeons : « Sauf mention contraire, les
informations publiques diffusées sur ce site (données, bases de données,
publications, fichiers téléchargeables) sont mises à disposition sous la Licence
Ouverte / Open Licence version 2.0 (Etalab) ». C'est cette page qui fait foi ici,
et non la fiche data.gouv.fr du COG, encore étiquetée en version 1.0 — un
étiquetage hérité, alors que 99 des 100 jeux publiés par l'INSEE sur ce portail
sont en 2.0.

**Le point qu'il fallait vérifier et qui n'était pas acquis** : les coordonnées.
`geo.api.gouv.fr` ne publie pas de licence pour son découpage administratif, et
api.gouv.fr liste OpenStreetMap parmi ses partenaires — ce qui aurait signifié
**ODbL**, donc une obligation de partage à l'identique incompatible avec le
reste. Le générateur des contours
([`etalab/contours-administratifs`](https://github.com/etalab/contours-administratifs))
tranche : les communes viennent d'**ADMIN EXPRESS**, et OpenStreetMap n'est
utilisé que pour les collectivités d'outre-mer. Les quatre départements du corpus
sont en métropole : aucune donnée ODbL n'entre ici.

## Ce que la licence oblige à faire

La LO 2.0 permet la réutilisation, y compris commerciale, à trois conditions —
qui s'appliqueront à toute publication du corpus, pas seulement à ce dossier :

1. mentionner la source, sous la forme « Source : Insee » et « Source : IGN » ;
2. mentionner la date de dernière mise à jour des données quand elle est connue —
   ici les millésimes ci-dessus et la date d'extraction ;
3. ne pas altérer le sens des informations ni induire en erreur quant à leur
   interprétation.

La troisième n'est pas une formalité pour ce projet : c'est exactement le risque
que la pondération par population fait courir si elle est publiée sans dire ce
qu'elle mesure.
