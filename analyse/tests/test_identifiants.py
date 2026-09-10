"""Tests du format des identifiants de document échangés avec l'analyse."""

import pytest

from analyse.identifiants import (
    CONTRIBUTION,
    DOLEANCE,
    id_document,
    lire_id_document,
)


def test_une_contribution_s_ecrit_par_son_id_nu():
    """Les livraisons déjà faites restent relisibles : ce format ne change pas."""
    assert id_document(CONTRIBUTION, 42) == "42"


def test_une_doleance_s_ecrit_prefixee():
    assert id_document(DOLEANCE, 42) == "d42"


def test_un_niveau_inconnu_est_refuse():
    with pytest.raises(ValueError, match="niveau inconnu"):
        id_document("page", 42)


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        ("42", (CONTRIBUTION, 42)),
        ("d42", (DOLEANCE, 42)),
        ("D42", (DOLEANCE, 42)),
        ("  42  ", (CONTRIBUTION, 42)),
    ],
)
def test_relit_les_deux_formats(brut, attendu):
    assert lire_id_document(brut) == attendu


@pytest.mark.parametrize("brut", ["doc 73", "", "abc", "3.5", "d", None])
def test_ne_relit_pas_ce_qui_n_est_pas_un_identifiant(brut):
    """Les livraisons antérieures numérotent les documents à leur façon."""
    assert lire_id_document(brut) is None


def test_l_aller_retour_est_stable():
    for niveau in (CONTRIBUTION, DOLEANCE):
        assert lire_id_document(id_document(niveau, 7)) == (niveau, 7)
