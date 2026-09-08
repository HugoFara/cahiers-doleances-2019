"""Tests du seed de démonstration."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database import seed_mock
from database.models import Base, Contribution, Extraction, Instance, PageExtraction, Topic


@pytest.fixture
def engine(monkeypatch):
    """Redirige le seed vers une base SQLite en mémoire.

    L'engine doit être le même objet à chaque appel, sinon chaque `create_engine`
    ouvrirait une base en mémoire distincte et vide.
    """
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(seed_mock, "get_engine", lambda: engine)
    return engine


def test_le_seed_remplit_les_tables_attendues(engine):
    seed_mock.main()
    with Session(engine) as session:
        assert session.query(Contribution).count() == len(seed_mock.MOCK)
        assert session.query(Extraction).count() == len(seed_mock.MOCK)
        assert session.query(Instance).count() > 0
        assert session.query(Topic).count() > 0


def test_le_seed_remplit_page_extraction(engine):
    """C'est la table que lit export_dataset : sans elle, la chaîne d'analyse
    n'est pas exerçable depuis le seul seed de démo."""
    seed_mock.main()
    with Session(engine) as session:
        pages = session.query(PageExtraction).all()
        assert len(pages) == len(seed_mock.MOCK)
        assert all(p.contribution_id is not None for p in pages)
        assert all(p.text for p in pages)


def test_le_seed_alimente_l_export_du_dataset(engine):
    """Test de bout en bout du chaînage seed -> export."""
    from database.export_dataset import construire_documents, lire_pages

    seed_mock.main()
    with Session(engine) as session:
        documents = construire_documents(lire_pages(session))

    assert len(documents) == len(seed_mock.MOCK)
    ids_contributions = {str(c.id) for c in Session(engine).query(Contribution).all()}
    assert {d["id"] for d in documents} == ids_contributions


def test_le_seed_refuse_de_tourner_deux_fois(engine):
    """Les ids sont auto-incrémentés : un second passage dupliquerait tout."""
    seed_mock.main()
    with pytest.raises(SystemExit):
        seed_mock.main()
