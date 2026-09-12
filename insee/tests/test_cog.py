"""Tests du chargement du référentiel INSEE dans `city`."""

import csv
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from database.models import Base, City
from insee.cog import (
    communes_par_departement,
    doubles_comptes,
    enrichir,
    lire,
    population_par_departement,
    population_totale,
)


@pytest.fixture
def session() -> Session:
    """SQLite avec les clés étrangères appliquées, comme le reste du module."""
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _activer_les_fk(connexion, _):
        connexion.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


COMMUNES = [
    # code, type, parente, nom, département, population
    ("01033", "COM", "", "Valserhône", "01", "16423"),
    ("01205", "COMD", "01033", "Lancrans", "01", "1054"),
    ("01039", "COM", "", "Béon", "01", "454"),
    ("28012", "COM", "", "Commune nouvelle d'Arrou", "28", "3803"),
    ("28999", "COM", "", "Sans Rien", "28", "100"),
]
GEOMETRIE = [("01033", "46.1", "5.8"), ("28012", "48.1", "1.1"), ("28999", "48.2", "1.2")]
PASSAGE = [
    ("01039", "01138", "Culoz-Béon", "2023-01-01", "création de commune nouvelle"),
    ("01205", "01033", "Valserhône", "2019-01-01", "création de commune nouvelle"),
    ("28012", "28012", "Vald'Yerre", "2023-01-01", "changement de nom"),
]


@pytest.fixture
def dossier(tmp_path: Path) -> Path:
    def ecrire(nom: str, entete: list[str], lignes: list[tuple]) -> None:
        with (tmp_path / nom).open("w", encoding="utf-8", newline="") as f:
            plume = csv.writer(f)
            plume.writerow(entete)
            plume.writerows(lignes)

    ecrire(
        "communes_2019.csv",
        ["code", "type", "commune_parente", "nom", "departement", "population"],
        COMMUNES,
    )
    ecrire("geometrie.csv", ["code", "latitude", "longitude"], GEOMETRIE)
    ecrire(
        "passage.csv",
        ["code_2019", "code_courant", "nom_courant", "date_effet", "evenement"],
        PASSAGE,
    )
    return tmp_path


# --- lire ---


def test_assemble_les_trois_extraits(dossier):
    referentiel = lire(dossier)
    valserhone = referentiel["01033"]
    assert valserhone.nom == "Valserhône"
    assert valserhone.population == 16423
    assert (valserhone.latitude, valserhone.longitude) == (46.1, 5.8)


def test_une_commune_inchangee_porte_son_propre_code_courant(dossier):
    """NULL voudrait dire « inchangée », ce que chaque lecture aurait à retenir."""
    commune = lire(dossier)["28999"]
    assert commune.code_courant == "28999"
    assert commune.nom_courant == "Sans Rien"


def test_une_commune_sans_geometrie_reste_sans_coordonnees(dossier):
    assert lire(dossier)["01039"].latitude is None


def test_la_deleguee_connait_sa_parente(dossier):
    lancrans = lire(dossier)["01205"]
    assert lancrans.deleguee
    assert lancrans.commune_parente == "01033"


# --- population ---


def test_ne_compte_pas_deux_fois_une_deleguee_et_sa_parente(dossier):
    """Les 1 054 habitants de Lancrans sont déjà dans les 16 423 de Valserhône."""
    referentiel = lire(dossier)
    assert population_totale({"01033", "01205"}, referentiel) == 16423


def test_une_deleguee_seule_compte_pour_elle_meme(dossier):
    """Sans sa parente dans l'ensemble, il n'y a pas de recouvrement à retirer."""
    assert population_totale({"01205"}, lire(dossier)) == 1054


def test_les_doubles_comptes_sont_nommes(dossier):
    assert doubles_comptes({"01033", "01205"}, lire(dossier)) == [("01205", "01033")]


def test_aucun_double_compte_sans_la_parente(dossier):
    assert doubles_comptes({"01205", "01039"}, lire(dossier)) == []


def test_le_denominateur_departemental_ignore_les_deleguees(dossier):
    referentiel = lire(dossier)
    assert population_par_departement(referentiel)["01"] == 16423 + 454
    assert communes_par_departement(referentiel)["01"] == 2


# --- enrichir ---


def test_renseigne_les_communes_deja_en_base(session, dossier):
    session.add(City(code="01033", name="VALSERHONE"))
    session.flush()

    rapport = enrichir(session, lire(dossier))

    ville = session.get(City, "01033")
    assert ville.official_name == "Valserhône"
    assert ville.population == 16423
    assert ville.cog_type == "COM"
    assert rapport.rapprochees == 1


def test_n_ecrase_pas_la_graphie_du_corpus(session, dossier):
    """`name` est un fait de provenance : ce qu'a écrit l'en-tête du cahier."""
    session.add(City(code="01033", name="VALSERHONE"))
    session.flush()

    enrichir(session, lire(dossier))

    assert session.get(City, "01033").name == "VALSERHONE"


