"""Ce que la vue thèmes sert au front, sur une grille écrite à la main :
le groupe d'entrée, les groupes avec leurs poids, le fil d'Ariane."""

from collections import namedtuple

import pytest

from gradio_app.views import graph
from gradio_app.views.grille import APERCU, Grille

Topic = namedtuple("Topic", "name parent_nom description")
Detection = namedtuple("Detection", "topic external_doc_id summary verbatim")


def _grille(paires, **combien) -> Grille:
    return Grille(
        [Topic(nom, parent, "") for nom, parent in paires],
        [Detection(nom, f"doc{i}", "", "") for nom, n in combien.items() for i in range(n)],
        run_id=1,
        label="essai",
    )


@pytest.fixture
def plate() -> Grille:
    """Quatre racines, un niveau : la forme de la grille gouvernementale."""
    return _grille(
        [("r1", None), ("q1", "r1"), ("q2", "r1"), ("r2", None), ("q3", "r2")],
        q1=5, q2=2, q3=3,
    )


@pytest.fixture
def haute() -> Grille:
    """Un arbre de hauteur 5 et un de hauteur 1."""
    chaine = [("a0", None)] + [(f"a{i}", f"a{i - 1}") for i in range(1, 6)]
    return _grille(chaine + [("b0", None), ("b1", "b0")], a5=8, b1=2)


class TestGroupes:
    def test_le_groupe_d_entree_est_le_premier_peuple(self, plate, haute):
        # une grille plate n'a que des petits arbres : entrer sur A montrait
        # « aucun arbre » à l'ouverture
        assert graph.strate_par_defaut(plate) == "C"
        assert graph.strate_par_defaut(haute) == "A"

    def test_les_groupes_portent_leurs_poids(self, haute):
        groupes = {g["value"]: g for g in graph._strates(haute)}
        assert groupes["A"]["arbres"] == 1 and groupes["A"]["part"] == 80
        assert groupes["B"]["arbres"] == 0
        assert groupes["C"]["arbres"] == 1 and groupes["C"]["part"] == 20
        assert groupes["A"]["label"] == "Grands arbres"
        assert groupes["A"]["hauteur"] == "5 niveaux et plus"

    def test_l_apercu_sans_groupe_prend_celui_par_defaut(self, plate, monkeypatch):
        monkeypatch.setattr(graph, "grille", lambda run_id=None: plate)
        reponse = graph.apercu(None)
        assert reponse["strate"] == "C"
        assert [g["value"] for g in reponse["strates"] if g["arbres"]] == ["C"]
        assert reponse["figure"]["data"]
        # une grille à un seul groupe ne parle pas de groupes dans son panneau
        assert "Groupe" not in reponse["description"]
        assert "essai" in reponse["description"]

    def test_un_groupe_vide_dit_ou_sont_les_arbres(self, plate, monkeypatch):
        monkeypatch.setattr(graph, "grille", lambda run_id=None: plate)
        reponse = graph.apercu("A")
        assert reponse["figure"]["data"] == []
        assert "Petits arbres" in reponse["description"]
        assert "aucun arbre" in reponse["description"]


class TestFilDAriane:
    def test_l_apercu_ouvre_sur_la_vue_d_ensemble(self, plate, monkeypatch):
        monkeypatch.setattr(graph, "grille", lambda run_id=None: plate)
        (racine,) = graph.apercu(None)["niveaux"]
        assert racine["value"] == APERCU
        assert [o["value"] for o in racine["options"]] == [APERCU, "r1", "r2"]

    def test_un_noeud_donne_son_chemin_puis_la_descente(self, haute, monkeypatch):
        monkeypatch.setattr(graph, "grille", lambda run_id=None: haute)
        reponse = graph.noeud("a2")
        assert reponse["strate"] == "A"
        valeurs = [n["value"] for n in reponse["niveaux"]]
        assert valeurs == ["a0", "a1", "a2", None]
        assert reponse["niveaux"][-1]["label"].startswith("Descendre")
        assert [o["value"] for o in reponse["niveaux"][-1]["options"]] == ["a3"]

    def test_une_feuille_ne_propose_pas_de_descente(self, plate, monkeypatch):
        monkeypatch.setattr(graph, "grille", lambda run_id=None: plate)
        assert [n["value"] for n in graph.noeud("q1")["niveaux"]] == ["r1", "q1"]

    def test_les_couleurs_de_theme_ne_sont_pas_figees_par_le_serveur(self, plate, monkeypatch):
        """Le front pose texte, arêtes et fond de légende selon le thème."""
        monkeypatch.setattr(graph, "grille", lambda run_id=None: plate)
        figure = graph.apercu(None)["figure"]
        aretes = next(t for t in figure["data"] if t.get("mode") == "lines")
        assert "color" not in aretes["line"]
        assert "bgcolor" not in figure["layout"]["legend"]
