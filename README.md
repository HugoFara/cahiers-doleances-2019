# Cahiers de doléances

Projet Data For Good : Outil de découverte, visualisation et annotation des thèmes abordés dans des cahiers de doléances.
Les contributions extraites des PDF sont stockées en base PostgreSQL ; une app Gradio permet
de les parcourir commune par commune et de les annoter (anonymisé, contribution d'intérêt).

## Organisation

- `database/` : le modèle de données et les migrations qui structurent la base PostgreSQL | [documentation](database/README.md)
- `extraction/` : les pipelines d'extraction de texte depuis les PDFs
  - `extraction/without_ocr/` : extraction du texte natif, sans OCR | [documentation](extraction/without_ocr/README.md)
- `gradio_app/` : l'interface pour parcourir les contributions et les annoter | [documentation](gradio_app/README.md)
- `topic-builder/` : l'utilitaire de découverte, structuration et annotation des thèmes abordés dans les contributions | [documentation](topic-builder/README.md)

## Installation

Ce projet utilise [uv](https://docs.astral.sh/uv/) pour la gestion des dépendances Python
(prérequis). Une fois uv installé :

```bash
uv sync
```

Cela installe la bonne version de Python, crée l'environnement virtuel et installe les
dépendances. La version est épinglée à **3.14** dans `.python-version` (le projet accepte
3.12 à 3.14) : toutes les dépendances y ont un wheel, plus rien ne se compile à
l'installation. L'épingle reste utile : sans elle, `uv` prend l'interpréteur qu'il préfère
sur la machine, et sur une machine où le seul 3.14 géré par uv est la variante
*free-threaded* c'est elle qu'il choisit — variante pour laquelle les wheels manquent encore.
`topic-builder/` suit la même épingle, avec son propre lockfile.

Sous VSCode l'environnement s'active automatiquement ; sinon :

```bash
source .venv/bin/activate
```

Ou préfixez vos commandes par `uv run` :

```bash
uv run python -m database.seed_mock # remplit la base avec le seed de démo
uv run python gradio_app/app.py # lance l'app
```

## Base de données

La connexion PostgreSQL est lue depuis `.env` (`DB_HOST`, `DB_PORT`, `DB_USER`,
`DB_PASSWORD`, `DB_NAME`). Voir [database/README.md](database/README.md) pour le modèle,
les migrations Alembic et le seed.

**Prérequis : une base de données accessible**

Les scripts se connectent à PostgreSQL dès leur démarrage. Si la base n'est pas
disponible, ils s'arrêtent immédiatement avec un message d'erreur indiquant
l'hôte, le port et le nom de la base concernés.

Deux options pour disposer d'une base :

1. **Base locale avec Docker** (recommandé pour le développement) — `compose.yaml`
   lit les mêmes variables que les scripts Python, il n'y a que `.env` à renseigner :

   ```bash
   cp .env.example .env      # puis renseigner DB_USER, DB_PASSWORD, DB_NAME
   docker compose up -d      # ou : podman compose up -d
   uv run alembic upgrade head
   ```

   Le service déclare un *healthcheck* : `up -d` ne rend la main qu'une fois Postgres
   réellement prêt, sinon la migration qui suit échouerait (Postgres accepte les
   connexions avant d'avoir fini de s'initialiser). Les données survivent à un
   `docker compose down` ; `down -v` supprime le volume et repart d'une base vierge.

2. **Base distante du projet** : demander les credentials d'accès à `Ronan Sy`.

## Extraction des PDFs

Le module `extraction/without_ocr/` extrait le texte natif des PDFs page par page, le
stocke dans la table `page_extraction`, et calcule un score de qualité qui permet de
détecter les pages manuscrites. Le détail du pipeline et les commandes sont dans
[extraction/without_ocr/README.md](extraction/without_ocr/README.md).

### Lancer l'extraction

```bash
# 1. Renseigner la base de données et le dossier des PDFs dans .env
#    (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, PATH_TO_DATA)
# 2. Appliquer les migrations (notamment la table page_extraction)
uv run alembic upgrade head
# 3. Extraire tous les PDFs du dossier PATH_TO_DATA
uv run python -m extraction.without_ocr
```

Le script parcourt tous les PDFs de `PATH_TO_DATA`, extrait chaque page et la persiste
en base. Les PDFs déjà extraits sont ignorés (supprimer les rows existants pour
ré-extraire). À la fin il affiche un récapitulatif : nombre de PDFs traités, échecs
éventuels et identifiants des contributions créées.

Une fois l'extraction terminée, les contributions sont visibles dans l'app Gradio que
vous pouvez lancer avec :

```bash
uv run python gradio_app/app.py
```

## Analyse des thèmes

`topic-builder/` attend un CSV `id,content` en entrée. `database/export_dataset.py`
le produit depuis la base, une ligne par contribution. Le seed de démo suffit pour
l'essayer, sans avoir de PDF sous la main :

```bash
uv run python -m database.export_dataset --output topic-builder/data/cahiers/dataset.csv
```

L'`id` du document est l'`id` de la contribution. C'est ce qui permet à
`database/load_analysis.py` de rattacher les thèmes détectés à la bonne contribution
au retour de l'analyse, au lieu de les laisser orphelins. La boucle complète :

```
extraction  ->  page_extraction  ->  export_dataset  ->  topic-builder
                                                              |
                    topic / instance  <-  load_analysis  <-  taxonomy.json
                                                              instances.json
```

## Qualité et sécurité du code (pre-commit)

Les hooks [pre-commit](https://pre-commit.com/) tournent à chaque commit, et la CI
les rejoue sur chaque PR (`.github/workflows/pre-commit.yaml`). Trois familles :

- **hygiène** : espaces/fins de ligne, newline final, syntaxe YAML, résidus de merge ;
- **lint Python** : ruff avec autofix. Les règles sont déclarées dans
  `pyproject.toml` (`[tool.ruff.lint]`) : sans elles le lint suit les défauts de
  ruff, qui changent entre versions — le repo passait en 0.15 et sortait 12
  erreurs en 0.16 sans qu'une ligne de code ait bougé ;
- **sécurité** : [gitleaks](https://github.com/gitleaks/gitleaks) bloque tout secret
  (mot de passe, clé API, token) avant qu'il parte dans un repo public, et
  `check-added-large-files` refuse les fichiers > 500 Ko (dump, PDF égaré).

`pre-commit` ne fait pas partie des dépendances du projet : on le lance avec
`uvx`, qui l'installe à la volée dans un environnement isolé (`uv run pre-commit`
échoue avec `Failed to spawn: pre-commit`).

```bash
uvx pre-commit install # une fois : active les hooks à chaque commit
uvx pre-commit run --all-files # lancer manuellement sur tout le repo
uvx pre-commit autoupdate # mettre à jour les versions des hooks
```

## Tests

Deux suites, parce que `topic-builder/` est un projet uv autonome (lockfile et
dépendances séparés) qui se teste depuis son propre dossier :

```bash
uv run --extra dev pytest          # extraction/ et database/ (depuis la racine)
cd topic-builder && uv run pytest  # topic-builder/
```

La CI rejoue les deux sur chaque PR (`.github/workflows/tests.yaml`), en plus des
hooks pre-commit.
