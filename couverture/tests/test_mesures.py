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


# --- transcription ---


def test_une_page_manuscrite_transcrite_n_est_plus_ecartee():
    transcrite = page(needs_ocr=True)
    transcrite.id = 7
    couverture = mesurer([page(), transcrite, page(needs_ocr=True)], transcrites={7})
    assert couverture.pages.ecartes == 1
    assert couverture.transcrites == 1
    assert "réintégrées par transcription : 1" in "\n".join(couverture.resume())


def test_un_cahier_muet_cesse_de_l_etre_une_fois_transcrit():
    a, b = page(needs_ocr=True), page(needs_ocr=True)
    a.id, b.id = 1, 2
    assert mesurer([a, b]).cahiers_muets == ["c.pdf"]
    assert mesurer([a, b], transcrites={1}).cahiers_muets == []
    assert mesurer([a, b], transcrites={1, 2}).cahiers.ecartes == 0


def test_sans_transcrites_la_mesure_est_celle_du_squelette():
    assert mesurer([page(needs_ocr=True)]).transcrites == 0


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


# --- pondération par population ---


COMMUNES = {"01033": 16423, "01039": 454, "01205": 0}


def test_sans_populations_il_n_y_a_pas_de_ponderation():
    """Le rapport perd la pondération, pas les autres mesures."""
    assert mesurer([page()], {1: "01033"}).habitants is None


def test_la_part_en_habitants_dit_autre_chose_que_la_part_en_communes():
    """Une commune muette de 454 habitants pèse 3 % là où elle pèse 50 % en communes."""
    pages = [
        page(pdf_name="a.pdf", contribution_id=1),
        page(pdf_name="b.pdf", needs_ocr=True, contribution_id=2),
    ]
    couverture = mesurer(pages, {1: "01033", 2: "01039"}, COMMUNES)
    assert couverture.communes.taux == 0.5
    assert couverture.habitants.total == 16423 + 454
    assert couverture.habitants.ecartes == 454


def test_une_deleguee_a_zero_ne_gonfle_pas_le_total():
    """Ses habitants sont déjà dans ceux de sa parente : `insee.cog` l'a mis à 0."""
    pages = [
        page(pdf_name="a.pdf", contribution_id=1),
        page(pdf_name="b.pdf", contribution_id=2),
    ]
    couverture = mesurer(pages, {1: "01033", 2: "01205"}, COMMUNES)
    assert couverture.habitants.total == 16423


def test_une_commune_absente_du_referentiel_pese_zero():
    """Ne pas lui inventer une population, et ne pas faire échouer la mesure."""
    couverture = mesurer([page()], {1: "99999"}, COMMUNES)
    assert couverture.habitants.total == 0


def test_la_ponderation_apparait_dans_le_resume():
    couverture = mesurer([page(needs_ocr=True)], {1: "01039"}, COMMUNES)
    assert any("habitants" in ligne for ligne in couverture.resume())


# --- noms officiels ---


NOMS = {"01039": "Béon", "28012": "Vald'Yerre"}


def test_le_nom_officiel_l_emporte_sur_la_graphie_du_cahier():
    """Cette liste est faite pour être publiée : « Vald'Yerre » s'y lit mieux."""
    pages = [page(city="COMMUNE NOUVELLE D ARROU", needs_ocr=True, contribution_id=1)]
    couverture = mesurer(pages, {1: "28012"}, None, NOMS)
    assert couverture.communes_muettes == ["Vald'Yerre"]


def test_sans_nom_officiel_on_retombe_sur_la_graphie():
    pages = [page(city="TRIZAY", needs_ocr=True, contribution_id=1)]
    assert mesurer(pages, {1: "17452"}, None, NOMS).communes_muettes == ["TRIZAY"]


def test_sans_graphie_ni_nom_officiel_le_code_vaut_mieux_que_rien():
    pages = [page(city=None, needs_ocr=True, contribution_id=1)]
    assert mesurer(pages, {1: "17452"}, None, NOMS).communes_muettes == ["17452"]
