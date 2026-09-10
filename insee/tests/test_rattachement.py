"""Tests du rattachement des contributions à leur commune."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from database.models import Base, City, Contribution
from insee.rattachement import couverture_par_departement, graphie_retenue, rattacher


@pytest.fixture
def session() -> Session:
    """SQLite avec les clés étrangères **appliquées**.

    Elles sont désactivées par défaut, et sans elles un test ne voit pas qu'une
    contribution est écrite avant la commune qu'elle désigne — ce que PostgreSQL
    refuse. C'est exactement le bug que ce module a eu.
    """
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _activer_les_fk(connexion, _):
        connexion.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def contribution(pdf: str, city: str | None = None) -> Contribution:
    return Contribution(pdf_file=pdf, city=city)


BOURG = "CC_01000_190304_01053_MD_15462.pdf"
GUEREINS = "CC_01090_190304_01183_MD_15511.pdf"
SANS_CODE = "CC_01260_190301_00000_MD_15582.pdf"


# --- graphie_retenue ---


def test_retient_la_graphie_la_plus_riche():
    graphies = ["TORCE VIVIERS EN CHARNIE", "TORCÉ-VIVIERS-EN-CHARNIE"]
    assert graphie_retenue(graphies) == "TORCÉ-VIVIERS-EN-CHARNIE"


@pytest.mark.parametrize("graphies", [[], ["", "   "]])
def test_aucune_graphie_exploitable(graphies):
    assert graphie_retenue(graphies) is None


def test_deux_communes_sous_un_meme_code_retiennent_la_plus_attestee():
    """Anomalie de données : on tranche sans faire semblant qu'elle n'existe pas."""
    assert graphie_retenue(["TRIZAY", "TRIZAY", "FONTENET"]) == "TRIZAY"


# --- rattacher ---


def test_rattache_chaque_contribution_au_code_de_son_cahier(session):
    session.add_all([contribution(BOURG, "BOURG-EN-BRESSE"), contribution(GUEREINS, "GUEREINS")])
    session.flush()

    rapport = rattacher(session)
    session.flush()

    assert (rapport.contributions, rapport.rattachees) == (2, 2)
    assert sorted(c.city_code for c in session.scalars(session.query(Contribution).statement)) == [
        "01053",
        "01183",
    ]


def test_cree_la_commune_avec_son_departement(session):
    session.add(contribution(BOURG, "BOURG-EN-BRESSE"))
    session.flush()
    rattacher(session)
    session.flush()

    ville = session.get(City, "01053")
    assert (ville.name, ville.department) == ("BOURG-EN-BRESSE", "01")


def test_la_population_et_les_coordonnees_restent_vides(session):
    """Elles demandent le COG : les laisser NULL plutôt que d'inventer."""
    session.add(contribution(BOURG, "BOURG-EN-BRESSE"))
    session.flush()
    rattacher(session)
    session.flush()

    ville = session.get(City, "01053")
    assert (ville.population, ville.latitude, ville.longitude) == (None, None, None)


def test_les_graphies_d_une_meme_commune_donnent_une_seule_ligne(session):
    session.add_all([
        contribution(BOURG, "BOURG EN BRESSE"),
        contribution(BOURG, "BOURG-EN-BRESSE"),
    ])
    session.flush()
    rattacher(session)
    session.flush()

    assert session.query(City).count() == 1
    assert session.get(City, "01053").name == "BOURG-EN-BRESSE"


def test_un_cahier_sans_code_reste_non_rattache(session):
    """Deux cahiers du corpus n'ont pas de commune à la source : ne pas inventer."""
    session.add(contribution(SANS_CODE))
    session.flush()

    rapport = rattacher(session)
    session.flush()

    assert rapport.rattachees == 0
    assert rapport.cahiers_sans_code == [SANS_CODE]
    assert session.query(Contribution).one().city_code is None


def test_une_contribution_sans_graphie_cree_quand_meme_sa_commune(session):
    """35 % des cahiers n'ont pas de commune lisible mais ont leur code."""
    session.add(contribution(BOURG, None))
    session.flush()
    rattacher(session)
    session.flush()

    ville = session.get(City, "01053")
    assert ville is not None and ville.name is None


def test_le_rattachement_est_idempotent(session):
    session.add(contribution(BOURG, "BOURG-EN-BRESSE"))
    session.flush()
    rattacher(session)
    session.flush()
    rattacher(session)
    session.flush()
    assert session.query(City).count() == 1


def test_relancer_n_efface_pas_une_graphie_deja_connue(session):
    """Un lot sans graphie ne doit pas faire régresser ce qu'on savait déjà."""
    session.add(contribution(BOURG, "BOURG-EN-BRESSE"))
    session.flush()
    rattacher(session)
    session.flush()

    session.query(Contribution).one().city = None
    rattacher(session)
    session.flush()
    assert session.get(City, "01053").name == "BOURG-EN-BRESSE"


# --- couverture par département ---


def test_la_couverture_compte_communes_et_contributions(session):
    session.add_all([contribution(BOURG), contribution(BOURG), contribution(GUEREINS)])
    session.flush()
    rattacher(session)
    session.flush()

    assert couverture_par_departement(session) == {"01": (2, 3)}


def test_une_commune_sans_contribution_compte_quand_meme(session):
    """Une commune connue mais muette n'est pas une commune absente."""
    session.add(City(code="53001", department="53"))
    session.flush()
    assert couverture_par_departement(session) == {"53": (1, 0)}
