"""Tests de l'export des contributions vers le dataset CSV de topic-builder."""

import csv

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.export_dataset import construire_documents, ecrire_dataset, lire_pages
from database.models import Base, PageExtraction


def page(contribution_id: int, page_number: int, text: str, needs_ocr: bool = False) -> PageExtraction:
    return PageExtraction(
        contribution_id=contribution_id,
        pdf_name="cahier.pdf",
        page_number=page_number,
        text=text,
        quality_score=0.2 if needs_ocr else 0.9,
        needs_ocr=needs_ocr,
        city="Trizay",
    )


@pytest.fixture
def session() -> Session:
    """Base SQLite en mémoire : le filtrage SQL est testé sans Postgres."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# --- construire_documents ---


def test_regroupe_les_pages_par_contribution_dans_l_ordre():
    documents = construire_documents([page(1, 3, "trois"), page(1, 4, "quatre"), page(2, 3, "autre")])
    assert documents == [
        {"id": "1", "content": "trois\nquatre"},
        {"id": "2", "content": "autre"},
    ]


def test_l_id_du_document_est_l_id_de_la_contribution():
    """C'est ce qui permettra à load_analysis de résoudre instance.contribution_id."""
    assert construire_documents([page(42, 3, "texte")])[0]["id"] == "42"


@pytest.mark.parametrize("texte_vide", ["", "   ", "\n\n"])
def test_ecarte_les_pages_sans_texte(texte_vide):
    documents = construire_documents([page(1, 3, "utile"), page(1, 4, texte_vide)])
    assert documents == [{"id": "1", "content": "utile"}]


def test_ecarte_les_contributions_sans_aucun_texte():
    """Un cahier entièrement manuscrit ne donne aucune ligne, pas une ligne vide."""
    assert construire_documents([page(1, 3, "   "), page(1, 4, "")]) == []


def test_ecarte_les_pages_sans_contribution():
    """La FK est nullable ; un document d'id "None" ne serait jamais rattachable."""
    orpheline = page(1, 3, "orpheline")
    orpheline.contribution_id = None
    assert construire_documents([orpheline, page(1, 4, "rattachée")]) == [
        {"id": "1", "content": "rattachée"}
    ]


def test_aucune_page_donne_aucun_document():
    assert construire_documents([]) == []


# --- lire_pages ---


def test_lire_pages_exclut_les_pages_manuscrites_par_defaut(session):
    session.add_all([page(1, 3, "dactylographié"), page(1, 4, "gribouillis", needs_ocr=True)])
    session.flush()
    assert [p.text for p in lire_pages(session)] == ["dactylographié"]


def test_lire_pages_garde_les_pages_manuscrites_sur_demande(session):
    session.add_all([page(1, 3, "dactylographié"), page(1, 4, "gribouillis", needs_ocr=True)])
    session.flush()
    assert len(lire_pages(session, garder_pages_ocr=True)) == 2


def test_lire_pages_garde_les_pages_dont_le_flag_est_null(session):
    """La colonne est nullable : `is_not(True)` garde les NULL là où `!= True` les perdrait.

    L'extraction renseigne toujours le flag aujourd'hui, mais rien ne l'impose au
    niveau du schéma — une page insérée par une autre voie ne doit pas disparaître
    du dataset à cause de la logique ternaire de SQL.
    """
    session.add_all([PageExtraction(contribution_id=1, page_number=3, text="ancien", needs_ocr=None)])
    session.flush()
    assert [p.text for p in lire_pages(session)] == ["ancien"]


def test_lire_pages_trie_par_contribution_puis_par_page(session):
    session.add_all([page(2, 3, "b"), page(1, 5, "a2"), page(1, 3, "a1")])
    session.flush()
    assert [p.text for p in lire_pages(session)] == ["a1", "a2", "b"]


# --- ecrire_dataset ---


def test_ecrit_un_csv_relisible_par_topic_builder(tmp_path):
    chemin = tmp_path / "sous-dossier" / "dataset.csv"
    ecrire_dataset([{"id": "1", "content": "ligne un\nligne deux"}], chemin)
    with chemin.open(encoding="utf-8", newline="") as f:
        lignes = list(csv.DictReader(f))
    assert lignes == [{"id": "1", "content": "ligne un\nligne deux"}]
