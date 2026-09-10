# App Gradio : visualisation et annotation

Deux interfaces sur un seul serveur :

    /          Par commune  parcourir les contributions (texte extrait + PDF) et
               activer deux variables (Anonymisé, Contribution d'intérêt)
    /graphe    Vue graphe des thèmes  explorer la taxonomie en cliquant les nœuds

Les données sont lues **directement dans la base PostgreSQL**, pas de fichier
intermédiaire. Les PDF viennent de l'Object Storage Scaleway.

## L'avertissement, avant tout chiffre

Trois phrases en haut de **chacune des deux pages**, visibles sans clic — un
avertissement qu'il faut déplier n'est pas un avertissement. Les précisions et
les sources sont repliées dessous. Tout est calculé, rien n'est écrit en dur : la
part de pages écartées, les communes sans aucune page lisible avec leur poids en
habitants, la grille de thèmes servie parmi celles qui coexistent en base, et les
mentions de source exigées par la Licence Ouverte 2.0.

La vue graphe est servie hors de Gradio, en HTML : l'avertissement y est injecté
au moment de la requête, dans un gabarit qui porte un `<!--avertissement-->`.
C'était la page qui en avait le plus besoin — elle montre une taxonomie, donc une
lecture du corpus, et elle n'affichait rien.

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

**Une seule grille servie.** Plusieurs grilles de thèmes coexistent en base
(`database/runs.py`) ; sans filtre l'app les empilerait, et les noms de thèmes —
uniques dans une grille, pas dans la table — se confondraient. `GRILLE_SERVIE`
filtre sur la grille active. Ce filtre n'avait été posé que sur la vue graphe :
**la vue commune cumulait les détections de toutes les grilles**, ce qui ne se
voyait pas tant qu'une seule était chargée.

**Vue graphe** : la taxonomie et ses détections sont chargées une fois au
démarrage (6788 topics, 9579 instances) puis servies en JSON. Le graphe est une
page maison, pas un onglet Gradio : `gr.Plot` n'expose pas d'évènement de clic,
or on veut naviguer en cliquant les nœuds. Le Blocks est monté sur la même
FastAPI via `gr.mount_gradio_app`, après les routes du graphe pour que `/` ne
masque pas `/graphe`.

Les arbres sont rangés en **strates** par hauteur (A canopée, B sous-bois,
C semis) et la couleur donne la **distance à la racine**, pas le `level` de la
livraison. C'est un outil d'exploration, pas une représentation proportionnelle
du corpus : voir `analyse/structure_arbres_v3.ipynb` pour les biais assumés.

**PDF** : la base ne stocke que le nom du fichier, S3 le range sous un préfixe.
On construit l'index nom → clé au premier appel, puis on sert une **URL
présignée** (1 h). Le navigateur va chercher le fichier directement sur
Scaleway : certains PDF font 43 Mo, ils ne transitent pas par l'app. Repli sur
`data/raw/pdfs/` si le bucket est injoignable.

| Fichier | Rôle |
|---|---|
| `app.py` | assemble le Blocks, expose les routes du graphe, monte le tout |
| `views/commune.py` | vue « Par commune » : navigation + annotation |
| `views/graph.py` | vue graphe : strates, couleurs, layout, réponses JSON |
| `views/static/` | page du graphe (`index.html`, `style.css`, `app.js`) |
| `views/style.css` | styles du Blocks, chargé via `css_paths` |
| `data_helpers.py` | requêtes SQL (SQLAlchemy + pandas) et écriture des annotations |
| `s3_helpers.py` | index des PDF et URL présignées |

## Prérequis

1. Base accessible et remplie : `uv run python -m database.seed_mock` (démo) ou
   `uv run python -m database.load_analysis` (livraison analyse).
2. `.env` renseigné :
   - base : `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
   - PDF : `S3_ENDPOINT`, `S3_BUCKET_NAME`, `SCW_ACCESS_KEY`, `SCW_SECRET_KEY`
     (`S3_REGION` est déduite de l'endpoint si elle n'est pas renseignée)

## Lancer

```bash
uv run python gradio_app/app.py   # http://localhost:7860
```

## Limites connues

- L'avertissement de la vue commune est calculé au démarrage, comme la
  taxonomie ; celui de la vue graphe est recalculé à chaque requête.
- **On ne peut pas changer de grille depuis l'app**, seulement savoir laquelle
  est servie. Le faire demanderait de sortir la taxonomie de l'état de module de
  `views/graph.py` — environ cinq cents lignes calculées à l'import — pour la
  paramétrer par run. C'est un refactoring, pas un câblage : il est listé au plan
  comme tel plutôt que fait à moitié. En attendant, on change de grille en
  activant l'autre run en base et en redémarrant.
- La taxonomie est chargée au démarrage : recharger la base demande un
  redémarrage de l'app.
- `instance.contribution_id` est NULL **pour la livraison analyse actuelle**, dont
  les documents sont numérotés par l'équipe analyse (`doc 73`) sans correspondance
  en base : la vue graphe affiche cet identifiant source, et la vue commune
  n'affiche pas les thèmes détectés. Les livraisons produites depuis
  `database/export_dataset.py` portent l'`id` de la contribution et sont rattachées
  automatiquement par `load_analysis.py` ; les deux vues se rempliront à ce
  moment-là, sans changement de code.
