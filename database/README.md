# Base de données : modèle et fonctionnement

## Le modèle

```mermaid
erDiagram
    contribution ||--o{ extraction : "contribution_id"
    contribution ||--o{ page_extraction : "contribution_id"
    run ||--o{ doleance : "run_id"
    run ||--o{ topic : "run_id"
    run ||--o{ instance : "run_id"
    contribution ||--o{ doleance : "contribution_id"
    doleance ||--o{ instance : "doleance_id"
    contribution ||--o{ instance : "contribution_id"
    topic ||--o{ instance : "topic_id"
    topic ||--o{ topic : "parent_id"
    contribution ||--o{ feeling : "contribution_id"
    contribution ||--o| annotation : "contribution_id"

    contribution {
        int id PK
        string city "parsée du nom du fichier"
        string pdf_file
        int start_page
        int end_page
        bool is_handwritten
    }
    extraction {
        int id PK
        int contribution_id FK
        string ocr "modèle qui a produit le texte"
        string text
        int num_words
        int num_lines
    }
    page_extraction {
        int id PK
        int contribution_id FK
        string pdf_name
        int page_number
        text text
        float quality_score "0.0 illisible à 1.0 propre"
        bool needs_ocr "page manuscrite suspectée"
        string city
    }
    run {
        int id PK
        string kind "segmentation | analyse"
        string label "nom lisible de la couche"
        string source "dossier de livraison ou module"
        string model "modèle LLM ou OCR employé"
        string prompt_version
        json parameters "seuils et config appliqués"
        string corpus "ce sur quoi le run a tourné"
        string author
        datetime created_at
        bool active "run servi par défaut pour ce genre"
        text notes
    }
    doleance {
        int id PK
        int run_id FK "découpage qui l'a produite"
        int contribution_id FK "contribution de la page d'ouverture"
        string pdf_name "cahier découpé"
        string city
        int position "rang dans le cahier"
        int start_page
        int end_page
        text text
        string signal "règle de découpage ayant ouvert la doléance"
        int num_words
    }
    topic {
        int id PK
        int run_id FK "grille à laquelle il appartient"
        string external_id "UUID de la livraison ; unique dans un run"
        string name
        text description
        int level "rang d'abstraction fourni par l'analyse"
        bool validated "relecture humaine"
        int parent_id FK "thème englobant ; NULL = racine"
        text parent "ancien parent par nom, à supprimer"
    }
    instance {
        int id PK
        int run_id FK "livraison qui l'a produite"
        int contribution_id FK "NULL tant que le lien doc n'est pas résolu"
        int doleance_id FK "renseigné si la livraison porte sur des doléances"
        string external_doc_id "id du document dans la livraison"
        int topic_id FK
        text verbatim "extrait exact qui porte le thème"
        text summary "justification de la détection"
    }
    feeling {
        int id PK
        int contribution_id FK
        string name
    }
    annotation {
        int contribution_id PK, FK
        bool is_anonymized
        bool is_of_interest
    }
```

| Table | Contenu | Owner |
|---|---|---|
| `contribution` | métadonnées : commune, fichier, pages, manuscrit | équipe séparation |
| `extraction` | texte extrait une ligne par essai d'OCR | équipe extraction |
| `page_extraction` | texte extrait page par page (OCR-free) avec score de qualité et flag `needs_ocr` | équipe extraction |
| `run` | une production de couche interprétative : un découpage, une grille | `database/runs.py` |
| `doleance` | le texte d'un contributeur, découpé du cahier | `segmentation/` |
| `topic` | taxonomie des thèmes, hiérarchie via `parent_id` | équipe analyse |
| `instance` | détections de thèmes : verbatim + justification, une ligne par détection | équipe analyse |
| `feeling` | sentiments détectés : une ligne par résultat | équipe analyse |
| `annotation` | variables activées dans l'app ("Anonymisé", "d'intérêt") | outil Gradio |

**La logique** : une tâche métier = une table, chaque équipe n'écrit que dans la sienne
(CR de réunion), et tout pointe vers `contribution.id`. **La pertinence** : aucune donnée
n'est écrite par deux équipes, et l'avancement se lit par l'existence des lignes (pas de
ligne `extraction` = pas encore extraite, pas de ligne `annotation` = pas encore annotée).

## Les couches, et pourquoi elles sont versionnées

Le squelette du corpus, c'est la provenance : `contribution` -> `page_extraction`,
rattachés à un cahier et à une commune. Il ne bouge pas.

