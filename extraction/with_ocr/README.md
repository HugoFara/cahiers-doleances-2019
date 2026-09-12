# extraction/with_ocr — la transcription des pages (Mistral + Ollama)

`without_ocr` lit la couche texte des PDFs : elle donne les cahiers
dactylographiés, pas les manuscrits — **47 % des pages écartées, 37 communes
sans aucune page lisible** (`couverture/`). Ce module rend l'image de la page
depuis le PDF et la fait transcrire par un modèle OCR. C'est la couche 3 du
plan (`docs/plan_post_ocr.md`) : une lecture de l'image, versionnée par un
run, qui n'écrase jamais le squelette.

## Deux backends

- **mistral** (défaut) : l'API Mistral OCR (`mistral-ocr-latest`), facturée à
  la page (~4 $ / 1 000 pages au tarif 2026-09, moitié en batch, +10 %
  endpoint UE), en secondes par page. Seul backend testé qui rend la
  **géométrie ligne à ligne** (texte + polygones), conservée dans
  `page_transcription.layout` — le préalable du plan pour découper sur le
  blanc vertical, lier un verbatim au scan et occulter sur l'image. Demande
  `MISTRAL_API_KEY` dans `.env`.
- **ollama** : un modèle de vision local (`glm-ocr` par défaut ; `qwen3-vl`,
  `ornith-1.5`…), zéro coût, aucune donnée ne quitte la machine — mais sans
  GPU compter en minutes par page (207 s mesurées sur ornith-1.5:9b, CPU
  seul, dont la chaîne de pensée fuite et est coupée au marqueur
  `</think>`). Pas de géométrie : `layout` reste NULL.

## Lancer

```bash
uv run alembic upgrade head                        # crée page_transcription
uv run python -m extraction.with_ocr --limite 5    # essai sur 5 pages
uv run python -m extraction.with_ocr               # les 2 510 pages manuscrites
uv run python -m extraction.with_ocr --backend ollama --model glm-ocr
uv run python -m extraction.with_ocr --run-id 3    # reprend le run 3 interrompu
uv run python -m extraction.with_ocr --batch --format jpeg   # mistral à moitié prix
```

**Batch** (`--batch`, mistral seulement) : l'API prend un fichier JSONL de
requêtes, une par page, le traite dans les 24 h — moins d'une heure en
pratique — et rend un fichier de réponses, **à moitié prix**. Les fichiers
sont limités à 512 Mo : la passe découpe les pages en lots, ouvre un job par
lot, attend et persiste chaque lot quand il aboutit. Les jobs ouverts sont
notés dans `run.parameters["lots"]` et commités aussitôt : `--run-id` reprend
une passe interrompue en récoltant les lots en attente, sans rien renvoyer.
Le service demande la **facturation activée** sur le compte Mistral (HTTP 402
sinon, même quand l'OCR unitaire passe).

**Format** (`--format`) : `png` par défaut, sans perte ; `jpeg` (qualité 85)
pèse dix fois moins. Les scans embarqués dans les PDF sont des JPEG 2000 de
~1 250 px de large — ~150 DPI pour un A4 : à 300 DPI le rendu
sur-échantillonne, et en PNG une page pèse 1 à 13 Mo (mesuré le 2026-09-11).
Pour le batch, `jpeg` est ce qui rend l'envoi praticable : ~3 Go pour le
manuscrit au lieu de ~30.

Périmètres (`--perimetre`) : `manuscrit` (défaut — les pages `needs_ocr`),
`typé`, `suspect` (typé sous le seuil de qualité : les formulaires
pré-imprimés remplis à la main que `needs_ocr` manque — fuite mesurée le
2026-09-10, 2 pages « typées » sur 15), `tout`. Avec `--run-id`, un
`--perimetre` différent **étend la passe** au lieu d'en ouvrir une autre : le
run note `manuscrit+suspect`. C'est voulu — une passe est une couche, un seul
run de transcription est actif, et c'est lui que `database/pages.py` lit.

La passe commite toutes les 20 pages et se reprend par `--run-id` : les pages
déjà transcrites du run sont sautées, l'unicité (run, page) l'interdit en
base. Une page en échec est loggée et sautée, la passe continue.

**Dérives.** Un modèle local s'emballe parfois : il boucle sur une ligne ou
un mot jusqu'à produire des dizaines de milliers de caractères (13 pages sur
2 984 au run 18, jusqu'à 50 000 caractères, que le score wordfreq ne voit
pas). Trois parades, mesurées le 2026-09-12 :

- la génération est **plafonnée** (`OLLAMA_NUM_PREDICT`, 2 048 tokens : une
  page A4 manuscrite en fait moins de 1 500) — une dérive coûte trente
  secondes, pas dix minutes ;
- la dérive est un accident de tirage, pas une propriété de la page (la même
  page dérive à un appel et pas au suivant) : un résultat en dérive
  (`database.pages.est_derive`) ou arrêté par le plafond est **retiré** à
  graine fixée, `OLLAMA_RETIRAGES` fois au plus, et le premier tirage propre
  est gardé ; sinon le dernier, que la lecture écarte ;
