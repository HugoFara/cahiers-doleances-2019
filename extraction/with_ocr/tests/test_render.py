"""Le rendu : nom du cahier + numéro de page → PNG."""

import pymupdf
import pytest

from extraction.with_ocr import render
from extraction.with_ocr.settings import settings


@pytest.fixture
def dossier_pdf(tmp_path, monkeypatch):
    """Un dossier PATH_TO_DATA avec un cahier de deux pages."""
    doc = pymupdf.open()
    for texte in ("page une", "page deux"):
        page = doc.new_page()
        page.insert_text((72, 72), texte)
    doc.save(tmp_path / "CC_01000_190304_01053_MD_15462.pdf")
    doc.close()
    monkeypatch.setattr(settings, "path_to_data", str(tmp_path))
    render.reinitialiser_index()
    yield tmp_path
    render.reinitialiser_index()


def test_rendre_page_produit_un_png(dossier_pdf):
    png = render.rendre_page("CC_01000_190304_01053_MD_15462.pdf", 1, 150)
    assert png.startswith(b"\x89PNG")
    assert len(png) > 1000


def test_le_numero_de_page_est_pris_en_compte(dossier_pdf):
    une = render.rendre_page("CC_01000_190304_01053_MD_15462.pdf", 1, 100)
    deux = render.rendre_page("CC_01000_190304_01053_MD_15462.pdf", 2, 100)
    assert une != deux


def test_un_cahier_absent_leve_pdf_introuvable(dossier_pdf):
    with pytest.raises(render.PdfIntrouvable):
        render.rendre_page("CC_inexistant.pdf", 1, 150)


def test_une_page_hors_limites_leve_value_error(dossier_pdf):
    with pytest.raises(ValueError, match="hors limites"):
        render.rendre_page("CC_01000_190304_01053_MD_15462.pdf", 3, 150)


def test_path_to_data_manquante_leve_value_error(monkeypatch):
    monkeypatch.setattr(settings, "path_to_data", "")
    render.reinitialiser_index()
    with pytest.raises(ValueError, match="PATH_TO_DATA"):
        render.index_pdfs()
    render.reinitialiser_index()
