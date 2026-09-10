"""Tests du chargement de la livraison de l'équipe analyse."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from analyse.identifiants import CONTRIBUTION, DOLEANCE
from analyse.load_analysis import (
    Cibles,
    charger_instances,
    charger_topics,
    mesurer_correspondance,
    resoudre_document,
    taux_correspondance,
)
from database.models import (
    Base,
    Contribution,
    Doleance,
    Instance,
    PageExtraction,
    Topic,
)
from database.runs import ANALYSE, creer_run


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def run(session) -> int:
    """Toute instance appartient à une grille : les tests en ouvrent une."""
    return creer_run(session, ANALYSE, label="test").id


def cibles(contributions=(), doleances=None) -> Cibles:
    """Ce que la base est censée connaître, sans avoir à la remplir."""
    return Cibles(contributions=set(contributions), doleances=dict(doleances or {}))


def document(doc_id, *noms_de_topics) -> dict:
    return {
        "id": doc_id,
        "labels": [
            {"name": nom, "extract": f"verbatim {nom}", "rationale": f"parce que {nom}"}
            for nom in noms_de_topics
        ],
    }


# --- resoudre_document ---


def test_resout_un_id_de_document_qui_est_un_id_de_contribution():
    """Cas des livraisons produites depuis analyse/export_dataset.py."""
    assert resoudre_document("42", cibles({41, 42, 43})) == (CONTRIBUTION, 42)


def test_resout_un_id_prefixe_comme_une_doleance():
    """Livraison produite avec --niveau doleance : les ids portent un « d »."""
    assert resoudre_document("d42", cibles(doleances={42: 7})) == (DOLEANCE, 42)


def test_un_id_de_doleance_ne_designe_jamais_une_contribution():
    """Sans le préfixe, `d42` et `42` se confondraient : deux corpus mélangés."""
    assert resoudre_document("d42", cibles({42})) is None
    assert resoudre_document("42", cibles(doleances={42: 7})) is None


def test_ne_resout_pas_un_id_absent_de_la_base():
    assert resoudre_document("99", cibles({1, 2})) is None


@pytest.mark.parametrize("valeur", ["doc 73", "", "abc", "3.5"])
def test_ne_resout_pas_un_id_non_numerique(valeur):
    """Les livraisons antérieures numérotent les documents à leur façon."""
    assert resoudre_document(valeur, cibles({1, 2, 73})) is None


# --- charger_instances ---


def test_rattache_les_instances_a_leur_contribution(session, run):
    session.add(Contribution(id=7, city="Trizay"))
    session.add(Topic(id=1, name="fiscalité"))
    session.flush()

    inconnus, rattachees = charger_instances(session, [document(7, "fiscalité")], {"fiscalité": 1}, cibles({7}), run)

    assert (inconnus, rattachees) == (0, 1)
    instance = session.query(Instance).one()
    assert instance.contribution_id == 7
    assert instance.external_doc_id == "7"


def test_conserve_external_doc_id_quand_le_rapprochement_echoue(session, run):
    """Comportement d'avant : l'instance existe, simplement non rattachée."""
    session.add(Topic(id=1, name="fiscalité"))
    session.flush()

    inconnus, rattachees = charger_instances(session, [document("73", "fiscalité")], {"fiscalité": 1}, cibles(), run)

    assert (inconnus, rattachees) == (0, 0)
    instance = session.query(Instance).one()
    assert instance.contribution_id is None
    assert instance.external_doc_id == "73"


def test_ignore_les_labels_dont_le_topic_est_inconnu(session, run):
    session.add(Contribution(id=7, city="Trizay"))
    session.add(Topic(id=1, name="fiscalité"))
    session.flush()

    inconnus, rattachees = charger_instances(
        session, [document(7, "fiscalité", "thème fantôme")], {"fiscalité": 1}, cibles({7}), run
    )

    assert (inconnus, rattachees) == (1, 1)
    assert session.query(Instance).count() == 1


def test_remplace_les_instances_existantes(session, run):
    session.add(Topic(id=1, name="fiscalité"))
    session.add(Instance(id=99, run_id=run, external_doc_id="ancienne", topic_id=1))
    session.flush()

    charger_instances(session, [document("73", "fiscalité")], {"fiscalité": 1}, cibles(), run)

    assert [i.external_doc_id for i in session.query(Instance).all()] == ["73"]


def test_rattache_une_instance_de_doleance_a_sa_doleance_et_a_sa_contribution(session, run):
    """La doléance porte le lien fin, la contribution reste renseignée pour l'app."""
    session.add(Contribution(id=7, city="Trizay"))
    session.add(Doleance(id=42, contribution_id=7, text="un texte"))
    session.add(Topic(id=1, name="fiscalité"))
    session.flush()

    inconnus, rattachees = charger_instances(
        session, [document("d42", "fiscalité")], {"fiscalité": 1}, cibles(doleances={42: 7}), run
    )

    assert (inconnus, rattachees) == (0, 1)
    instance = session.query(Instance).one()
    assert (instance.doleance_id, instance.contribution_id) == (42, 7)
    assert instance.external_doc_id == "d42"


