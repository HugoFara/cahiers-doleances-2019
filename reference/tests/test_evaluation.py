"""Tests des mesures : ce qui compte comme une bonne frontière, et à quel prix."""

import pytest

from reference.evaluation import (
    agreger,
    evaluer_cahier,
    f_mesure,
    taille_fenetre,
    window_diff,
)

# --- frontières exactes ---


def test_un_decoupage_parfait():
    vp, predites, attendues, wd = evaluer_cahier({0, 5, 12}, {0, 5, 12}, lignes=20)
    assert (vp, predites, attendues) == (2, 2, 2)
    assert wd == 0.0


def test_la_premiere_ligne_ne_compte_pas():
    """Elle ouvre forcément une doléance : la prédire est gratuit."""
    vp, predites, attendues, _ = evaluer_cahier({0}, {0}, lignes=20)
    assert (vp, predites, attendues) == (0, 0, 0)


def test_une_frontiere_decalee_d_une_ligne_est_comptee_fausse_deux_fois():
    """Sévérité assumée : c'est la mesure qui dit si les signaux sont les bons."""
    vp, predites, attendues, _ = evaluer_cahier({0, 10}, {0, 11}, lignes=20)
    assert (vp, predites, attendues) == (0, 1, 1)


def test_une_frontiere_manquee():
    vp, predites, attendues, _ = evaluer_cahier({0, 5, 12}, {0, 5}, lignes=20)
    assert (vp, predites, attendues) == (1, 1, 2)


def test_une_frontiere_en_trop():
    vp, predites, attendues, _ = evaluer_cahier({0, 5}, {0, 5, 9}, lignes=20)
    assert (vp, predites, attendues) == (1, 2, 1)


# --- f_mesure ---


def test_f_mesure_moyenne_harmonique():
    assert f_mesure(1.0, 1.0) == 1.0
    assert f_mesure(0.5, 0.5) == 0.5


@pytest.mark.parametrize(("p", "r"), [(0.0, 1.0), (1.0, 0.0), (0.0, 0.0)])
def test_f_mesure_nulle_si_une_moitie_manque(p, r):
    assert f_mesure(p, r) == 0.0


# --- WindowDiff ---


def test_window_diff_nul_sur_un_decoupage_identique():
    assert window_diff({5, 12}, {5, 12}, lignes=20) == 0.0


def test_window_diff_penalise_peu_un_decalage_d_une_ligne():
    """Là où précision et rappel tombent à zéro, WindowDiff reste faible."""
    assert window_diff({10}, {11}, lignes=20) < 0.3


def test_window_diff_penalise_une_frontiere_absente():
    manquee = window_diff({10}, set(), lignes=20)
    decalee = window_diff({10}, {11}, lignes=20)
    assert manquee > decalee


def test_window_diff_sur_un_cahier_d_une_ligne():
    """Cas dégénéré : rien à découper, pas de division par zéro."""
    assert window_diff(set(), set(), lignes=1) == 0.0


def test_taille_fenetre_suit_la_longueur_des_segments():
    assert taille_fenetre({10}, lignes=20) == 5  # deux segments de 10 lignes
    assert taille_fenetre(set(), lignes=20) == 10  # un seul segment


# --- agrégation ---


def test_agreger_un_seul_cahier():
    score = agreger({"a": evaluer_cahier({0, 5}, {0, 5}, lignes=10)})
    assert (score.precision, score.rappel, score.f1) == (1.0, 1.0, 1.0)
    assert score.cahiers == 1


def test_agreger_sans_aucune_frontiere_ne_divise_pas_par_zero():
    score = agreger({"a": evaluer_cahier({0}, {0}, lignes=10)})
    assert (score.precision, score.rappel, score.f1) == (0.0, 0.0, 0.0)


def test_la_ponderation_ramene_le_score_a_la_population():
    """L'échantillon sur-représente exprès les cahiers à plusieurs auteurs.

    Non pondéré, le cahier difficile pèse autant que le cahier courant ; pondéré
    par ce que chacun représente, c'est le cas courant qui domine — comme dans
    le corpus.
    """
    resultats = {
        "courant": evaluer_cahier({0, 5}, {0, 5}, lignes=10),  # trouvé
        "difficile": evaluer_cahier({0, 5}, {0}, lignes=10),  # manqué
    }
    echantillon = agreger(resultats)
    population = agreger(resultats, poids={"courant": 90.0, "difficile": 10.0})
    assert echantillon.rappel == 0.5
    assert population.rappel == pytest.approx(0.9)


def test_le_resume_ne_fait_pas_passer_un_cas_trivial_pour_un_echec():
    """0 frontière attendue et 0 trouvée est un accord, pas un score de 0 %."""
    score = agreger({"a": evaluer_cahier({0}, {0}, lignes=10)})
    assert "rien à mesurer" in score.resume()
    assert "P 0%" not in score.resume()
