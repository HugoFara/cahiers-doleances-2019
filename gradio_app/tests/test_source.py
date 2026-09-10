"""Tests du retour à la source.

Sans base ni S3 : `gradio_app/source.py` ne construit que des URL. Le seul
chemin qui touche à l'extérieur (`lien_source`) est testé en lui donnant un
dossier de cahiers factice.
"""

import pytest

from gradio_app import source


class TestAvecPage:
    def test_ajoute_l_ancre_comprise_par_les_visionneuses(self):
        assert source.avec_page("http://x/c.pdf", 3) == "http://x/c.pdf#page=3"

    def test_sans_page_l_url_est_intacte(self):
        assert source.avec_page("http://x/c.pdf", None) == "http://x/c.pdf"

    def test_une_page_illisible_ne_casse_pas_le_lien(self):
        """Une page NULL en base arrive parfois en NaN par pandas."""
        assert source.avec_page("http://x/c.pdf", "N/C") == "http://x/c.pdf"

    def test_une_page_hors_bornes_est_ignoree(self):
        assert source.avec_page("http://x/c.pdf", 0) == "http://x/c.pdf"

    def test_la_page_suit_les_parametres_d_une_url_presignee(self):
        presignee = "https://s3/x.pdf?X-Amz-Signature=abc"
        assert source.avec_page(presignee, 7).endswith("#page=7")


class TestLibellePage:
    def test_une_seule_page(self):
        assert source.libelle_page(3) == "p. 3"

    def test_une_doleance_qui_court_sur_plusieurs_pages(self):
        assert source.libelle_page(3, 15) == "p. 3-15"

    def test_debut_et_fin_confondus_ne_font_qu_une_page(self):
        assert source.libelle_page(3, 3) == "p. 3"

    def test_sans_page_le_libelle_est_vide(self):
        assert source.libelle_page(None) == ""


class TestLienSource:
    @pytest.fixture
    def sans_s3(self, monkeypatch):
        """S3 injoignable : l'app doit rester utilisable hors ligne."""
        monkeypatch.setattr(source, "_url_presignee", lambda cahier: None)

    def test_sans_cahier_il_n_y_a_pas_de_lien(self, sans_s3):
        assert source.lien_source(None) is None
        assert source.lien_source("") is None

    def test_un_cahier_introuvable_ne_produit_pas_de_lien_mort(
        self, sans_s3, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(source, "PDF_DIR", tmp_path)
        assert source.lien_source("absent.pdf", 3) is None

    def test_a_defaut_de_s3_le_cahier_local_sert(self, sans_s3, monkeypatch, tmp_path):
        (tmp_path / "cahier.pdf").write_bytes(b"%PDF-1.4")
        monkeypatch.setattr(source, "PDF_DIR", tmp_path)
        lien = source.lien_source("cahier.pdf", 3)
        assert lien is not None
        assert lien.startswith("/gradio_api/file=")
        assert lien.endswith("#page=3")

    def test_s3_l_emporte_sur_le_dossier_local(self, monkeypatch, tmp_path):
        (tmp_path / "cahier.pdf").write_bytes(b"%PDF-1.4")
        monkeypatch.setattr(source, "PDF_DIR", tmp_path)
        monkeypatch.setattr(
            source, "_url_presignee", lambda cahier: "https://s3/cahier.pdf"
        )
        assert source.lien_source("cahier.pdf", 5) == "https://s3/cahier.pdf#page=5"
