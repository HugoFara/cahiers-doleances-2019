"""Unit tests for city extraction (regex) and end markers."""

import pytest

from extraction.without_ocr.extract_text import find_city, find_end_page, pages_de_garde


def test_find_city_nominal():
    text = "Le grand\ndébat national\nCahier citoyen\nBOURG-EN-BRESSE - 01053\n01000\n"
    assert find_city(text) == "BOURG-EN-BRESSE"


def test_find_city_case_insensitive():
    text = "cahier citoyen  \nBourg-en-Bresse - 01053\n01000"
    assert find_city(text) == "BOURG-EN-BRESSE"


def test_find_city_compound_multiple_words():
    text = "Cahier citoyen\nPONT de VAUX - 01305\n01190"
    assert find_city(text) == "PONT DE VAUX"


def test_find_city_with_hyphens():
    text = "Cahier citoyen\nSAINTE-MENEHOULD - 51435\n51800"
    assert find_city(text) == "SAINTE-MENEHOULD"


def test_find_city_absent():
    text = "A text without any city header here."
    assert find_city(text) is None


def test_find_city_missing_postal_code():
    text = "Cahier citoyen\nBOURG-EN-BRESSE - 01053\n"
    assert find_city(text) is None


def test_find_city_broken_format_no_insee_code():
    text = "Cahier citoyen\nBOURG-EN-BRESSE\n01000"
    assert find_city(text) is None  # missing hyphen + INSEE code


def test_find_city_first_match_wins():
    text = (
        "Cahier citoyen\nPREMIERE - 12345\n11111\n"
        "du contenu\n"
        "Cahier citoyen\nSECONDE - 67890\n22222\n"
    )
    assert find_city(text) == "PREMIERE"


def test_find_city_header_among_metadata_content():
    # The header may be surrounded by typed content in the first pages
    text = (
        "Le grand débat national\n"
        "Cahier citoyen\n"
        "MIRIBEL - 01269\n01750\n"
        "Some metadata after\n"
    )
    assert find_city(text) == "MIRIBEL"


def test_find_end_page_absent():
    assert find_end_page(["page1", "page2"]) is None


def test_find_end_page_first_occurrence():
    pages = ["page0", "Fin des pages écrites", "page2", "Fin des pages écrites"]
    assert find_end_page(pages) == 1


def test_find_end_page_no_noise_before():
    pages = ["page0", "page1", "page2", "Fin des pages écrites\n", "suite"]
    assert find_end_page(pages) == 3


def test_find_end_page_marker_at_start():
    pages = ["Fin des pages écrites", "page1"]
    assert find_end_page(pages) == 0


def test_find_end_page_ignores_pages_before_start():
    """La feuille de fin scannée à la place d'une page de garde n'est pas une fin."""
    pages = ["garde", "Fin des pages écrites", "écrite", "écrite", "Fin des pages écrites"]
    assert find_end_page(pages, start=2) == 4


def test_find_end_page_from_start_without_later_marker():
    pages = ["garde", "Fin des pages écrites", "écrite"]
    assert find_end_page(pages, start=2) is None


@pytest.mark.parametrize(
    ("nom", "attendu"),
    [
        ("CC_01000_190304_01053_MD_15462.pdf", 2),
        ("CO_01000_190215_D_02389.pdf", 0),
        ("CR_01150_190304_MD_02737.pdf", 0),
        ("IL_28220_190322_M_01189.pdf", 0),
        ("Cahier_citoyen_test.pdf", 2),
    ],
)
def test_les_pages_de_garde_dependent_de_la_categorie(nom, attendu):
    """Un registre a une couverture et une feuille de garde ; une lettre commence en page 1."""
    assert pages_de_garde(nom) == attendu
