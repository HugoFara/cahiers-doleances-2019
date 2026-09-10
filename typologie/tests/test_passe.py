"""Tests de la passe : lecture du corpus et écriture des deux axes."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database.models import (
    Base,
    Doleance,
    DuplicateGroup,
    DuplicateMember,
    Typologie,
)
from database.runs import DOUBLONS, SEGMENTATION, TYPOLOGIE, creer_run
from typologie.classement import AUTEUR, INDIVIDU, LETTRE_TYPE, REGISTRE, SUPPORT
from typologie.passe import (
    classer_tout,
    lire_doleances,
    lire_recopies,
    oublier_run,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def decoupage(session) -> int:
    return creer_run(session, SEGMENTATION, label="test").id


@pytest.fixture
def run(session) -> int:
    return creer_run(session, TYPOLOGIE, label="règles de forme").id


def doleance(session, run_id: int, texte: str) -> int:
    ligne = Doleance(run_id=run_id, text=texte)
    session.add(ligne)
    session.flush()
    return ligne.id


# --- lecture ---


def test_ne_lit_que_les_doleances_du_decoupage_servi(session, decoupage):
    autre = creer_run(session, SEGMENTATION, label="v2", actif=False).id
    gardee = doleance(session, decoupage, "Je demande la baisse des taxes.")
    doleance(session, autre, "texte d'un autre découpage")
    assert set(lire_doleances(session, decoupage)) == {gardee}


def test_les_doleances_sans_texte_sont_ignorees(session, decoupage):
    gardee = doleance(session, decoupage, "un texte")
    doleance(session, decoupage, "")
    session.add(Doleance(run_id=decoupage, text=None))
    session.flush()
    assert set(lire_doleances(session, decoupage)) == {gardee}


# --- recopies ---


def _groupe(session, run_id: int, communes: int, doleance_id: int) -> None:
    groupe = DuplicateGroup(run_id=run_id, size=2, cities=communes)
    session.add(groupe)
    session.flush()
    session.add(DuplicateMember(group_id=groupe.id, doleance_id=doleance_id))
    session.flush()


def test_un_texte_recopie_dans_plusieurs_communes_est_une_lettre_type(
    session, decoupage
):
    dedup = creer_run(session, DOUBLONS, label="seuil 0.8").id
    identifiant = doleance(session, decoupage, "texte diffusé")
    _groupe(session, dedup, communes=4, doleance_id=identifiant)
    assert lire_recopies(session, dedup) == {identifiant}


def test_un_cahier_scanne_deux_fois_dans_une_commune_ne_dit_rien_du_support(
    session, decoupage
):
    dedup = creer_run(session, DOUBLONS, label="seuil 0.8").id
    identifiant = doleance(session, decoupage, "texte en double")
    _groupe(session, dedup, communes=1, doleance_id=identifiant)
    assert lire_recopies(session, dedup) == set()


def test_sans_deduplication_servie_la_passe_tourne_quand_meme(session):
    assert lire_recopies(session, None) == set()


def test_les_groupes_d_un_autre_run_de_deduplication_sont_ignores(session, decoupage):
    ancien = creer_run(session, DOUBLONS, label="seuil 0.6", actif=False).id
    servi = creer_run(session, DOUBLONS, label="seuil 0.8").id
    identifiant = doleance(session, decoupage, "texte diffusé")
    _groupe(session, ancien, communes=4, doleance_id=identifiant)
    assert lire_recopies(session, servi) == set()


# --- écriture ---


def test_chaque_doleance_recoit_une_ligne_par_axe(session, decoupage, run):
    identifiant = doleance(session, decoupage, "Je demande la baisse des taxes.")
    comptes = classer_tout(session, run, {identifiant: "Je demande la baisse."})
    session.flush()
    lignes = session.scalars(
        select(Typologie).where(Typologie.doleance_id == identifiant)
    ).all()
    assert {ligne.axis for ligne in lignes} == {SUPPORT, AUTEUR}
    assert comptes[AUTEUR][INDIVIDU] == 1
    assert comptes[SUPPORT][REGISTRE] == 1


def test_la_relecture_humaine_part_de_nulle_part(session, decoupage, run):
    identifiant = doleance(session, decoupage, "un texte")
    classer_tout(session, run, {identifiant: "un texte"})
    session.flush()
    assert all(
        ligne.confirmed is None
        for ligne in session.scalars(select(Typologie)).all()
    )


def test_la_recopie_est_reportee_sur_le_support(session, decoupage, run):
    identifiant = doleance(session, decoupage, "texte diffusé")
    classer_tout(session, run, {identifiant: "texte diffusé"}, recopies={identifiant})
    session.flush()
    support = session.scalars(
        select(Typologie).where(Typologie.axis == SUPPORT)
    ).one()
    assert support.value == LETTRE_TYPE


def test_oublier_un_run_ne_touche_pas_aux_autres(session, decoupage, run):
    autre = creer_run(session, TYPOLOGIE, label="v2", actif=False).id
    identifiant = doleance(session, decoupage, "un texte")
    classer_tout(session, run, {identifiant: "un texte"})
    classer_tout(session, autre, {identifiant: "un texte"})
    session.flush()

    oublier_run(session, run)

    restants = session.scalars(select(Typologie)).all()
    assert {ligne.run_id for ligne in restants} == {autre}
