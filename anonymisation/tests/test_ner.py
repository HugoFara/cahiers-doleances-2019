"""La reconnaissance d'entités nommées : découpage en morceaux à offsets
exacts, passage des entités du modèle aux offsets du texte, seuils et
genres — modèle bouchonné, jamais chargé."""

import pytest

from anonymisation.detecteurs import INSTITUTION, LIEU, NOM, fusionner
from anonymisation.ner import EntitesNommees, morceaux
from anonymisation.passe import detecter_tout
from anonymisation.rendu import PassageRendu, caviarder


class TestMorceaux:
    def test_chaque_morceau_est_une_tranche_exacte_du_texte(self):
        texte = "Une phrase. Une autre !\nParagraphe deux.\n\n" + "Longue phrase. " * 50
        for debut, morceau in morceaux(texte, 200):
            assert texte[debut : debut + len(morceau)] == morceau
            assert len(morceau) <= 200

    def test_les_lignes_courtes_sont_regroupees_sauts_de_ligne_compris(self):
        """Le texte de l'OCR a un saut de ligne par ligne du scan : une ligne par
        appel du modèle serait dix fois trop lent, et le contexte se perd."""
        assert morceaux("Une phrase. Une autre.\nSuite.", 100) == [
            (0, "Une phrase. Une autre.\nSuite."),
        ]
        assert morceaux("Une phrase. Une autre.\nSuite.", 24) == [
            (0, "Une phrase. Une autre."),
            (23, "Suite."),
        ]

    def test_un_paragraphe_long_se_coupe_aux_phrases_et_se_regroupe(self):
        texte = "Aaaa aaaa. " * 10  # 110 caractères, dix phrases
        ms = morceaux(texte, 50)
        assert [len(m.strip()) for _, m in ms] == [43, 43, 21]
        assert all(m.strip().endswith(".") for _, m in ms)

    def test_une_phrase_plus_longue_que_la_taille_se_coupe_a_la_taille(self):
        texte = "x" * 250
        assert [(d, len(m)) for d, m in morceaux(texte, 100)] == [
            (0, 100),
            (100, 100),
            (200, 50),
        ]

    def test_les_lignes_vides_ne_donnent_rien(self):
        assert morceaux("\n\n  \n", 100) == []


def _bouchon(entites_par_morceau):
    """Un détecteur dont le modèle rend, pour chaque morceau, les entités données."""
    ner = EntitesNommees(modele="bouchon")
    ner.entites = lambda morceau: entites_par_morceau.get(morceau, [])
    return ner


class TestDetecter:
    def test_les_offsets_reviennent_au_texte_entier(self):
        texte = "Première ligne sans rien.\nJ'ai parlé à Bernard Martin hier."
        # les deux lignes tiennent dans un morceau : le modèle voit le texte
        # entier, et ses offsets sont déjà ceux du texte
        ner = _bouchon(
            {
                texte: [
                    {
                        "entity_group": "PER",
                        "score": 0.99,
                        "start": 39,
                        "end": 53,
                        "word": "Bernard Martin",
                    }
                ]
            }
        )
        (p,) = ner.detecter(texte)
        assert texte[p.debut : p.fin] == "Bernard Martin"
        assert p.genre == NOM
        assert p.detecteur == "ner:bouchon"

    def test_les_offsets_d_un_second_morceau_sont_decales(self):
        texte = "Première ligne sans rien.\nJ'ai parlé à Bernard Martin hier."
        ner = _bouchon(
            {
                "J'ai parlé à Bernard Martin hier.": [
                    {
                        "entity_group": "PER",
                        "score": 0.99,
                        "start": 13,
                        "end": 27,
                        "word": "x",
                    }
                ]
            }
        )
        ner.taille = 40  # la seconde ligne fait un morceau à elle seule, à l'offset 26
        (p,) = ner.detecter(texte)
        assert (p.debut, p.fin) == (39, 53)
        assert texte[p.debut : p.fin] == "Bernard Martin"

    def test_les_blancs_et_la_ponctuation_accroches_au_span_sont_rognes(self):
        texte = "Vu avec Bernard, hier."
        ner = _bouchon(
            {
                texte: [
                    {
                        "entity_group": "PER",
                        "score": 0.9,
                        "start": 7,
                        "end": 16,
                        "word": " Bernard,",
                    }
                ]
            }
        )
        (p,) = ner.detecter(texte)
        assert texte[p.debut : p.fin] == "Bernard"

    def test_les_genres_et_leurs_seuils(self):
        texte = "Bernard habite Segny et travaille à la SNCF, dixit Le Monde."
        entites = [
            {
                "entity_group": "PER",
                "score": 0.45,
                "start": 0,
                "end": 7,
                "word": "Bernard",
            },
            {
                "entity_group": "LOC",
                "score": 0.55,
                "start": 15,
                "end": 20,
                "word": "Segny",
            },
            {
                "entity_group": "ORG",
                "score": 0.95,
                "start": 39,
                "end": 43,
                "word": "SNCF",
            },
            {
                "entity_group": "MISC",
                "score": 0.99,
                "start": 51,
                "end": 59,
                "word": "Le Monde",
            },
        ]
        passages = _bouchon({texte: entites}).detecter(texte)
        assert [(texte[p.debut : p.fin], p.genre) for p in passages] == [
            ("Bernard", NOM),  # 0,45 >= 0,4 : gardé, rappel avant précision
            ("SNCF", INSTITUTION),
        ]  # le lieu à 0,55 est sous son seuil de 0,6 ; MISC est ignoré

    def test_un_lieu_ne_se_caviarde_pas_un_nom_si(self):
        texte = "Bernard, de Segny."
        passages = _bouchon(
            {
                texte: [
                    {
                        "entity_group": "PER",
                        "score": 0.9,
                        "start": 0,
                        "end": 7,
                        "word": "Bernard",
                    },
                    {
                        "entity_group": "LOC",
                        "score": 0.9,
                        "start": 12,
                        "end": 17,
                        "word": "Segny",
                    },
                ]
            }
        ).detecter(texte)
        rendus = [PassageRendu(p.debut, p.fin, p.genre) for p in passages]
        assert caviarder(texte, rendus) == "[nom], de Segny."
        assert passages[1].genre == LIEU


