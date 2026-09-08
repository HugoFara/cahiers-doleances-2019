"""Tests du chargement de la livraison de l'équipe analyse."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.load_analysis import charger_instances, resoudre_contribution
from database.models import Base, Contribution, Instance, Topic


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def document(doc_id, *noms_de_topics) -> dict:
    return {
        "id": doc_id,
        "labels": [
            {"name": nom, "extract": f"verbatim {nom}", "rationale": f"parce que {nom}"}
            for nom in noms_de_topics
        ],
    }


# --- resoudre_contribution ---


def test_resout_un_id_de_document_qui_est_un_id_de_contribution():
    """Cas des livraisons produites depuis database/export_dataset.py."""
    assert resoudre_contribution("42", {41, 42, 43}) == 42


def test_ne_resout_pas_un_id_absent_de_la_base():
    assert resoudre_contribution("99", {1, 2}) is None


@pytest.mark.parametrize("valeur", ["doc 73", "", "abc", "3.5"])
def test_ne_resout_pas_un_id_non_numerique(valeur):
    """Les livraisons antérieures numérotent les documents à leur façon."""
    assert resoudre_contribution(valeur, {1, 2, 73}) is None


# --- charger_instances ---


def test_rattache_les_instances_a_leur_contribution(session):
    session.add(Contribution(id=7, city="Trizay"))
    session.add(Topic(id=1, name="fiscalité"))
    session.flush()

    inconnus, rattachees = charger_instances(session, [document(7, "fiscalité")], {"fiscalité": 1}, {7})

    assert (inconnus, rattachees) == (0, 1)
    instance = session.query(Instance).one()
    assert instance.contribution_id == 7
    assert instance.external_doc_id == "7"


def test_conserve_external_doc_id_quand_le_rapprochement_echoue(session):
    """Comportement d'avant : l'instance existe, simplement non rattachée."""
    session.add(Topic(id=1, name="fiscalité"))
    session.flush()

    inconnus, rattachees = charger_instances(session, [document("73", "fiscalité")], {"fiscalité": 1}, set())

    assert (inconnus, rattachees) == (0, 0)
    instance = session.query(Instance).one()
    assert instance.contribution_id is None
    assert instance.external_doc_id == "73"


def test_ignore_les_labels_dont_le_topic_est_inconnu(session):
    session.add(Contribution(id=7, city="Trizay"))
    session.add(Topic(id=1, name="fiscalité"))
    session.flush()

    inconnus, rattachees = charger_instances(
        session, [document(7, "fiscalité", "thème fantôme")], {"fiscalité": 1}, {7}
    )

    assert (inconnus, rattachees) == (1, 1)
    assert session.query(Instance).count() == 1


def test_remplace_les_instances_existantes(session):
    session.add(Topic(id=1, name="fiscalité"))
    session.add(Instance(id=99, external_doc_id="ancienne", topic_id=1))
    session.flush()

    charger_instances(session, [document("73", "fiscalité")], {"fiscalité": 1}, set())

    assert [i.external_doc_id for i in session.query(Instance).all()] == ["73"]
