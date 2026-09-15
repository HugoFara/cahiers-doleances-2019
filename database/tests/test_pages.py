"""Le texte de lecture : transcription active d'abord, squelette sinon, rien
pour le manuscrit sans transcription — SQLite en mémoire."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.models import Base, PageExtraction, PageTranscription, Run
from database.pages import (
    AUCUNE,
    SQUELETTE,
    TRANSCRIPTION_ACTIVE,
    derives,
    est_commentaire_page_vide,
    est_derive,
    lire_pages,
)
from database.runs import TRANSCRIPTION, creer_run


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _page(
    session,
    numero,
    texte,
    needs_ocr,
    pdf="CC_01000_190304_01053_MD_15462.pdf",
    categorie="CC",
):
    page = PageExtraction(
        pdf_name=pdf,
        page_number=numero,
        text=texte,
        quality_score=0.1 if needs_ocr else 0.9,
        needs_ocr=needs_ocr,
        contribution_id=1,
        categorie=categorie,
    )
    session.add(page)
    session.flush()
    return page


def _run(session, actif=True) -> Run:
    run = creer_run(
        session, TRANSCRIPTION, label="OCR", source="test", author="t", actif=actif
    )
    session.flush()
    return run


def _transcrire(session, run, page, texte):
    session.add(
        PageTranscription(
            run_id=run.id,
            page_extraction_id=page.id,
            pdf_name=page.pdf_name,
            page_number=page.page_number,
            text=texte,
            quality_score=0.9,
        )
    )
    session.flush()


def test_sans_run_de_transcription_on_lit_le_squelette_et_pas_le_manuscrit(session):
    _page(session, 3, "texte typé", False)
    _page(session, 4, "bru1t d'extr@ction", True)
    lues = lire_pages(session)
    assert [(p.page.page_number, p.texte, p.source) for p in lues] == [
        (3, "texte typé", SQUELETTE)
    ]


def test_les_illisibles_se_gardent_sur_demande(session):
    _page(session, 3, "texte typé", False)
    _page(session, 4, "bru1t", True)
    lues = lire_pages(session, garder_illisibles=True)
    assert [p.source for p in lues] == [SQUELETTE, AUCUNE]
    assert lues[1].texte == ""
    assert not lues[1].lisible


def test_la_transcription_du_run_actif_prime_sur_le_squelette(session):
    typee = _page(session, 3, "texte typé", False)
    manuscrite = _page(session, 4, "bru1t", True)
    run = _run(session)
    _transcrire(session, run, manuscrite, "Pouvoir d'achat : ce terme…")
    _transcrire(session, run, typee, "texte typé, relu par l'OCR")
    lues = lire_pages(session)
    assert [(p.texte, p.source) for p in lues] == [
        ("texte typé, relu par l'OCR", TRANSCRIPTION_ACTIVE),
        ("Pouvoir d'achat : ce terme…", TRANSCRIPTION_ACTIVE),
    ]
    assert lues[1].transcription.run_id == run.id


def test_un_run_non_actif_ne_compte_pas(session):
    manuscrite = _page(session, 4, "bru1t", True)
    run = _run(session, actif=False)
    _transcrire(session, run, manuscrite, "lisible")
    assert lire_pages(session) == []


def test_seul_le_run_actif_est_lu_quand_deux_coexistent(session):
    manuscrite = _page(session, 4, "bru1t", True)
    ancien = _run(session, actif=False)
    _transcrire(session, ancien, manuscrite, "ancienne lecture")
    nouveau = _run(session)
    _transcrire(session, nouveau, manuscrite, "nouvelle lecture")
    (lue,) = lire_pages(session)
    assert lue.texte == "nouvelle lecture"


def test_le_commentaire_du_modele_sur_une_page_vide_ne_se_lit_pas(session):
    vide = _page(session, 5, "", True)
    run = _run(session)
    _transcrire(
        session,
        run,
        vide,
        "Cette image ne contient aucun texte. Il s'agit d'une page jaune uniforme.",
    )
    (lue,) = lire_pages(session, garder_illisibles=True)
    assert lue.source == TRANSCRIPTION_ACTIVE
    assert lue.texte == ""
    assert lue.lisible  # la page a bien été transcrite : elle est vide, pas illisible


@pytest.mark.parametrize(
    "texte",
    [
        "L'image ne contient aucun texte visible.",
        "La page ne contient aucun texte",
        "Cette image ne contient aucun texte. Il s'agit d'une page de couleur jaune.",
        "Le document est une page blanche, sans écriture.",
        "Page vierge.",
    ],
)
def test_les_formulations_de_page_vide_sont_reconnues(texte):
    assert est_commentaire_page_vide(texte)


@pytest.mark.parametrize(
    "texte",
    [
        "Pouvoir d'achat : ce terme ne veut pas dire grand chose.",
        "On nous laisse une page vide pour nous exprimer, alors je m'exprime : " * 6,
        "Il faut baisser les impôts.",
    ],
)
def test_une_vraie_contribution_n_est_pas_prise_pour_une_page_vide(texte):
    assert not est_commentaire_page_vide(texte)


def test_l_ordre_contribution_suit_l_export(session):
    _page(session, 9, "b", False, pdf="CC_02.pdf")
    _page(session, 2, "a", False, pdf="CC_01.pdf")
    assert [p.texte for p in lire_pages(session, ordre="cahier")] == ["a", "b"]
    assert [p.texte for p in lire_pages(session, ordre="contribution")] == ["a", "b"]
    with pytest.raises(ValueError, match="ordre inconnu"):
        lire_pages(session, ordre="page")


def test_le_filtre_par_contribution(session):
    _page(session, 2, "a", False)
    b = _page(session, 3, "b", False)
    b.contribution_id = 2
    session.flush()
    assert [p.texte for p in lire_pages(session, contributions=[2])] == ["b"]
    assert [p.texte for p in lire_pages(session, contributions=[])] == []
    assert [p.texte for p in lire_pages(session)] == ["a", "b"]


# --- dérives du modèle -------------------------------------------------------

PHRASE = "Il faut baisser les impôts et rouvrir la gare de notre village. "
LIGNE_BOUCLE = "1) Je demande le RIC\n"


@pytest.mark.parametrize(
    "texte",
    [
        # trop de caractères pour une page, quel que soit le contenu
        "".join(f"paragraphe {i} : {PHRASE}" for i in range(220)),
        # trop de mots pour une page
        " ".join(f"mot{i}" for i in range(2_100)),
        # la même ligne, des milliers de fois
        LIGNE_BOUCLE * 5_000,
        # les mêmes n-grammes, en boucle, sur une page de taille plausible
        PHRASE * 30,
    ],
)
def test_une_derive_est_reconnue(texte):
    assert est_derive(texte)


@pytest.mark.parametrize(
    "texte",
    [
        "",
        "Il faut baisser les impôts.",
        # une vraie page dense : 600 mots distincts, des lignes distinctes
        "\n".join(" ".join(f"mot{i * 12 + j}" for j in range(12)) for i in range(50)),
        # un refrain répété quelques fois dans une page normale — pas une boucle
        (PHRASE * 3) + " ".join(f"autre{i}" for i in range(300)),
        # une liste numérotée au refrain répété, mais aux demandes distinctes
        "\n".join(f"{i}) Je demande que l'on rouvre {lieu}" for i, lieu in enumerate(
            ["la gare", "la poste", "l'école", "la maternité", "le tribunal"] * 8
        )),
    ],
)
def test_une_page_normale_n_est_pas_une_derive(texte):
    assert not est_derive(texte)


def test_une_derive_transcrite_ne_se_lit_pas_mais_reste_transcrite(session):
    run = _run(session)
    page = _page(session, 4, "bruit du squelette", True)
    _transcrire(session, run, page, LIGNE_BOUCLE * 5_000)
    lues = lire_pages(session, garder_illisibles=True)
    assert [(p.texte, p.source) for p in lues] == [("", TRANSCRIPTION_ACTIVE)]
    assert [t.page_number for t in derives(session)] == [4]


def test_sans_run_actif_il_n_y_a_pas_de_derive(session):
    assert derives(session) == []


def test_la_categorie_separe_cahiers_et_courriers(session):
    """Un courrier et un cahier ne se lisent pas ensemble ; sans filtre, si."""
    _page(session, 3, "registre", False)
    _page(session, 3, "lettre", False, pdf="CO_01000_190215_D_02389.pdf", categorie="CO")
    _page(session, 3, "hors convention", False, pdf="a.pdf", categorie=None)

    assert [p.texte for p in lire_pages(session, categorie="CC")] == ["registre"]
    assert [p.texte for p in lire_pages(session, categorie="co")] == ["lettre"]
    assert len(lire_pages(session)) == 3