Le reste — le découpage en doléances, les thèmes, les détections — est une
**couche interprétative** posée dessus. Une heuristique décide qu'une page porte
trois auteurs ; un modèle décide qu'un paragraphe parle de fiscalité. Ces
décisions doivent être visibles, attribuées, comparables et réversibles, donc
versionnées : c'est le rôle de `run`.

Avant cette table, `load_analysis.py` faisait `DELETE FROM instance` à chaque
livraison et `charger_topics` upsertait dans une table `topic` unique : **une
seule grille pouvait exister à la fois**, et rien ne disait de quel modèle ni de
quel prompt elle venait. Charger une grille pour la comparer détruisait
l'ancienne.

Cinq genres aujourd'hui : `segmentation`, `analyse`, `doublons`,
`anonymisation` et `typologie`. Dans chaque genre, un seul
run est `active` — c'est celui que l'app et les exports servent — garanti par un
index unique partiel, pas seulement par le code appelant. Les autres restent en
base, lisibles et comparables.

```python
from database.runs import ANALYSE, SEGMENTATION, creer_run, run_actif, runs

creer_run(session, ANALYSE, label="grille émergente v4", model="qwen3-4b", ...)
run_actif(session, ANALYSE)   # la grille servie, ou None sur une base vierge
runs(session, ANALYSE)        # toutes les grilles, de la plus récente à la plus ancienne
```

**Un run est toujours attribué.** `run.author` est `NOT NULL` depuis le
10 septembre 2026 : `creer_run` résout l'auteur d'office quand la commande ne le
donne pas — `--auteur`, puis la variable `CAHIER_DOLEANCES_AUTEUR`, puis la
configuration git du dépôt, puis le compte système (`database/auteur.py`). Avant
cela l'auteur était seulement *réclamé*, par un message imprimé en fin de
commande ; la base porte encore quatre runs anonymes, comblés en `inconnu` par la
migration, pour montrer ce que valait le rappel. Une couche interprétative qu'on
ne peut rattacher à personne ne se discute pas, elle se subit.

`run_actif` renvoyant `None` est un **état normal** (base migrée mais pas encore
chargée) : les lectures le traitent comme « couche vide », pas comme une erreur.
L'app l'exprime en SQL — `WHERE t.run_id = (SELECT id FROM run WHERE kind='analyse' AND active)`
— la sous-requête vaut NULL, la comparaison n'est jamais vraie, les vues sont vides.

**Conséquence sur l'unicité** : `topic.external_id` n'est plus unique dans la
table mais dans un run (`uq_topic_run_external_id`). Deux grilles peuvent
réutiliser le même UUID de livraison. De même, les noms de thèmes ne sont uniques
que dans une grille — toute lecture qui s'appuie dessus doit filtrer sur le run.

## Mettre à jour le modèle de données

La source de vérité est `database/models.py` ; Alembic versionne chaque évolution dans
`database/migrations/versions/` (committé, rejouable sur une base vierge).

Évolution **additive** (nouvelle colonne, nouvelle table) :

1. Modifier `database/models.py`
2. `uv run alembic revision --autogenerate -m "description"`
3. **Relire** le script généré dans `database/migrations/versions/`
4. `uv run alembic upgrade head`
5. Committer `models.py` + la migration

Évolution **destructive** (supprimer une colonne) : jamais en un coup — dump d'abord,
puis trois migrations *expand → backfill → contract* avec vérification chiffrée avant
le contract (voir les migrations du passage aux instances de topics comme exemple :
`expand ref_topic` → `backfill topic.name` → `contract suppression de topic.name`).

**Renommage** (table ou colonne) : `--autogenerate` ne le détecte pas — il générerait un
`drop` + `create` destructeur. On écrit la migration à la main avec `op.rename_table` /
`op.alter_column(new_column_name=…)`, qui préservent données, index et FK (voir la
migration `rename : topic -> instance, ref_topic -> topic`).

L'autogenerate crée les contraintes avec le nom `None`, ce qui rend le `downgrade`
inapplicable : les nommer à la main (`op.create_unique_constraint("uq_...", ...)`).

Ne pas reformater une migration déjà appliquée : c'est une archive, la retoucher
ne produit que du bruit dans les diffs et des conflits de merge.

La connexion est construite par `database/db.py` depuis `.env` (ou `DATABASE_URL`
pour un SQLite local) — jamais de credentials dans un fichier committé.

## Exporter le corpus pour l'analyse

`database/export_dataset.py` écrit le CSV `id,content` attendu par
`topic-builder`, à deux niveaux (`--niveau`) :

