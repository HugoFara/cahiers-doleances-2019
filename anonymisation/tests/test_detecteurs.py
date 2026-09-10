"""Tests des règles de repérage des données personnelles."""

import pytest

from anonymisation.detecteurs import (
    ADRESSE,
    EMAIL,
    IBAN,
    INSTITUTION,
    NOM,
    ROLE_PUBLIC,
    TELEPHONE,
    URL,
    Passage,
    detecter,
    fusionner,
    signatures,
)


def genres(texte: str) -> list[tuple[str, str]]:
    return [(p.genre, texte[p.debut : p.fin]) for p in detecter(texte)]


# --- formes ---


def test_repere_une_adresse_electronique():
    assert (EMAIL, "jean.martin@example.fr") in genres("écrire à jean.martin@example.fr")


@pytest.mark.parametrize(
    "numero",
    ["06 12 34 56 78", "06.12.34.56.78", "0612345678", "+33 6 12 34 56 78", "01-23-45-67-89"],
)
def test_repere_les_numeros_avec_leurs_separateurs(numero):
    """Les cahiers les écrivent de toutes les façons."""
    assert (TELEPHONE, numero) in genres(f"mon numéro est le {numero} merci")


def test_ne_prend_pas_une_annee_pour_un_numero():
    assert TELEPHONE not in [g for g, _ in genres("depuis 1998 et jusqu'en 2019")]


def test_repere_un_iban():
    texte = "mon compte FR76 3000 4000 0500 0012 3456 789 est vide"
    assert (IBAN, "FR76 3000 4000 0500 0012 3456 789") in genres(texte)


def test_repere_une_url():
    assert (URL, "www.exemple.fr") in genres("voir sur www.exemple.fr pour la suite")


@pytest.mark.parametrize(
    "adresse",
    [
        "mairie@stdenislesbourg.fr",
        "cahierscitoyens@granddebat.fr",
        "prefet@ain.gouv.fr",
        "secretariat.mairie@wanadoo.fr",
    ],
)
def test_une_adresse_institutionnelle_n_est_pas_une_donnee_personnelle(adresse):
    """Publique par destination : l'occulter viderait les textes de leur objet."""
    assert (INSTITUTION, adresse) in genres(f"écrire à {adresse} pour la suite")


def test_l_adresse_d_un_particulier_reste_personnelle():
    """Aucune forme ne l'en distingue à coup sûr : d'où la file de relecture."""
    assert (EMAIL, "jean.martin@wanadoo.fr") in genres("écrire à jean.martin@wanadoo.fr")


# --- adresses ---


def test_repere_une_adresse_postale():
    assert (ADRESSE, "12 rue des Lilas") in genres("j'habite 12 rue des Lilas")


def test_l_adresse_garde_ses_articles():
    """« avenue de la Gare » : couper aux articles amputerait l'adresse."""
    assert (ADRESSE, "3 bis avenue de la Gare") in genres("au 3 bis avenue de la Gare depuis 1998")


def test_l_adresse_s_arrete_a_la_proposition_suivante():
    """Sans borne, « où habite M. Dupont » serait avalé et le nom disparaîtrait."""
    resultat = genres("le 12 rue des Lilas où habite M. Dupont")
    assert (ADRESSE, "12 rue des Lilas") in resultat
    assert (NOM, "M. Dupont") in resultat


def test_une_rue_sans_numero_n_est_pas_une_adresse():
    """« la rue est mal entretenue » ne désigne personne."""
    assert ADRESSE not in [g for g, _ in genres("la rue des Lilas est mal entretenue")]


# --- noms ---


@pytest.mark.parametrize(
    "mention", ["M. Dupont", "Mme Marie-Claire Bernard", "Monsieur Jean Martin"]
)
def test_repere_un_nom_marque_par_une_civilite(mention):
    assert (NOM, mention) in genres(f"j'ai vu {mention} hier")


def test_une_fonction_publique_n_est_pas_occultee():
    """Un ministre cité dans son rôle n'a pas à disparaître : l'occulter viderait
    les textes de leur objet."""
    assert genres("Monsieur le Préfet, je vous écris")[0][0] == ROLE_PUBLIC


def test_un_nom_en_signature_est_repere():
    texte = "Il faut baisser les impôts locaux sans tarder\nJean Martin"
    assert (NOM, "Jean Martin") in genres(texte)


def test_une_phrase_en_fin_de_texte_n_est_pas_une_signature():
    texte = "Un premier point sur la fiscalite locale\nIl faut que cela change, et vite."
    assert NOM not in [g for g, _ in genres(texte)]


def test_la_premiere_ligne_n_est_jamais_une_signature():
    """Elle ouvre la doléance — en-tête, date, apostrophe — elle ne la signe pas."""
    assert signatures("Jean Martin\nIl faut baisser les impots locaux sans tarder") == []


def test_seule_la_fin_du_texte_est_examinee_pour_les_signatures():
    """Un titre en tête de doléance n'est pas une signature."""
    texte = "Jean Martin\n" + "\n".join(f"ligne {i} du corps du texte" for i in range(8))
    assert signatures(texte) == []


# --- fusion ---


def test_deux_passages_qui_se_chevauchent_fusionnent():
    fusionnes = fusionner([Passage(0, 10, NOM, "a"), Passage(5, 15, NOM, "b")])
    assert [(p.debut, p.fin) for p in fusionnes] == [(0, 15)]


def test_le_role_public_l_emporte_sur_la_civilite():
    """« Monsieur le Maire » est vu par les deux règles ; le rôle décide."""
    fusionnes = fusionner([Passage(0, 17, NOM, "civilite"), Passage(9, 17, ROLE_PUBLIC, "role")])
    assert fusionnes[0].genre == ROLE_PUBLIC


def test_des_passages_disjoints_ne_fusionnent_pas():
    fusionnes = fusionner([Passage(0, 5, NOM, "a"), Passage(10, 15, EMAIL, "b")])
    assert len(fusionnes) == 2


def test_aucun_passage():
    assert fusionner([]) == []
    assert detecter("") == []