def test_ne_cree_aucune_commune(session, dossier):
    """Le référentiel renseigne le corpus, il ne décide pas de son périmètre."""
    enrichir(session, lire(dossier))
    assert session.query(City).count() == 0


def test_signale_un_code_absent_du_referentiel(session, dossier):
    session.add(City(code="99999"))
    session.flush()

    rapport = enrichir(session, lire(dossier))

    assert rapport.inconnues == ["99999"]
    assert rapport.rapprochees == 0


def test_classe_une_deleguee_comme_telle_et_non_comme_disparue(session, dossier):
    """Elle n'a pas disparu depuis 2019 : elle avait déjà disparu avant."""
    session.add(City(code="01205"))
    session.flush()

    rapport = enrichir(session, lire(dossier))

    assert rapport.deleguees == ["01205"]
    assert rapport.disparues == []


def test_repere_une_commune_disparue_depuis_le_pivot(session, dossier):
    session.add(City(code="01039"))
    session.flush()

    rapport = enrichir(session, lire(dossier))

    assert rapport.disparues == ["01039"]
    assert session.get(City, "01039").current_code == "01138"


def test_un_renommage_n_est_pas_une_disparition(session, dossier):
    """Le code n'a pas bougé : rien à rattraper, seulement à signaler."""
    session.add(City(code="28012"))
    session.flush()

    rapport = enrichir(session, lire(dossier))

    assert rapport.renommees == ["28012"]
    assert rapport.disparues == []


def test_une_absorbee_n_est_pas_comptee_comme_renommee(session, dossier):
    """Son `nom_courant` est celui de la commune qui l'a absorbée, pas le sien."""
    session.add(City(code="01039"))
    session.flush()

    assert enrichir(session, lire(dossier)).renommees == []


def test_compte_les_communes_sans_coordonnees(session, dossier):
    session.add_all([City(code="01033"), City(code="01039")])
    session.flush()

    assert enrichir(session, lire(dossier)).sans_coordonnees == 1


# --- le référentiel versionné du dépôt ---


def test_le_referentiel_versionne_se_lit():
    referentiel = lire()
    assert len(referentiel) > 1000
    assert all(c.population is not None for c in referentiel.values())


@pytest.mark.parametrize(
    ("code", "nom", "code_courant"),
    [
        # Déposés sous un code qui ne désignait déjà plus une commune de plein
        # exercice : Dommartin avait fusionné un an avant les cahiers, Lancrans
        # le 1er janvier 2019, six semaines avant.
        ("01144", "Dommartin", "01025"),
        ("01205", "Lancrans", "01033"),
        # Commune de plein exercice en 2019, absorbée depuis.
        ("01039", "Béon", "01138"),
    ],
)
def test_les_cas_limites_du_corpus_sont_bien_rattaches(code, nom, code_courant):
    """Ces trois-là sont la raison d'être du millésime pivot et de la table de passage."""
    commune = lire()[code]
    assert commune.nom == nom
    assert commune.code_courant == code_courant


def test_le_referentiel_versionne_couvre_les_departements_du_corpus():
    """Un cahier dont le code manque au référentiel n'aurait ni population ni poids."""
    referentiel = lire()
    departements = {c.departement for c in referentiel.values()}
    assert departements == {"01", "28", "39", "53"}
    # Un code par département, pris dans les noms de fichiers du corpus.
    assert {"01053", "28012", "39198", "53007"} <= set(referentiel)


def test_les_contours_se_lisent_en_anneaux_latitude_longitude(tmp_path):
    import json

    from insee.cog import contours_departements

    (tmp_path / "departements.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"code": "53", "nom": "Mayenne"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-0.9, 48.0], [-0.5, 48.0], [-0.5, 48.4], [-0.9, 48.0]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"code": "2A", "nom": "Corse-du-Sud"},
                        "geometry": {
                            "type": "MultiPolygon",
                            "coordinates": [
                                [[[9.0, 41.5], [9.2, 41.5], [9.0, 41.5]]],
                                [[[8.5, 41.9], [8.6, 41.9], [8.5, 41.9]], [[8.55, 41.91], [8.56, 41.91], [8.55, 41.91]]],
                            ],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    contours = contours_departements(tmp_path)

    assert contours["53"] == [[(48.0, -0.9), (48.0, -0.5), (48.4, -0.5), (48.0, -0.9)]]
    assert len(contours["2A"]) == 2  # deux morceaux, le trou du second ignoré
    assert contours["2A"][1] == [(41.9, 8.5), (41.9, 8.6), (41.9, 8.5)]
    assert contours_departements(tmp_path / "ailleurs") == {}


def test_le_referentiel_versionne_couvre_la_metropole():
    from insee.cog import contours_departements

    contours = contours_departements()
    assert len(contours) == 96
    assert {"01", "28", "39", "53", "2A", "2B"} <= set(contours)
    assert all(anneau[0] == anneau[-1] for anneaux in contours.values() for anneau in anneaux)