class TestCombiner:
    def test_un_lieu_du_modele_ne_decaviarde_pas_une_adresse(self):
        from anonymisation.detecteurs import ADRESSE, Passage
        from anonymisation.passe import combiner

        adresse = Passage(0, 16, ADRESSE, "regex_adresse")
        lieu = Passage(3, 16, LIEU, "ner:x")
        assert combiner([adresse], [lieu]) == [adresse]

    def test_une_organisation_du_modele_ne_decaviarde_pas_un_courriel(self):
        from anonymisation.detecteurs import EMAIL, Passage
        from anonymisation.passe import combiner

        courriel = Passage(0, 16, EMAIL, "regex_email")
        org = Passage(0, 7, INSTITUTION, "ner:x")
        assert combiner([courriel], [org]) == [courriel]

    def test_un_lieu_hors_de_toute_forme_est_garde(self):
        from anonymisation.detecteurs import Passage
        from anonymisation.passe import combiner

        lieu = Passage(20, 25, LIEU, "ner:x")
        assert combiner([Passage(0, 5, NOM, "signature")], [lieu]) == [
            Passage(0, 5, NOM, "signature"),
            lieu,
        ]

    def test_un_nom_du_modele_se_fond_dans_un_role_public(self):
        from anonymisation.detecteurs import ROLE_PUBLIC, Passage
        from anonymisation.passe import combiner

        role = Passage(0, 17, ROLE_PUBLIC, "roles")
        (p,) = combiner([role], [Passage(12, 17, NOM, "ner:x")])
        assert p.genre == ROLE_PUBLIC


class TestFusionAvecLesFormes:
    def test_le_role_public_l_emporte_sur_le_nom_du_modele(self):
        from anonymisation.detecteurs import ROLE_PUBLIC, Passage

        formes = [Passage(0, 17, ROLE_PUBLIC, "roles")]
        ner = [Passage(12, 17, NOM, "ner:x")]
        (p,) = fusionner(formes + ner)
        assert (p.debut, p.fin, p.genre) == (0, 17, ROLE_PUBLIC)


@pytest.fixture
def session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from database.models import Base

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_la_passe_ecrit_les_passages_du_modele_avec_son_detecteur(session):
    from sqlalchemy import select

    from database.models import PiiSpan
    from database.runs import ANONYMISATION, creer_run

    run = creer_run(session, ANONYMISATION, label="t", author="t")
    session.flush()
    texte = "J'ai parlé à Bernard Martin, tel 06 12 34 56 78."
    ner = _bouchon(
        {
            texte: [
                {
                    "entity_group": "PER",
                    "score": 0.9,
                    "start": 13,
                    "end": 27,
                    "word": "Bernard Martin",
                }
            ]
        }
    )
    comptes = detecter_tout(session, run.id, {1: texte}, ner)
    assert comptes == {NOM: 1, "telephone": 1}
    spans = session.scalars(select(PiiSpan).order_by(PiiSpan.start)).all()
    assert [(texte[s.start : s.end], s.kind, s.detector) for s in spans] == [
        ("Bernard Martin", NOM, "ner:bouchon"),
        ("06 12 34 56 78", "telephone", "regex_telephone"),
    ]
