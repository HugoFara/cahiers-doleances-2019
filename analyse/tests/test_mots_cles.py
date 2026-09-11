"""Le rattachement par mots-clés : lexique vérifié, run à part, instances
citant le texte — recherche bouchonnée, SQLite en mémoire. Le lexique commité
est lui-même vérifié contre la grille."""

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from analyse import mots_cles
from analyse.mots_cles import (
    DETECTEUR,
    charger,
    lire_lexique,
    termes_trouves,
    verifier_cibles,
)
from database.models import Base, Doleance, Instance, Topic
from database.runs import ANALYSE, SEGMENTATION, creer_run

GRILLES = Path(__file__).resolve().parents[1] / "grilles"


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _grille(tmp_path: Path) -> Path:
    grille = {
        "label": "test",
        "source": {"titre": "t", "url": "u"},
        "topics": [
            {
                "id": "r",
                "name": "racine",
                "description": "",
                "parent": None,
                "level": 1,
            },
            {"id": "q1", "name": "impôts", "description": "", "parent": "r"},
            {"id": "q2", "name": "vote blanc", "description": "", "parent": "r"},
        ],
    }
    chemin = tmp_path / "grille.json"
    chemin.write_text(json.dumps(grille), encoding="utf-8")
    return chemin


def _lexique(tmp_path: Path, requetes: dict, **extra) -> Path:
    _grille(tmp_path)
    lexique = {
        "grille": "grille.json",
        "detecteur": DETECTEUR,
        "requetes": requetes,
    } | extra
    chemin = tmp_path / "grille.mots_cles.json"
    chemin.write_text(json.dumps(lexique, ensure_ascii=False), encoding="utf-8")
    return chemin


def _decoupage(session, textes: list[str]) -> int:
    run = creer_run(session, SEGMENTATION, label="découpage", author="t")
    session.flush()
    for i, texte in enumerate(textes, start=1):
        session.add(
            Doleance(
                run_id=run.id,
                contribution_id=i,
                pdf_name="c.pdf",
                text=texte,
                position=i,
            )
        )
    session.flush()
    return run.id


def _recherche(session, requete: str, run_decoupage: int) -> list[tuple]:
    """Bouchon de la recherche plein texte : sous-chaîne pliée, un terme suffit."""
    from recherche.extraits import plier, termes

    lignes = session.execute(
        select(Doleance.id, Doleance.contribution_id, Doleance.text).where(
            Doleance.run_id == run_decoupage
        )
    ).all()
    mots = termes(requete)
    return [
        ligne for ligne in lignes if any(m in plier(ligne.text or "") for m in mots)
    ]


class TestLexique:
    def test_une_cle_manquante_leve_value_error(self, tmp_path):
        chemin = tmp_path / "l.json"
        chemin.write_text('{"grille": "g.json", "requetes": {"q1": "impôt"}}')
        with pytest.raises(ValueError, match="clés manquantes"):
            lire_lexique(chemin)

    def test_un_autre_detecteur_est_refuse(self, tmp_path):
        chemin = _lexique(tmp_path, {"q1": "impôt"}, detecteur="LLM")
        with pytest.raises(ValueError, match="détecteur"):
            lire_lexique(chemin)

    def test_une_requete_sans_terme_est_refusee(self, tmp_path):
        chemin = _lexique(tmp_path, {"q1": "impôt", "q2": "or -taxe"})
        with pytest.raises(ValueError, match="sans terme"):
            lire_lexique(chemin)

    def test_un_theme_inconnu_de_la_grille_est_refuse(self, tmp_path):
        chemin = _lexique(tmp_path, {"q9": "impôt"})
        with pytest.raises(ValueError, match="thèmes inconnus"):
            verifier_cibles(
                lire_lexique(chemin), json.loads((tmp_path / "grille.json").read_text())
            )


class TestTermesTrouves:
    def test_retrouve_les_termes_a_l_accent_et_au_pluriel_pres(self):
        texte = "Les IMPOTS sont trop lourds, la taxe fonciere aussi."
        assert termes_trouves(texte, "impôt or taxe or ISF") == ["impot", "taxe"]

    def test_une_expression_compte_par_ses_mots(self):
        assert termes_trouves(
            "Je demande le vote blanc.", '"vote blanc" or abstention'
        ) == [
            "vote",
            "blanc",
        ]


