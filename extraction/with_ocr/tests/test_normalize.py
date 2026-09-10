"""La normalisation retire la syntaxe, jamais les mots."""

from extraction.with_ocr.normalize import (
    couper_chaine_de_pensee,
    normaliser,
    normaliser_markdown,
)


def test_les_titres_markdown_sont_retires():
    assert normaliser_markdown("# AUGMENTATION DU SMIC") == "AUGMENTATION DU SMIC"
    assert normaliser_markdown("### annexe") == "annexe"


def test_les_liens_d_images_sont_retires():
    texte = "Commune\n![img-0.jpeg](img-0.jpeg)\nde Meillonnas"
    assert normaliser_markdown(texte) == "Commune\n\nde Meillonnas"


def test_l_emphase_est_retiree():
    assert normaliser_markdown("**47 %** des pages et `needs_ocr`") == "47 % des pages et needs_ocr"


def test_l_orthographe_d_origine_est_intacte():
    """Version diplomatique : `Amsi` et `TISF` restent tels quels."""
    texte = "Amsi le coût de la main d'œuvre n'augmente pas.\ntaxer TISF"
    assert normaliser_markdown(texte) == texte


def test_la_chaine_de_pensee_est_coupee_au_marqueur():
    texte = "The user wants me to transcribe.</think>\n\nAUGMENTATION DU SMIC"
    assert couper_chaine_de_pensee(texte) == "AUGMENTATION DU SMIC"


def test_sans_marqueur_le_texte_passe_inchange():
    assert couper_chaine_de_pensee("transcription simple") == "transcription simple"


def test_normaliser_enchaine_pensee_puis_syntaxe():
    texte = "brouillon</think>\n# Titre\n**texte**"
    assert normaliser(texte) == "Titre\ntexte"
