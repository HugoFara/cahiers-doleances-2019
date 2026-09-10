"""Tests de l'écriture des groupes de doublons."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from database.models import (
    Base,
    City,
    Contribution,
    Doleance,
    DuplicateGroup,
    DuplicateMember,
)
from database.runs import DOUBLONS, SEGMENTATION, creer_run
from doublons.groupes import Groupe
from doublons.persistance import (
    communes_des_doleances,
    enregistrer,
    lire_doleances,
    oublier_run,
)


@pytest.fixture
def session() -> Session:
    """SQLite avec les clés étrangères appliquées : un membre ne peut pas
    précéder son groupe, ce que PostgreSQL refuserait."""
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
    return creer_run(session, DOUBLONS, label="seuil 0.8").id


def doleance(session, run_id: int, texte: str, contribution_id: int | None = None) -> int:
    ligne = Doleance(run_id=run_id, text=texte, contribution_id=contribution_id)
    session.add(ligne)
    session.flush()
    return ligne.id


# --- lecture ---


def test_ne_lit_que_les_doleances_du_decoupage_servi(session, decoupage):
    autre = creer_run(session, SEGMENTATION, label="v2", actif=False).id
    a = doleance(session, decoupage, "servi")
    doleance(session, autre, "ancien")
    assert lire_doleances(session, decoupage) == {a: "servi"}


@pytest.mark.parametrize("vide", ["", "   "])
def test_ecarte_les_doleances_sans_texte(session, decoupage, vide):
    """Sans ce filtre, tous les textes vides formeraient un groupe géant."""
    doleance(session, decoupage, vide)
    assert lire_doleances(session, decoupage) == {}


def test_les_communes_viennent_du_code_insee(session, decoupage):
    """Le code, pas la graphie : lui seul dit si un texte a circulé entre communes."""
    session.add(City(code="17452", name="TRIZAY", department="17"))
    contribution = Contribution(pdf_file="c.pdf", city="TRIZAY", city_code="17452")
    session.add(contribution)
    session.flush()
    identifiant = doleance(session, decoupage, "un texte", contribution.id)
    assert communes_des_doleances(session, decoupage) == {identifiant: "17452"}


def test_une_doleance_non_rattachee_n_a_pas_de_commune(session, decoupage):
    contribution = Contribution(pdf_file="c.pdf", city_code=None)
    session.add(contribution)
    session.flush()
    doleance(session, decoupage, "un texte", contribution.id)
    assert communes_des_doleances(session, decoupage) == {}


# --- écriture ---


def test_ecrit_un_groupe_et_ses_membres(session, decoupage, run):
    a = doleance(session, decoupage, "un tract")
    b = doleance(session, decoupage, "un tract")
    total = enregistrer(session, run, [Groupe((a, b), 0.95)], {a: "17452", b: "17168"})
    session.flush()

    groupe = session.query(DuplicateGroup).one()
    assert (total, groupe.size, groupe.cities) == (2, 2, 2)
    assert groupe.similarity_min == 0.95
    assert session.query(DuplicateMember).count() == 2


def test_compte_les_communes_distinctes_pas_les_membres(session, decoupage, run):
    """Le même tract recopié trois fois dans une seule commune, ce n'est pas
    une campagne : `cities` est ce qui distingue les deux situations."""
    ids = [doleance(session, decoupage, "un tract") for _ in range(3)]
    enregistrer(session, run, [Groupe(tuple(ids), 1.0)], dict.fromkeys(ids, "17452"))
    session.flush()
    assert session.query(DuplicateGroup).one().cities == 1


def test_un_membre_sans_commune_ne_compte_pas_pour_une(session, decoupage, run):
    ids = [doleance(session, decoupage, "un tract") for _ in range(2)]
    enregistrer(session, run, [Groupe(tuple(ids), 1.0)], {ids[0]: "17452"})
    session.flush()
    assert session.query(DuplicateGroup).one().cities == 1


def test_aucun_groupe_n_ecrit_rien(session, decoupage, run):
    assert enregistrer(session, run, [], {}) == 0
    assert session.query(DuplicateGroup).count() == 0


# --- rejouer ---


def test_oublier_un_run_ne_touche_pas_les_autres(session, decoupage, run):
    a = doleance(session, decoupage, "un tract")
    b = doleance(session, decoupage, "un tract")
    autre = creer_run(session, DOUBLONS, label="seuil 0.6", actif=False).id
    enregistrer(session, run, [Groupe((a, b), 0.95)], {})
    enregistrer(session, autre, [Groupe((a, b), 0.62)], {})
    session.flush()

    oublier_run(session, run)

    assert [g.run_id for g in session.query(DuplicateGroup)] == [autre]
    assert session.query(DuplicateMember).count() == 2


def test_oublier_un_run_emporte_ses_membres(session, decoupage, run):
    a = doleance(session, decoupage, "un tract")
    b = doleance(session, decoupage, "un tract")
    enregistrer(session, run, [Groupe((a, b), 0.95)], {})
    session.flush()
    oublier_run(session, run)
    assert session.query(DuplicateMember).count() == 0
