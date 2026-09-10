"""Tests de ce qu'un résultat de recherche annonce de lui-même."""

from recherche.requetes import Resultat


def resultat(**champs) -> Resultat:
    defauts = {
        "doleance_id": 510,
        "cahier": "CC_28.pdf",
        "commune": "Unverre",
        "code_commune": "28398",
        "rang": 0.02,
        "mots": 2217,
        "extrait": "…",
        "caviarde": True,
    }
    return Resultat(**{**defauts, **champs})


def test_un_texte_recopie_est_signale():
    """Les cinq premiers résultats d'une recherche peuvent être le même tract."""
    r = resultat(communes_du_groupe=6)
    assert r.recopie
    assert "6 communes" in r.resume()


def test_un_texte_unique_ne_l_est_pas():
    assert not resultat(communes_du_groupe=1).recopie
    assert "communes" not in resultat(communes_du_groupe=1).resume()


def test_sans_deduplication_on_n_affirme_rien():
    """`None` veut dire « la déduplication n'a pas tourné », pas « texte unique »."""
    assert not resultat(communes_du_groupe=None).recopie


def test_un_extrait_non_caviarde_le_dit():
    assert "non caviardé" in resultat(caviarde=False).resume()


def test_un_extrait_caviarde_ne_dit_rien_de_special():
    assert "caviardé" not in resultat().resume()


def test_le_resume_nomme_la_commune():
    assert "Unverre" in resultat().resume()


def test_sans_nom_de_commune_le_code_vaut_mieux_que_rien():
    assert "28398" in resultat(commune=None).resume()


def test_sans_rien_le_resume_le_dit():
    assert "commune inconnue" in resultat(commune=None, code_commune=None).resume()
