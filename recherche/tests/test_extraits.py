"""Tests de la fabrication des extraits.

Sans base de données : `recherche/extraits.py` ne manipule que des chaînes.
"""

import pytest

from recherche.extraits import fenetre, plier, termes

# --- plier ---


@pytest.mark.parametrize(
    ("entree", "attendu"),
    [("École", "ecole"), ("ÉOLIENNE", "eolienne"), ("qüe", "que"), ("Impôt", "impot")],
)
def test_plie_les_accents_et_la_casse(entree, attendu):
    """La même indifférence que la configuration SQL, qui passe par unaccent."""
    assert plier(entree) == attendu


# --- termes ---


def test_retient_les_mots_de_la_requete():
    assert termes("éoliennes bruit") == ["eoliennes", "bruit"]


def test_ecarte_les_mots_nies():
    """Surligner un mot exclu par l'utilisateur serait le contraire de sa demande."""
    assert termes("impôt -taxe") == ["impot"]


def test_ecarte_les_operateurs():
    assert termes("école or collège") == ["ecole", "college"]


def test_les_guillemets_ne_sont_pas_des_mots():
    assert termes('"pouvoir d\'achat"') == ["pouvoir", "d", "achat"]


def test_ne_repete_pas_un_terme():
    assert termes("école école") == ["ecole"]


def test_une_requete_sans_mot_ne_donne_rien():
    assert termes("-- 42") == []


# --- fenetre ---


LONG = "Nous demandons " + "un texte de remplissage assez long. " * 40 + "Fin."


def test_un_texte_court_est_rendu_entier():
    assert fenetre("Trois mots ici.", ["mots"]) == "Trois mots ici."


def test_un_texte_vide_ne_casse_pas():
    assert fenetre("   ", ["mots"]) == ""


def test_l_extrait_s_ouvre_sur_le_terme():
    texte = "a" * 400 + " les éoliennes du plateau " + "b" * 400
    extrait = fenetre(texte, ["eoliennes"])
    assert "éoliennes du plateau" in extrait


def test_l_extrait_est_borne():
    extrait = fenetre(LONG, ["remplissage"], largeur=120)
    assert len(extrait) < 200


def test_les_points_de_suspension_disent_qu_on_a_coupe():
    extrait = fenetre("z" * 300 + " cible " + "z" * 300, ["cible"])
    assert extrait.startswith("… ") and extrait.endswith(" …")


def test_pas_de_points_de_suspension_au_bord():
    extrait = fenetre("cible " + "z " * 200, ["cible"])
    assert not extrait.startswith("…")


def test_la_radicalisation_est_rattrapee_par_un_prefixe():
    """PostgreSQL trouve « éolien » en cherchant « éoliennes » ; Python doit suivre."""
    texte = "y" * 400 + " le parc éolien du plateau " + "y" * 400
    assert "éolien du plateau" in fenetre(texte, ["eoliennes"])


def test_un_terme_trop_court_ne_surligne_pas_n_importe_quoi():
    """Sous quatre lettres, un préfixe mordrait sur la moitié du corpus."""
    texte = "z" * 400 + " abcdefgh " + "z" * 400
    assert fenetre(texte, ["abc"]).startswith("z")


def test_un_terme_introuvable_ouvre_sur_le_debut():
    """Le mot était dans un passage occulté : on montre le début plutôt que rien."""
    extrait = fenetre("Le début du texte. " + "z " * 300, ["absent"])
    assert extrait.startswith("Le début du texte.")


def test_l_extrait_ne_coupe_pas_au_milieu_d_un_mot():
    extrait = fenetre(LONG, ["remplissage"], largeur=100)
    nu = extrait.strip("… ")
    assert nu.split()[0] in LONG.split()
    assert nu.split()[-1] in LONG.split()


def test_l_espacement_est_normalise():
    """Un extrait vient de l'OCR : ses retours à la ligne ne veulent rien dire."""
    assert fenetre("a\n\n  b\tc", ["a"]) == "a b c"
