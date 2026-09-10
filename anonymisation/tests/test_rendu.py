"""Tests du rendu caviardé."""

import pytest

from anonymisation.rendu import PassageRendu, a_caviarder, caviarder

TEXTE = "Contacter Jean Martin au 06 12 34 56 78 pour la suite."
NOM = PassageRendu(10, 21, "nom")
TELEPHONE = PassageRendu(25, 39, "telephone")


# --- politique ---


def test_un_passage_non_relu_est_caviarde():
    """Tant qu'un humain n'a pas tranché, le doute profite à la personne."""
    assert a_caviarder(PassageRendu(0, 5, "nom", confirme=None)) is True


def test_un_faux_positif_releve_n_est_pas_caviarde():
    assert a_caviarder(PassageRendu(0, 5, "nom", confirme=False)) is False


def test_une_fonction_publique_n_est_pas_caviardee():
    """L'occulter viderait les textes de leur objet."""
    assert a_caviarder(PassageRendu(0, 5, "role_public")) is False


def test_une_fonction_publique_confirmee_reste_visible():
    assert a_caviarder(PassageRendu(0, 5, "role_public", confirme=True)) is False


def test_une_adresse_institutionnelle_reste_visible():
    """Le standard d'une mairie n'est pas la donnée personnelle d'un citoyen."""
    assert a_caviarder(PassageRendu(0, 5, "institution")) is False


# --- rendu ---


def test_le_marqueur_dit_ce_qui_a_ete_retire():
    rendu = caviarder(TEXTE, [NOM, TELEPHONE])
    assert rendu == "Contacter [nom] au [téléphone] pour la suite."


def test_le_texte_d_origine_n_est_pas_modifie():
    """C'est tout le principe : le caviardage est un rendu, la source fait foi."""
    avant = TEXTE
    caviarder(TEXTE, [NOM])
    assert TEXTE == avant


def test_un_texte_sans_passage_est_rendu_tel_quel():
    assert caviarder(TEXTE, []) == TEXTE


def test_les_passages_sont_caviardes_quel_que_soit_leur_ordre():
    assert caviarder(TEXTE, [TELEPHONE, NOM]) == caviarder(TEXTE, [NOM, TELEPHONE])


def test_deux_passages_qui_se_recouvrent_ne_doublent_pas_le_marqueur():
    """Les détections sont corrigeables à la main : deux qui se recouvrent ne
    doivent pas donner deux marqueurs collés."""
    rendu = caviarder(TEXTE, [NOM, PassageRendu(10, 16, "nom")])
    assert rendu.count("[nom]") == 1
    assert rendu == "Contacter [nom] au 06 12 34 56 78 pour la suite."


def test_un_passage_entierement_contenu_dans_un_autre_disparait():
    rendu = caviarder(TEXTE, [NOM, PassageRendu(12, 15, "nom")])
    assert rendu.count("[nom]") == 1


def test_un_genre_inconnu_reste_occulte():
    """Un détecteur ajouté plus tard ne doit pas laisser passer son passage."""
    assert "[occulté]" in caviarder(TEXTE, [PassageRendu(10, 21, "biometrie")])


@pytest.mark.parametrize("confirme", [False])
def test_un_faux_positif_laisse_le_texte_intact(confirme):
    rendu = caviarder(TEXTE, [PassageRendu(10, 21, "nom", confirme=confirme)])
    assert rendu == TEXTE
