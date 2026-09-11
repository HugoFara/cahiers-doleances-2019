"""Ce que la carte prépare avant de tracer : tailles, indicateurs, muettes."""

import pandas as pd

from gradio_app.views.carte import TAILLE_MAX, TAILLE_MIN, preparer


def _communes(*lignes):
    return pd.DataFrame(
        lignes,
        columns=["code", "nom", "departement", "population", "latitude", "longitude",
                 "cahiers", "pages", "manuscrites", "transcrites", "lisibles", "doleances"],
    )


class TestPreparer:
    def test_la_taille_suit_la_racine_de_la_population(self):
        df = preparer(_communes(
            ("01001", "A", "01", 100, 46.0, 5.0, 1, 4, 0, 0, 4, 2),
            ("01002", "B", "01", 40_000, 46.1, 5.1, 1, 4, 0, 0, 4, 2),
        )).set_index("code")
        assert df.loc["01002", "taille"] == TAILLE_MAX
        assert TAILLE_MIN < df.loc["01001", "taille"] < TAILLE_MAX
        assert df.loc["01001", "taille"] - TAILLE_MIN < (TAILLE_MAX - TAILLE_MIN) / 10

    def test_les_indicateurs_ne_divisent_pas_par_zero(self):
        df = preparer(_communes(("01001", "A", "01", 0, 46.0, 5.0, 1, 0, 0, 0, 0, 0)))
        assert df.iloc[0]["pour_mille"] == 0.0
        assert df.iloc[0]["part_manuscrite"] == 0.0

    def test_une_commune_sans_page_lisible_est_muette(self):
        df = preparer(_communes(
            ("01001", "A", "01", 500, 46.0, 5.0, 1, 3, 3, 0, 0, 0),
            ("01002", "B", "01", 500, 46.1, 5.1, 1, 3, 3, 3, 3, 1),
        )).set_index("code")
        assert bool(df.loc["01001", "muette"]) is True
        assert bool(df.loc["01002", "muette"]) is False
        assert "muette" in df.loc["01001", "survol"]
        assert "3 transcrite(s)" in df.loc["01002", "survol"]

    def test_sans_coordonnees_la_commune_ne_se_place_pas(self):
        df = preparer(_communes(("01001", "A", "01", 500, None, None, 1, 3, 0, 0, 3, 1)))
        assert df.empty

    def test_le_survol_ne_laisse_pas_passer_de_balise(self):
        df = preparer(_communes(("01001", "<b>A</b>", "01", 500, 46.0, 5.0, 1, 3, 0, 0, 3, 1)))
        assert "&lt;b&gt;A&lt;/b&gt;" in df.iloc[0]["survol"]
