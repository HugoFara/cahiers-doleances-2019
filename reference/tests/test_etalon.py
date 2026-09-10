"""Tests de l'étalon : ce qui est écrit sur disque, et ce qui ne l'est pas."""

import pytest

from reference.etalon import (
    COLONNES_ETALON,
    MAX_ECARTS_MONTRES,
    EtalonDesaligne,
    LigneEtalon,
    ecrire_fichier_de_travail,
    empreinte,
    figer,
    lire_etalon,
    verifier_alignement,
)
from segmentation.decoupage import Ligne


def lignes(*textes: str, page: int = 3) -> list[Ligne]:
    return [Ligne(texte=t, page=page) for t in textes]


# --- empreinte ---


def test_l_empreinte_ignore_l_espacement():
    """L'extraction peut recoller les mots autrement sans changer la ligne."""
    assert empreinte("Monsieur  le   Préfet,") == empreinte("Monsieur le Préfet,")


def test_l_empreinte_distingue_deux_lignes():
    assert empreinte("Monsieur le Préfet,") != empreinte("Madame, Monsieur,")


def test_l_empreinte_ne_permet_pas_de_relire_le_texte():
    """C'est la condition pour que l'étalon soit commitable."""
    texte = "Je suis la seule infirmière du village."
    assert texte not in empreinte(texte)
    assert len(empreinte(texte)) == 16


# --- fichier de travail ---


def test_le_fichier_de_travail_porte_le_texte_et_attend_l_annotation(tmp_path):
    chemin = tmp_path / "v1.csv"
    total = ecrire_fichier_de_travail(chemin, {"c.pdf": lignes("une", "deux")})
    contenu = chemin.read_text()
    assert total == 2
    assert "une" in contenu and "deux" in contenu


def test_la_premiere_ligne_est_pre_marquee(tmp_path):
    """Elle ouvre forcément une doléance ; les autres sont laissées vides.

    Pré-remplir avec la prédiction du découpage biaiserait l'étalon vers ce
    qu'on cherche à évaluer.
    """
    chemin = tmp_path / "v1.csv"
    ecrire_fichier_de_travail(chemin, {"c.pdf": lignes("une", "deux", "trois")})
    lues = chemin.read_text().splitlines()[1:]
    marques = [ligne.split(",")[-1].strip() for ligne in lues]
    assert marques == ["1", "", ""]


# --- figer ---


@pytest.fixture
def travail(tmp_path):
    chemin = tmp_path / "travail.csv"
    chemin.write_text(
        "pdf_name,page,ligne,texte,debut_doleance\n"
        "c.pdf,3,0,Monsieur le Préfet,1\n"
        "c.pdf,3,1,Le corps de la doléance,\n"
        "c.pdf,3,2,Madame Monsieur,oui\n"
    )
    return chemin


def test_figer_remplace_le_texte_par_son_empreinte(travail, tmp_path):
    etalon = tmp_path / "v1.csv"
    debuts = figer(travail, etalon)
    contenu = etalon.read_text()
    assert debuts == 2
    assert "Monsieur le Préfet" not in contenu
    assert contenu.splitlines()[0] == ",".join(COLONNES_ETALON)


@pytest.mark.parametrize("marque", ["1", "x", "oui", "VRAI", " 1 "])
def test_figer_accepte_ce_qu_un_annotateur_ecrit_dans_un_tableur(marque, tmp_path):
    travail = tmp_path / "t.csv"
    travail.write_text(f"pdf_name,page,ligne,texte,debut_doleance\nc.pdf,3,0,x,{marque}\n")
    assert figer(travail, tmp_path / "e.csv") == 1


def test_figer_refuse_un_fichier_aux_mauvaises_colonnes(tmp_path):
    travail = tmp_path / "t.csv"
    travail.write_text("pdf_name,texte\nc.pdf,x\n")
    with pytest.raises(ValueError, match="colonnes absentes"):
        figer(travail, tmp_path / "e.csv")


def test_l_aller_retour_conserve_les_annotations(travail, tmp_path):
    etalon = tmp_path / "v1.csv"
    figer(travail, etalon)
    relu = lire_etalon(etalon)
    assert [ligne.debut_doleance for ligne in relu] == [True, False, True]
    assert [ligne.ligne for ligne in relu] == [0, 1, 2]


# --- alignement ---


def etalon_de(*textes: str) -> list[LigneEtalon]:
    return [
        LigneEtalon("c.pdf", 3, i, empreinte(t), i == 0)
        for i, t in enumerate(textes)
    ]


def test_l_alignement_passe_sur_le_corpus_d_origine():
    verifier_alignement(etalon_de("une", "deux"), {"c.pdf": lignes("une", "deux")})


def test_l_alignement_detecte_un_texte_qui_a_change():
    """Un étalon désaligné donnerait des scores crédibles et faux."""
    with pytest.raises(EtalonDesaligne, match="texte différent"):
        verifier_alignement(etalon_de("une", "deux"), {"c.pdf": lignes("une", "autre")})


def test_l_alignement_detecte_un_cahier_disparu():
    with pytest.raises(EtalonDesaligne, match="absent du corpus"):
        verifier_alignement(etalon_de("une"), {})


def test_l_alignement_detecte_un_cahier_raccourci():
    with pytest.raises(EtalonDesaligne, match="au-delà du cahier"):
        verifier_alignement(etalon_de("une", "deux"), {"c.pdf": lignes("une")})


def test_l_alignement_ne_noie_pas_le_message_sous_les_ecarts():
    """Un corpus décalé produit un écart par ligne ; on en montre assez, pas plus."""
    beaucoup = etalon_de(*[f"ligne {i}" for i in range(50)])
    with pytest.raises(EtalonDesaligne) as erreur:
        verifier_alignement(beaucoup, {"c.pdf": lignes("une seule ligne")})
    assert str(erreur.value).count("\n  ") == MAX_ECARTS_MONTRES
