"""Tests de la grille de thèmes.

Cette logique était l'état de module de `views/graph.py`, calculé à l'import
depuis une connexion PostgreSQL : elle était la seule vue du dépôt sans aucun
test, parce qu'il n'y avait aucun moyen de la monter. Extraite dans une classe
qui reçoit des lignes, elle se teste sur une taxonomie écrite à la main.
"""

from collections import namedtuple

import pytest

from gradio_app.views.grille import APERCU_ARBRES, Grille

Topic = namedtuple("Topic", "name parent_nom description")
Detection = namedtuple("Detection", "topic external_doc_id summary verbatim")


def topics(*paires) -> list[Topic]:
    """`("enfant", "parent")` ; un parent `None` fait une racine."""
    return [Topic(nom, parent, f"description de {nom}") for nom, parent in paires]


def detections(**combien) -> list[Detection]:
    return [
        Detection(nom, f"doc{i}", "résumé", "verbatim")
        for nom, n in combien.items()
        for i in range(n)
    ]


@pytest.fixture
def arbre() -> Grille:
    """Un arbre de hauteur 2 : racine -> deux enfants -> un petit-enfant."""
    return Grille(
        topics(
            ("racine", None),
            ("fiscalite", "racine"),
            ("services", "racine"),
            ("impot_local", "fiscalite"),
        ),
        detections(impot_local=3, services=2, fiscalite=1),
        run_id=7,
        label="grille d'essai",
    )


class TestStructure:
    def test_les_detections_remontent_le_long_de_l_arbre(self, arbre):
        assert arbre.rec("impot_local") == 3
        assert arbre.rec("fiscalite") == 4  # 1 propre + 3 de l'enfant
        assert arbre.rec("racine") == 6

    def test_les_detections_propres_ne_remontent_pas(self, arbre):
        assert arbre.propres["fiscalite"] == 1
        assert arbre.propres.get("racine", 0) == 0

    def test_la_profondeur_se_compte_depuis_la_racine(self, arbre):
        assert arbre.prof("racine") == 0
        assert arbre.prof("fiscalite") == 1
        assert arbre.prof("impot_local") == 2

    def test_le_chemin_va_de_la_racine_au_noeud(self, arbre):
        assert arbre.chemin("impot_local") == ["racine", "fiscalite", "impot_local"]

    def test_les_enfants_sont_tries_par_poids(self, arbre):
        """Le plus fourni d'abord : c'est l'ordre des sélecteurs et du layout."""
        assert arbre.kids("racine") == ["fiscalite", "services"]

    def test_un_theme_isole_n_est_pas_un_arbre(self):
        """Sans parent ni enfant, il n'y a rien à parcourir."""
        g = Grille(topics(("seul", None)), detections(seul=5))
        assert "seul" not in g.propre
        assert g.racines == []

    def test_un_cycle_de_parente_est_ecarte_au_lieu_de_boucler(self):
        """La livraison en contient : sans cela, tous les parcours partent en rond."""
        g = Grille(topics(("a", "b"), ("b", "a")), detections(a=1))
        assert g.propre == set()
        assert g.racines == []

    def test_un_arbre_sans_aucune_detection_n_encombre_pas_le_selecteur(self):
        g = Grille(
            topics(("vide", None), ("feuille", "vide"), ("plein", None), ("f2", "plein")),
            detections(f2=1),
        )
        assert g.racines == ["plein"]


class TestGrilleVide:
    def test_une_grille_sans_theme_se_construit_sans_lever(self):
        """Base migrée mais analyse pas chargée : un état normal, pas une erreur."""
        g = Grille()
        assert g.vide
        assert g.prof_max == 0
        assert g.racines == []
        assert g.total_detections == 0

    def test_une_grille_sans_arbre_se_declare_vide(self):
        g = Grille(topics(("seul", None)), detections(seul=3))
        assert g.vide
        assert len(g) == 1
        assert g.total_detections == 3


