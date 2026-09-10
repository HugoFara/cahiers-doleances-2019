"""Tests du tirage stratifié."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.models import Base, Doleance
from database.runs import SEGMENTATION, creer_run
from reference.echantillon import (
    MIN_PAR_STRATE,
    compter_par_cahier,
    repartir,
    strate,
    tirer,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def peupler(session, run_id: int, cahiers: dict[str, int]) -> None:
    """Crée `n` doléances par cahier, pour donner sa strate à chacun."""
    for pdf_name, n in cahiers.items():
        for position in range(n):
            session.add(
                Doleance(run_id=run_id, pdf_name=pdf_name, position=position, text="x")
            )
    session.flush()


# --- strate ---


@pytest.mark.parametrize(("nb", "attendu"), [(0, "une"), (1, "une"), (2, "deux"), (7, "trois-et-plus")])
def test_strate(nb, attendu):
    assert strate(nb) == attendu


# --- repartir ---


def test_repartir_respecte_le_plancher_des_strates_rares():
    """Sans plancher, une strate à 2 % disparaît d'un échantillon de 60."""
    quotas = repartir({"une": 1000, "deux": 100, "trois-et-plus": 20}, taille=60)
    assert quotas["trois-et-plus"] >= min(MIN_PAR_STRATE, 20)


def test_repartir_ne_demande_jamais_plus_que_la_strate_contient():
    quotas = repartir({"une": 3, "deux": 2}, taille=60)
    assert quotas == {"une": 3, "deux": 2}


def test_repartir_rogne_sur_la_strate_la_plus_fournie():
    quotas = repartir({"une": 1000, "deux": 100, "trois-et-plus": 50}, taille=40)
    assert sum(quotas.values()) <= 40
    assert quotas["une"] >= MIN_PAR_STRATE


def test_repartir_sur_une_population_vide():
    assert repartir({}, taille=60) == {}


# --- tirer ---


def test_le_tirage_est_reproductible(session):
    run = creer_run(session, SEGMENTATION, label="test").id
    peupler(session, run, {f"c{i}.pdf": 1 for i in range(50)})
    premier, _ = tirer(session, run, taille=10, graine=42)
    second, _ = tirer(session, run, taille=10, graine=42)
    assert premier == second


def test_une_graine_differente_donne_un_autre_echantillon(session):
    run = creer_run(session, SEGMENTATION, label="test").id
    peupler(session, run, {f"c{i}.pdf": 1 for i in range(50)})
    assert tirer(session, run, 10, graine=1) != tirer(session, run, 10, graine=2)


def test_le_poids_dit_combien_de_cahiers_chaque_tire_represente(session):
    run = creer_run(session, SEGMENTATION, label="test").id
    peupler(session, run, {f"a{i}.pdf": 1 for i in range(100)})
    peupler(session, run, {f"b{i}.pdf": 2 for i in range(10)})
    cahiers, poids = tirer(session, run, taille=20, graine=7)

    for nom_strate, w in poids.items():
        tires = sum(1 for _, s in cahiers if s == nom_strate)
        population = 100 if nom_strate == "une" else 10
        assert w == pytest.approx(population / tires)


def test_les_strates_rares_sont_sur_representees(session):
    """C'est le but : l'étalon doit contenir les cas qui font échouer le découpage."""
    run = creer_run(session, SEGMENTATION, label="test").id
    peupler(session, run, {f"a{i}.pdf": 1 for i in range(200)})
    peupler(session, run, {f"b{i}.pdf": 3 for i in range(20)})
    cahiers, _ = tirer(session, run, taille=30, graine=7)

    part_tiree = sum(1 for _, s in cahiers if s == "trois-et-plus") / len(cahiers)
    assert part_tiree > 20 / 220


def test_tirer_sur_un_run_sans_doleances(session):
    run = creer_run(session, SEGMENTATION, label="test").id
    assert tirer(session, run, taille=10, graine=1) == ([], {})


def test_le_comptage_ignore_les_autres_runs(session):
    run = creer_run(session, SEGMENTATION, label="test").id
    autre = creer_run(session, SEGMENTATION, label="autre", actif=False).id
    peupler(session, run, {"a.pdf": 1})
    peupler(session, autre, {"b.pdf": 1})
    assert compter_par_cahier(session, run) == {"a.pdf": 1}
