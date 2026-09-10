"""Tests des empreintes de similarité."""

import pytest

from doublons.empreintes import (
    MAX_HASH,
    TAILLE_SIGNATURE,
    fragments,
    jaccard,
    normaliser,
    paires_candidates,
    signature,
)

# --- normaliser ---


def test_la_casse_les_accents_et_la_ponctuation_sautent():
    """Ils varient d'une transcription à l'autre sans changer le texte."""
    assert normaliser("Les impôts, c'est TROP !") == normaliser("les impots c est trop")


def test_les_chiffres_restent():
    """Dans ces cahiers ils portent du sens : montants, articles, effectifs."""
    assert "1132" in normaliser("les 1 132 fonctionnaires").replace(" ", "")
    assert normaliser("article 49-3") == "article 49 3"


@pytest.mark.parametrize("vide", ["", "   ", "!!!", None])
def test_un_texte_sans_mot_donne_une_chaine_vide(vide):
    assert normaliser(vide) == ""


# --- fragments ---


def test_les_fragments_glissent_mot_a_mot():
    assert fragments("un deux trois quatre cinq six", taille=5) == {
        "un deux trois quatre cinq",
        "deux trois quatre cinq six",
    }


def test_un_texte_plus_court_qu_un_fragment_en_donne_un_seul():
    """Sinon les doléances de trois mots n'auraient aucune empreinte."""
    assert fragments("baisser les impots", taille=5) == {"baisser les impots"}


def test_un_texte_vide_ne_donne_aucun_fragment():
    assert fragments("") == set()


# --- signature ---


def test_deux_textes_identiques_ont_la_meme_signature():
    assert signature(fragments("les impots sont trop eleves ici")) == signature(
        fragments("Les impôts sont trop élevés ici")
    )


def test_la_signature_est_stable_d_une_execution_a_l_autre():
    """`hash()` est randomisé par processus : deux runs ne grouperaient pas pareil."""
    attendue = signature(fragments("un texte de reference pour cette verification"))
    assert signature(fragments("un texte de reference pour cette verification")) == attendue


def test_un_texte_vide_a_une_signature_neutre():
    sign = signature(set())
    assert len(sign) == TAILLE_SIGNATURE
    assert set(sign) == {MAX_HASH}


# --- jaccard ---


def test_jaccard_sur_deux_ensembles_identiques():
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_sur_deux_ensembles_disjoints():
    assert jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_partiel():
    assert jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)


def test_jaccard_de_deux_ensembles_vides():
    """Deux textes sans fragment sont identiques, pas incomparables."""
    assert jaccard(set(), set()) == 1.0


# --- LSH ---


def test_le_lsh_propose_les_textes_proches():
    a = fragments("il faut baisser les impots locaux qui etouffent les menages modestes")
    b = fragments("il faut baisser les impots locaux qui etouffent les menages modeste")
    signatures = {1: signature(a), 2: signature(b)}
    assert paires_candidates(signatures) == {(1, 2)}


def test_le_lsh_ecarte_les_textes_sans_rapport():
    a = fragments("il faut baisser les impots locaux qui etouffent les menages")
    b = fragments("je demande la proportionnelle integrale aux elections legislatives")
    assert paires_candidates({1: signature(a), 2: signature(b)}) == set()


def test_le_lsh_sur_un_corpus_vide():
    assert paires_candidates({}) == set()


def test_le_lsh_sur_un_seul_texte():
    assert paires_candidates({1: signature(fragments("un texte seul"))}) == set()
