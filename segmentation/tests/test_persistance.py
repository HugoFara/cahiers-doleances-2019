"""Tests de la navette entre `page_extraction` et `doleance`."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.models import Base, Doleance, PageExtraction
from database.runs import SEGMENTATION, creer_run
from segmentation.persistance import (
    cahiers_deja_decoupes,
    enregistrer_cahier,
    grouper_par_cahier,
    lire_pages,
    oublier_cahier,
)

CORPS = (
    "Les impôts locaux augmentent chaque année sans contrepartie visible, "
    "et les services publics disparaissent les uns après les autres."
)


def page(
    page_number: int,
    text: str,
    *,
    contribution_id: int = 1,
    pdf_name: str = "cahier.pdf",
    needs_ocr: bool = False,
    city: str = "TRIZAY",
) -> PageExtraction:
    return PageExtraction(
        contribution_id=contribution_id,
        pdf_name=pdf_name,
        page_number=page_number,
        text=text,
        quality_score=0.2 if needs_ocr else 0.9,
        needs_ocr=needs_ocr,
        city=city,
    )


@pytest.fixture
def session() -> Session:
    """Base SQLite en mémoire : le découpage se teste sans PostgreSQL."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def run(session) -> int:
    """Un run de découpage : toute doléance écrite appartient à l'un d'eux."""
    return creer_run(session, SEGMENTATION, label="test").id


# --- grouper_par_cahier ---


def test_regroupe_les_pages_par_cahier():
    cahiers = grouper_par_cahier(
        [page(3, "a"), page(4, "b"), page(3, "c", pdf_name="autre.pdf")]
    )
    assert set(cahiers) == {"cahier.pdf", "autre.pdf"}
    assert [p.text for p in cahiers["cahier.pdf"]] == ["a", "b"]


def test_ecarte_les_pages_sans_cahier():
    """`pdf_name` est nullable : rattacher au hasard mélangerait deux communes."""
    orpheline = page(3, "orpheline")
    orpheline.pdf_name = None
    cahiers = grouper_par_cahier([orpheline, page(4, "rattachée")])
    assert list(cahiers) == ["cahier.pdf"]
    assert [p.text for p in cahiers["cahier.pdf"]] == ["rattachée"]


# --- lire_pages ---


def test_lire_pages_exclut_les_pages_manuscrites_par_defaut(session):
    session.add_all([page(3, "dactylographié"), page(4, "gribouillis", needs_ocr=True)])
    session.flush()
    assert [p.text for p in lire_pages(session)] == ["dactylographié"]


def test_lire_pages_garde_les_pages_dont_le_flag_est_null(session):
    """Même logique ternaire que dans export_dataset : `is_not(True)` garde les NULL."""
    ancienne = page(3, "ancien")
    ancienne.needs_ocr = None
    session.add(ancienne)
    session.flush()
    assert [p.text for p in lire_pages(session)] == ["ancien"]


def test_lire_pages_trie_par_cahier_puis_par_page(session):
    session.add_all(
        [page(5, "b2"), page(3, "b1"), page(4, "a", pdf_name="autre.pdf")]
    )
    session.flush()
    assert [p.text for p in lire_pages(session)] == ["a", "b1", "b2"]


# --- enregistrer_cahier ---


def test_ecrit_une_ligne_par_doleance_numerotee_dans_l_ordre(session, run):
    pages = [page(3, "Le 21 février 2019\n" + CORPS + "\nLe 22 février 2019\n" + CORPS)]
    enregistrer_cahier(session, "cahier.pdf", pages, run)
    session.flush()
    lignes = session.query(Doleance).order_by(Doleance.position).all()
    assert [ligne.position for ligne in lignes] == [0, 1]
    assert [ligne.signal for ligne in lignes] == ["debut", "date"]


def test_reprend_la_commune_et_le_cahier_des_pages(session, run):
    enregistrer_cahier(session, "cahier.pdf", [page(3, CORPS)], run)
    session.flush()
    ligne = session.query(Doleance).one()
    assert (ligne.city, ligne.pdf_name) == ("TRIZAY", "cahier.pdf")


def test_rattache_la_doleance_a_la_contribution_de_sa_premiere_page(session, run):
    """Une contribution par page : c'est la page d'ouverture qui porte le lien."""
    pages = [
        page(3, "Le 21 février 2019\n" + CORPS, contribution_id=10),
        page(4, "Le 22 février 2019\n" + CORPS, contribution_id=11),
    ]
    enregistrer_cahier(session, "cahier.pdf", pages, run)
    session.flush()
    lignes = session.query(Doleance).order_by(Doleance.position).all()
    assert [ligne.contribution_id for ligne in lignes] == [10, 11]


def test_compte_les_mots(session, run):
    enregistrer_cahier(session, "cahier.pdf", [page(3, "trois petits mots")], run)
    session.flush()
    assert session.query(Doleance).one().num_words == 3


def test_un_cahier_sans_texte_n_ecrit_rien(session, run):
    assert enregistrer_cahier(session, "cahier.pdf", [page(3, "")], run) == []


# --- idempotence ---


def test_les_cahiers_deja_decoupes_sont_reconnus(session, run):
    enregistrer_cahier(session, "cahier.pdf", [page(3, CORPS)], run)
    session.flush()
    assert cahiers_deja_decoupes(session, run) == {"cahier.pdf"}


def test_oublier_un_cahier_ne_touche_pas_les_autres(session, run):
    enregistrer_cahier(session, "cahier.pdf", [page(3, CORPS)], run)
    enregistrer_cahier(session, "autre.pdf", [page(3, CORPS, pdf_name="autre.pdf")], run)
    session.flush()
    oublier_cahier(session, "cahier.pdf", run)
    session.flush()
    assert cahiers_deja_decoupes(session, run) == {"autre.pdf"}


def test_un_nouveau_run_repart_d_un_corpus_vierge(session, run):
    """Le run précédent reste intact : on ne détruit plus pour réessayer."""
    enregistrer_cahier(session, "cahier.pdf", [page(3, CORPS)], run)
    session.flush()

    second = creer_run(session, SEGMENTATION, label="règles v2").id
    assert cahiers_deja_decoupes(session, second) == set()

    enregistrer_cahier(session, "cahier.pdf", [page(3, CORPS)], second)
    session.flush()
    assert session.query(Doleance).count() == 2
    assert {d.run_id for d in session.query(Doleance)} == {run, second}


def test_oublier_un_cahier_ne_touche_pas_les_autres_runs(session, run):
    enregistrer_cahier(session, "cahier.pdf", [page(3, CORPS)], run)
    second = creer_run(session, SEGMENTATION, label="règles v2").id
    enregistrer_cahier(session, "cahier.pdf", [page(3, CORPS)], second)
    session.flush()

    oublier_cahier(session, "cahier.pdf", second)
    session.flush()
    assert [d.run_id for d in session.query(Doleance)] == [run]