- `contribution` (défaut) : lit `page_extraction`, une ligne par contribution,
  pages concaténées dans l'ordre. Les pages `needs_ocr` (manuscrites, texte
  illisible) sont écartées par défaut ; `--keep-ocr-pages` les réintègre pour
  inspecter le corpus complet. **Une contribution, c'est une page** : plusieurs
  contributeurs peuvent s'y côtoyer, et une doléance longue y est coupée en deux.
- `doleance` : lit `doleance`, une ligne par contributeur, telle que
  `segmentation/` l'a découpée. C'est la bonne unité d'analyse.

**L'`id` du document est la clé primaire de la ligne exportée** — `42` pour une
contribution, `d42` pour une doléance. La livraison de l'analyse renvoie ses
labels indexés par cet id, ce qui rend le rapprochement immédiat au retour (voir
plus bas). Le préfixe n'est pas cosmétique : les deux tables ont des id
auto-incrémentés qui se recouvrent, sans marquage une livraison sur les doléances
serait rechargée en désignant des contributions au hasard. Le format est dans
`database/identifiants.py`, partagé par l'export et le chargement.

## Charger la livraison de l'équipe analyse (temporaire TODO: mettre dans une future pipeline)

`database/load_analysis.py` lit `analyse/analysis_v4/` (`taxonomy.json` +
`instances.json`) et remplit `topic` et `instance`. Il est important de récupérer ce script dans la future data pipeline.

`instance.contribution_id` est résolu quand l'id de document de la livraison
correspond à une contribution existante — c'est le cas des livraisons produites
depuis `export_dataset.py`. Sinon (livraisons antérieures, numérotées `doc 73` par
l'équipe analyse) il reste NULL et l'instance n'est rattachée que par
`external_doc_id`, comme avant. Le script affiche le nombre d'instances rattachées.

Quand la livraison porte sur des doléances (ids `d42`), `instance.doleance_id` est
résolu **et** `contribution_id` est repris de la doléance : les vues de l'app
joignent sur `contribution_id`, elles continuent de fonctionner sans connaître le
nouveau niveau.

**La livraison d'août ne décrit pas ce corpus.** `load_analysis.py` vérifie que
les verbatims d'une livraison se retrouvent bien dans le texte visé, et refuse le
rattachement en dessous de 30 % : c'est ce garde-fou qui laisse
`instance.contribution_id` à NULL. Mesuré le 10 septembre 2026, la raison est
plus profonde qu'un décalage d'identifiants — sur les 9 579 extraits de cette
livraison, **3,8 % seulement** se retrouvent dans les 6,4 millions de caractères
de `page_extraction`, et **24 % de son vocabulaire y est absent**. Elle porte sur
une autre extraction, ou un autre périmètre. Aucun rattachement par verbatim ne
la sauvera : il faut refaire l'analyse sur le corpus actuel.

## Commandes

```bash
uv run alembic revision --autogenerate -m "..." # générer une migration
uv run alembic upgrade head # appliquer à la base
uv run alembic current # version actuelle de la base
uv run alembic check # écart entre models.py et la base
uv run python -m database.seed_mock # seed de démo : 4 contributions dactylographiées réelles
uv run python -m database.export_dataset --output data/dataset.csv # corpus -> CSV topic-builder
uv run python -m database.export_dataset --niveau doleance --output data/dataset.csv # au niveau doléance
uv run python -m database.load_analysis # charger la livraison analyse (met à jour sa grille)
uv run python -m database.load_analysis <dossier> --nouveau-run --label "v5" # charger en grille de plus
```

## Dumps

Format custom `pg_dump`, nommés `<base>_<date>[_<étape>].dump`. Ils contiennent
`alembic_version`, donc la version de schéma voyage avec les données.

- **En local** : `database/backups/` (ignoré par git, les dumps contiennent le
  texte des cahiers).
- **Sur S3** : bucket `cahiers-upload`, préfixe `backups/`. Le script
  `gradio_app/s3_helpers.py` ne lit que les `.pdf`, un dump n'interfère donc pas
  avec l'aperçu PDF.

Dump avant toute évolution destructive :

```bash
set -a; . ./.env; set +a
PGPASSWORD="$DB_PASSWORD" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  --format=custom --no-owner --no-privileges \
  --file="database/backups/${DB_NAME}_$(date +%F).dump"
```

Restaurer :

```bash
PGPASSWORD="$DB_PASSWORD" pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  --clean --if-exists --no-owner database/backups/<fichier>.dump
```
