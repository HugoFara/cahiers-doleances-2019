"""Tests des signaux : ce qui compte, c'est où et avec quelle casse."""

from typologie import regles


def test_une_formule_d_appel_n_ouvre_que_si_elle_est_en_tete():
    ouverture = "Monsieur le Préfet,\nvoici mes propositions."
    assert regles.APPEL in regles.signaux(ouverture)


def test_une_formule_d_appel_citee_au_milieu_n_ouvre_rien():
    """« Monsieur le Maire ne répond jamais » n'ouvre pas un courrier."""
    milieu = "x" * (regles.OUVERTURE + 50) + "\nMonsieur le Maire ne répond jamais.\n"
    # Assez long pour que la fin ne recouvre pas non plus le début.
    milieu += "y" * (regles.CLOTURE + 50)
    assert regles.APPEL not in regles.signaux(milieu)


def test_une_formule_de_politesse_ne_compte_qu_a_la_fin():
    debut = "Veuillez agréer mes salutations.\n" + "mot " * 400
    assert regles.POLITESSE not in regles.signaux(debut)
    fin = "mot " * 400 + "\nVeuillez agréer, Monsieur le Préfet."
    assert regles.POLITESSE in regles.signaux(fin)


def test_la_casse_separe_une_organisation_d_un_mot_courant():
    """`re.IGNORECASE` s'applique aussi aux classes : le piège de la v1."""
    assert regles.ORGANISATION not in regles.signaux(
        "il faudrait travailler dans une association ou une collectivité"
    )
    assert regles.ORGANISATION in regles.signaux(
        "l’association Vivre à Meximieux demande la révision du plan"
    )


def test_la_premiere_personne_compte_ses_formes_elidees():
    assert regles.PREMIERE_PERSONNE in regles.signaux("j’ai travaillé quarante ans")
    assert regles.PREMIERE_PERSONNE in regles.signaux("Je demande la suppression")


def test_une_liste_de_revendications_ne_porte_aucun_signal_d_auteur():
    """Le cas le plus fréquent du corpus : personne n'est sujet."""
    liste = (
        "- Suppression de la taxe d'habitation.\n"
        "- Rétablissement de l'ISF.\n"
        "- Baisse du nombre de parlementaires.\n"
    )
    trouves = regles.signaux(liste)
    assert regles.PREMIERE_PERSONNE not in trouves
    assert regles.ORGANISATION not in trouves


def test_un_texte_de_bruit_d_extraction_est_repere():
    bruit = "i 1 i 7 1 , 1 i_ / 0 _l \\ , i i ( U ft) wttc ? r 1 l H çz n X b 1 f M h"
    assert regles.texte_illisible(bruit)
    assert regles.TEXTE_ILLISIBLE in regles.signaux(bruit)


def test_de_la_prose_meme_telegraphique_n_est_pas_du_bruit():
    prose = (
        "Rétablir l'impôt sur la fortune. Baisser les taxes sur les carburants. "
        "Revaloriser les petites retraites et les pensions de réversion."
    )
    assert not regles.texte_illisible(prose)


def test_un_texte_trop_court_n_est_pas_juge_illisible():
    """Trois mots dont un mal reconnu feraient déjà tomber la part."""
    assert not regles.texte_illisible("Le 21 février 2019")


def test_la_brievete_est_un_signal_a_part_entiere():
    assert regles.TEXTE_BREF in regles.signaux("un mot court")
    long = "mot " * (regles.MOTS_TEXTE_BREF + 10)
    assert regles.TEXTE_BREF not in regles.signaux(long)


def test_un_texte_vide_ne_porte_aucun_signal():
    assert regles.signaux("") == set()
    assert regles.signaux("   \n  ") == set()
