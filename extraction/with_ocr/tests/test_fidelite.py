"""La fidélité sur le typé : les mesures, le tirage — backend bouchonné."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.models import Base, PageExtraction
from extraction.with_ocr.backends import OcrResult
from extraction.with_ocr.fidelite import (
    CARACTERES_MIN,
    QUALITE_MIN,
    cer,
    cer_plie,
    mesurer,
    plier,
    plier_fort,
    tirer,
    wer,
)


def test_un_texte_identique_a_zero_erreur():
    assert cer("Le chat dort.", "Le chat dort.") == 0.0
    assert wer("Le chat dort.", "Le chat dort.") == 0.0


def test_l_espacement_et_les_sauts_de_ligne_ne_comptent_pas():
    assert cer("Le chat\ndort.", "Le  chat dort.") == 0.0
    assert plier("a \n\n b") == "a b"


def test_le_cer_rapporte_la_distance_a_la_reference():
    # « chat » -> « chien » : 3 éditions sur 13 caractères
    assert cer("Le chat dort.", "Le chien dort.") == pytest.approx(3 / 13)


def test_le_wer_compte_les_mots():
    assert wer("le chat dort", "le chien dort") == pytest.approx(1 / 3)
    assert wer("le chat dort", "le chat") == pytest.approx(1 / 3)


def test_le_cer_plie_ignore_accents_casse_et_ponctuation():
    assert plier_fort("Élève, très !") == "eleve tres"
    assert cer_plie("Élève, très !", "eleve tres") == 0.0
    assert cer("Élève, très !", "eleve tres") > 0


def test_une_reference_vide_est_parfaite_ou_nulle():
    assert cer("", "") == 0.0
    assert cer("", "du bruit") == 1.0


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _page(session, dept, numero, **champs):
    defauts = {
        "pdf_name": f"CC_{dept}000_190304_{dept}053_MD_{numero:05d}.pdf",
        "page_number": numero,
        "text": "x" * (CARACTERES_MIN + 10),
        "quality_score": 0.95,
        "needs_ocr": False,
    }
    page = PageExtraction(**(defauts | champs))
    session.add(page)
    session.flush()
    return page


def test_le_tirage_prend_du_type_de_bonne_couche_a_parts_egales(session):
    for i in range(1, 6):
        _page(session, "01", i)
        _page(session, "28", 10 + i)
    _page(session, "01", 50, needs_ocr=True)  # manuscrit : exclu
    _page(session, "01", 51, quality_score=QUALITE_MIN - 0.1)  # mauvaise couche
    _page(session, "01", 52, text="court")  # trop courte

    tirage = tirer(session, taille=4, graine=1)

    assert len(tirage) == 4
    assert sorted(p.pdf_name[3:5] for p in tirage) == ["01", "01", "28", "28"]
    assert all(not p.needs_ocr and p.quality_score >= QUALITE_MIN for p in tirage)
    assert [p.id for p in tirer(session, 4, graine=1)] == [p.id for p in tirage]


def test_mesurer_compare_la_transcription_a_la_couche_texte(session, monkeypatch):
    page = _page(session, "01", 1, text="Le chat dort.")

    class _Backend:
        def transcrire(self, image, format="png"):
            return OcrResult("Le chien dort.")

    monkeypatch.setattr(
        "extraction.with_ocr.fidelite.rendre_page", lambda *a, **k: b"jpeg"
    )
    score = mesurer(_Backend(), page, 300, "jpeg")
    assert score.page_id == page.id
    assert score.caracteres == 13
    assert score.cer == pytest.approx(3 / 13)
    assert score.wer == pytest.approx(1 / 3)
