"""Tests des runs : versionnement et pluralité des couches interprétatives."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import Base, Run, Topic
from database.runs import (
    ANALYSE,
    SEGMENTATION,
    activer_run,
    creer_run,
    id_run_actif,
    run_actif,
    runs,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_un_run_cree_est_actif_par_defaut(session):
    run = creer_run(session, ANALYSE, label="grille émergente v4")
    assert run_actif(session, ANALYSE) is run


def test_un_nouveau_run_remplace_le_precedent_comme_run_servi(session):
    ancien = creer_run(session, ANALYSE, label="v3")
    nouveau = creer_run(session, ANALYSE, label="v4")
    assert run_actif(session, ANALYSE) is nouveau
    assert ancien.active is False


def test_le_run_precedent_reste_en_base(session):
    """C'est tout l'intérêt : deux grilles doivent pouvoir être comparées."""
    creer_run(session, ANALYSE, label="v3")
    creer_run(session, ANALYSE, label="v4")
    assert [r.label for r in runs(session, ANALYSE)] == ["v4", "v3"]


def test_un_run_peut_etre_charge_sans_devenir_le_run_servi(session):
    servi = creer_run(session, ANALYSE, label="v3")
    creer_run(session, ANALYSE, label="expérimentale", actif=False)
    assert run_actif(session, ANALYSE) is servi


def test_les_genres_sont_independants(session):
    """Changer de grille de thèmes ne change pas le découpage servi."""
    decoupage = creer_run(session, SEGMENTATION, label="signaux de texte")
    creer_run(session, ANALYSE, label="v4")
    assert run_actif(session, SEGMENTATION) is decoupage


def test_activer_un_ancien_run_le_ramene_au_premier_plan(session):
    ancien = creer_run(session, ANALYSE, label="v3")
    creer_run(session, ANALYSE, label="v4")
    activer_run(session, ancien)
    assert run_actif(session, ANALYSE) is ancien


def test_la_base_refuse_deux_runs_actifs_du_meme_genre(session):
    """Garanti par un index unique partiel, pas seulement par le code appelant."""
    creer_run(session, ANALYSE, label="v3")
    session.add(Run(kind=ANALYSE, label="v4 forcée", active=True))
    with pytest.raises(IntegrityError):
        session.flush()


def test_un_genre_inconnu_est_refuse(session):
    with pytest.raises(ValueError, match="genre inconnu"):
        creer_run(session, "sentiment", label="x")


def test_aucun_run_actif_est_un_etat_normal(session):
    """Base fraîchement migrée : la couche est vide, ce n'est pas une erreur."""
    assert run_actif(session, ANALYSE) is None
    assert id_run_actif(session, ANALYSE) is None


def test_le_run_porte_de_quoi_le_rejouer(session):
    run = creer_run(
        session,
        ANALYSE,
        label="grille émergente v4",
        source="data/analyse_poc_2026-08-11",
        model="qwen3-4b-instruct-fp8",
        prompt_version="discover_topics.md@2026-08",
        parameters={"seuil": 0.3},
        corpus="2855 pages",
        author="équipe analyse",
    )
    session.flush()
    relu = session.get(Run, run.id)
    assert relu.model == "qwen3-4b-instruct-fp8"
    assert relu.parameters == {"seuil": 0.3}
    assert relu.created_at is not None


def test_deux_grilles_peuvent_reutiliser_le_meme_uuid_de_livraison(session):
    """L'unicité de external_id vaut dans un run, pas dans la table."""
    v3 = creer_run(session, ANALYSE, label="v3", actif=False)
    v4 = creer_run(session, ANALYSE, label="v4")
    session.add_all([
        Topic(run_id=v3.id, external_id="uuid-1", name="fiscalité"),
        Topic(run_id=v4.id, external_id="uuid-1", name="fiscalité (reformulé)"),
    ])
    session.flush()
    assert session.query(Topic).count() == 2


def test_un_run_ne_peut_pas_contenir_deux_fois_le_meme_uuid(session):
    run = creer_run(session, ANALYSE, label="v4")
    session.add_all([
        Topic(run_id=run.id, external_id="uuid-1", name="a"),
        Topic(run_id=run.id, external_id="uuid-1", name="b"),
    ])
    with pytest.raises(IntegrityError):
        session.flush()
