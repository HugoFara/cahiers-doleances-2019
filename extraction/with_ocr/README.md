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
```

Périmètres (`--perimetre`) : `manuscrit` (défaut — les pages `needs_ocr`),
`typé`, `suspect` (typé sous le seuil de qualité : les formulaires
pré-imprimés remplis à la main que `needs_ocr` manque — fuite mesurée le
2026-09-10, 2 pages « typées » sur 15), `tout`.

La passe commite toutes les 20 pages et se reprend par `--run-id` : les pages
déjà transcrites du run sont sautées, l'unicité (run, page) l'interdit en
base. Une page en échec est loggée et sautée, la passe continue.

## Ce qu'elle produit

Un run de genre `transcription` (`database/runs.py`) et ses lignes
`page_transcription` : texte normalisé (syntaxe markdown retirée,
**orthographe intacte** — version diplomatique), géométrie ligne à ligne
quand le backend la donne, score wordfreq de la transcription. Le texte de
`page_extraction` n'est pas touché : deux passes — deux modèles, deux DPI —
coexistent et se comparent, et retirer l'une ne casse rien.

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

## Tests

```bash
uv run --extra dev pytest extraction/with_ocr/tests/
```

Unitaires, sans réseau ni base : normalisation, rendu (PDF fabriqué),
parsing des réponses de backends (requêtes bouchonnées), périmètres et
reprise sur SQLite en mémoire.
