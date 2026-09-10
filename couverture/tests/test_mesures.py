"""Tests des mesures de couverture."""

import pytest

from couverture.mesures import distribution_qualite, mesurer, sensibilite_seuil
from database.models import PageExtraction


def page(
    pdf_name: str = "c.pdf",
    city: str | None = "TRIZAY",
    needs_ocr: bool | None = False,
    quality_score: float | None = 0.9,
    contribution_id: int = 1,
) -> PageExtraction:
    return PageExtraction(
        pdf_name=pdf_name,
        city=city,
        needs_ocr=needs_ocr,
        quality_score=quality_score,
        contribution_id=contribution_id,
    )


# --- Part ---


def test_le_taux_est_la_portion_ecartee():
    couverture = mesurer([page(), page(needs_ocr=True)])
    assert couverture.pages.taux == 0.5
    assert couverture.pages.retenus == 1


def test_un_corpus_vide_ne_divise_pas_par_zero():
    couverture = mesurer([])
    assert couverture.pages.taux == 0.0


# --- ce qui compte comme écarté ---


def test_une_page_dont_le_flag_est_null_n_est_pas_comptee_manuscrite():
    """La colonne est nullable ; l'absence de flag n'est pas une affirmation.

    Même logique ternaire que `export_dataset.lire_pages`, qui garde ces pages.
    """
    assert mesurer([page(needs_ocr=None)]).pages.ecartes == 0


# --- échelles ---


def test_un_cahier_est_touche_des_qu_une_page_manque():
    couverture = mesurer([page(), page(needs_ocr=True)])
    assert couverture.cahiers.ecartes == 1
    assert couverture.cahiers_muets == []


def test_un_cahier_entierement_manuscrit_est_muet():
    """Distinction utile : être partiellement lu n'est pas être absent."""
    couverture = mesurer([page(needs_ocr=True), page(needs_ocr=True)])
    assert couverture.cahiers_muets == ["c.pdf"]


def test_une_commune_muette_n_a_aucune_voix_dans_l_analyse():
    pages = [
        page(pdf_name="a.pdf", city="TRIZAY", needs_ocr=True),
        page(pdf_name="b.pdf", city="FONTENET"),
    ]
    couverture = mesurer(pages)
    assert couverture.communes_muettes == ["TRIZAY"]
    assert couverture.communes.total == 2


def test_les_graphies_d_une_meme_commune_ne_font_qu_une():
    """Sans regroupement, AHUILLE et AHUILLÉ compteraient pour deux communes."""
    pages = [page(pdf_name="a.pdf", city="AHUILLE"), page(pdf_name="b.pdf", city="AHUILLÉ")]
    assert mesurer(pages).communes.total == 1


def test_une_commune_est_muette_meme_si_ses_cahiers_sont_separes():
    pages = [
        page(pdf_name="a.pdf", city="TRIZAY", needs_ocr=True),
        page(pdf_name="b.pdf", city="TRIZAY", needs_ocr=True),
    ]
    assert mesurer(pages).communes_muettes == ["TRIZAY"]


def test_une_page_sans_commune_ne_fabrique_pas_de_commune():
    assert mesurer([page(city=None)]).communes.total == 0


def test_une_page_sans_cahier_est_quand_meme_comptee():
    """La colonne est nullable : la page ne doit pas disparaître du total."""
    couverture = mesurer([page(pdf_name=None, needs_ocr=True)])
    assert couverture.pages.ecartes == 1
    assert couverture.cahiers.total == 1


# --- distribution ---


def test_la_distribution_couvre_toutes_les_tranches():
    tranches = distribution_qualite([page(quality_score=0.95)])
    assert len(tranches) == 10
    assert tranches["0.9-1.0"] == 1
    assert tranches["0.0-0.1"] == 0


def test_un_score_de_1_tombe_dans_la_derniere_tranche():
    """Sans borne, l'indice déborderait du dictionnaire."""
    assert distribution_qualite([page(quality_score=1.0)])["0.9-1.0"] == 1


def test_la_distribution_ignore_les_scores_absents():
    assert sum(distribution_qualite([page(quality_score=None)]).values()) == 0


# --- sensibilité ---


def test_la_sensibilite_dit_ce_que_le_seuil_decide():
    pages = [page(quality_score=s) for s in (0.05, 0.25, 0.45, 0.95)]
    parts = sensibilite_seuil(pages, [0.1, 0.3, 0.5])
    assert [parts[s].ecartes for s in (0.1, 0.3, 0.5)] == [1, 2, 3]


def test_la_sensibilite_ignore_les_pages_sans_score():
    pages = [page(quality_score=0.05), page(quality_score=None)]
    assert sensibilite_seuil(pages, [0.3])[0.3].total == 1


@pytest.mark.parametrize("seuils", [[], [0.3]])
def test_la_sensibilite_sur_un_corpus_vide(seuils):
    assert all(part.taux == 0.0 for part in sensibilite_seuil([], seuils).values())


# --- identification des communes par code INSEE ---


def test_le_code_insee_compte_les_communes_sans_graphie():
    """Le point du rattachement : un tiers des cahiers n'a pas de commune lisible.

    Par graphie, ces communes ne sont comptées ni au numérateur ni au
    dénominateur — elles disparaissent. Mesuré sur le corpus : 307 communes par
    graphie, 459 par code.
    """
    pages = [
        page(pdf_name="a.pdf", city="TRIZAY", contribution_id=1),
        page(pdf_name="b.pdf", city=None, contribution_id=2),
    ]
    assert mesurer(pages).communes.total == 1
    assert mesurer(pages, {1: "17452", 2: "17168"}).communes.total == 2


def test_le_code_insee_l_emporte_sur_la_graphie():
    """Deux graphies proches mais deux communes distinctes : le code tranche."""
    pages = [
        page(pdf_name="a.pdf", city="SAINT-DENIS", contribution_id=1),
        page(pdf_name="b.pdf", city="SAINT DENIS", contribution_id=2),
    ]
    assert mesurer(pages).communes.total == 1
    assert mesurer(pages, {1: "93066", 2: "97411"}).communes.total == 2


def test_une_contribution_hors_rattachement_n_est_pas_comptee():
    """Deux cahiers du corpus n'ont pas de code : ne pas leur en inventer un."""
    pages = [page(contribution_id=1), page(pdf_name="b.pdf", contribution_id=2)]
    assert mesurer(pages, {1: "17452"}).communes.total == 1


def test_une_commune_reste_muette_par_code():
    pages = [
        page(pdf_name="a.pdf", city=None, needs_ocr=True, contribution_id=1),
        page(pdf_name="b.pdf", city="FONTENET", contribution_id=2),
    ]
    couverture = mesurer(pages, {1: "17452", 2: "17168"})
    assert couverture.communes_muettes == ["17452"]
