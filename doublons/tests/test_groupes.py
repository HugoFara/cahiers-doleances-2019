"""Tests du regroupement des doléances quasi identiques."""

import pytest

from doublons.groupes import SEUIL_PLANCHER, grouper, paires_similaires

TRACT = (
    "Nous demandons le retablissement de l impot de solidarite sur la fortune "
    "et la suppression du CICE, ainsi qu une reforme de la fiscalite ecologique "
    "qui epargne les menages les plus modestes."
)
TRACT_RECOPIE = (
    "Nous demandons le rétablissement de l'impôt de solidarité sur la fortune "
    "et la suppression du CICE, ainsi qu'une réforme de la fiscalité écologique "
    "qui épargne les ménages les plus modestes."
)
AUTRE = (
    "Il faudrait rouvrir la maternite fermee en 2017, car les femmes de la "
    "commune doivent desormais faire plus de cinquante kilometres pour accoucher "
    "et cela devient dangereux l hiver."
)


# --- paires_similaires ---


def test_un_texte_recopie_est_retrouve_malgre_accents_et_ponctuation():
    paires = paires_similaires({1: TRACT, 2: TRACT_RECOPIE})
    assert [(a, b) for a, b, _ in paires] == [(1, 2)]
    assert paires[0][2] == 1.0


def test_deux_doleances_sans_rapport_ne_sont_pas_rapprochees():
    assert paires_similaires({1: TRACT, 2: AUTRE}) == []


def test_le_seuil_decide():
    """Le même couple est retenu ou non selon le seuil, dans la plage couverte."""
    mots = TRACT.split()
    proche = " ".join(mots[:26] + ["et", "une", "revalorisation", "des", "retraites"])
    assert paires_similaires({1: TRACT, 2: proche}, seuil=0.95) == []
    assert paires_similaires({1: TRACT, 2: proche}, seuil=0.5) != []


def test_le_filtre_lsh_ne_descend_pas_sous_son_plancher():
    """Sous SEUIL_PLANCHER, abaisser le seuil rend *moins* de doublons.

    Le LSH ne propose qu'une paire sur quatre à 0,3 de similarité : le seuil ne
    veut plus rien dire, et rien ne le signalerait sans ce constat écrit.
    """
    tronque = " ".join(TRACT.split()[:12])  # ~0,22 de similarité avec TRACT
    assert paires_similaires({1: TRACT, 2: tronque}, seuil=0.2) == []
    assert SEUIL_PLANCHER > 0.2


# --- grouper ---


def test_trois_copies_font_un_seul_groupe():
    groupes = grouper({1: TRACT, 2: TRACT_RECOPIE, 3: TRACT})
    assert len(groupes) == 1
    assert groupes[0].membres == (1, 2, 3)
    assert groupes[0].taille == 3


def test_une_doleance_unique_ne_forme_pas_de_groupe():
    assert grouper({1: TRACT, 2: AUTRE}) == []


def test_deux_familles_de_textes_font_deux_groupes():
    groupes = grouper({1: TRACT, 2: TRACT_RECOPIE, 3: AUTRE, 4: AUTRE})
    assert [g.membres for g in groupes] == [(1, 2), (3, 4)]


def test_le_chainage_reunit_une_lettre_type_qui_derive():
    """A ressemble à B, B à C : les trois sont la même lettre, même si A et C
    ont divergé. C'est voulu, et `similarite_min` dit à quel point c'est ténu."""
    mots = TRACT.split()
    a = " ".join(mots)
    b = " ".join(mots[2:] + ["et", "une", "revalorisation", "des", "petites", "retraites"])
    c = " ".join(mots[5:] + ["et", "une", "revalorisation", "des", "petites", "retraites",
                             "ainsi", "qu", "une", "hausse", "du", "smic"])
    groupes = grouper({1: a, 2: b, 3: c}, seuil=0.5)
    assert len(groupes) == 1
    assert groupes[0].membres == (1, 2, 3)
    assert groupes[0].similarite_min < 1.0


def test_les_groupes_sont_ordonnes_du_plus_grand_au_plus_petit():
    groupes = grouper({1: TRACT, 2: TRACT, 3: TRACT, 4: AUTRE, 5: AUTRE})
    assert [g.taille for g in groupes] == [3, 2]


def test_le_regroupement_est_reproductible():
    corpus = {1: TRACT, 2: TRACT_RECOPIE, 3: AUTRE, 4: AUTRE}
    assert grouper(corpus) == grouper(corpus)


@pytest.mark.parametrize("corpus", [{}, {1: TRACT}])
def test_un_corpus_trop_petit_ne_donne_aucun_groupe(corpus):
    assert grouper(corpus) == []


def test_les_textes_vides_ne_forment_pas_un_groupe_geant():
    """Sans garde, tous les textes vides seraient « identiques » entre eux.

    `lire_doleances` les écarte en amont ; ce test dit ce qui se passerait si
    l'un passait quand même : rien de plus qu'un groupe des seuls textes vides.
    """
    groupes = grouper({1: TRACT, 2: "", 3: "   "})
    assert all(1 not in g.membres for g in groupes)
