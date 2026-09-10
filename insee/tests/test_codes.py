"""Tests de la lecture du code INSEE dans ses deux sources."""

import pytest

from insee.codes import (
    code_de_l_entete,
    code_du_nom_de_fichier,
    departement,
    normaliser,
    rapprocher,
)

ENTETE = "Le grand\ndébat national\nCahier citoyen\n{}\n01000"


# --- nom de fichier ---


def test_lit_le_code_du_nom_de_fichier():
    assert code_du_nom_de_fichier("CC_01000_190304_01053_MD_15462.pdf") == "01053"


def test_ne_confond_pas_le_code_postal_avec_le_code_insee():
    """Les deux sont à cinq chiffres et se suivent dans le nom : l'ordre décide."""
    assert code_du_nom_de_fichier("CC_01420_190304_01082_MD_15474.pdf") == "01082"


def test_un_code_de_remplissage_ne_vaut_pas_un_code():
    """00000 dit « commune non renseignée », ce n'est pas une commune."""
    assert code_du_nom_de_fichier("CC_01260_190301_00000_MD_15582.pdf") is None


@pytest.mark.parametrize(
    "nom",
    ["autre.pdf", "", "CC_01000_190304_MD_15462.pdf", "CC_01000_190304_0105_MD_1.pdf"],
)
def test_un_nom_hors_motif_ne_donne_pas_de_code(nom):
    assert code_du_nom_de_fichier(nom) is None


# --- en-tête ---


@pytest.mark.parametrize(
    "ligne",
    ["BOURG-EN-BRESSE - 01053", "GUEREINS-01053", "MONTCEAUX- 01053", "SAINT-DENIS-les-BOURG - 01053"],
)
def test_lit_le_code_de_l_entete_quel_que_soit_l_espacement(ligne):
    assert code_de_l_entete(ENTETE.format(ligne)) == "01053"


def test_un_entete_sans_code_ne_donne_rien():
    assert code_de_l_entete(ENTETE.format("Commune - IIcSlIIajO")) is None


def test_un_texte_qui_n_est_pas_un_entete_ne_donne_rien():
    assert code_de_l_entete("un texte quelconque avec 01053 dedans") is None


# --- département ---


@pytest.mark.parametrize(
    ("code", "attendu"),
    [
        ("01053", "01"),
        ("53001", "53"),
        ("2A004", "2A"),
        ("2B033", "2B"),
        ("97411", "974"),
        ("98411", "984"),
    ],
)
def test_departement(code, attendu):
    """Corse et outre-mer ont des préfixes à part : les traiter comme les autres
    rangerait Saint-Denis de La Réunion dans l'Aisne."""
    assert departement(code) == attendu


def test_departement_d_un_code_invalide():
    assert departement("00000") is None
    assert departement(None) is None


# --- normaliser ---


def test_normaliser_met_la_corse_en_majuscules():
    assert normaliser("2a004") == "2A004"


@pytest.mark.parametrize("valeur", ["", None, "123", "123456", "00000"])
def test_normaliser_refuse_ce_qui_n_est_pas_un_code(valeur):
    assert normaliser(valeur) is None


# --- rapprochement ---


def test_deux_sources_d_accord():
    assert rapprocher("01053", "01053") == ("01053", "accord")


def test_le_nom_de_fichier_l_emporte_sur_l_entete():
    """Cas réel : un en-tête portait le code postal là où on attend l'INSEE.

    Le fichier vient du système qui a déposé le cahier ; l'en-tête est un champ
    rempli à la main puis passé dans une extraction de texte.
    """
    assert rapprocher("01082", "01420") == ("01082", "desaccord")


def test_une_seule_source_suffit():
    assert rapprocher("01053", None) == ("01053", "fichier")
    assert rapprocher(None, "01053") == ("01053", "entete")


def test_aucune_source():
    assert rapprocher(None, None) == (None, "aucun")
