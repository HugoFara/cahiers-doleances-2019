# App Gradio : visualisation et annotation

Une page, quatre onglets, sur un seul serveur :

    /          Par commune  parcourir les contributions (texte lu + PDF) et
               activer deux variables (Anonymisé, Contribution d'intérêt)
               Recherche    chercher dans le texte des doléances
               Lecture      ce qu'une grille fait voir du corpus, et ce qu'elle rate
               Thèmes       explorer une grille de thèmes en cliquant les nœuds
    /graphe    la vue thèmes seule, la même, avec son en-tête (pour un lien)

Les données sont lues **directement dans la base PostgreSQL**, pas de fichier
intermédiaire. Les PDF viennent de l'Object Storage Scaleway.

## L'avertissement, avant tout chiffre

Trois phrases en haut de la page, au-dessus des onglets, visibles sans clic — un
avertissement qu'il faut déplier n'est pas un avertissement. Les précisions et
les sources sont repliées dessous. Tout est calculé, rien n'est écrit en dur : la
part de pages écartées, les communes sans aucune page lisible avec leur poids en
habitants, la grille de thèmes servie parmi celles qui coexistent en base, et les
mentions de source exigées par la Licence Ouverte 2.0.

La vue thèmes est servie hors de Gradio, en HTML : ouverte seule (`/graphe`),
l'avertissement y est injecté au moment de la requête, dans un gabarit qui
porte un `<!--avertissement-->` ; intégrée dans l'onglet, elle cache le sien,
celui de la page hôte vaut pour elle. C'était la page qui en avait le plus
besoin — elle montre une taxonomie, donc une lecture du corpus, et elle
n'affichait rien.

Ce n'est pas un scrupule décoratif. Un site de consultation est un acte
éditorial : « 34 % des contributions parlent de fiscalité » sera lu comme un
sondage si rien ne dit le contraire. La troisième condition de la Licence
Ouverte 2.0, sous laquelle sont les données INSEE et IGN, est d'ailleurs de « ne
pas induire en erreur quant à leur interprétation ».

Les compteurs viennent de `couverture.mesures` et `insee.cog`, jamais d'un calcul
refait dans l'app : deux implémentations de la même règle divergent, et celle qui
s'affiche à l'écran serait la dernière corrigée. La mise en forme, elle, est dans
`gradio_app/avertissements.py`, sans base ni Gradio, donc testée.

## Fonctionnement

**Par commune** : une contribution affiche ses thèmes (`instance` reliées au
référentiel `topic`, avec verbatim et résumé quand l'analyse existe), ses
sentiments (`feeling`), le texte de sa dernière extraction (`extraction`,
`max(id)`) et son PDF. Les deux cases cochées sont écrites dans `annotation`
(UPSERT ; les deux décochées = ligne supprimée).

**Le sélecteur de commune repose sur le code INSEE**, plus sur la graphie de
l'en-tête du PDF. Ce parsing échoue sur un tiers des cahiers, et la conséquence
n'était pas cosmétique : 153 communes n'avaient aucune entrée dans la liste et
**2 169 contributions sur 5 365 — 40 % — n'étaient atteignables par aucun chemin
de l'app**. Château-Gontier-sur-Mayenne et ses cent contributions en faisaient
partie. Le libellé affiche le nom officiel du Code officiel géographique, retombe
sur la graphie du corpus, puis sur le code seul. Les 144 contributions dont le
cahier n'a pas de code à la source ont leur propre entrée en fin de liste, plutôt
que de rester invisibles.

**On peut changer de grille de thèmes depuis la vue thèmes.** La base est faite
pour que plusieurs coexistent — c'est ce qui rend le choix de l'une visible et
discutable — mais l'app n'en servait qu'une, calculée à l'import. La logique de
grille est maintenant dans `views/grille.py`, une classe qui reçoit des lignes et
ne connaît ni la base ni Plotly ; `views/graph.py` en tient un cache par run.
Effet secondaire du refactoring, et pas le moindre : cette vue était **la seule
du dépôt sans aucun test**, et le premier essai sur une petite grille a fait
tomber un `IndexError` que la grille livrée masquait — une strate sans arbre.

**Chaque étiquette renvoie à sa page source, en un clic.** Le visualiseur PDF
s'ouvre sur la page de la contribution affichée plutôt qu'en couverture, les
thèmes détectés portent leur page et sont cliquables, et chaque résultat de
recherche l'est aussi (`gradio_app/source.py`, ancre `#page=N`). C'est la seule
granularité que le corpus permette : encadrer le passage sur l'image demanderait
la géométrie des lignes, que l'extraction ne produit pas. Quand le cahier est
introuvable — S3 muet et pas de copie locale — le libellé reste affiché sans
lien : un lien mort vaut moins que rien.

**Recherche** : plein texte sur les doléances (`recherche/`). Ses extraits sont
**caviardés**, quand la vue par commune montre le texte brut — et l'écart est
voulu : la recherche est le premier endroit où le corpus se lit en vrac, hors du
cahier qui lui donnait son contexte. Les doublons y sont signalés, sans quoi une
recherche présenterait la lettre présidentielle comme les cinq contributions les
plus pertinentes du corpus.

**Lecture** : la part des doléances par thème, pour la grille choisie, avec
trois barres par thème — doléances rattachées (plusieurs thèmes possibles),
**rubrique dominante** (une par doléance : celle qui a le plus de détections,
ou pour les mots-clés le plus de termes qui ont mordu), et la **distribution
de référence** de la grille quand son fichier en porte une (`reference` dans
`analyse/grilles/*.json`, copiée dans les paramètres du run). La barre **hors
grille** ferme le graphique : sans elle, « 34 % parlent de fiscalité » ne dit
pas sur quelle part du corpus il porte. Dessous, les doléances que la grille
ne voit pas, les plus longues d'abord, caviardées comme des résultats de
recherche (`recherche.requetes.sans_detection`). Entre les deux, deux
croisements : la **co-occurrence** des thèmes dans une même doléance,
rapportée au hasard parmi les doléances rattachées (1 = indépendants ; la
longueur pousse tout au-dessus de 1, ce sont les écarts qui se lisent), et
les thèmes par **taille de commune** (strates de population du COG 2019,
`city.population`), en part des doléances de la strate. La vue thèmes montre la
*grille*, celle-ci montre le *corpus* : sur une grille plate l'arbre n'a rien
à dire, et même sur une grille profonde il répond à « comment la grille est
rangée », pas à « de quoi parlent les doléances ». Les runs « mots-clés »
sont nommés tels quels dans le titre : un détecteur de vocabulaire, l'étalon
bas d'un futur modèle.

**Une seule grille servie.** Plusieurs grilles de thèmes coexistent en base
(`database/runs.py`) ; sans filtre l'app les empilerait, et les noms de thèmes —
uniques dans une grille, pas dans la table — se confondraient. `GRILLE_SERVIE`
filtre sur la grille active. Ce filtre n'avait été posé que sur la vue thèmes :
**la vue commune cumulait les détections de toutes les grilles**, ce qui ne se
voyait pas tant qu'une seule était chargée.

**Vue thèmes** : la taxonomie et ses détections sont chargées une fois par
grille puis servies en JSON. Le graphe est une page maison, pas un composant
Gradio : `gr.Plot` n'expose pas d'évènement de clic, or on veut naviguer en
cliquant les nœuds. Elle est **intégrée dans l'onglet « Thèmes »** par un cadre
(`/graphe?integre=1&theme=…`) : jusqu'au 11 septembre 2026 on y allait par un
lien, et l'on passait du thème sombre de Gradio à une page claire, avec une
autre police et une autre navigation. Le cadre reçoit le thème de l'hôte par
l'URL ; la page suit la palette du thème Gradio « Soft » en clair comme en
sombre, et la police est celle du système des deux côtés. Le Blocks est monté
sur la même FastAPI via `gr.mount_gradio_app`, après les routes du graphe pour
que `/` ne masque pas `/graphe`.

La navigation tient en deux lignes : la grille (et, si la grille en peuple
plusieurs, les **groupes d'arbres par hauteur** : grands, 5 niveaux et plus ;
moyens, 3 à 4 ; petits, 1 à 2, avec leur nombre d'arbres et leur part des
détections), puis un **fil d'Ariane** : vue d'ensemble › racine › niveau ›
… › descendre. La vue s'ouvre sur le premier groupe peuplé ; une grille de
quatre thèmes n'a qu'un groupe et ne montre pas le sélecteur. Les groupes
s'appelaient « strates » (canopée, sous-bois, semis) et l'entrée se faisait
toujours par la canopée, vide sur toute grille peu profonde : renommés et
corrigés le 2026-09-11. La couleur donne la **distance à la racine**, pas le
`level` de la livraison. C'est un outil d'exploration, pas une représentation
proportionnelle du corpus.

`?grille=<run>&noeud=<nom>` ouvre directement une grille, ou un thème dedans.

**PDF** : la base ne stocke que le nom du fichier, S3 le range sous un préfixe.
On construit l'index nom → clé au premier appel, puis on sert une **URL
présignée** (1 h). Le navigateur va chercher le fichier directement sur
Scaleway : certains PDF font 43 Mo, ils ne transitent pas par l'app. Repli sur
`data/raw/pdfs/` si le bucket est injoignable.

| Fichier | Rôle |
|---|---|
| `app.py` | assemble le Blocks, expose les routes du graphe, monte le tout |
| `views/commune.py` | vue « Par commune » : navigation + annotation |
| `views/recherche.py` | vue « Recherche » : plein texte, extraits caviardés, lien vers la page |
| `views/lecture.py` | vue « Lecture » : parts par thème, dominante, référence, hors grille lisible |
| `views/graph.py` | vue thèmes : dessin Plotly et réponses JSON, une grille par run |
| `views/grille.py` | la grille de thèmes comme objet — sans base ni Plotly, donc testée |
| `views/static/` | page des thèmes (`index.html`, `style.css`, `app.js`) : thème, groupes, fil d'Ariane |
| `views/style.css` | styles du Blocks, chargé via `css_paths` |
| `data_helpers.py` | requêtes SQL (SQLAlchemy + pandas) et écriture des annotations |
| `source.py` | le retour à la source : URL du cahier avec l'ancre `#page=N` |
| `avertissements.py` | ce que le corpus n'est pas, calculé depuis la base, sans Gradio |
| `s3_helpers.py` | index des PDF et URL présignées |

`gradio_app` est un paquet comme les autres : il s'importe en `gradio_app.…`
partout, et se lance par `python -m gradio_app.app`. Il consomme les passes
(`couverture`, `insee`, `recherche`) et n'en fonde aucune.

## Prérequis

1. Base accessible et remplie : `uv run python -m database.seed_mock` (démo) ou
   `uv run python -m analyse.load_analysis <dossier>` (livraison analyse).
2. `.env` renseigné :
   - base : `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
   - PDF : `S3_ENDPOINT`, `S3_BUCKET_NAME`, `SCW_ACCESS_KEY`, `SCW_SECRET_KEY`
     (`S3_REGION` est déduite de l'endpoint si elle n'est pas renseignée)

## Lancer

```bash
uv run python -m gradio_app.app   # http://localhost:7860
```

## Limites connues

- L'avertissement de la vue commune est calculé au démarrage, comme la
  taxonomie ; celui de la vue thèmes est recalculé à chaque requête.
- Le sélecteur de grille n'apparaît que s'il y en a plusieurs en base : avec une
  seule, il n'offrirait aucun choix. L'avertissement, lui, annonce toujours
  laquelle est servie. La grille « cadrage gouvernemental 2019 »
  (`analyse/grilles/`) se charge sans détections : le sélecteur la liste, la vue
  l'affiche vide et dit pourquoi.
- Une grille est lue au premier accès puis gardée en mémoire : recharger une
  livraison en base demande un redémarrage de l'app (ou un appel à
  `graph.oublier_les_grilles()`).
- `instance.contribution_id` est NULL **pour la livraison analyse actuelle**, dont
  les documents sont numérotés par l'équipe analyse (`doc 73`) sans correspondance
  en base : la vue thèmes affiche cet identifiant source, et la vue commune
  n'affiche pas les thèmes détectés. Les livraisons produites depuis
  `analyse/export_dataset.py` portent l'`id` de la contribution et sont rattachées
  automatiquement par `load_analysis.py` ; les deux vues se rempliront à ce
  moment-là, sans changement de code.