class TestChargement:
    def test_un_run_a_part_non_actif_porte_le_detecteur_et_les_requetes(
        self, session, tmp_path
    ):
        _decoupage(session, ["Baissez les impôts !"])
        chemin = _lexique(tmp_path, {"q1": "impôt", "q2": '"vote blanc"'})
        run, comptes = charger(session, chemin, auteur="t", chercher=_recherche)
        assert run.kind == ANALYSE
        assert run.active is False
        assert run.model == DETECTEUR
        assert run.label == f"test — {DETECTEUR}"
        assert run.parameters["requetes"] == {"q1": "impôt", "q2": '"vote blanc"'}
        assert run.parameters["detector"] == DETECTEUR
        assert comptes == {"q1": 1, "q2": 0}
        themes = session.scalars(select(Topic).where(Topic.run_id == run.id)).all()
        assert {t.external_id for t in themes} == {"r", "q1", "q2"}

    def test_chaque_doleance_qui_repond_donne_une_instance_citant_le_texte(
        self, session, tmp_path
    ):
        _decoupage(
            session,
            [
                "Baissez les impôts, c'est urgent.",
                "Rien à voir.",
                "Reconnaître le vote blanc.",
            ],
        )
        chemin = _lexique(tmp_path, {"q1": "impôt or taxe", "q2": '"vote blanc"'})
        run, comptes = charger(session, chemin, auteur="t", chercher=_recherche)
        assert comptes == {"q1": 1, "q2": 1}
        instances = session.scalars(
            select(Instance)
            .where(Instance.run_id == run.id)
            .order_by(Instance.doleance_id)
        ).all()
        assert [i.doleance_id for i in instances] == [1, 3]
        assert [i.contribution_id for i in instances] == [1, 3]
        assert instances[0].external_doc_id == "d1"
        assert instances[0].summary == f"{DETECTEUR} : impot"
        # le verbatim est un passage du texte, sans points de suspension
        assert instances[0].verbatim in "Baissez les impôts, c'est urgent."
        assert instances[1].verbatim == "Reconnaître le vote blanc."

    def test_relancer_remplace_les_instances_sans_dupliquer_le_run(
        self, session, tmp_path
    ):
        _decoupage(session, ["Baissez les impôts !"])
        chemin = _lexique(tmp_path, {"q1": "impôt", "q2": '"vote blanc"'})
        run1, _ = charger(session, chemin, auteur="t", chercher=_recherche)
        session.commit()
        chemin = _lexique(tmp_path, {"q1": "taxe", "q2": '"vote blanc"'})
        run2, comptes = charger(session, chemin, auteur="t", chercher=_recherche)
        assert run2.id == run1.id
        assert comptes == {"q1": 0, "q2": 0}
        assert (
            session.scalar(select(Instance).where(Instance.run_id == run1.id)) is None
        )
        assert run2.parameters["requetes"]["q1"] == "taxe"

    def test_sans_decoupage_actif_on_refuse(self, session, tmp_path):
        chemin = _lexique(tmp_path, {"q1": "impôt"})
        with pytest.raises(ValueError, match="aucun découpage actif"):
            charger(session, chemin, auteur="t", chercher=_recherche)

    def test_activer_en_fait_la_grille_servie(self, session, tmp_path):
        _decoupage(session, ["Baissez les impôts !"])
        chemin = _lexique(tmp_path, {"q1": "impôt"})
        run, _ = charger(session, chemin, auteur="t", activer=True, chercher=_recherche)
        assert run.active is True


class TestLexiqueCadrage2019:
    """Le lexique commité vise la grille commitée, question par question."""

    def test_le_lexique_vise_les_20_questions_de_la_grille(self):
        lexique = lire_lexique(GRILLES / "cadrage_gouvernemental_2019.mots_cles.json")
        grille = mots_cles.lire_grille(GRILLES / lexique["grille"])
        verifier_cibles(lexique, grille)
        questions = {t["id"] for t in grille["topics"] if t["parent"] is not None}
        assert set(lexique["requetes"]) == questions
        assert len(questions) == 20

    def test_aucune_requete_ne_nomme_le_document_lui_meme(self):
        """« cahier de doléances » et « grand débat » rattacheraient tout le corpus."""
        lexique = lire_lexique(GRILLES / "cadrage_gouvernemental_2019.mots_cles.json")
        for requete in lexique["requetes"].values():
            assert "doléances" not in requete.lower()
            assert "grand débat" not in requete.lower()


class TestLexiqueVraiDebat2019:
    """Le lexique du Vrai Débat vise ses neuf rubriques, et ne nomme pas le document."""

    def test_le_lexique_vise_les_9_rubriques_de_la_grille(self):
        lexique = lire_lexique(GRILLES / "vrai_debat_2019.mots_cles.json")
        grille = mots_cles.lire_grille(GRILLES / lexique["grille"])
        verifier_cibles(lexique, grille)
        assert set(lexique["requetes"]) == {t["id"] for t in grille["topics"]}
        assert len(lexique["requetes"]) == 9

    def test_aucune_requete_ne_nomme_le_document_ni_son_contexte(self):
        """Le corpus parle de lui-même et des gilets jaunes : ce n'est pas un thème."""
        lexique = lire_lexique(GRILLES / "vrai_debat_2019.mots_cles.json")
        for requete in lexique["requetes"].values():
            bas = requete.lower()
            assert "doléances" not in bas
            assert "grand débat" not in bas
            assert "vrai débat" not in bas
            assert "gilets jaunes" not in bas