class TestStrates:
    def test_un_arbre_bas_tombe_dans_les_semis(self, arbre):
        assert arbre.hauteur["racine"] == 2
        assert arbre.strate_de["racine"] == "C"

    def test_un_arbre_haut_tombe_dans_la_canopee(self):
        chaine = [("n0", None)] + [(f"n{i}", f"n{i - 1}") for i in range(1, 6)]
        g = Grille(topics(*chaine), detections(n5=1))
        assert g.hauteur["n0"] == 5
        assert g.strate_de["n0"] == "A"

    def test_les_bornes_de_hauteur_d_une_strate_vide_ne_levent_pas(self, arbre):
        """Le bug que le refactoring a mis au jour.

        La version précédente indexait la liste triée des hauteurs sans la
        tester : `IndexError` dès qu'une strate n'avait aucun arbre. Invisible
        sur la grille livrée, dont les trois strates sont peuplées ; certain dès
        qu'on en ouvre une plus petite, ce que l'app permet maintenant.
        """
        assert arbre.racines_strate["A"] == []
        assert arbre.bornes_hauteur("A") == "—"
        assert arbre.detections_strate("A") == 0

    def test_une_seule_hauteur_ne_s_ecrit_pas_en_intervalle(self, arbre):
        assert arbre.bornes_hauteur("C") == "2"

    def test_plusieurs_hauteurs_donnent_un_intervalle(self):
        """Deux arbres de la même strate, de hauteurs différentes."""
        g = Grille(
            topics(("plat", None), ("f", "plat"),
                   ("creux", None), ("c1", "creux"), ("c2", "c1")),
            detections(f=1, c2=1),
        )
        assert sorted(g.racines_strate["C"]) == ["creux", "plat"]
        assert g.bornes_hauteur("C") == "1–2"

    def test_le_total_ne_compte_que_ce_qui_est_apercevable(self, arbre):
        assert arbre.detections_totales() == arbre.rec("racine")

    def test_l_apercu_plafonne_le_nombre_d_arbres(self):
        """Au-delà, le layout radial devient un anneau illisible."""
        paires, compte = [], {}
        for i in range(APERCU_ARBRES + 5):
            paires += [(f"r{i}", None), (f"f{i}", f"r{i}")]
            compte[f"f{i}"] = i + 1
        g = Grille(topics(*paires), detections(**compte))
        assert len(g.racines_strate["C"]) == APERCU_ARBRES + 5
        assert len(g.racines_apercu("C")) == APERCU_ARBRES


class TestParcours:
    def test_le_voisinage_ramene_parents_et_enfants(self, arbre):
        assert set(arbre.voisinage("fiscalite")) == {
            "racine",
            "fiscalite",
            "impot_local",
            "services",  # à deux crans, par la racine
        }

    def test_le_squelette_coupe_sous_le_cran_demande(self, arbre):
        garde, lien = arbre.squelette(1, ["racine"])
        assert garde == {"racine", "fiscalite", "services"}
        assert lien["fiscalite"] == "racine"
        assert lien["racine"] is None

    def test_le_squelette_ne_laisse_jamais_un_noeud_orphelin(self, monkeypatch):
        """Tout nœud gardé pend à un nœud gardé, ou à rien.

        C'est l'invariant que le dessin exige : une arête vers un parent élagué
        n'a nulle part où aller. Le plafond est abaissé pour forcer l'élagage.
        """
        from gradio_app.views import grille as module

        monkeypatch.setattr(module, "APERCU_CAP", 3)
        paires, compte = [("racine", None)], {}
        for i in range(8):
            paires += [(f"branche{i}", "racine"), (f"feuille{i}", f"branche{i}")]
            compte[f"feuille{i}"] = i + 1
        g = Grille(topics(*paires), detections(**compte))

        garde, lien = g.squelette(9, ["racine"])
        assert len(garde) < len(g.propre)  # l'élagage a bien eu lieu
        assert all(lien[n] is None or lien[n] in garde for n in garde)
        assert "racine" in garde  # la racine demandée est toujours gardée

    def test_le_layout_place_chaque_noeud_garde(self, arbre):
        garde, lien = arbre.squelette(2, ["racine"])
        positions = arbre.layout_foret(garde, lien)
        assert set(positions) == garde
        assert all(len(p) == 2 for p in positions.values())

    def test_la_racine_est_plus_pres_du_centre_que_ses_enfants(self, arbre):
        garde, lien = arbre.squelette(2, ["racine"])
        pos = arbre.layout_foret(garde, lien)
        rayon = lambda n: (pos[n][0] ** 2 + pos[n][1] ** 2) ** 0.5  # noqa: E731
        assert rayon("racine") < rayon("fiscalite") < rayon("impot_local")


class TestIdentite:
    def test_la_grille_porte_le_run_dont_elle_vient(self, arbre):
        """C'est ce qui permet d'en servir plusieurs et de dire laquelle."""
        assert arbre.run_id == 7
        assert arbre.label == "grille d'essai"
