"""La répartition que l'onglet Lecture trace : parts, dominante, hors grille."""

import pandas as pd

from gradio_app.views.lecture import HORS_GRILLE, repartition


def _detections(*lignes):
    return pd.DataFrame(
        lignes, columns=["topic_id", "external_id", "topic", "doleance_id", "n"]
    )


class TestRepartition:
    def test_une_doleance_compte_dans_chaque_theme_qui_la_voit(self):
        d = _detections((1, "a", "A", 10, 1), (2, "b", "B", 10, 1), (1, "a", "A", 11, 1))
        t = repartition(d, total=4).set_index("external_id")
        assert t.loc["a", "doleances"] == 2
        assert t.loc["b", "doleances"] == 1
        assert t.loc["a", "part"] == 50.0

    def test_la_dominante_est_le_theme_le_plus_detecte(self):
        d = _detections((1, "a", "A", 10, 1), (2, "b", "B", 10, 3))
        t = repartition(d, total=1).set_index("external_id")
        assert t.loc["b", "dominantes"] == 1
        assert t.loc["a", "dominantes"] == 0

    def test_a_egalite_la_premiere_de_la_grille_domine(self):
        d = _detections((2, "b", "B", 10, 2), (1, "a", "A", 10, 2))
        t = repartition(d, total=1).set_index("external_id")
        assert t.loc["a", "dominantes"] == 1

    def test_le_hors_grille_est_le_reste_du_denominateur(self):
        d = _detections((1, "a", "A", 10, 1), (2, "b", "B", 10, 1))
        t = repartition(d, total=5).set_index("external_id")
        assert t.loc[HORS_GRILLE, "doleances"] == 4
        assert t.loc[HORS_GRILLE, "part"] == 80.0
        assert t.index[-1] == HORS_GRILLE

    def test_l_ordre_de_reference_est_suivi_et_les_absents_sont_a_zero(self):
        d = _detections((1, "a", "A", 10, 1))
        t = repartition(d, total=1, ordre=["b", "a"])
        assert list(t["external_id"]) == ["b", "a", HORS_GRILLE]
        assert t.iloc[0]["doleances"] == 0

    def test_sans_detection_tout_est_hors_grille(self):
        t = repartition(_detections(), total=3).set_index("external_id")
        assert list(t.index) == [HORS_GRILLE]
        assert t.loc[HORS_GRILLE, "doleances"] == 3

    def test_sans_doleance_les_parts_ne_divisent_pas_par_zero(self):
        t = repartition(_detections(), total=0)
        assert t["part"].tolist() == [0.0]