- `--perimetre derives`, avec `--run-id`, **rejoue les pages en dérive d'un
  run** dans ce run : leurs transcriptions sont retirées, refaites, et le run
  compte ces reprises (`derives_reprises`). Un run ouvert avant le plafond le
  note à la reprise (`num_predict`, `retirages`), comme il note une extension
  de périmètre.

Une pénalité de répétition (`repeat_penalty` 1,15) a été essayée et écartée :
elle ne réduit pas les dérives et abîme le texte (sauts de ligne perdus).

## Ce qu'elle produit

Un run de genre `transcription` (`database/runs.py`) et ses lignes
`page_transcription` : texte normalisé (syntaxe markdown retirée,
**orthographe intacte** — version diplomatique), géométrie ligne à ligne
quand le backend la donne, score wordfreq de la transcription. Le texte de
`page_extraction` n'est pas touché : deux passes — deux modèles, deux DPI —
coexistent et se comparent, et retirer l'une ne casse rien.

**Et une copie en clair, sous `data/`.** La base vit dans un volume podman ;
quinze heures de GPU n'y ont pas d'autre copie. `export` dépose un run en
fichiers texte lisibles sans outil, un dossier par run, un fichier par page,
avec le run en JSON et un manifeste CSV (ids, cahier, page, score, longueur) :

```bash
uv run python -m extraction.with_ocr.export --run-id 18
# data/transcriptions/run_18_ollama-ornith-1.5-9b/<cahier>/p0007.txt
```

Incrémental : relancé sur un run qui avance, il n'écrit que les pages
nouvelles ou changées. `data/` est hors dépôt (NDA) ; ces fichiers ne sont
jamais commités.

## Mesuré à l'essai du 2026-09-10 (31 pages)

- manuscrit : wordfreq **0,13 → 0,90 ± 0,05** — Mistral OCR lit le manuscrit ;
- dactylographié : 2,9 s ± 0,8 s/page ; la couche texte des archives est
  elle-même corrompue (en-têtes notamment), l'OCR la corrige ;
- coût corpus entier : 22-26 $, ~6 h en séquentiel ;
- **wordfreq mesure la proportion de mots français connus, pas la fidélité** :
  une hallucination fluide scorerait bien. Le seul juge est l'échantillon de
  référence annoté (`reference/`) — à passer avant toute passe complète ;
- envoyer les scans bruts à une API pose la question P3 (hébergement
  d'opinions politiques nominatives) : endpoint UE, self-host, ou backend
  ollama local. À trancher avant la passe complète — voir
  `docs/plan_post_ocr.md`, section « Ce que coûte l'OCR ».

## Fidélité, là où une vérité existe

Il n'y a pas d'étalon manuscrit : personne n'a encore transcrit à la main un
échantillon de pages, et `reference/` annote des frontières de doléances,
pas du texte. `fidelite.py` mesure ce qui peut l'être aujourd'hui : sur des
pages **typées** dont la couche texte du PDF est bonne (wordfreq ≥ 0,9,
800 à 4 000 caractères), le backend transcrit l'image et on compare à la
couche, en caractères (CER) et en mots (WER), plus un CER « plié » sans
accents, casse ni ponctuation, qui isole le contenu de l'orthographe. Tirage
stratifié par département, graine fixe ; rien n'est persisté.

```bash
uv run python -m extraction.with_ocr.fidelite --backend ollama --model ornith-1.5:9b --taille 30
uv run python -m extraction.with_ocr.fidelite --pages 2709,4425     # des pages précises
```

**Mesuré le 2026-09-12, ornith-1.5:9b, 30 pages typées (67 616 caractères)** :
CER moyen **0,026**, médian 0,019, max 0,110 ; WER moyen 0,079, médian
0,074 ; CER plié moyen 0,014 — la moitié des erreurs de caractères sont
d'accent, de casse ou de ponctuation. Longueur transcrite / référence entre
0,96 et 1,02 sur toutes les pages : ni troncature, ni ajout. Sans le
retirage des dérives, le même tirage donnait un CER moyen de 0,067 à cause
de deux pages parties en boucle (0,81 et 0,57), revenues à 0,066 et 0,020
au tirage suivant — la dérive est bien un accident, et le retirage la
corrige aussi ici.

C'est une mesure sur l'imprimé, pas sur le manuscrit : elle borne ce que
le modèle, la consigne et la normalisation perdent quand la lecture est
facile. La couche texte de référence est elle-même imparfaite (en-têtes
corrompus, mesuré le 2026-09-10) : une part du 2,6 % lui revient. La
fidélité sur le manuscrit attend un étalon transcrit à la main.

## Tests

```bash
uv run --extra dev pytest extraction/with_ocr/tests/
```

Unitaires, sans réseau ni base : normalisation, rendu (PDF fabriqué),
parsing des réponses de backends (requêtes bouchonnées), périmètres et
reprise sur SQLite en mémoire, lots et récolte du mode batch (client
bouchonné), retirage des dérives, mesures de fidélité et tirage.
