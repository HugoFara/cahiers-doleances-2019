"""Tests du chargement d'une grille écrite à la main, et de la grille livrée."""

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from analyse.grille import charger, lire_grille
from database.models import Base, Run, Topic
from database.runs import ANALYSE, creer_run

CADRAGE = Path(__file__).resolve().parents[1] / "grilles" / "cadrage_gouvernemental_2019.json"


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def grille(tmp_path, topics, **extra) -> Path:
    contenu = {"label": "essai", "source": {"titre": "t", "url": "u"}, "topics": topics, **extra}
    fichier = tmp_path / "grille.json"
    fichier.write_text(json.dumps(contenu), encoding="utf-8")
    return fichier


def theme(id, parent=None, **champs) -> dict:
    return {"id": id, "name": id, "description": f"description de {id}", "parent": parent, **champs}


class TestLecture:
    def test_les_valeurs_par_defaut_sont_posees(self, tmp_path):
        g = lire_grille(grille(tmp_path, [theme("a")]))
        assert g["topics"][0]["level"] == 0
        assert g["topics"][0]["validated"] is False

    def test_une_cle_absente_est_une_erreur(self, tmp_path):
        with pytest.raises(ValueError, match="sans"):
            lire_grille(grille(tmp_path, [{"id": "a", "name": "a"}]))

    def test_un_identifiant_en_double_est_une_erreur(self, tmp_path):
        with pytest.raises(ValueError, match="double"):
            lire_grille(grille(tmp_path, [theme("a"), theme("a")]))

    def test_un_parent_inconnu_est_une_erreur(self, tmp_path):
        """Une grille de cadrage se relit à la main, elle ne se répare pas au chargement."""
        with pytest.raises(ValueError, match="parent inconnu"):
            lire_grille(grille(tmp_path, [theme("a", parent="fantome")]))

    def test_une_grille_vide_est_une_erreur(self, tmp_path):
        with pytest.raises(ValueError, match="aucun"):
            lire_grille(grille(tmp_path, []))


class TestChargement:
    def test_la_grille_devient_un_run_non_actif(self, session, tmp_path):
        """Sans détections, elle n'a rien à servir : elle est listée, pas servie."""
        autre = creer_run(session, ANALYSE, label="servie", author="x")
        run = charger(session, grille(tmp_path, [theme("a"), theme("b", "a")]), auteur="x")
        assert run.kind == ANALYSE
        assert run.active is False
        assert autre.active is True
        assert run.model is None
        assert "t — u" == run.notes

    def test_les_themes_et_leur_parente_sont_en_base(self, session, tmp_path):
        run = charger(session, grille(tmp_path, [theme("a"), theme("b", "a")]), auteur="x")
        topics = {t.external_id: t for t in session.query(Topic).filter(Topic.run_id == run.id)}
        assert set(topics) == {"a", "b"}
        assert topics["b"].parent_id == topics["a"].id
        assert topics["a"].parent_id is None

    def test_recharger_le_meme_fichier_met_a_jour_sans_dupliquer(self, session, tmp_path):
        fichier = grille(tmp_path, [theme("a")])
        premier = charger(session, fichier, auteur="x")
        fichier.write_text(
            json.dumps({"label": "essai", "source": {}, "topics": [theme("a", name="renommé")]})
        )
        second = charger(session, fichier, auteur="x")
        assert second.id == premier.id
        assert session.query(Run).count() == 1
        assert session.query(Topic).one().name == "renommé"

    def test_activer_en_fait_la_grille_servie(self, session, tmp_path):
        autre = creer_run(session, ANALYSE, label="servie", author="x")
        run = charger(session, grille(tmp_path, [theme("a")]), auteur="x", activer=True)
        assert run.active is True
        assert autre.active is False


class TestCadrageGouvernemental2019:
    """La grille livrée : ce qu'elle doit être pour rester une reproduction."""

    @pytest.fixture
    def cadrage(self) -> dict:
        return lire_grille(CADRAGE)

    def test_quatre_themes_de_la_lettre_aux_francais(self, cadrage):
        racines = [t for t in cadrage["topics"] if t["parent"] is None]
        assert [t["name"] for t in racines] == [
            "La fiscalité et les dépenses publiques",
            "L'organisation de l'État et des services publics",
            "La transition écologique",
            "La démocratie et la citoyenneté",
        ]

    def test_chaque_question_est_reproduite_telle_quelle(self, cadrage):
        """La description d'un thème enfant est la question de la lettre, pas une glose."""
        questions = [t for t in cadrage["topics"] if t["parent"] is not None]
        assert len(questions) == 20
        assert all(t["description"].endswith("?") for t in questions)

    def test_la_source_est_nommee_et_datee(self, cadrage):
        assert cadrage["source"]["url"].startswith("https://www.elysee.fr/")
        assert cadrage["source"]["consultee_le"]

    def test_rien_n_est_marque_valide_d_avance(self, cadrage):
        """Les noms courts sont éditoriaux : c'est à une relecture de les valider."""
        assert not any(t["validated"] for t in cadrage["topics"])

    def test_elle_se_charge(self, session):
        run = charger(session, CADRAGE, auteur="x")
        assert session.query(Topic).filter(Topic.run_id == run.id).count() == 24
