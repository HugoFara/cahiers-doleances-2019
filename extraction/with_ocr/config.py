"""Configuration métier de la passe OCR (constantes et consigne).

Distinct de ``settings.py`` (qui lit l'environnement) : on trouve ici les
paramètres de la passe, ceux que le run doit porter dans `run.parameters`
pour pouvoir être rejouée et jugée.
"""

import enum


class OcrConfig(enum.Enum):
    """Paramètres de la passe OCR, accédés via ``.value``."""

    # Rendu de la page avant envoi. 300 DPI est le compromis mesuré à
    # l'essai du 2026-09-10 : scan lisible, ~1-2 Mo par page.
    DPI = 300

    # Backend mistral : modèle OCR de la Plateforme.
    MISTRAL_MODEL = "mistral-ocr-latest"
    # Prix catalogue 2026-09, USD par tranche de 1 000 pages (batch : moitié,
    # endpoint régional UE : +10 %). Sert à l'estimation affichée en fin de
    # passe, pas à la facturation.
    MISTRAL_PRICE_PER_1000_PAGES = 4.0
    MISTRAL_TIMEOUT_S = 180
    # Mode batch : l'API accepte des fichiers JSONL de 512 Mo au plus, une
    # requête par ligne (image en base64) ; on reste sous la limite avec
    # de la marge. Les jobs aboutissent en général en moins d'une heure,
    # au plus dans les 24 h : on les interroge toutes les minutes.
    MISTRAL_BATCH_FILE_MAX_BYTES = 400 * 1024 * 1024
    MISTRAL_BATCH_POLL_S = 60

    # Backend ollama : modèle local par défaut, léger et spécialisé OCR.
    OLLAMA_MODEL = "glm-ocr"
    # L'image seule consomme ~4 000 tokens : sous 8 192, une page A4 à
    # 300 DPI ne passe pas (erreur 4096 mesurée sur ornith-1.5). Sans GPU,
    # une page peut prendre des minutes : le timeout est large.
    OLLAMA_NUM_CTX = 16384
    OLLAMA_TIMEOUT_S = 1800
    # Consigne de transcription diplomatique : ne rien corriger, ne rien
    # commenter. Elle va dans `run.parameters`.
    OLLAMA_PROMPT = (
        "Transcris intégralement le texte de cette image d'un document "
        "d'archives. Conserve l'orthographe, la ponctuation et les sauts de "
        "ligne d'origine. Ne corrige rien, n'ajoute aucun commentaire ni "
        "texte d'introduction : ne produis que la transcription."
    )

    RETRIES = 2

    # Page « typée » dont le score reste sous ce seuil : suspecte d'être un
    # manuscrit sur formulaire pré-imprimé. pymupdf n'y lit que le pré-imprimé
    # (les pointillés), mais le texte imprimé pousse `needs_ocr` au-dessus de
    # 0,3 — fuite mesurée à l'essai du 2026-09-10 (2 pages « typées » sur 15).
    SUSPECT_QUALITY = 0.6

    # Commite toutes les N pages : la passe séquentielle du corpus prend des
    # heures, une interruption ne doit rien perdre (`--run-id` reprend).
    COMMIT_EVERY = 20
