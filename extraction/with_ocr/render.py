"""Rendu des pages : nom du cahier + numéro de page → image PNG.

``page_extraction.page_number`` est le numéro de page du PDF (1-indexé) :
les deux premières pages de métadonnées sont scannées elles aussi, elles ne
sont simplement pas persistées. Le rendu se fait depuis le dossier
``PATH_TO_DATA``, le même que `without_ocr`.
"""

from pathlib import Path

import pymupdf

from extraction.with_ocr.settings import settings


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
    balayer le dossier autant de fois.
    """
    global _index
    if _index is None:
        dossier = _dossier_pdf()
        if not dossier.is_dir():
            raise FileNotFoundError(f"PATH_TO_DATA directory not found: {dossier}")
        _index = {p.name: p for p in dossier.glob("*.pdf")}
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


def rendre_page(nom_pdf: str, page_number: int, dpi: int) -> bytes:
    """Rend la page ``page_number`` (1-indexée) du cahier, en PNG.

    Args:
        nom_pdf: nom du fichier du cahier, tel que porté par la base.
        page_number: numéro de page dans le PDF, à partir de 1.
        dpi: résolution du rendu.

    Returns:
        Les octets du PNG.

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
        return pix.tobytes("png")
