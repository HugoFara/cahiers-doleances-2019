"""La persistance : périmètres, reprise, unicité (run, page) — SQLite en mémoire."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import Base, PageExtraction, PageTranscription
from database.runs import TRANSCRIPTION
from extraction.with_ocr.persist import (
    enregistrer,
    etendre_perimetre,
    ouvrir_run,
    pages_a_transcrire,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _page(session, **champs) -> PageExtraction:
    defauts = {
        "pdf_name": "CC_01000_190304_01053_MD_15462.pdf",
        "page_number": 3,
        "text": "du texte",
        "quality_score": 0.9,
        "needs_ocr": False,
    }
    page = PageExtraction(**(defauts | champs))
    session.add(page)
    session.flush()
    return page


def _run(session) -> int:
    run = ouvrir_run(
        session,
        backend="mistral",
        model="mistral-ocr-latest",
        dpi=300,
        perimetre="tout",
    )
    session.flush()
    return run


def test_le_perimetre_manuscrit_ne_prend_que_needs_ocr(session):
    _page(session, needs_ocr=True)
    _page(session, needs_ocr=False, page_number=4)
    run = _run(session)
    pages = pages_a_transcrire(session, run, "manuscrit")
    assert [p.needs_ocr for p in pages] == [True]


def test_le_perimetre_suspect_prend_le_type_mal_note(session):
    _page(session, needs_ocr=False, quality_score=0.9)
    suspecte = _page(session, needs_ocr=False, quality_score=0.44, page_number=4)
    run = _run(session)
    pages = pages_a_transcrire(session, run, "suspect")
    assert [p.id for p in pages] == [suspecte.id]


def test_le_perimetre_tout_prend_tout(session):
    _page(session, needs_ocr=True)
    _page(session, needs_ocr=False, page_number=4)
    run = _run(session)
    assert len(pages_a_transcrire(session, run, "tout")) == 2


def test_un_perimetre_inconnu_leve_value_error(session):
    run = _run(session)
    with pytest.raises(ValueError, match="périmètre inconnu"):
        pages_a_transcrire(session, run, "manuscrits")


def test_la_limite_borne_le_tirage(session):
    for numero in range(5):
        _page(session, needs_ocr=True, page_number=numero + 3)
    run = _run(session)
    assert len(pages_a_transcrire(session, run, "manuscrit", limite=2)) == 2


def test_une_page_deja_transcrite_est_sautee(session):
    """C'est ce qui rend la passe reprenable après interruption."""
    page = _page(session, needs_ocr=True)
    run = _run(session)
    enregistrer(session, run, page, "transcription", None, 0.9)
    session.flush()
    assert pages_a_transcrire(session, run, "manuscrit") == []


def test_une_page_ne_peut_pas_etre_transcrite_deux_fois_dans_un_run(session):
    page = _page(session, needs_ocr=True)
    run = _run(session)
    enregistrer(session, run, page, "première", None, 0.9)
    enregistrer(session, run, page, "seconde", None, 0.9)
    with pytest.raises(IntegrityError):
        session.flush()


def test_deux_runs_peuvent_transcrire_la_meme_page(session):
    """Deux passes — deux modèles — coexistent et se comparent."""
    page = _page(session, needs_ocr=True)
    run_a = _run(session)
    run_b = ouvrir_run(
        session,
        backend="ollama",
        model="glm-ocr",
        dpi=300,
        perimetre="tout",
        prompt="consigne",
    )
    session.flush()
    enregistrer(session, run_a, page, "par mistral", [{"text": "par mistral"}], 0.9)
    enregistrer(session, run_b, page, "par glm-ocr", None, 0.85)
    session.flush()
    assert session.query(PageTranscription).count() == 2


def test_le_run_porte_les_parametres_de_la_passe(session):
    run = ouvrir_run(
        session,
        backend="ollama",
        model="qwen3-vl:32b",
        dpi=200,
        perimetre="manuscrit",
        prompt="consigne",
    )
    session.flush()
    assert run.kind == TRANSCRIPTION
    assert run.model == "ollama:qwen3-vl:32b"
    assert run.parameters["dpi"] == 200
    assert run.parameters["prompt"] == "consigne"
    assert run.author  # résolu d'office — un run anonyme ne se discute pas


# --- périmètre étendu ---


def test_un_perimetre_composite_prend_l_union(session):
    run = _run(session)
    _page(session, page_number=3, needs_ocr=True)
    _page(session, page_number=4, needs_ocr=False, quality_score=0.4)
    _page(session, page_number=5, needs_ocr=False, quality_score=0.9)
    pages = pages_a_transcrire(session, run, "manuscrit+suspect")
    assert [p.page_number for p in pages] == [3, 4]


def test_un_perimetre_composite_inconnu_leve_value_error(session):
    run = _run(session)
    with pytest.raises(ValueError, match="périmètre inconnu"):
        pages_a_transcrire(session, run, "manuscrit+ailleurs")


def test_la_reprise_etend_le_run_au_perimetre_demande(session):
    run = ouvrir_run(session, backend="ollama", model="m", dpi=300, perimetre="manuscrit")
    session.flush()
    assert etendre_perimetre(session, run, None) == "manuscrit"
    assert etendre_perimetre(session, run, "manuscrit") == "manuscrit"
    assert etendre_perimetre(session, run, "suspect") == "manuscrit+suspect"
    assert run.parameters["perimetre"] == "manuscrit+suspect"
    assert run.corpus == "manuscrit+suspect"
    # demandé une seconde fois : déjà couvert, rien ne change
    assert etendre_perimetre(session, run, "suspect") == "manuscrit+suspect"