def test_recharger_une_grille_ne_touche_pas_a_l_autre(session, run):
    """Le point de tout le versionnement : `DELETE FROM instance` détruisait tout."""
    autre = creer_run(session, ANALYSE, label="grille concurrente", actif=False).id
    session.add(Topic(id=1, run_id=run, name="fiscalité"))
    session.add(Topic(id=2, run_id=autre, name="fiscalité"))
    session.add(Instance(id=99, run_id=autre, external_doc_id="d1", topic_id=2))
    session.flush()

    charger_instances(session, [document("73", "fiscalité")], {"fiscalité": 1}, cibles(), run)
    session.flush()

    par_run = {i.run_id: i.external_doc_id for i in session.query(Instance).all()}
    assert par_run == {run: "73", autre: "d1"}


def test_charger_les_topics_d_un_run_ignore_ceux_des_autres(session, run):
    """Deux grilles peuvent réutiliser le même UUID sans se contaminer."""
    autre = creer_run(session, ANALYSE, label="grille concurrente", actif=False).id
    session.add(Topic(run_id=autre, external_id="uuid-1", name="intouchée"))
    session.flush()

    charger_topics(
        session,
        [{"id": "uuid-1", "name": "fiscalité", "description": "", "level": 0, "validated": False}],
        run,
    )
    session.flush()

    noms = {t.run_id: t.name for t in session.query(Topic).all()}
    assert noms == {run: "fiscalité", autre: "intouchée"}


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
    taux, testes = mesurer_correspondance(session, [doc], cibles({7}))
    assert (taux, testes) == (1.0, 1)


def test_mesure_detecte_une_livraison_qui_parle_dun_autre_corpus(session):
    """Cas du dump POC : les id sont des positions dans un CSV, pas des contributions."""
    contribution_avec_texte(session, 7, "un texte sur les routes départementales")
    doc = {"id": 7, "labels": [{"name": "fiscalité", "extract": "supprimer la CSG"}]}
    taux, testes = mesurer_correspondance(session, [doc], cibles({7}))
    assert taux == 0.0 and testes == 1


def test_mesure_cherche_le_verbatim_dans_le_texte_de_la_doleance(session):
    """Le garde-fou doit valoir aussi pour une livraison au niveau doléance."""
    session.add(Doleance(id=42, contribution_id=7, text="je demande la proportionnelle"))
    session.flush()
    doc = {"id": "d42", "labels": [{"name": "vote", "extract": "je demande la proportionnelle"}]}
    assert mesurer_correspondance(session, [doc], cibles(doleances={42: 7})) == (1.0, 1)


def test_mesure_sans_aucun_id_resolu(session):
    doc = {"id": 999, "labels": [{"name": "x", "extract": "y"}]}
    assert mesurer_correspondance(session, [doc], cibles({1, 2})) == (0.0, 0)


def test_charger_instances_sans_rattachement_laisse_contribution_id_null(session, run):
    """`rattacher=False` : on charge les thèmes sans inventer de lien."""
    session.add(Contribution(id=3))
    topic = Topic(external_id="t1", name="vote")
    session.add(topic)
    session.flush()
    charger_instances(session, [document(3, "vote")], {"vote": topic.id}, cibles({3}), run, False)
    session.flush()
    instances = session.query(Instance).all()
    assert len(instances) == 1
    assert instances[0].contribution_id is None
    assert instances[0].external_doc_id == "3"
