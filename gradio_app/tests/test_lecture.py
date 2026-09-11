"""La répartition que l'onglet Lecture trace : parts, dominante, hors grille."""

import pandas as pd

from gradio_app.views.lecture import (
    HORS_GRILLE,
    SANS_COMMUNE,
    cooccurrences,
    par_strate,
    repartition,
    strate,
)


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



class TestCooccurrences:
    def test_les_doleances_en_commun_sont_comptees_une_fois(self):
        d = _detections((1, "a", "A", 10, 1), (2, "b", "B", 10, 1), (2, "b", "B", 10, 1), (1, "a", "A", 11, 1))
        communs, _ = cooccurrences(d, total=2)
        assert communs.loc["A", "B"] == 1
        assert communs.loc["A", "A"] == 2

    def test_le_rapport_vaut_1_quand_les_themes_sont_independants(self):
        # 4 doléances rattachées : A dans 2, B dans 2, ensemble dans 1 → 1 / (2×2/4) = 1
        d = _detections(
            (1, "a", "A", 10, 1), (2, "b", "B", 10, 1),
            (1, "a", "A", 11, 1), (2, "b", "B", 12, 1),
            (3, "c", "C", 13, 1),
        )
        _, rapports = cooccurrences(d, total=99)
        assert rapports.loc["A", "B"] == 1.0
        assert rapports.loc["A", "A"] == 1.0

    def test_toujours_ensemble_donne_un_rapport_superieur_a_1(self):
        d = _detections((1, "a", "A", 10, 1), (2, "b", "B", 10, 1), (3, "c", "C", 11, 1))
        _, rapports = cooccurrences(d, total=2)
        assert rapports.loc["A", "B"] == 2.0

    def test_sans_detection_les_matrices_sont_vides(self):
        communs, rapports = cooccurrences(_detections(), total=3)
        assert communs.empty and rapports.empty


class TestStrates:
    def test_la_strate_suit_les_bornes(self):
        assert strate(88) == "moins de 500 hab."
        assert strate(500) == "500 à 2 000"
        assert strate(9_999) == "2 000 à 10 000"
        assert strate(41_527) == "10 000 et plus"
        assert strate(None) == SANS_COMMUNE

    def test_la_part_est_rapportee_aux_doleances_de_la_strate(self):
        pop = pd.DataFrame({"doleance_id": [10, 11, 12], "population": [100, 100, 5_000]})
        d = _detections((1, "a", "A", 10, 1), (1, "a", "A", 12, 1))
        parts, effectifs = par_strate(d, pop)
        assert effectifs["moins de 500 hab."] == 2
        assert parts.loc["A", "moins de 500 hab."] == 50.0
        assert parts.loc["A", "2 000 à 10 000"] == 100.0
        assert parts.loc[HORS_GRILLE, "moins de 500 hab."] == 50.0

    def test_les_strates_vides_sont_omises_et_l_inconnue_va_en_dernier(self):
        pop = pd.DataFrame({"doleance_id": [10, 11], "population": [100, None]})
        parts, _ = par_strate(_detections((1, "a", "A", 10, 1)), pop)
        assert list(parts.columns) == ["moins de 500 hab.", SANS_COMMUNE]
