"""Tests du regroupement des graphies de communes.

Sans base de données : `gradio_app/communes.py` ne travaille que sur des listes.
"""

from gradio_app.communes import cle_commune, libelle_commune, regrouper


class TestCleCommune:
    def test_ignore_les_accents(self):
        assert cle_commune("AHUILLÉ") == cle_commune("AHUILLE")

    def test_ignore_les_traits_dunion(self):
        assert cle_commune("FONTENAY-SUR-CONIE") == cle_commune("FONTENAY SUR CONIE")

    def test_ignore_les_apostrophes(self):
        assert cle_commune("L'HUISSERIE") == cle_commune("L HUISSERIE")
        assert cle_commune("L’HUISSERIE") == cle_commune("L HUISSERIE")

    def test_ignore_la_casse(self):
        assert cle_commune("Ahuillé") == cle_commune("AHUILLE")

    def test_ecrase_les_espaces_multiples(self):
        assert cle_commune("FONTENAY  SUR   CONIE") == "FONTENAY SUR CONIE"

    def test_communes_differentes_gardent_des_cles_differentes(self):
        assert cle_commune("ALEXAIN") != cle_commune("ALLUYES")


class TestRegrouper:
    def test_fusionne_les_variantes_accentuees(self):
        assert regrouper(["AHUILLE", "AHUILLÉ"]) == {"AHUILLÉ": ["AHUILLE", "AHUILLÉ"]}

    def test_affiche_la_graphie_la_plus_riche(self):
        # accents et traits d'union portent de l'information : on les garde
        groupes = regrouper(["TORCE VIVIERS EN CHARNIE", "TORCÉ-VIVIERS-EN-CHARNIE"])
        assert list(groupes) == ["TORCÉ-VIVIERS-EN-CHARNIE"]

    def test_conserve_toutes_les_variantes_pour_le_filtre(self):
        # la requête SQL doit chercher les deux graphies, sinon la commune
        # n'affiche qu'une partie de ses contributions
        groupes = regrouper(["FONTENAY SUR CONIE", "FONTENAY-SUR-CONIE"])
        assert groupes["FONTENAY-SUR-CONIE"] == [
            "FONTENAY SUR CONIE",
            "FONTENAY-SUR-CONIE",
        ]

    def test_ne_fusionne_pas_des_communes_distinctes(self):
        assert len(regrouper(["ALEXAIN", "ALLUYES", "ABONDANT"])) == 3

    def test_ignore_les_valeurs_vides(self):
        assert regrouper(["", "   ", "ALEXAIN"]) == {"ALEXAIN": ["ALEXAIN"]}

    def test_dedoublonne_les_repetitions(self):
        assert regrouper(["ALEXAIN", "ALEXAIN"]) == {"ALEXAIN": ["ALEXAIN"]}

    def test_ignore_les_espaces_de_bord(self):
        assert regrouper([" ALEXAIN "]) == {"ALEXAIN": ["ALEXAIN"]}

    def test_tri_alphabetique_des_communes_affichees(self):
        assert list(regrouper(["ZOUAFQUES", "ABONDANT", "MAYENNE"])) == [
            "ABONDANT",
            "MAYENNE",
            "ZOUAFQUES",
        ]

    def test_liste_vide(self):
        assert regrouper([]) == {}


class TestLibelleCommune:
    def test_le_nom_officiel_l_emporte(self):
        assert libelle_commune("Vald'Yerre", "ARROU", "28012") == "Vald'Yerre (28012)"

    def test_sans_nom_officiel_on_retombe_sur_la_graphie(self):
        assert libelle_commune(None, "AHUILLÉ", "53001") == "AHUILLÉ (53001)"

    def test_sans_rien_le_code_vaut_mieux_qu_un_trou(self):
        """153 communes du corpus n'ont aucune graphie : elles étaient hors liste."""
        assert libelle_commune(None, None, "53062") == "53062 (53062)"

    def test_le_code_est_toujours_affiche(self):
        """Deux communes peuvent porter le même nom ; le code, lui, identifie."""
        assert libelle_commune("Saint-Denis", None, "93066").endswith("(93066)")
