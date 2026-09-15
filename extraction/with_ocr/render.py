"""Rendu des pages : nom du cahier + numéro de page → image PNG.

``page_extraction.page_number`` est le numéro de page du PDF (1-indexé) :
les deux premières pages de métadonnées sont scannées elles aussi, elles ne
sont simplement pas persistées. Le rendu se fait depuis le dossier
``PATH_TO_DATA``, le même que `without_ocr`.
"""

from pathlib import Path

import pymupdf

from extraction.with_ocr.settings import settings
from extraction.without_ocr import discovery


class PdfIntrouvable(FileNotFoundError):
    """Le PDF du cahier est absent de PATH_TO_DATA."""


_index: dict[str, Path] | None = None


def _dossier_pdf() -> Path:
    raw = settings.path_to_data
    if not raw:
        raise ValueError(
            "PATH_TO_DATA is not set. Add it to your .env file "
            "(`PATH_TO_DATA=/path/to/pdfs`)."
        )
    return Path(raw)


def index_pdfs() -> dict[str, Path]:
    """Index des PDFs de PATH_TO_DATA, par nom de fichier.

    Construit une fois par passe : les lignes `page_extraction` ne portent
    que le nom, et chercher sur disque à chacune des 2 510 lignes serait
    balayer le dossier autant de fois. L'arborescence est celle que
    `without_ocr` parcourt — plate ou celle du versement BnF.
    """
    global _index
    if _index is None:
        _index = discovery.index_pdfs(_dossier_pdf())
    return _index


def reinitialiser_index() -> None:
    """Oublie l'index construit — sert aux tests qui changent de dossier."""
    global _index
    _index = None


def trouver_pdf(nom: str) -> Path:
    """Le chemin du cahier nommé, ou lève ``PdfIntrouvable``."""
    chemin = index_pdfs().get(nom)
    if chemin is None:
        raise PdfIntrouvable(f"{nom} absent de PATH_TO_DATA")
    return chemin


FORMATS = ("png", "jpeg")
JPEG_QUALITY = 85


def rendre_page(
    nom_pdf: str, page_number: int, dpi: int, format: str = "png"
) -> bytes:
    """Rend la page ``page_number`` (1-indexée) du cahier, en image.

    Les scans embarqués dans les PDF sont des JPEG 2000 d'environ 1 250 px de
    large — ~150 DPI pour un A4 : au-delà, le rendu sur-échantillonne. En PNG
    à 300 DPI une page pèse 1 à 13 Mo (mesuré le 2026-09-11), en JPEG à 85
    dix fois moins : c'est ce qui rend l'envoi en batch praticable.

    Args:
        nom_pdf: nom du fichier du cahier, tel que porté par la base.
        page_number: numéro de page dans le PDF, à partir de 1.
        dpi: résolution du rendu.
        format: ``png`` (sans perte) ou ``jpeg`` (qualité 85).

    Returns:
        Les octets de l'image.

    Raises:
        PdfIntrouvable: le cahier est absent de PATH_TO_DATA.
        ValueError: la page est hors des limites du PDF.
    """
    chemin = trouver_pdf(nom_pdf)
    with pymupdf.open(chemin) as doc:
        if not 1 <= page_number <= doc.page_count:
            raise ValueError(
                f"{nom_pdf}: page {page_number} hors limites (1-{doc.page_count})"
            )
        pix = doc[page_number - 1].get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72))
        if format == "jpeg":
            return pix.tobytes("jpeg", jpg_quality=JPEG_QUALITY)
        if format == "png":
            return pix.tobytes("png")
        raise ValueError(f"format inconnu : {format!r} (attendu : {', '.join(FORMATS)})")
