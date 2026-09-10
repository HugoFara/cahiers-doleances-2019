"""Tests du découpage d'un cahier en doléances."""

import pytest

from segmentation.decoupage import (
    Ligne,
    decouper,
    decouper_cahier,
    lignes_du_cahier,
    signal_ouverture,
)

# Un corps de doléance assez long pour franchir MIN_CARACTERES_DOLEANCE : sans
# volume, aucun signal ne coupe, et les tests ne mesureraient que le garde-fou.
CORPS = (
    "Les impôts locaux augmentent chaque année sans contrepartie visible, "
    "et les services publics disparaissent les uns après les autres."
)
AUTRE_CORPS = (
    "Il faut rétablir un impôt sur les grandes fortunes, c'est une question "
    "de justice élémentaire que tout le monde comprend ici."
)


def lignes(*textes: str, page: int = 3) -> list[Ligne]:
    return [Ligne(texte=t, page=page) for t in textes]


# --- signal_ouverture ---


@pytest.mark.parametrize(
    "ligne",
    [
        "Le 21 février 2019",
        "le 1er mars 2019",
        "Bourg-en-Bresse, le 3 mars 2019",
        "21/02/2019",
        "Le 21-02-19",
    ],
)
def test_une_ligne_entierement_datee_ouvre_une_doleance(ligne):
    assert signal_ouverture(ligne) == "date"


@pytest.mark.parametrize(
    "ligne",
    [
        "Monsieur le Préfet,",
        "Madame, Monsieur,",
        "Mesdames, Messieurs",
        "Chère Madame,",
    ],
)
def test_une_apostrophe_ouvre_une_doleance(ligne):
    assert signal_ouverture(ligne) == "apostrophe"


@pytest.mark.parametrize(
    "ligne",
    [
        "Le 21 février 2019, nous avons appris la fermeture de la maternité.",
        "Monsieur le Maire a répondu qu'il n'avait pas les moyens de le faire.",
    ],
)
def test_une_phrase_qui_commence_par_une_date_ou_un_titre_ne_coupe_pas(ligne):
    """Sinon toute narration datée se découperait en autant de doléances."""
    assert signal_ouverture(ligne) is None


def test_un_filet_de_separation_ouvre_une_doleance():
    assert signal_ouverture("----------") == "separateur"
    assert signal_ouverture("* * * * *") == "separateur"


def test_une_numerotation_explicite_ouvre_une_doleance():
    assert signal_ouverture("Contribution n° 12") == "numerotation"


@pytest.mark.parametrize("ligne", ["1. Baisser les impôts", "2° Rétablir l'ISF", "- et aussi"])
def test_une_puce_de_liste_ne_coupe_pas(ligne):
    """Les doléances énumèrent leurs demandes ; couper à chaque puce les émietterait."""
    assert signal_ouverture(ligne) is None


# --- decouper ---


def test_l_en_tete_d_une_lettre_ne_se_decoupe_pas_lui_meme():
    """Date puis apostrophe s'enchaînent : deux signaux, une seule doléance."""
    doleances = decouper(lignes("Le 21 février 2019", "Monsieur le Préfet,", CORPS))
    assert len(doleances) == 1
    assert doleances[0].signal == "debut"


def test_deux_lettres_a_la_suite_donnent_deux_doleances():
    doleances = decouper(
        lignes(
            "Le 21 février 2019",
            "Monsieur le Préfet,",
            CORPS,
            "Le 22 février 2019",
            "Madame, Monsieur,",
            AUTRE_CORPS,
        )
    )
    assert [d.signal for d in doleances] == ["debut", "date"]
    assert doleances[1].texte.startswith("Le 22 février 2019")


def test_la_formule_de_politesse_ferme_la_doleance_avec_sa_signature():
    """Deux contributions qui s'enchaînent sans en-tête : seule la clôture coupe."""
    doleances = decouper(
        lignes(
            CORPS,
            "Je vous prie d'agréer mes salutations distinguées.",
            "Jean Dupont",
            AUTRE_CORPS,
        )
    )
    assert len(doleances) == 2
    assert doleances[0].texte.endswith("Jean Dupont")
    assert doleances[1].signal == "cloture"


def test_la_signature_reste_avec_sa_doleance():
    doleances = decouper(
        lignes(CORPS, "Cordialement,", "Jean Dupont", "Retraité", "Trizay")
    )
    assert len(doleances) == 1


def test_un_cahier_sans_aucun_signal_reste_une_seule_doleance():
    """Résultat honnête : on ne fabrique pas de coupures là où le texte n'en montre pas."""
    assert len(decouper(lignes(CORPS, AUTRE_CORPS))) == 1


def test_aucune_ligne_ne_donne_aucune_doleance():
    assert decouper([]) == []


def test_le_decoupage_ne_perd_aucune_ligne():
    """Invariant : recoller les doléances redonne le texte d'entrée.

    C'est la garantie qui permettra de rejouer un découpage plus fin (géométrie
    des lignes, LLM) sans avoir perdu du texte au passage.
    """
    entree = lignes(
        "Le 21 février 2019",
        "Monsieur le Préfet,",
        CORPS,
        "Veuillez agréer mes salutations.",
        "Jean Dupont",
        "----------",
        AUTRE_CORPS,
        "Contribution n° 3",
        CORPS,
    )
    doleances = decouper(entree)
    assert len(doleances) > 1
    recolle = "\n".join(d.texte for d in doleances)
    assert recolle == "\n".join(ligne.texte for ligne in entree)


# --- lignes_du_cahier et pages ---


def test_les_lignes_gardent_leur_numero_de_page():
    resultat = lignes_du_cahier([(3, "a\nb"), (4, "c")])
    assert [(ligne.texte, ligne.page) for ligne in resultat] == [
        ("a", 3),
        ("b", 3),
        ("c", 4),
    ]


def test_les_lignes_vides_sont_ignorees():
    assert [ligne.texte for ligne in lignes_du_cahier([(3, "a\n\n   \nb")])] == ["a", "b"]


def test_une_doleance_a_cheval_sur_deux_pages_garde_ses_deux_bornes():
    doleances = decouper_cahier([(3, "Le 21 février 2019\n" + CORPS), (4, AUTRE_CORPS)])
    assert len(doleances) == 1
    assert (doleances[0].page_debut, doleances[0].page_fin) == (3, 4)


def test_une_page_vide_ne_produit_rien():
    assert decouper_cahier([(3, "")]) == []
