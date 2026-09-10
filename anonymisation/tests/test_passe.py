"""Tests de l'écriture des passages repérés."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from anonymisation.passe import detecter_tout, lire_doleances, oublier_run
from database.models import Base, Doleance, PiiSpan
from database.runs import ANONYMISATION, SEGMENTATION, creer_run

TEXTE = "Écrire à jean.martin@example.fr pour la suite du dossier municipal."


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _activer_les_fk(connexion, _):
        connexion.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def decoupage(session) -> int:
    return creer_run(session, SEGMENTATION, label="test").id


@pytest.fixture
def run(session) -> int:
    return creer_run(session, ANONYMISATION, label="formes").id


def doleance(session, run_id: int, texte: str) -> int:
    ligne = Doleance(run_id=run_id, text=texte)
    session.add(ligne)
    session.flush()
    return ligne.id


def test_ne_lit_que_les_doleances_du_decoupage_servi(session, decoupage):
    autre = creer_run(session, SEGMENTATION, label="v2", actif=False).id
    identifiant = doleance(session, decoupage, TEXTE)
    doleance(session, autre, TEXTE)
    assert lire_doleances(session, decoupage) == {identifiant: TEXTE}


def test_ecrit_des_offsets_pas_du_texte(session, decoupage, run):
    """La table ne doit contenir aucun extrait : c'est ce qui rend la source
    corrigeable et le caviardage rejouable."""
    identifiant = doleance(session, decoupage, TEXTE)
    detecter_tout(session, run, {identifiant: TEXTE})
    session.flush()

    passage = session.query(PiiSpan).filter_by(kind="email").one()
    assert TEXTE[passage.start : passage.end] == "jean.martin@example.fr"
    assert not any(isinstance(v, str) and "@" in v for v in vars(passage).values())


def test_compte_les_passages_par_genre(session, decoupage, run):
    identifiant = doleance(session, decoupage, TEXTE)
    comptes = detecter_tout(session, run, {identifiant: TEXTE})
    assert comptes == {"email": 1}


def test_la_relecture_est_vide_au_depart(session, decoupage, run):
    """`confirmed` à NULL : la file de relecture, c'est cela."""
    identifiant = doleance(session, decoupage, TEXTE)
    detecter_tout(session, run, {identifiant: TEXTE})
    session.flush()
    assert session.query(PiiSpan).one().confirmed is None


def test_oublier_un_run_ne_touche_pas_les_autres(session, decoupage, run):
    autre = creer_run(session, ANONYMISATION, label="avec NER", actif=False).id
    identifiant = doleance(session, decoupage, TEXTE)
    detecter_tout(session, run, {identifiant: TEXTE})
    detecter_tout(session, autre, {identifiant: TEXTE})
    session.flush()

    oublier_run(session, run)
    assert [p.run_id for p in session.query(PiiSpan)] == [autre]


def test_aucune_doleance(session, decoupage, run):
    assert detecter_tout(session, run, {}) == {}
