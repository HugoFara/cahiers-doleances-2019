"""Tests du chargement de la livraison de l'équipe analyse."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.load_analysis import (
    charger_instances,
    mesurer_correspondance,
    resoudre_contribution,
    taux_correspondance,
)
from database.models import Base, Contribution, Instance, PageExtraction, Topic


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


# --- taux_correspondance ---


def test_taux_correspondance_verbatim_present():
    assert taux_correspondance([("le vote blanc", "je demande que le vote blanc compte")]) == 1.0


def test_taux_correspondance_verbatim_absent():
    assert taux_correspondance([("le vote blanc", "un texte sans rapport")]) == 0.0


def test_taux_correspondance_ignore_casse_et_espaces():
    assert taux_correspondance([("Le  VOTE   blanc", "que le vote blanc compte")]) == 1.0


def test_taux_correspondance_normalise_les_tirets_et_apostrophes():
    """Les PDF utilisent − (U+2212) et ’ là où la livraison écrit - et '."""
    assert taux_correspondance([("- l'impôt", "− l’impôt sur le revenu")]) == 1.0


def test_taux_correspondance_sans_paire():
    assert taux_correspondance([]) == 0.0


def test_taux_correspondance_partiel():
    paires = [("present", "texte present"), ("absent", "texte")]
    assert taux_correspondance(paires) == 0.5


# --- mesurer_correspondance et garde-fou du rattachement ---


def contribution_avec_texte(session, contribution_id: int, texte: str) -> None:
    session.add(Contribution(id=contribution_id))
    session.add(
        PageExtraction(contribution_id=contribution_id, page_number=1, text=texte)
    )
    session.flush()


def test_mesure_detecte_une_livraison_qui_parle_du_bon_corpus(session):
    contribution_avec_texte(session, 7, "je demande la proportionnelle aux élections")
    doc = {"id": 7, "labels": [{"name": "vote", "extract": "je demande la proportionnelle"}]}
    taux, testes = mesurer_correspondance(session, [doc], {7})
    assert (taux, testes) == (1.0, 1)


def test_mesure_detecte_une_livraison_qui_parle_dun_autre_corpus(session):
    """Cas du dump POC : les id sont des positions dans un CSV, pas des contributions."""
    contribution_avec_texte(session, 7, "un texte sur les routes départementales")
    doc = {"id": 7, "labels": [{"name": "fiscalité", "extract": "supprimer la CSG"}]}
    taux, testes = mesurer_correspondance(session, [doc], {7})
    assert taux == 0.0 and testes == 1


def test_mesure_sans_aucun_id_resolu(session):
    doc = {"id": 999, "labels": [{"name": "x", "extract": "y"}]}
    assert mesurer_correspondance(session, [doc], {1, 2}) == (0.0, 0)


def test_charger_instances_sans_rattachement_laisse_contribution_id_null(session):
    """`rattacher=False` : on charge les thèmes sans inventer de lien."""
    session.add(Contribution(id=3))
    topic = Topic(external_id="t1", name="vote")
    session.add(topic)
    session.flush()
    charger_instances(session, [document(3, "vote")], {"vote": topic.id}, {3}, False)
    session.flush()
    instances = session.query(Instance).all()
    assert len(instances) == 1
    assert instances[0].contribution_id is None
    assert instances[0].external_doc_id == "3"
