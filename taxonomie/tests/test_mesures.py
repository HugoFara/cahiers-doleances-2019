"""Tests des mesures d'une grille de thèmes."""

import pytest

from taxonomie.mesures import couverture, hierarchie, reutilisation

# --- réutilisation ---


def test_un_theme_atteste_par_un_seul_document_est_un_singleton():
    """C'est la mesure centrale : un tel thème paraphrase un document."""
    usage = reutilisation([("t1", "d1"), ("t2", "d1"), ("t2", "d2")], ["t1", "t2"])
    assert usage.singletons == 1
    assert usage.part_singletons == 0.5


def test_deux_detections_du_meme_theme_dans_un_document_ne_comptent_qu_une_fois():
    """Sinon un thème cité trois fois dans un texte passerait pour réutilisé."""
    usage = reutilisation([("t1", "d1"), ("t1", "d1"), ("t1", "d1")], ["t1"])
    assert usage.documents_par_theme["t1"] == 1
    assert usage.singletons == 1


def test_les_themes_jamais_detectes_sont_comptes_a_part():
    """Un tiers de la grille livrée est dans ce cas : découverte, jamais appliquée."""
    usage = reutilisation([("t1", "d1")], ["t1", "t2", "t3"])
    assert usage.themes_sans_document == 2
    assert usage.themes == 3


def test_les_themes_jamais_detectes_ne_faussent_pas_la_part_de_singletons():
    """La part porte sur les thèmes attestés : les autres ne sont pas des singletons,
    ils ne sont rien."""
    usage = reutilisation([("t1", "d1"), ("t1", "d2")], ["t1", "t2", "t3"])
    assert usage.part_singletons == 0.0


def test_une_grille_sans_aucune_detection():
    usage = reutilisation([], ["t1", "t2"])
    assert (usage.themes, usage.documents, usage.part_singletons) == (2, 0, 0.0)


# --- hiérarchie ---


def test_compte_racines_et_profondeur():
    arbre = hierarchie([("a", None, "A"), ("b", "a", "B"), ("c", "b", "C")])
    assert (arbre.racines, arbre.profondeur_max) == (1, 2)


def test_un_theme_hors_de_tout_arbre_est_isole():
    """Ni parent ni enfant : il ne se remonte ni ne se descend."""
    arbre = hierarchie([("a", None, "A"), ("b", "a", "B"), ("seul", None, "S")])
    assert arbre.isoles == 1


def test_un_parent_absent_de_la_grille_fait_une_racine():
    """`parent_id` peut pointer hors du run : le thème est alors une racine de fait."""
    assert hierarchie([("a", "fantome", "A")]).racines == 1


def test_detecte_un_cycle():
    """La vue graphe de l'app s'en protège déjà ; encore faut-il savoir s'il y en a."""
    assert hierarchie([("a", "b", "A"), ("b", "a", "B")]).cycliques == 2


def test_un_cycle_ne_boucle_pas_indefiniment():
    arbre = hierarchie([("a", "b", "A"), ("b", "c", "B"), ("c", "a", "C")])
    assert arbre.cycliques == 3


def test_compte_les_noms_portes_par_plusieurs_themes():
    """Les noms sont la clé de jointure au chargement : un doublon casse la jointure."""
    assert hierarchie([("a", None, "Fiscalité"), ("b", None, "Fiscalité")]).noms_dupliques == 1


def test_la_largeur_maximale_dit_si_un_parent_est_un_fourre_tout():
    arbre = hierarchie([("p", None, "P")] + [(f"e{i}", "p", f"E{i}") for i in range(5)])
    assert arbre.enfants_max == 5


def test_une_grille_vide():
    arbre = hierarchie([])
    assert (arbre.racines, arbre.profondeur_max, arbre.enfants_max) == (0, 0, 0)


# --- couverture ---


TEXTE = "Il faut baisser les impots locaux. Et rouvrir la maternite fermee en 2017."


def test_la_couverture_mesure_ce_que_les_verbatims_citent():
    mesure = couverture({"d1": TEXTE}, {"d1": ["Il faut baisser les impots locaux."]})
    assert 0.4 < mesure.part_couverte < 0.5
    assert mesure.part_hors_grille == pytest.approx(1 - mesure.part_couverte)


def test_deux_verbatims_qui_se_chevauchent_ne_comptent_qu_une_fois():
    """Sinon la couverture dépasserait 100 %."""
    mesure = couverture(
        {"d1": TEXTE},
        {"d1": ["Il faut baisser les impots", "faut baisser les impots locaux"]},
    )
    assert mesure.part_couverte <= 1.0
    assert mesure.caracteres_couverts == len("Il faut baisser les impots locaux")


def test_un_verbatim_reformule_ne_couvre_rien():
    """Ce n'est pas une citation : le compter fausserait la couverture."""
    mesure = couverture({"d1": TEXTE}, {"d1": ["le contribuable est excede"]})
    assert mesure.caracteres_couverts == 0
    assert mesure.verbatims_introuvables == 1


def test_la_couverture_ignore_casse_espaces_tirets_et_apostrophes():
    """Les PDF portent − (U+2212) et ’ là où la livraison écrit - et '."""
    mesure = couverture({"d1": "− l’impôt sur le revenu"}, {"d1": ["- l'impot sur le revenu"]})
    assert mesure.verbatims_introuvables == 0
    assert mesure.part_couverte == pytest.approx(1.0)


def test_un_document_sans_aucun_theme_est_compte():
    mesure = couverture({"d1": TEXTE, "d2": TEXTE}, {"d1": [TEXTE]})
    assert mesure.documents_sans_theme == 1


def test_un_corpus_vide_ne_divise_pas_par_zero():
    mesure = couverture({}, {})
    assert (mesure.part_couverte, mesure.part_hors_grille) == (0.0, 1.0)
