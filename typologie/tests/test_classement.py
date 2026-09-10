"""Tests du classement : l'ordre des règles fait partie de la décision."""

from typologie import classement, regles


def test_le_bruit_d_extraction_l_emporte_sur_tout():
    """Aucune règle de forme ne veut rien dire sur un texte illisible."""
    signaux = {regles.TEXTE_ILLISIBLE, regles.APPEL, regles.PREMIERE_PERSONNE}
    assert classement.support(signaux)[0] == classement.ILLISIBLE
    assert classement.auteur(signaux)[0] == classement.INDETERMINE


def test_l_apparat_passe_avant_le_courrier():
    """C'est un courrier, mais son objet est de transmettre, pas de contribuer."""
    signaux = {
        regles.TRANSMISSION,
        regles.TEXTE_BREF,
        regles.SIGNATURE_ELU,
        regles.APPEL,
        regles.POLITESSE,
    }
    assert classement.support(signaux)[0] == classement.APPARAT


def test_une_transmission_noyee_dans_un_long_texte_n_est_pas_de_l_apparat():
    """Le découpage a manqué la rupture : le contenu ne part pas avec l'emballage."""
    signaux = {regles.TRANSMISSION, regles.SIGNATURE_ELU, regles.APPEL}
    assert classement.support(signaux)[0] == classement.COURRIER


def test_le_support_lettre_type_vient_de_la_couche_doublons():
    valeur, detecteur = classement.support(set(), recopie=True)
    assert valeur == classement.LETTRE_TYPE
    assert detecteur == "doublon_multi_communes"


def test_un_en_tete_de_mairie_seul_ne_conclut_a_aucun_auteur():
    """Les communes ont fourni les cahiers : leur papier n'est pas leur parole."""
    assert classement.auteur({regles.ENTETE_MAIRIE})[0] == classement.INDETERMINE


def test_une_signature_d_elu_conclut_a_un_auteur_institutionnel():
    assert classement.auteur({regles.SIGNATURE_ELU})[0] == classement.INSTITUTION


def test_le_collectif_l_emporte_sur_la_premiere_personne():
    """« Nous, soussignés… je demande » reste un texte collectif."""
    signaux = {regles.SOUSSIGNES_PLURIEL, regles.PREMIERE_PERSONNE}
    assert classement.auteur(signaux)[0] == classement.COLLECTIF


def test_indetermine_est_une_valeur_et_porte_son_detecteur():
    valeur, detecteur = classement.auteur(set())
    assert valeur == classement.INDETERMINE
    assert detecteur == "aucun_signal"


def test_le_detecteur_ne_nomme_que_les_signaux_reellement_presents():
    _, detecteur = classement.support({regles.APPEL})
    assert detecteur == regles.APPEL


def test_classer_renseigne_toujours_les_deux_axes():
    axes = classement.classer("Je demande la suppression de la taxe d'habitation.")
    assert set(axes) == set(classement.AXES)
    assert axes[classement.AUTEUR][0] == classement.INDIVIDU
    assert axes[classement.SUPPORT][0] == classement.REGISTRE


def test_toutes_les_valeurs_produites_sont_declarees():
    """Une valeur non déclarée passerait sans bruit dans les comptages."""
    cas = [
        set(),
        {regles.TEXTE_ILLISIBLE},
        {regles.FORMULAIRE},
        {regles.PETITION},
        {regles.CONSEIL_MUNICIPAL, regles.SIGNATURE_ELU},
        {regles.OBJET},
        {regles.TRANSMISSION, regles.TEXTE_BREF, regles.ENTETE_MAIRIE},
        {regles.NOUS_COLLECTIF},
        {regles.PREMIERE_PERSONNE},
    ]
    for signaux in cas:
        assert classement.support(signaux)[0] in classement.SUPPORTS
        assert classement.auteur(signaux)[0] in classement.AUTEURS
    assert classement.support(set(), recopie=True)[0] in classement.SUPPORTS
