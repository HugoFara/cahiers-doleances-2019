"""Tests de l'avertissement affiché au-dessus des vues.

Sans base de données : `gradio_app/avertissements.py` ne met en forme que des
compteurs déjà calculés.
"""

import pytest

from couverture.mesures import Couverture, Part
from gradio_app.avertissements import Etat, details, essentiel, markdown


def couverture(
    pages=(5365, 2510),
    communes=(459, 402),
    muettes=37,
    habitants: tuple[int, int] | None = (937022, 36697),
) -> Couverture:
    return Couverture(
        pages=Part(*pages),
        cahiers=Part(516, 445),
        communes=Part(*communes),
        cahiers_muets=[],
        communes_muettes=[f"c{i}" for i in range(muettes)],
        habitants=None if habitants is None else Part(*habitants),
    )


def etat(**champs) -> Etat:
    defauts = {
        "couverture": couverture(),
        "grille": {"label": "grille émergente", "created_at": "2026-09-10 18:00:00"},
        "communes_listees": 459,
        "communes_du_corpus": 459,
    }
    return Etat(**{**defauts, **champs})


# --- l'essentiel ---


def test_annonce_la_part_ecartee_en_pourcentage_et_en_valeur():
    ligne = essentiel(etat())[0]
    assert "47" in ligne and "2510" in ligne and "5365" in ligne


def test_le_pourcentage_ne_se_coupe_pas_de_son_signe():
    """Espace insécable : « 47 » et « % » en bout de ligne se sépareraient."""
    assert "47 %" in essentiel(etat())[0]


def test_annonce_les_communes_muettes():
    assert "37 communes" in essentiel(etat())[1]


def test_la_part_en_habitants_accompagne_la_part_en_communes():
    """Publier l'une sans l'autre est trompeur dans les deux sens."""
    ligne = essentiel(etat())[1]
    assert "4 %" in ligne and "les petites" in ligne


def test_sans_ponderation_la_ligne_reste_juste():
    """Le référentiel INSEE peut manquer : l'avertissement ne doit pas mentir."""
    ligne = essentiel(etat(couverture=couverture(habitants=None)))[1]
    assert "37 communes" in ligne
    assert "habitants" not in ligne


def test_dit_que_les_comptages_ne_sont_pas_un_sondage():
    assert "sondage" in essentiel(etat())[2]


def test_un_corpus_vide_ne_divise_pas_par_zero():
    vide = couverture(pages=(0, 0), communes=(0, 0), muettes=0, habitants=None)
    assert "—" in essentiel(etat(couverture=vide))[0]


# --- les détails ---


def test_nomme_la_grille_servie():
    ligne = details(etat())[0]
    assert "grille émergente" in ligne and "2026-09-10" in ligne


def test_une_grille_sans_date_reste_annoncable():
    ligne = details(etat(grille={"label": "essai"}))[0]
    assert "essai" in ligne and "chargée le" not in ligne


def test_une_grille_sans_nom_ne_laisse_pas_un_trou():
    assert "sans nom" in details(etat(grille={"label": None}))[0]


def test_aucune_grille_active_n_est_pas_une_base_vide():
    """Le symptôme est le même — des vues vides — la cause n'est pas la même."""
    ligne = details(etat(grille=None))[0]
    assert "Aucune grille" in ligne and "pas une base vide" in ligne


def test_signale_les_communes_hors_de_la_liste():
    ligne = details(etat(communes_listees=307))[1]
    assert "152 communes" in ligne and "anomalie" in ligne


def test_quand_la_liste_est_complete_elle_le_dit():
    ligne = details(etat())[1]
    assert "459 communes" in ligne and "anomalie" not in ligne


@pytest.mark.parametrize("source", ["Source : Insee", "Source : IGN", "Licence Ouverte 2.0"])
def test_porte_les_mentions_obligatoires(source):
    """La Licence Ouverte 2.0 impose la source et la date des données."""
    assert any(source in ligne for ligne in details(etat()))


# --- le rendu ---


def test_les_details_sont_replies():
    rendu = markdown(etat())
    assert "<details>" in rendu and "</details>" in rendu


def test_l_essentiel_est_hors_du_repli():
    """Ce qui doit être lu ne doit pas demander un clic."""
    rendu = markdown(etat())
    assert rendu.index("sondage") < rendu.index("<details>")
