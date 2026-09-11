"""Les backends OCR : Mistral (API cloud) et Ollama (local).

Même contrat des deux côtés : ``transcrire(image, format) -> OcrResult``. Mistral rend
la géométrie ligne à ligne (`layout`) — le préalable du plan, sans lequel ni
découpage sur le blanc vertical, ni verbatim lié au scan, ni occultation sur
l'image. Ollama ne rend que du texte : son `layout` reste NULL.
"""

import base64
import time
from dataclasses import dataclass

import requests

from extraction.with_ocr.config import OcrConfig
from extraction.with_ocr.settings import logger, settings


@dataclass
class OcrResult:
    """Ce qu'un backend rend pour une page.

    Attributes:
        texte: texte brut du backend, avant normalisation.
        layout: lignes avec coordonnées, quand le backend les donne.
        duree_s: temps d'appel, pour le bilan de la passe.
    """

    texte: str
    layout: list[dict] | None = None
    duree_s: float = 0.0


class ErreurOcr(RuntimeError):
    """Le backend a répondu en erreur, après épuisement des tentatives."""


class MistralBackend:
    """Mistral OCR via la Plateforme (``mistral-ocr-latest``).

    Facturé à la page (~4 $ / 1 000 pages au tarif 2026-09, moitié en batch) :
    la passe affiche son coût estimé en bilan. Envoyer les scans bruts à
    l'API est la question P3 du plan (hébergement d'opinions politiques
    nominatives) — à trancher avant la passe complète, voir
    `docs/plan_post_ocr.md`.
    """

    nom = "mistral"

    def __init__(
        self,
        model: str | None = None,
        url: str | None = None,
        api_key: str | None = None,
    ):
        self.model = model or OcrConfig.MISTRAL_MODEL.value
        self.url = url or settings.mistral_ocr_url
        self.api_key = api_key if api_key is not None else settings.mistral_api_key
        if not self.api_key:
            raise ValueError(
                "MISTRAL_API_KEY manquante dans .env — backend mistral inutilisable"
            )

    def transcrire(self, image: bytes, format: str = "png") -> OcrResult:
        """Transcrit une page rendue en image (``png`` ou ``jpeg``).

        Raises:
            ErreurOcr: toutes les tentatives ont échoué.
        """
        b64 = base64.b64encode(image).decode()
        payload = {
            "model": self.model,
            "document": {
                "type": "image_url",
                "image_url": f"data:image/{format};base64,{b64}",
            },
            "include_image_base64": False,
        }
        t0 = time.time()
        derniere = ""
        for tentative in range(OcrConfig.RETRIES.value):
            try:
                reponse = requests.post(
                    self.url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                    timeout=OcrConfig.MISTRAL_TIMEOUT_S.value,
                )
                if reponse.status_code == 200:
                    return self._depouiller(reponse.json(), time.time() - t0)
                derniere = f"HTTP {reponse.status_code} : {reponse.text[:200]}"
            except requests.RequestException as exc:
                derniere = str(exc)[:200]
            logger.warning("Mistral OCR, tentative %d : %s", tentative + 1, derniere)
        raise ErreurOcr(
            f"Mistral OCR en échec après {OcrConfig.RETRIES.value} tentatives : {derniere}"
        )

    @staticmethod
    def _depouiller(data: dict, duree: float) -> OcrResult:
        """Texte ordonné, et lignes avec polygones quand il y en a."""
        textes: list[str] = []
        layout: list[dict] = []
        for page in data.get("pages", []):
            lignes = page.get("lines")
            if lignes:
                for ligne in lignes:
                    textes.append(ligne.get("text", ""))
                    layout.append(ligne)
            elif "markdown" in page:
                textes.append(page["markdown"])
        return OcrResult(
            texte="\n".join(textes),
            layout=layout or None,
            duree_s=round(duree, 2),
        )


class OllamaBackend:
    """Modèle de vision local servi par Ollama (glm-ocr, qwen3-vl, ornith…).

    Zéro coût, aucune donnée ne quitte la machine — mais sans GPU compter en
    minutes par page (207 s mesurées sur ornith-1.5:9b, CPU seul). Le contexte
    doit contenir l'image (~4 000 tokens pour un A4 à 300 DPI) : `num_ctx`
    est monté en conséquence.
    """

    nom = "ollama"

    def __init__(
        self,
        model: str | None = None,
        url: str | None = None,
        num_ctx: int | None = None,
        timeout_s: int | None = None,
    ):
        self.model = model or OcrConfig.OLLAMA_MODEL.value
        self.url = (url or settings.ollama_url).rstrip("/")
        self.num_ctx = num_ctx or OcrConfig.OLLAMA_NUM_CTX.value
        self.timeout_s = timeout_s or OcrConfig.OLLAMA_TIMEOUT_S.value

    def transcrire(self, image: bytes, format: str = "png") -> OcrResult:
        """Transcrit une page rendue en image (le format est indifférent ici).

        Raises:
            ErreurOcr: toutes les tentatives ont échoué.
        """
        b64 = base64.b64encode(image).decode()
        payload = {
            "model": self.model,
            "prompt": OcrConfig.OLLAMA_PROMPT.value,
            "images": [b64],
            "stream": False,
            "options": {"num_ctx": self.num_ctx},
        }
        t0 = time.time()
        derniere = ""
        for tentative in range(OcrConfig.RETRIES.value):
            try:
                reponse = requests.post(
                    f"{self.url}/api/generate",
                    json=payload,
                    timeout=self.timeout_s,
                )
                if reponse.status_code == 200:
                    return OcrResult(
                        texte=reponse.json().get("response", ""),
                        duree_s=round(time.time() - t0, 2),
                    )
                derniere = f"HTTP {reponse.status_code} : {reponse.text[:200]}"
            except requests.RequestException as exc:
                derniere = str(exc)[:200]
            logger.warning("Ollama, tentative %d : %s", tentative + 1, derniere)
        raise ErreurOcr(
            f"Ollama en échec après {OcrConfig.RETRIES.value} tentatives : {derniere}"
        )


def fabrique_backend(backend: str, model: str | None = None):
    """Le backend demandé par la ligne de commande.

    Raises:
        ValueError: backend inconnu, ou clé API manquante pour mistral.
    """
    if backend == MistralBackend.nom:
        return MistralBackend(model=model)
    if backend == OllamaBackend.nom:
        return OllamaBackend(model=model)
    raise ValueError(f"backend inconnu : {backend!r} (mistral | ollama)")
