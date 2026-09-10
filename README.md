# Cahiers de doléances

Projet Data For Good : Outil de découverte, visualisation et annotation des thèmes abordés dans des cahiers de doléances.
Les contributions extraites des PDF sont stockées en base PostgreSQL ; une app Gradio permet
de les parcourir commune par commune et de les annoter (anonymisé, contribution d'intérêt).

## Organisation

- `database/` : le modèle de données et les migrations qui structurent la base PostgreSQL | [documentation](database/README.md)
- `extraction/` : les pipelines d'extraction de texte depuis les PDFs
  - `extraction/without_ocr/` : extraction du texte natif, sans OCR | [documentation](extraction/without_ocr/README.md)
- `segmentation/` : le découpage des cahiers en doléances individuelles | [documentation](segmentation/README.md)
- `couverture/` : ce que le corpus analysé laisse dehors | [documentation](couverture/README.md)
- `insee/` : le rattachement des contributions au code INSEE de leur commune, et le référentiel géographique | [documentation](insee/README.md)
- `doublons/` : les textes qui reviennent — tracts, lettres-types, campagnes | [documentation](doublons/README.md)
- `typologie/` : ce qu'est une doléance — genre de document, genre d'auteur | [documentation](typologie/README.md)
- `anonymisation/` : le repérage des passages personnels | [documentation](anonymisation/README.md)
- `taxonomie/` : ce que vaut une grille de thèmes | [documentation](taxonomie/README.md)
- `reference/` : le jeu de référence annoté à la main, et la mesure de ce que valent les couches | [documentation](reference/README.md)
- `gradio_app/` : l'interface pour parcourir les contributions et les annoter | [documentation](gradio_app/README.md)
- `topic-builder/` : l'utilitaire de découverte, structuration et annotation des thèmes abordés dans les contributions | [documentation](topic-builder/README.md)
- `docs/` : les notes de cadrage — [le plan d'après-OCR](docs/plan_post_ocr.md) et le
  [journal des décisions](docs/journal_des_decisions.md)

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

## Ce que le corpus analysé contient

Avant tout comptage : **47 % des pages du corpus sont écartées** par le filtre
`needs_ocr`, c'est-à-dire l'écriture manuscrite. Trente-sept communes n'ont
aucune page lisible. Le corpus analysé jusqu'ici est sa moitié dactylographiée —
lettres de maires, associations, textes tapés.

```bash
uv run python -m insee rattacher   # d'abord : identifier les communes par leur code
uv run python -m insee cog         # puis : population, pour pondérer
uv run python -m couverture        # le chiffre, avec sa sensibilité au seuil
```

Le rattachement INSEE vient en premier parce qu'il change le compte : la commune
n'était identifiée que par la graphie de son en-tête, absente sur un tiers des
cahiers. 459 communes par code contre 307 par graphie — voir
[insee/README.md](insee/README.md).

La population change la lecture une seconde fois : les 37 communes muettes ne
pèsent que **4 % des habitants**, parce que ce sont les petites. Les deux
chiffres se publient ensemble — l'un seul exagère la perte de volume, l'autre
seul masque que ce sont toujours les mêmes communes qui disparaissent.

Détail et méthode dans [couverture/README.md](couverture/README.md). Ce taux doit
accompagner toute statistique tirée du corpus, sans quoi elle se lit comme
portant sur l'ensemble.

## Découpage en doléances

Une contribution, dans le pipeline actuel, c'est **une page** — or une page de
registre porte souvent plusieurs contributeurs, et une doléance longue court sur
deux pages. `segmentation/` découpe le texte des cahiers en doléances
individuelles, la vraie unité d'analyse, et les stocke dans la table `doleance` :

```bash
uv run alembic upgrade head                          # crée les tables doleance et run
uv run python -m segmentation --auteur "prénom nom"  # découpe les cahiers
```

Le découpage est heuristique et **versionné** : il appartient à la couche
d'annotation, pas au squelette du corpus, donc deux découpages peuvent coexister
et se comparer (`--nouveau-run`). Ses règles et leurs limites sont documentées
dans [segmentation/README.md](segmentation/README.md).

## Doublons

Les registres portent des tracts collés et des lettres-types recopiées, qui
gonflent les fréquences de thèmes si on les compte comme autant de contributions
distinctes :

```bash
uv run python -m doublons --auteur "prénom nom"
```

13 groupes, 33 doléances sur 1 002 (3 %). Rien n'est supprimé : « ce texte
apparaît dans six communes » est un résultat, pas du bruit. C'est d'ailleurs
ainsi qu'on a découvert que la lettre du Président de la République figure encore
dans onze doléances — voir [doublons/README.md](doublons/README.md).

## Typologie : ce qu'est une doléance avant ce qu'elle dit

Un mot d'habitant, une motion de conseil municipal et le courrier par lequel la
mairie transmet le cahier ne pèsent pas pareil, et les compter ensemble fausse
tout :

```bash
uv run python -m typologie
```

Deux axes — le support et l'auteur — posés par des règles de forme, versionnés
par un run. Le résultat déplace le corpus : **une doléance sur cinq n'est pas une
contribution** (181 illisibles, 24 pages de transmission), la première personne
ne marque que 24 % des doléances mais 48 % des mots, et huit pétitions pèsent 4 %
du corpus. Ces règles ne lisent que le texte, jamais la mise en page ni
l'écriture, et rien n'est vérifié — voir
[typologie/README.md](typologie/README.md).

## Mesurer le découpage

Les runs permettent de faire coexister deux découpages ; encore faut-il un
étalon pour dire lequel vaut mieux. `reference/` tire un échantillon stratifié
de cahiers, produit un fichier à annoter à la main, et mesure le découpage servi
contre ces annotations :

```bash
uv run python -m reference --nom v1 tirer --taille 60  # échantillon à annoter
uv run python -m reference --nom v1 figer              # étalon commitable
uv run python -m reference --nom v1 evaluer            # précision, rappel, WindowDiff
```

Le fichier à annoter porte le texte des cahiers et reste dans `data/`, ignoré par
git ; l'étalon figé n'en garde que des empreintes, ce qui le rend versionnable
sans publier d'écrits nominatifs. Détail dans
[reference/README.md](reference/README.md).

## Analyse des thèmes

`topic-builder/` attend un CSV `id,content` en entrée. `database/export_dataset.py`
le produit depuis la base, à deux niveaux :

```bash
# une ligne par contribution (= une page)
uv run python -m database.export_dataset --output topic-builder/data/cahiers/dataset.csv
# une ligne par doléance (= ce qu'a écrit une personne) — à préférer
uv run python -m database.export_dataset --niveau doleance --output topic-builder/data/cahiers/dataset.csv
```

Comme le découpage, les grilles de thèmes sont versionnées : charger une
livraison ne détruit plus la précédente, plusieurs grilles concurrentes
coexistent et l'app sert celle qui est active (voir
[database/README.md](database/README.md)).

L'`id` du document est la clé primaire de la ligne exportée : `42` pour une
contribution, `d42` pour une doléance. C'est ce qui permet à
`database/load_analysis.py` de rattacher les thèmes détectés à la bonne ligne au
retour de l'analyse, au lieu de les laisser orphelins — et le préfixe évite que
les deux plages d'id, qui se recouvrent, soient confondues. La boucle complète :

```
extraction  ->  page_extraction  ->  segmentation  ->  doleance
                                                          |
                                                    export_dataset  ->  topic-builder
                                                                              |
                          topic / instance  <-  load_analysis  <-  taxonomy.json
                                                                   instances.json
```

## Données personnelles

```bash
uv run python -m anonymisation --auteur "prénom nom"
uv sync --extra ner && uv run python -m anonymisation --ner   # + entités nommées, en local
```

**97 % des doléances contiennent au moins un passage repéré** : nom, courriel,
téléphone, adresse, et depuis le 11 septembre 2026 les noms cités au fil du
texte, par un modèle d'entités nommées qui tourne sur la machine (rien ne
sort). Ce n'est pas une anonymisation : le rappel n'est pas mesuré, et rien
n'est occulté sur les images. Rien ici ne permet de déclarer une doléance
publiable ; voir [anonymisation/README.md](anonymisation/README.md) pour ce
qui manque.

La table ne contient que des offsets — le texte d'origine reste intact et fait
foi, le caviardage est produit à la lecture.

## Mesurer une grille de thèmes

```bash
uv run python -m taxonomie
```

Sur la grille livrée en août : **76 % des thèmes attestés ne le sont que par un
seul document**, et 35 % de la grille n'a aucune détection. Un thème attesté une
fois est la paraphrase d'un document, pas un thème. Ces mesures ne disent pas si
une grille est bonne — elles disent ce qu'elle fait, ce qui permet de comparer
deux grilles au lieu de relancer des passes de factorisation à l'aveugle. Voir
[taxonomie/README.md](taxonomie/README.md).

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
